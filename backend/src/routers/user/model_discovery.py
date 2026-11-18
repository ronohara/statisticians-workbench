"""
The discovery walk — what a connection's server actually serves (plan Item 15).

Given a connection, ask its provider for the model list and record what comes
back: one `LLMModel` per name, one `ProviderModelIntersect` linking that model to
the provider, and one `ConnectionModelIntersect` linking it to *this* connection.

WHY THE WALK CREATES THREE THINGS AND NOT ONE
The abandoned plan stored a model as `("providerCode", "modelName")` on
`ProviderModel`, and that key cannot tell two servers apart. A refresh through one
Ollama host deleted another host's models, because both hosts are `ollama-local`
and the key had nowhere to record which server had been asked. The three tables
make the three facts separable: the model is a model, the provider offers it, and
this connection serves it. Discovery writes all three because a first sighting
establishes all three.

ONE TRANSACTION, NOT ONE PER MODEL
A walk against a large catalogue is hundreds of upserts. If it fails halfway, the
database must hold either the whole result or none of it — a partial catalogue
looks exactly like a server that genuinely lost half its models, and the next
reader has no way to tell the two apart. `conn.transaction()` nests as a
savepoint when the caller already holds a transaction, so the boundary holds
either way without the caller having to know.

PRUNING, AND WHY IT IS SCOPED TO THE PAIR
A walk that only ever adds would accumulate rows for models a server has stopped
serving, and `lastSeenAt` could no longer be read as "still offered". So the walk
deletes the connection's own rows for models the server did not return — and only
those. The predicate is `("connectionId", "modelId")`, so the provider intersect
and the model record are unreachable from it: both hold facts that may have come
from a server this walk cannot see, and deleting one server's findings on another
server's evidence is the defect this redesign exists to correct.

AN EMPTY LIST IS AN ERROR, NOT AN EMPTY SERVER
`_fetch_models_from_provider` returns `[]` when the body will not parse or the
model list is not a list. Feeding that to the prune would delete every row for the
connection, because `x <> ALL('{}')` is true for everything — the abandoned
implementation removed 421 of 425 rows exactly that way. So an empty list raises
`EmptyCatalogue` before the transaction opens and changes nothing. It is an
exception rather than an empty `DiscoveryResult` on purpose: a caller that cannot
tell "found nothing" from "removed everything" finds out from the damage.

WHAT THIS DOES NOT DO
The walk returns a *reason* (`empty_catalogue`, a prune count), never a rendered
sentence; the route that calls it renders, and owns the translation keys (Item 31).

WHY THE FETCH IS NOT RE-IMPLEMENTED HERE
`_fetch_models_from_provider` already resolves the endpoint from the provider's
default, handles the local/hosted difference (`/api/tags` versus `/models`) and
normalises both response shapes. A second HTTP path would answer differently for
the same server, which is precisely how the abandoned plan's two refresh paths
came to disagree. Discovery calls that function and nothing else.

THE IMPORT POINTS ONE WAY, DELIBERATELY
This module imports `ai_connections`; `ai_connections` must never import this one.
When an endpoint for the walk is added it belongs here, beside the walk, so the
edge stays one-directional. The reverse edge would be an import cycle — the same
shape that `chat/probe_vocabulary.py` was created to remove an hour earlier in
this plan, and Go cannot express it at all.
"""

import httpx
from dataclasses import dataclass

from src import db
from src.utils.encryption import decrypt_field_or_null


class _ProviderFetchError(Exception):
    """A fetch failure carrying a translation key + interpolation vars. The
    POST handler maps it to a t()-translated bare-string 400 (option b)."""
    def __init__(self, key, **kwargs):
        self.key = key
        self.kwargs = kwargs
        super().__init__(key)


