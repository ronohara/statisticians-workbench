"""Probe a database connection: can it be reached, and if not, why?

The model used to discover a broken connection one call at a time. A session on
2026-11-05 spent six `get_columns` calls on tables of an unreachable host, then
two more on dataset ids it invented, before giving up and substituting a source
the user had not asked for — and the whole detour was avoidable, because the
first failure already contained the reason.

Three things make it avoidable:

  * a probe that answers the question cheaply,
  * a classification that says what KIND of failure it was, so the next move is
    determined rather than guessed from a hostname, and
  * a cache, so a listing does not pay thirteen probes every turn.

================================================================
WHY CONNECTING IS NOT ENOUGH, AND LISTING IS TOO MUCH
================================================================

`SELECT 1` proves the host answers and the credential is accepted. It does not
distinguish a database whose schema is readable from one whose account cannot see
it, and "the data is there but not readable by this account" is a different fact
from "the host is down" — one invites a retry elsewhere, the other is hopeless.

A full listing would answer both, and costs a schema enumeration on every probe.
On a 200-table Access database that is the expensive half of the work, spent to
answer a yes/no question.

So the probe connects, then asks for ONE row from `information_schema.tables`
restricted to the visible schema. That is cheap on a big schema and on a small
one, and it separates `reachable` from `no_permission`.

================================================================
WHY THE CLASSIFICATION READS THE MESSAGE, NOT THE EXCEPTION TYPE
================================================================

`IsConnectionError` in the Go tree returns true for any driver error, and the
Python equivalent would be `except Exception`. Both are right for their purpose —
the dbdesign 502 asks only "did the connection fail" — and both are useless here,
because a wrong password, a missing database and a refused socket are all `true`
and each implies a different next move.

The rules below read the driver's own message in a fixed order. The order is part
of the contract: a message can contain more than one phrase, and `auth` must win
over `unreachable` because the corrective action differs.

================================================================
WHY A STALE NEGATIVE MUST READ AS UNKNOWN
================================================================

A cached "unreachable" that has gone stale makes the model refuse work it could
do. On the development machine that is not hypothetical: `x360` failed because
`leno` was on another wireless network, and was reachable again minutes later.

So freshness is applied on READ, and an expired row reports `unknown` rather than
its stored state. Unknown invites a probe; `unreachable` forbids one. The
asymmetry is deliberate and it is why a value that merely expired cannot mislead.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from typing import Optional

import asyncpg

from .crud import get_connection_row
from ...utils.connection_timeouts import resolve_connection_timeouts
from ...utils.encryption import decrypt_field

log = logging.getLogger(__name__)

# ============================================================
# THE STATES
# ============================================================
#
# Closed, and mirrored by the CHECK constraint on the column, so a value that
# reaches the database is one the reader knows how to interpret.
PROBE_REACHABLE = "reachable"
PROBE_UNREACHABLE = "unreachable"
PROBE_AUTH_FAILED = "auth_failed"
PROBE_NO_DATABASE = "no_database"
PROBE_NO_PERMISSION = "no_permission"
PROBE_INCOMPLETE = "incomplete"
# Connected, authenticated, then the source errored while its schema was read.
# Derived from WHERE the failure happened, not from its text — see the note above
# `_classify_phase`.
PROBE_SCHEMA_ERROR = "schema_error"

# What a reader reports when the stored answer is too old to stand behind. Not a
# state that is ever stored: it is the absence of a fresh claim.
PROBE_UNKNOWN = "unknown"

# How long a stored answer stands. A read rule, not a column, so changing it
# needs no migration.
#
# **Five minutes, raised from sixty seconds on 2026-11-07.** The old number was
# tuned for the wrong actor. Measured from the sweep log: every cache HIT came
# 16–17 s after the previous sweep, and every miss came minutes later — so the
# only thing sixty seconds ever served was a model listing sources twice inside
# one turn. Every human turn, which is read-a-reply-then-click, missed and paid
# the full sweep: 28 connections, 16 of them unreachable, 5 s deadline each, 4 at
# a time — about 21 seconds, inside the turn the user is waiting for.
#
# Five minutes turns that from "once per turn" into "once per conversation,
# unless it runs long". The cost is that a connection which recovers is reported
# dead for up to five minutes; an expired answer is re-probed rather than
# discarded, so the first turn after the expiry corrects it.
#
# Not tuned further on purpose. The two-tier alternative — a longer TTL for
# failures than for successes, since 80 of the 81 seconds are failures — was
# designed and set aside: one number that experience can tune beats two that
# nobody has data for yet.
PROBE_TTL_SECONDS = 300

# A probe the model is waiting on must not take as long as a connection attempt
# the user expects to be slow. Five seconds refuses a dead host well inside the
# time a turn can afford.
PROBE_DEADLINE_SECONDS = 5

# How many probes may be in flight at once. A dead host costs one deadline; with
# thirteen connections and no cap it would cost thirteen.
PROBE_CONCURRENCY = 4

# ============================================================
# THE CLASSIFICATION RULES
# ============================================================
#
# Ordered, first match wins. Each entry is (state, substrings). Matching is
# case-insensitive because the drivers differ in case, and several SQLSTATEs are
# carried inside the message text rather than as a separate attribute by the
# sync drivers.
_CLASSIFICATION_RULES = (
    (
        PROBE_AUTH_FAILED,
        (
            "password authentication failed",
            "authentication failed",
            "access denied for user",
            "login failed for user",
            "invalid username/password",
            "28p01",  # invalid_password
            "28000",  # invalid_authorization_specification
        ),
    ),
    (
        PROBE_NO_DATABASE,
        (
            "does not exist",       # asyncpg: database "x" does not exist
            "unknown database",     # MySQL: Unknown database 'x'
            "cannot open database", # MSSQL
            "3d000",                # invalid_catalog_name
        ),
    ),
    (
        PROBE_NO_PERMISSION,
        (
            "permission denied for schema",
            "permission denied for table",
            "42501",  # insufficient_privilege
        ),
    ),
)


# ============================================================
# THE PHASE IS THE FACT THE MESSAGE CANNOT GIVE
# ============================================================
#
# A probe does two things: connect, then read one row of information_schema. If the
# CONNECT succeeded, the network worked and the credential was accepted — so
# whatever failed afterwards cannot be unreachability, whatever the message says.
#
# That matters for `Access Northwind` (connections 144 and 274), which reported:
#
#   ERROR: msaccess: column "Attachments" of table "Employees" has DAO type 101
#          (Unknown), which the type map does not place (SQLSTATE XX000)
#
# and classified as `unreachable`, the fallback for an unrecognised message. The
# fallback is the safe direction for a refusal and still wrong here: the host
# answered, and the error was about the CONTENT of one table. `unreachable` sends
# the model to another connection and the user to check a network that is fine.
#
# Adding "msaccess" to the message rules would catch one vendor's phrasing and
# nothing else. The phase catches the class.
PROBE_PHASE_CONNECT = "connect"
PROBE_PHASE_QUERY = "query"


def _classify_phase(exc: BaseException, phase: str) -> tuple[str, str]:
    """Classify by where the failure happened first, then by what it said.

    ``phase`` is `connect` (no session was established) or `query` (a session
    exists). The order is part of the contract:

      1. query + permission   -> no_permission   (connected, cannot read)
      2. query + anything     -> schema_error    (connected, the source errored)
      3. connect + auth       -> auth_failed
      4. connect + no db      -> no_database
      5. connect + anything   -> unreachable

    Rules 1 and 2 come first because after a successful connect the message rules
    for connect-phase failures cannot apply — an auth message at query phase
    would be a driver oddity, not a credential failure.
    """
    message = str(exc) or exc.__class__.__name__
    lowered = message.lower()

    if phase == PROBE_PHASE_QUERY:
        for needle in ("permission denied for schema", "permission denied for table", "42501"):
            if needle in lowered:
                return PROBE_NO_PERMISSION, message
        return PROBE_SCHEMA_ERROR, message

    for state, needles in _CLASSIFICATION_RULES:
        if any(needle in lowered for needle in needles):
            return state, message
    return PROBE_UNREACHABLE, message


def classify_connection_error(exc: BaseException, db_type: str = "") -> tuple[str, str]:
    """Turn a driver exception into one of the states, and keep the message.

    Returns ``(state, detail)``. ``detail`` is the driver's own text, stored so a
    class the rules do not recognise still reaches the user verbatim rather than
    being swallowed into a generic "it did not work".

    **An unrecognised message becomes `unreachable`, not a silent success.** That
    is the honest reading of "something stopped us connecting, and we do not know
    what", and it is the safe direction: unreachable is refused rather than
    trusted, so a wrong guess costs a retry rather than a wrong answer.

    ``db_type`` is accepted and currently unused — it is the seam a driver-specific
    rule would hang on, and naming it now means adding one does not change every
    call site.
    """
    message = str(exc) or exc.__class__.__name__
    lowered = message.lower()

    for state, needles in _CLASSIFICATION_RULES:
        if any(needle in lowered for needle in needles):
            return state, message

    return PROBE_UNREACHABLE, message


# ============================================================
# THE PROBE ITSELF
# ============================================================


@dataclass(frozen=True)
class ProbeResult:
    """One connection's answer at one moment.

    Frozen, for the reason `ConnectionTimeouts` is: it is a fact about a moment,
    and handing a mutable one around invites a caller to edit what another sees.
    """

    connection_id: int
    state: str
    detail: Optional[str] = None
    succeeded: bool = False
    elapsed_ms: int = 0

    @property
    def is_fresh(self) -> bool:
        return False  # a result is always fresh by construction; see probe_is_fresh


def probe_is_fresh(probed_at, now=None, ttl: int = PROBE_TTL_SECONDS) -> bool:
    """Whether a stored answer is recent enough to stand behind.

    Applied on read, not written into the row, so changing the TTL never needs a
    migration and a per-connection override is not implied.
    """
    if probed_at is None:
        return False
    from datetime import datetime, timezone

    if now is None:
        now = datetime.now(timezone.utc).replace(tzinfo=None)
    if probed_at.tzinfo is not None:
        probed_at = probed_at.astimezone(timezone.utc).replace(tzinfo=None)
    return (now - probed_at).total_seconds() < ttl


class ProbePhaseError(Exception):
    """A driver failure that knows which phase it happened in.

    The phase is the fact the message cannot supply, and it is the difference
    between `schema_error` and `unreachable`. Carrying it as an exception keeps the
    driver helpers readable — they raise, and the classifier reads `phase`.
    """

    def __init__(self, phase: str, cause: BaseException):
        super().__init__(str(cause))
        self.phase = phase
        self.cause = cause


async def _probe_connection_row(row: dict, password: str, deadline: float) -> ProbeResult:
    """Connect, then ask for one visible table. Classify whatever stops us.

    **Connect and query are separate try-blocks on purpose.** The phase a failure
    happened in is what tells `schema_error` from `unreachable`, and one try-block
    around both loses it — which is how two Access connections were reported as
    unreachable while their host was answering.

    Anything the driver raises is classified rather than re-raised: a probe that
    threw would fail the listing it belongs to, and a listing must survive one
    unreachable host.
    """
    db_type = (row.get("type") or "").lower()
    started = asyncio.get_event_loop().time()

    if db_type not in ("postgresql", "postgres", "access", "mysql", "mssql"):
        return ProbeResult(
            connection_id=row["connection_id"],
            state=PROBE_INCOMPLETE,
            detail=f"unknown connection type: {db_type!r}",
        )

    # The outer bound has to know which phase it interrupted, and the helper
    # cannot say from inside a cancelled coroutine. So the phases are bounded
    # separately: the connect gets the deadline, and the query phase gets the same
    # budget measured from when the connect returned.
    try:
        connected = await asyncio.wait_for(
            _probe_connect(row, password, db_type), timeout=deadline
        )
    except asyncio.TimeoutError:
        elapsed = int((asyncio.get_event_loop().time() - started) * 1000)
        return ProbeResult(
            connection_id=row["connection_id"],
            state=PROBE_UNREACHABLE,
            detail=f"no answer within {deadline:.0f}s",
            elapsed_ms=elapsed,
        )
    except ProbePhaseError as exc:
        elapsed = int((asyncio.get_event_loop().time() - started) * 1000)
        state, detail = _classify_phase(exc.cause, exc.phase)
        return ProbeResult(
            connection_id=row["connection_id"], state=state, detail=detail,
            elapsed_ms=elapsed,
        )

    try:
        visible = await asyncio.wait_for(
            _probe_describe(connected, row, db_type), timeout=deadline
        )
    except asyncio.TimeoutError:
        # **The connect already succeeded.** Whatever this timeout interrupted, the
        # network works and the credential was accepted — so it cannot be
        # unreachability. Reporting one made the SAME connection flip between
        # schema_error and unreachable depending on whether the catalog read beat
        # five seconds: measured 2026-11-05, connection 274 answered in 4.71s once
        # and timed out at 10.56s the next call.
        #
        # The state is schema_error because the phase proves usage; what failed was
        # the source describing itself.
        elapsed = int((asyncio.get_event_loop().time() - started) * 1000)
        return ProbeResult(
            connection_id=row["connection_id"],
            state=PROBE_SCHEMA_ERROR,
            detail=f"connected, but reading its schema did not finish within {deadline:.0f}s",
            elapsed_ms=elapsed,
        )
    except ProbePhaseError as exc:
        elapsed = int((asyncio.get_event_loop().time() - started) * 1000)
        state, detail = _classify_phase(exc.cause, exc.phase)
        return ProbeResult(
            connection_id=row["connection_id"], state=state, detail=detail,
            elapsed_ms=elapsed,
        )
    except Exception as exc:  # noqa: BLE001 — an unphased failure is a connect failure
        elapsed = int((asyncio.get_event_loop().time() - started) * 1000)
        state, detail = classify_connection_error(exc, db_type)
        return ProbeResult(
            connection_id=row["connection_id"], state=state, detail=detail,
            elapsed_ms=elapsed,
        )

    elapsed = int((asyncio.get_event_loop().time() - started) * 1000)
    if not visible:
        # Connected, credential accepted, and not one table to show. That is a
        # permission answer, not a reachability one, and the two send the model
        # in different directions.
        return ProbeResult(
            connection_id=row["connection_id"], state=PROBE_NO_PERMISSION,
            detail="connected, but no table is visible to this account",
            elapsed_ms=elapsed,
        )
    return ProbeResult(
        connection_id=row["connection_id"], state=PROBE_REACHABLE, elapsed_ms=elapsed,
        succeeded=True,
    )


_VISIBLE_RELATION = (
    "SELECT 1 FROM information_schema.tables "
    "WHERE table_schema = current_schema() LIMIT 1"
)


async def _probe_connect(row: dict, password: str, db_type: str):
    """Open a session. Returns a driver-specific handle, or raises ProbePhaseError.

    Separate from the describe step so the caller can bound each phase and know
    which one a timeout interrupted. A session that never opened cannot have
    failed on schema content.
    """
    if db_type in ("postgresql", "postgres", "access"):
        port = row.get("port") or (9432 if db_type == "access" else 5432)
        try:
            return await asyncpg.connect(
                host=row["host"], port=port, user=row["username"],
                password=password, database=row["database"],
                timeout=PROBE_DEADLINE_SECONDS,
            )
        except Exception as exc:  # noqa: BLE001
            raise ProbePhaseError(PROBE_PHASE_CONNECT, exc) from exc

    if db_type == "mysql":
        import aiomysql

        try:
            return await aiomysql.connect(
                host=row["host"], port=row["port"] or 3306, db=row["database"],
                user=row["username"], password=password,
                connect_timeout=PROBE_DEADLINE_SECONDS,
            )
        except Exception as exc:  # noqa: BLE001
            raise ProbePhaseError(PROBE_PHASE_CONNECT, exc) from exc

    # MSSQL: pymssql is sync, so the whole helper runs in a thread. Its connect and
    # query are separated there for the same reason.
    return await asyncio.to_thread(_probe_mssql_connect, row, password)


def _probe_mssql_connect(row: dict, password: str):
    import pymssql

    try:
        return pymssql.connect(
            host=row["host"], port=row["port"] or 1433, database=row["database"],
            user=row["username"], password=password, tds_version="7.4",
            login_timeout=PROBE_DEADLINE_SECONDS,
        )
    except Exception as exc:  # noqa: BLE001
        raise ProbePhaseError(PROBE_PHASE_CONNECT, exc) from exc


async def _probe_describe(connected, row: dict, db_type: str) -> bool:
    """Ask the open session for one visible table. True when something is readable."""
    if db_type in ("postgresql", "postgres", "access"):
        try:
            found = await connected.fetchval(_VISIBLE_RELATION)
            return found is not None
        except Exception as exc:  # noqa: BLE001
            raise ProbePhaseError(PROBE_PHASE_QUERY, exc) from exc
        finally:
            await connected.close()

    if db_type == "mysql":
        try:
            async with connected.cursor() as cur:
                await cur.execute(_VISIBLE_RELATION)
                return await cur.fetchone() is not None
        except Exception as exc:  # noqa: BLE001
            raise ProbePhaseError(PROBE_PHASE_QUERY, exc) from exc
        finally:
            connected.close()

    return await asyncio.to_thread(_probe_mssql_describe, connected)


def _probe_mssql_describe(conn) -> bool:
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT TOP 1 1 FROM INFORMATION_SCHEMA.TABLES "
            "WHERE TABLE_TYPE IN ('BASE TABLE', 'VIEW')"
        )
        return cur.fetchone() is not None
    except Exception as exc:  # noqa: BLE001
        raise ProbePhaseError(PROBE_PHASE_QUERY, exc) from exc
    finally:
        conn.close()


async def probe_one(db_pool, user_id: str, language: str, connection_id: int,
                    force: bool = False) -> Optional[ProbeResult]:
    """Probe one connection and record the answer, or return the fresh stored one.

    Returns ``None`` when the connection does not exist or is not the caller's —
    which is a 404 elsewhere, not a probe result, and must not be recorded as a
    failure of the connection.

    ``force`` bypasses the cache. That is what the refresh tool uses: the model's
    one move to correct an answer it suspects is stale.
    """
    stored = await _stored_state(db_pool, user_id, connection_id)
    if stored is None:
        return None
    if not force and probe_is_fresh(stored["probedAt"]):
        return ProbeResult(
            connection_id=connection_id,
            state=stored["probeState"],
            detail=stored["probeDetail"],
            succeeded=stored["probeState"] == PROBE_REACHABLE,
        )

    row = await get_connection_row(connection_id, user_id, language)
    if row is None:
        return None

    password = row["password"]
    try:
        password = decrypt_field(password)
    except Exception:  # noqa: BLE001 — same behaviour as list_connection_tables
        pass

    async with db_pool.acquire() as conn:
        timeouts = await resolve_connection_timeouts(conn, connection_id)
    deadline = min(timeouts.connect_seconds or PROBE_DEADLINE_SECONDS,
                   PROBE_DEADLINE_SECONDS)

    payload = dict(row)
    payload["connection_id"] = connection_id
    result = await _probe_connection_row(payload, password, deadline)
    await _record(db_pool, connection_id, result)
    return result


async def probe_many(db_pool, user_id: str, language: str, connection_ids) -> dict:
    """Probe the connections whose stored answer has expired, in parallel.

    Returns a map of connection id to ``ProbeResult`` for every id asked about,
    using the stored answer where it is fresh and probing the rest.

    **The semaphore is not decoration.** A dead host costs one deadline; thirteen
    of them with no cap would cost thirteen, and the listing that triggers this is
    on the path of a turn somebody is waiting for.
    """
    ids = [int(c) for c in connection_ids]
    if not ids:
        return {}

    stored = await _stored_states(db_pool, user_id, ids)
    results: dict = {}
    to_probe = []
    for connection_id in ids:
        answer = stored.get(connection_id)
        if answer and probe_is_fresh(answer["probedAt"]):
            results[connection_id] = ProbeResult(
                connection_id=connection_id,
                state=answer["probeState"],
                detail=answer["probeDetail"],
                succeeded=answer["probeState"] == PROBE_REACHABLE,
            )
        else:
            to_probe.append(connection_id)

    if not to_probe:
        return results

    semaphore = asyncio.Semaphore(PROBE_CONCURRENCY)

    async def bounded(connection_id: int):
        async with semaphore:
            return connection_id, await probe_one(
                db_pool, user_id, language, connection_id, force=False
            )

    started = asyncio.get_event_loop().time()
    for connection_id, result in await asyncio.gather(
        *(bounded(c) for c in to_probe), return_exceptions=False
    ):
        if result is not None:
            results[connection_id] = result
    elapsed = asyncio.get_event_loop().time() - started

    # Logged, not returned: the sweep's cost is an operational fact about this
    # machine, and the first measurement of the all-dead case is what would
    # justify a total sweep deadline if one turns out to be needed.
    log.info(
        "connection probe sweep: %d probed, %d cached, %.2fs",
        len(to_probe), len(ids) - len(to_probe), elapsed,
    )
    return results


# ============================================================
# STORAGE
# ============================================================


async def _stored_states(db_pool, user_id: str, connection_ids) -> dict:
    async with db_pool.acquire() as conn:
        rows = await conn.fetch(
            'SELECT "connectionId", "probeState", "probeDetail", "probedAt" '
            'FROM "UserDatabaseConnection" '
            'WHERE "connectionId" = ANY($1::int[]) AND "userId" = $2',
            list(connection_ids), user_id,
        )
    return {
        r["connectionId"]: {
            "probeState": r["probeState"],
            "probeDetail": r["probeDetail"],
            "probedAt": r["probedAt"],
        }
        for r in rows
    }


async def _stored_state(db_pool, user_id: str, connection_id: int) -> Optional[dict]:
    states = await _stored_states(db_pool, user_id, [connection_id])
    return states.get(int(connection_id))


async def fresh_failures(db_pool, user_id: str, connection_ids) -> dict:
    """Recorded failures that are still fresh — a reason not to connect at all.

    The probe already answered the question, and a data path that connects anyway
    pays the connect deadline to rediscover it. Measured 2026-11-06: a schema read
    spent 60 seconds blocked on a host the probe had already recorded as
    unreachable.

    **Only a fresh failure qualifies.** An expired one is a stale opinion about a
    host that may well have come back, and refusing on it would make the cache the
    authority on reachability instead of the network. The TTL is the probe's own
    (`probe_is_fresh`), so the two cannot drift.

    Returns ``{connection_id: (state, detail)}`` for the failures, empty when
    there are none. It never raises: a probe table that cannot be read leaves the
    caller to connect, which is the behaviour that existed before this function.

    **The state travels with the detail, and that is the point of the tuple.** The
    detail alone is driver text — different words on each backend for one
    failure, and not something a reader can act on or a translation can render.
    The state is the closed vocabulary both backends share, so it is what a
    surface can say out loud. Until 2026-11-11 this function returned the detail
    and discarded the state one line above where it was read.
    """
    ids = [int(c) for c in (connection_ids or []) if c is not None]
    if not ids:
        return {}
    try:
        states = await _stored_states(db_pool, user_id, ids)
    except Exception:
        return {}
    refused = {}
    for connection_id, state in states.items():
        recorded = state.get("probeState")
        if not recorded or recorded == PROBE_REACHABLE:
            continue
        if not probe_is_fresh(state.get("probedAt")):
            continue
        refused[connection_id] = (recorded, state.get("probeDetail") or recorded)
    return refused


async def _record(db_pool, connection_id: int, result: ProbeResult) -> None:
    """Write one probe result.

    ``probeSuccessAt`` moves only on success, which is what makes "has this ever
    worked" answerable without a log. A failure leaves it alone rather than
    clearing it — the connection did work once, and that remains true.

    A failed write is logged and otherwise ignored: the probe's answer is still
    good for the turn in hand, and losing the cache must not fail the listing.
    """
    try:
        async with db_pool.acquire() as conn:
            await conn.execute(
                """
                UPDATE "UserDatabaseConnection"
                   SET "probeState" = $2,
                       "probeDetail" = $3,
                       -- UTC, and since 2026-11-08 the column says so itself.
                       -- Until Item 4 of the timestamp plan these columns were
                       -- `timestamp without time zone`, and a bare NOW() was cast to
                       -- the server's LOCAL time on the way in (Asia/Bangkok here,
                       -- +07); `probe_is_fresh` compared that against a naive UTC
                       -- `now`, so the difference was about -7 hours — always less
                       -- than the TTL, which made every stored answer look fresh for
                       -- seven hours. The fix then was to store UTC explicitly.
                       --
                       -- The columns are `timestamptz` now, so the wrapper must go.
                       -- Measured 2026-11-08: `pg_typeof(now() AT TIME ZONE 'UTC')`
                       -- is `timestamp without time zone`, and assigning that to a
                       -- `timestamptz` column reinterprets it in the session zone —
                       -- seven hours early. Keeping it would have made the migration
                       -- convert the history correctly and then corrupt every value
                       -- written afterwards.
                       "probedAt" = NOW(),
                       "probeSuccessAt" = CASE WHEN $4 THEN NOW()
                                               ELSE "probeSuccessAt" END
                 WHERE "connectionId" = $1
                """,
                connection_id, result.state, result.detail, result.succeeded,
            )
    except Exception as exc:  # noqa: BLE001
        log.warning("could not record probe for connection %s: %s", connection_id, exc)
