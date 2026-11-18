"""
The AI limits in force for one connection/model pair (plan Item 5).

One resolver, four tiers, one round trip. Precedence, highest first:

  1. the per-request override  — applied by the CALLER, not here: it belongs to one
                                 attempt and is never stored, so the resolver has
                                 nothing to read. See the note below.
  2. the pair's own tuning     — ConnectionModelIntersect, NULL meaning "inherit"
  3. the workbench default     — GlobalSettings, NOT NULL
  4. the built-in constant     — reachable only when the settings row is absent

WHY THIS MIRRORS resolve_slow_threshold RATHER THAN INVENTING A SHAPE

`routers/user/user_settings.py` already resolves a three-tier value with a LEFT JOIN
from `(SELECT 1)`, and its docstring records the defect that shape exists to avoid:
with a plain `FROM "User" WHERE id = $1`, a missing row returns nothing at all and
the *global* tier — which does not depend on the user — is lost with it. The Go twin
had that bug and returned the built-in where the global applied. The same trap waits
here: a plain `FROM "ConnectionModelIntersect" WHERE ...` would lose the global
defaults whenever the pair has never been discovered, which is the most common case.

WHY THE PER-REQUEST TIER IS NOT IN THIS FUNCTION

A per-request override is a property of one call, not of the pair or the workbench.
Putting it in the resolver would mean passing a request into a function whose whole
job is to answer "what is configured here", and it would make the four-tier ordering
look like it is decided in one place when the first tier is actually decided by the
caller. The contract is: call `resolve_ai_limits`, then apply any per-request
override on top. Item 12 adds that override; the ordering is documented here so the
caller knows where it sits.

WHY IT RETURNS ALL THREE

A call site that resolved only the value it happened to need would apply a partial
set — a timeout from the pair and a temperature from somewhere else — and no single
place would show the limits a request actually ran under. One value object, resolved
together, is cheap (one query) and impossible to half-apply.

WHY `conn` AND NOT THE POOL

Passed in rather than taken from `_db_pool`, so a caller already inside a transaction
resolves against that transaction's view — the same reason `resolve_slow_threshold`
takes a connection. A caller with no transaction passes one from the pool.
"""

from dataclasses import dataclass
from typing import Optional

# The fourth tier. Reachable only when the GlobalSettings row is absent, which the
# settings read path normally prevents by creating it. All three match the
# migration's column defaults, so a fresh install and a missing row agree.
#
# WHY THE TWO SAMPLING DEFAULTS LIVE HERE AND NOT IN llm_connection
#
# They used to be declared in llm_connection.py and imported from it. That created a
# circular import the moment this module started importing them: ai_limits →
# llm_connection → src.chat.providers → src.chat.__init__ → title → ai_limits. The
# cycle is invisible until something imports title first, which main.py does.
#
# The resolver is the right home: it is the module whose question is "what value is in
# force", so the bottom tier belongs with it. llm_connection imports them from here,
# which is a one-way edge.
DEFAULT_TEMPERATURE = 0.7
DEFAULT_MAX_TOKENS = 4000
DEFAULT_TIMEOUT_SECONDS = 120

#: The most a single AI call may be given, by any route — pair tuning, workbench
#: default, or a per-request escalation. The user's number and their reason, from
#: the design conversation of 2026-11-01: *"a number that means 20 minutes - a
#: completely unusable AI at that performance"*.
#:
#: It is a PRODUCT judgement about usability, not a structural invariant: past this,
#: the model is not slow, it is unusable, and holding a worker that long helps
#: nobody. That distinction is why it is enforced in the backend only and not as a
#: database CHECK — a constraint says "this can never be valid", and this number is
#: one someone might one day raise.
MAX_TIMEOUT_SECONDS = 1200

#: Provider errors that mean the call ran out of time rather than failed for another
#: reason. Matched as an exact token inside the ValueError a provider raises, because
#: that is the contract the provider layer states; a substring match would classify
#: `OLLAMA_TIMEOUT_HINT` as a timeout too.
TIMEOUT_ERRORS = frozenset({
    "OLLAMA_TIMEOUT",
    "OLLAMA_REMOTE_TIMEOUT",
    "OPENAI_TIMEOUT",
})


def is_timeout_error(exc: BaseException) -> bool:
    """Whether a provider exception means the call timed out.

    The client needs to tell "it ran out of time" from "it failed", because only the
    first offers a retry with more time. The provider layer signals this with a bare
    token in a ValueError; that token is the contract, so it is compared exactly
    rather than searched for.
    """
    return isinstance(exc, ValueError) and str(exc) in TIMEOUT_ERRORS