async def _fetch_models_from_provider(provider_code, api_key, endpoint):
    """Python port of the item-14 inline fetchModelsFromProvider.

    Raises _ProviderFetchError(key, **vars) — the POST handler maps it to a
    t()-translated bare-string 400. Returns the list of model codes.
    Timeouts mirror the frontend: 10s local / 300s remote. Connection
    failures raise _ProviderFetchError("user.fetch_failed") — the frontend
    re-throws Node's raw TypeError."""
    async with db.pool().acquire() as conn:
        provider = await conn.fetchrow(
            'SELECT "isLocal", "requiresApiKey", "defaultEndpoint" '
            'FROM "AIProvider" WHERE code = $1',
            provider_code,
        )
    if provider is None:
        raise _ProviderFetchError("user.unknown_provider", code=provider_code)

    base_url = (endpoint.strip() if endpoint else None) or provider["defaultEndpoint"] or ""
    if not base_url:
        raise _ProviderFetchError("user.no_endpoint")

    if provider["isLocal"]:
        url = f"{base_url.rstrip('/')}/api/tags"
        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(10.0)) as client:
                response = await client.get(url)
        except httpx.TimeoutException:
            raise _ProviderFetchError("user.connection_timeout_local",
                                      code=provider_code, baseUrl=base_url)
        except httpx.HTTPError:
            raise _ProviderFetchError("user.fetch_failed")
        if response.status_code != 200:
            raise _ProviderFetchError("user.provider_returned",
                                      status=response.status_code, text=response.text)
        try:
            data = response.json()
        except Exception:
            return []
        if data.get("models") and isinstance(data["models"], list):
            return [m.get("name") or m.get("model") or m for m in data["models"]]
        return []

    if provider["requiresApiKey"] and not api_key:
        raise _ProviderFetchError("user.api_key_required_fetch")

    headers = {"Authorization": f"Bearer {api_key}"}

    url = f"{base_url.rstrip('/')}/models"
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(300.0)) as client:
            response = await client.get(url, headers=headers)
    except httpx.TimeoutException:
        raise _ProviderFetchError("user.connection_timeout_remote",
                                  code=provider_code, baseUrl=base_url)
    except httpx.HTTPError:
        raise _ProviderFetchError("user.fetch_failed")
    if response.status_code != 200:
        raise _ProviderFetchError("user.provider_returned",
                                  status=response.status_code, text=response.text)
    try:
        data = response.json()
    except Exception:
        return []
    if data.get("data") and isinstance(data["data"], list):
        return [m.get("id") for m in data["data"]]
    return []


class ConnectionNotFound(Exception):
    """No connection row for the id. The caller decides the status code."""

    def __init__(self, connection_id):
        self.connection_id = connection_id
        super().__init__(f"connection {connection_id} not found")


class EmptyCatalogue(Exception):
    """The server answered, but with no usable model list, so nothing changed.

    Raised rather than returned: an empty list is evidence of a broken answer, not
    of an empty server. `_fetch_models_from_provider` returns [] when the body will
    not parse or the model list is not a list — and a prune driven by an empty list
    deletes every row, because `x <> ALL('{}')` is true for everything. The
    abandoned implementation removed 421 of 425 rows that way.

    Carrying the reason rather than the sentence: the route renders it (Item 31),
    so the translation keys live there and not in two backends' walk code.
    """

    reason = "empty_catalogue"

    def __init__(self, connection_id):
        self.connection_id = connection_id
        super().__init__(self.reason)


@dataclass(frozen=True)
class DiscoveryResult:
    """What one walk changed, in counts rather than in prose.

    Every field is derived from the statements actually executed, so a caller can
    tell "the server listed three models I already had" from "the server listed
    three models I had never seen" without re-querying. Item 16's abort message and
    its removal count both read from here.
    """

    models_seen: int
    models_created: int
    provider_intersects_created: int
    connection_intersects_created: int
    connection_intersects_refreshed: int
    connection_intersects_pruned: int


async def discover_connection(conn, connection_id):
    """Fetch this connection's catalogue and record it. Returns the counts.

    `conn` is an asyncpg connection. The walk joins the caller's transaction if
    there is one and opens its own if there is not, so the boundary is atomic in
    both cases.

    Raises `ConnectionNotFound` when the id names no row, and `_ProviderFetchError`
    unchanged when the server cannot be reached or answers badly — a transport
    failure is not an empty catalogue, and the two must not arrive looking alike.
    """
    row = await conn.fetchrow(
        'SELECT provider, "apiKey", endpoint FROM "UserAIConnection" '
        'WHERE "connectionId" = $1',
        connection_id,
    )
    if row is None:
        raise ConnectionNotFound(connection_id)

    api_key = decrypt_field_or_null(row["apiKey"])

    # Outside the transaction on purpose: a slow server must not hold locks while
    # the walk waits for it. A failure here raises and nothing is written, which is
    # the same end state as an abort after the transaction opened.
    model_names = await _fetch_models_from_provider(
        row["provider"], api_key, row["endpoint"]
    )

    return await record_discovery(conn, connection_id, row["provider"], model_names)


