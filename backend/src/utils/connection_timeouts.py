"""
Connection timeouts — how long the network may take, and how long a probe may take.

Plan: workbench-AI-timeout-policy-plan.html, Item 2.

WHY THIS IS SEPARATE FROM `ai_limits`

`AILimits` holds the three values that belong to a (connection, model) pair, and it
is the right home for them because a model on a slow host needs more time than the
same model on a fast one. This module holds two values that belong to the
CONNECTION, for the opposite reason: the TCP connect reaches the connection's
endpoint before any model is named, so a per-pair connect timeout could only ever
hold the same value across every model on that connection.

The two questions are different in kind, and a reader who merges them will set 900 s
for generation and wonder why a test still takes five minutes, or set 300 s for a
probe and wonder why chat gives up.

WHY TWO DEADLINES

  connect  Nothing answered at all — a dead host, a firewall dropping SYN, a wrong
           address. Knowable in seconds. Without this the kernel decides: measured
           on this machine, net.ipv4.tcp_syn_retries = 6 gives about 127 s per
           attempt, which is not a product decision.

  probe    Connected, asked, and the answer never came — a slow or hung model.
           Legitimately minutes, because a CPU-hosted model genuinely takes them.

One is a fault and the other is patience, so they cannot share a number.

THE CLAMP, AND WHY IT IS HERE RATHER THAN AT EACH CALL SITE

D6 decided: refuse the write, and clamp at use. Both halves matter. The refusal
happens at the API, where an administrator can be told their connect budget exceeds
the whole-call budget. The clamp happens here, because the two values resolve from
different tables — `UserAIConnection` and `ConnectionModelIntersect` — so a later
change to one can invalidate the other with no write to refuse.

The failure this prevents is specific and silent: with a 1 s total budget and a 10 s
connect deadline, the total deadline always fires first, the failure is reported as a
read timeout, and the classification the caller depends on never happens. Clamping
means the connect deadline can never outlive the total, so a connect failure is
always reported as a connect failure.

TIERS, THE SAME SHAPE AS `resolve_slow_threshold` AND `resolve_ai_limits`

  2. the connection's own value
  3. the workbench default on GlobalSettings
  4. the compiled constant below

Tier 1 — a per-request override — does not exist, and should not: a connect deadline
is a property of the server being reached, not of one request against it.
"""

from dataclasses import dataclass
from typing import Optional

#: The seed for a new settings row, and the value when the row is absent entirely.
#:
#: Ten seconds is generous for a LAN and still tolerable for a WAN endpoint behind a
#: proxy. Five was considered and rejected: it is right for this LAN and wrong for a
#: cloud endpoint, and a value that only works on one network is the hard-coded
#: constant this module exists to remove. A deployment that needs longer raises the
#: default or sets it per connection — which is the point of making it data.
DEFAULT_CONNECT_TIMEOUT_SECONDS = 10

#: The seed for a new settings row, and the value when the row is absent entirely.
#:
#: 300 s is not a new number: it is what DEFAULT_TIMEOUT has carried in
#: `chat/probe_vocabulary.py` since the probes were written, chosen because a
#: CPU-hosted 27B model takes minutes and a probe that times out on a slow-but-good
#: model records a false failure. Seeding the row with it means nobody's behaviour
#: changes on migration; what changes is that it can now be edited.
DEFAULT_PROBE_TIMEOUT_SECONDS = 300

#: The most a CONNECT may be given, by any route.
#:
#: A product judgement, not a structural invariant, and deliberately its own number
#: rather than a reuse of `ai_limits.MAX_TIMEOUT_SECONDS`. That one is 1200 s and
#: answers "how long will a user wait for a model to answer"; no product wants twenty
#: minutes to establish a TCP connection. The two ceilings would only coincide by
#: accident, and sharing a constant would let a future decision about generation
#: silently move this one.
CONNECT_TIMEOUT_CEILING = 60

#: The most a PROBE may be given, by any route.
#:
#: Also its own number, and for the same reason: it coincides with
#: MAX_TIMEOUT_SECONDS today, and the reasons do not coincide. One governs a user's
#: patience, the other a diagnosis.
PROBE_TIMEOUT_CEILING = 1200