def apply_timeout_override(limits: "AILimits", override: Optional[int]) -> "AILimits":
    """The limits with a per-request timeout applied on top, or `limits` unchanged.

    The per-request tier sits ABOVE the resolved tiers — that is the ordering the
    module docstring documents — and it touches only the timeout. Temperature and the
    output cap cannot be escalated per request: those change what the model says, and
    a retry that changes the answer is not a retry.

    The ceiling is enforced here rather than in each route, so chat and describe
    cannot disagree about it. A value below 1 is refused the same way; the caller
    turns the ValueError into its own coded 400.
    """
    if override is None:
        return limits
    if override < 1 or override > MAX_TIMEOUT_SECONDS:
        raise ValueError("invalid_timeout_override")
    return AILimits(
        temperature=limits.temperature,
        max_tokens=limits.max_tokens,
        timeout_seconds=override,
    )


@dataclass(frozen=True)
class AILimits:
    """The three values in force for one pair, already resolved.

    Frozen because a resolved limit set is a fact about a moment: passing it around
    and mutating it would let one call site change what another sees.
    """

    temperature: float
    max_tokens: int
    timeout_seconds: int


async def resolve_ai_limits(conn, connection_id: int, model_id: str) -> AILimits:
    """The AI limits in effect for `(connection_id, model_id)`.

    Tiers 2 to 4, in one round trip. See the module docstring for why the
    per-request override is not one of them.

    A pair that does not exist is not an error: every tier still answers, because
    the LEFT JOIN guarantees one row carrying the pair's columns (all NULL) and the
    global columns. That is what makes "tune the global and every untuned pair
    follows" true without a backfill.
    """
    # A LEFT JOIN from a one-row anchor, not `FROM "ConnectionModelIntersect" WHERE …`.
    #
    # With a plain FROM + WHERE, a pair nobody has discovered returns no row at all,
    # and the global defaults — which do not depend on the pair — are lost with it.
    # The join guarantees exactly one row carrying both tiers, so tier 3 survives an
    # absent pair. This is the same defect `resolve_slow_threshold` documents, and it
    # is the common case here rather than the exotic one: most pairs are not tuned.
    #
    # No LIMIT on the global side: GlobalSettings carries CHECK (id = 1), so there can
    # be at most one row and `g.id = 1` names it exactly. A LIMIT would be a filter
    # that silently picks a row when there should be one — the defect the constraint
    # was added to remove.
    row = await conn.fetchrow(
        'SELECT p."temperature" AS pair_temperature, '
        '       p."maxTokens" AS pair_max_tokens, '
        '       p."timeoutSeconds" AS pair_timeout, '
        '       g."temperature" AS global_temperature, '
        '       g."maxTokens" AS global_max_tokens, '
        '       g."timeoutSeconds" AS global_timeout '
        'FROM (SELECT 1) AS one '
        'LEFT JOIN public."ConnectionModelIntersect" p '
        '       ON p."connectionId" = $1 AND p."modelId" = $2 '
        'LEFT JOIN public."GlobalSettings" g ON g.id = 1',
        connection_id, model_id,
    )

    if row is None:
        # Cannot happen with the join, but a caller resolving inside an aborted
        # transaction should get the built-ins rather than an exception from a None.
        row = {}

    # Tier 2: the pair's own value. `is not None` rather than truthiness throughout —
    # a temperature of 0 is a real setting, and `if row["pair_temperature"]` would
    # treat it as absent and inherit the global default instead. That is exactly the
    # distinction Item 4's NULL-versus-0 test pins.
    temperature: Optional[float] = row.get("pair_temperature")
    if temperature is None:
        temperature = row.get("global_temperature")
    if temperature is None:
        temperature = DEFAULT_TEMPERATURE  # tier 4

    max_tokens: Optional[int] = row.get("pair_max_tokens")
    if max_tokens is None:
        max_tokens = row.get("global_max_tokens")
    if max_tokens is None:
        max_tokens = DEFAULT_MAX_TOKENS

    timeout_seconds: Optional[int] = row.get("pair_timeout")
    if timeout_seconds is None:
        timeout_seconds = row.get("global_timeout")
    if timeout_seconds is None:
        timeout_seconds = DEFAULT_TIMEOUT_SECONDS

    return AILimits(
        temperature=float(temperature),
        max_tokens=int(max_tokens),
        timeout_seconds=int(timeout_seconds),
    )


async def resolve_ai_limits_for_model(conn, connection_id: int, model_name: str) -> AILimits:
    """The limits for a request that names its model rather than its id.

    Every AI request carries `(connectionId, model)` where `model` is the model's
    NAME — that is what the provider is asked for. The pair, however, is keyed on
    `modelId`, which is `LLMModel.id`. So a request cannot address a pair without
    this translation, and putting it here keeps it in one place rather than in each
    call site.

    An unknown name is not an error and not a special case: no pair can exist for a
    model nothing has recorded, so the query below finds no `LLMModel` row, the join
    yields no pair columns, and `resolve_ai_limits` falls through to the workbench
    defaults. That is the same path as any untuned pair — see clause 3 of its tests.
    """
    model_id = await conn.fetchval(
        'SELECT id FROM public."LLMModel" WHERE "modelName" = $1', model_name
    )
    # A name nothing has recorded cannot match a pair; a value that cannot match is
    # what the resolver's join expects for "no pair here".
    return await resolve_ai_limits(conn, connection_id, model_id if model_id else "")