async def record_discovery(conn, connection_id, provider_code, model_names):
    """Record an already-fetched model list against a connection.

    Split from the fetch so the write path can be exercised without a server, and
    so a caller holding its own list — a repair, a migration — records through the
    same code the walk uses rather than through a second implementation.

    Raises `EmptyCatalogue` before opening a transaction: an empty list is a broken
    answer, and the prune below would take it as evidence that the server holds
    nothing. Distinct exception rather than an empty result, because a result a
    caller can mistake for success is the defect this whole plan keeps meeting.
    """
    # De-duplicated, order preserved. A list naming one model twice would otherwise
    # report a `models_seen` larger than the number of models, and every count in
    # this result exists to be compared against the others.
    model_names = list(dict.fromkeys(model_names))

    if not model_names:
        raise EmptyCatalogue(connection_id)

    created_models = 0
    created_provider = 0
    created_connection = 0
    refreshed = 0
    seen_model_ids = []

    async with conn.transaction():
        for model_name in model_names:
            model_id = await conn.fetchval(
                'INSERT INTO public."LLMModel" ("modelName") VALUES ($1) '
                'ON CONFLICT ("modelName") DO NOTHING RETURNING id',
                model_name,
            )
            if model_id is None:
                model_id = await conn.fetchval(
                    'SELECT id FROM public."LLMModel" WHERE "modelName" = $1', model_name
                )
            else:
                created_models += 1

            provider_intersect = await conn.fetchval(
                'INSERT INTO public."ProviderModelIntersect" ("providerCode", "modelId") '
                'VALUES ($1, $2) ON CONFLICT ("providerCode", "modelId") DO NOTHING '
                'RETURNING "modelId"',
                provider_code, model_id,
            )
            if provider_intersect is not None:
                created_provider += 1

            seen = await conn.fetchval(
                'SELECT 1 FROM public."ConnectionModelIntersect" '
                'WHERE "connectionId" = $1 AND "modelId" = $2',
                connection_id, model_id,
            )
            if seen is None:
                await conn.execute(
                    'INSERT INTO public."ConnectionModelIntersect" '
                    '("connectionId", "modelId", "lastSeenAt") '
                    'VALUES ($1, $2, clock_timestamp())',
                    connection_id, model_id,
                )
                created_connection += 1
            else:
                # A second walk sees the same rows; `lastSeenAt` is the whole of
                # what changes, and it is what makes "still served" distinguishable
                # from "served when this was set up".
                #
                # `clock_timestamp()`, not NOW(). NOW() is the TRANSACTION's start
                # time in PostgreSQL: inside a caller's transaction — which this
                # walk joins — every statement sees the same value, so a second
                # walk would record no advance at all. The column's meaning is "the
                # moment a walk saw this", and for a walk that can take a minute
                # against a large catalogue, transaction start is the wrong moment.
                # This is the one place in the schema that diverges from
                # CURRENT_TIMESTAMP, and it does so deliberately.
                await conn.execute(
                    'UPDATE public."ConnectionModelIntersect" '
                    'SET "lastSeenAt" = clock_timestamp() '
                    'WHERE "connectionId" = $1 AND "modelId" = $2',
                    connection_id, model_id,
                )
                refreshed += 1

            seen_model_ids.append(model_id)

        # Prune, scoped to this connection and nothing else. The pair is the whole
        # of the predicate: another connection to the same provider may serve
        # models this one does not, and its rows are not this walk's to delete —
        # that is the defect that started this redesign. The provider intersect and
        # the model record are deliberately untouched: both hold facts that may
        # have come from a server this walk cannot see.
        #
        # Counted with a CTE rather than by parsing `DELETE n`, so the number is
        # read from the statement that did the work rather than from its tag line.
        pruned = await conn.fetchval(
            'WITH gone AS (DELETE FROM public."ConnectionModelIntersect" '
            'WHERE "connectionId" = $1 AND "modelId" <> ALL($2::text[]) RETURNING 1) '
            'SELECT count(*) FROM gone',
            connection_id, seen_model_ids,
        )

    return DiscoveryResult(
        models_seen=len(model_names),
        models_created=created_models,
        provider_intersects_created=created_provider,
        connection_intersects_created=created_connection,
        connection_intersects_refreshed=refreshed,
        connection_intersects_pruned=pruned,
    )