@dataclass(frozen=True)
class ConnectionTimeouts:
    """The two deadlines in force for one connection, already resolved and clamped.

    Frozen for the same reason `AILimits` is: a resolved set is a fact about a moment,
    and mutating it would let one call site change what another sees.
    """

    connect_seconds: int
    probe_seconds: int


async def resolve_connection_timeouts(conn, connection_id: int) -> ConnectionTimeouts:
    """The timeouts in effect for `connection_id`.

    Tiers 2 to 4, in one round trip, clamped so the connect deadline never outlives
    the probe deadline.

    A connection with no row is not an error: the LEFT JOIN guarantees one row
    carrying the connection's columns (both NULL) and the globals, so the defaults
    still answer. That matters here more than it does for the pair resolver — a
    caller may reasonably ask about a connection id that has just been deleted.
    """
    # A LEFT JOIN from a one-row anchor, not `FROM "UserAIConnection" WHERE …`. With a
    # plain FROM + WHERE, an unknown connection returns no row and the globals — which
    # do not depend on it — are lost with it. That is the defect
    # `resolve_slow_threshold` documents, and it is the same query shape for the same
    # reason; the three resolvers in this tree should be readable side by side.
    #
    # No LIMIT on the global side: GlobalSettings carries CHECK (id = 1), so there can
    # be at most one row and `g.id = 1` names it exactly.
    row = await conn.fetchrow(
        'SELECT c."connectTimeoutSeconds" AS own_connect, '
        '       c."probeTimeoutSeconds" AS own_probe, '
        '       g."defaultConnectTimeoutSeconds" AS global_connect, '
        '       g."defaultProbeTimeoutSeconds" AS global_probe '
        'FROM (SELECT 1) AS one '
        'LEFT JOIN public."UserAIConnection" c ON c."connectionId" = $1 '
        'LEFT JOIN public."GlobalSettings" g ON g.id = 1',
        connection_id,
    )

    if row is None:
        # Cannot happen with the join, but a caller resolving inside an aborted
        # transaction should get the built-ins rather than an exception from a None.
        row = {}

    # `is not None` rather than truthiness throughout: the columns are nullable so
    # NULL means "inherit", and a stored 0 is refused by the CHECK rather than being
    # a legal value that truthiness would conflate with absence.
    connect: Optional[int] = row.get("own_connect")
    if connect is None:
        connect = row.get("global_connect")
    if connect is None:
        connect = DEFAULT_CONNECT_TIMEOUT_SECONDS  # tier 4

    probe: Optional[int] = row.get("own_probe")
    if probe is None:
        probe = row.get("global_probe")
    if probe is None:
        probe = DEFAULT_PROBE_TIMEOUT_SECONDS  # tier 4

    connect = int(connect)
    probe = int(probe)

    # THE CLAMP. A connect deadline longer than the whole call's budget can never fire:
    # the total deadline wins first, and the failure is then reported as a read timeout
    # rather than a connect timeout. Silently misclassifying is worse than silently
    # shortening, because the class is what the caller acts on.
    if connect > probe:
        connect = probe

    return ConnectionTimeouts(connect_seconds=connect, probe_seconds=probe)


def validate_connect_timeout(value) -> Optional[str]:
    """Why `value` is not a legal connect timeout, or None when it is.

    Returns a reason rather than a boolean so the caller can choose its own
    translated message per field without this module holding translation keys.

    Validate, don't coerce: a float or a numeric string is refused, not truncated.
    `True` is refused explicitly because `isinstance(True, int)` is True in Python and
    a bool would otherwise be accepted as 1.
    """
    return _validate(value, CONNECT_TIMEOUT_CEILING)


def validate_probe_timeout(value) -> Optional[str]:
    """Why `value` is not a legal probe timeout, or None when it is."""
    return _validate(value, PROBE_TIMEOUT_CEILING)


def _validate(value, ceiling: int) -> Optional[str]:
    if isinstance(value, bool) or not isinstance(value, int):
        return "not_an_integer"
    if value < 1:
        return "below_minimum"
    if value > ceiling:
        return "above_ceiling"
    return None
