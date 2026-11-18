"""
Model probes — the `tools` and `competence` tests.

AI model suitability plan, Item 7. Both probes drive the **provider layer**
(`ProviderFactory.create(...)` then `provider.call(...)`) rather than posting to
a provider's HTTP API by hand, because that is the same call the concierges make.
A hand-rolled probe measures a different code path: a provider whose `call()`
shapes messages, defaults a model or maps an error differently would pass the
probe and fail in production.

The message shapes mirror `chat/tool_agent.py::run_tool_loop` — an assistant
message carrying `tool_calls`, then a `role: "tool"` message carrying the result
and the same `tool_call_id` — so a model that passes here has passed on the
sequence it will actually be sent.

WHAT A PROBE RETURNS
--------------------
A `ProbeOutcome`, never a boolean. The reason recorded on the model depends on
telling "described the call" apart from "invented an answer", and a bool cannot
carry that. The outcome strings are exactly the reason keys Item 9 stores:
`ok`, `describes`, `fabricates`, `vocabulary`, `unstable`.

A probe that could not reach the model raises `ProbeTransportError` instead of
returning an outcome. That distinction is the whole point of the plan's warning
callout: a transport failure is not a verdict about a model, so the caller must
be able to tell the two apart and write nothing.

WHAT EACH TEST MEASURES
-----------------------
`tools`      — does the model emit a tool call for the tool it was told to call?
               Argument *values* are recorded as evidence but not judged; using
               the arguments correctly is `competence`'s question.
`competence` — two rounds. First, a tool whose argument is an enumerated set:
               does the model use a declared value rather than inventing one?
               Second, a tool that must carry a token returned by the first:
               does the model read the result it was given?
"""

import json
import logging

from src.utils.connection_timeouts import DEFAULT_CONNECT_TIMEOUT_SECONDS
from src.chat.failure_taxonomy import ProviderError, retry_attempts

from src.chat.probe_vocabulary import (
    DEFAULT_TIMEOUT,
    DESCRIBES,
    FABRICATES,
    INCONCLUSIVE,
    OK,
    UNSTABLE,
    INVALID_CHOICE,
    UNKNOWN_MEMBER,
    ProbeOutcome,
    ProbeTransportError,
)
from src.chat.providers.base import ProviderFactory
from src.routers.aitesting.concierge import run_test_turn
from src.routers.aitesting.synthetic_dataset import synthetic_dataset

logger = logging.getLogger(__name__)

# Mirrors chat/tool_agent.py:LLM_REPEAT_RETRIES. A token-repetition loop and a
# timeout are both transient — the loop is stochastic, so a retry often recovers.
PROBE_RETRIES = 3

# The outcome type, its closed set and `ProbeTransportError` are imported from
# `probe_vocabulary` rather than declared here, because the test concierge returns
# the same vocabulary as these probes and `probe_turn` calls that concierge.
# Declaring it in either module makes the other import its importer: a cycle. This
# module used to dodge it with a function-body import, which the no-lazy-loading
# rule forbids and Go cannot express at all — so the boundary moved instead of
# the import being hidden.


# ---------------------------------------------------------------------------
# Tool schemas. Deliberately tiny: one tool, one instruction, no dataset and no
# schema, so a failure cannot be blamed on context a concierge would not send.
# ---------------------------------------------------------------------------

_TOOLS_SCHEMA = [
    {
        "type": "function",
        "function": {
            "name": "get_dataset_schema",
            "description": "Return the columns of a dataset",
            "parameters": {
                "type": "object",
                "properties": {"dataset_id": {"type": "string"}},
                "required": ["dataset_id"],
            },
        },
    }
]

_COMPETENCE_QUERY_SCHEMA = [
    {
        "type": "function",
        "function": {
            "name": "run_query",
            "description": "Run an aggregate over a dataset",
            "parameters": {
                "type": "object",
                "properties": {
                    "dataset_id": {"type": "string"},
                    "operation": {
                        "type": "string",
                        "enum": ["count", "sum", "mean"],
                        "description": "One of the declared operations",
                    },
                },
                "required": ["dataset_id", "operation"],
            },
        },
    }
]

_COMPETENCE_REPORT_SCHEMA = [
    {
        "type": "function",
        "function": {
            "name": "report_token",
            "description": "Report the token returned by the previous tool call",
            "parameters": {
                "type": "object",
                "properties": {"token": {"type": "string"}},
                "required": ["token"],
            },
        },
    }
]

# The token the first round hands back. A model that reads its tool result must
# pass this exact string to the second tool.
_TOKEN = "r7f3a"


# ---------------------------------------------------------------------------
# Provider call
# ---------------------------------------------------------------------------

async def _call(
    provider_code: str,
    api_key,
    endpoint,
    model: str,
    messages: list,
    tools: list,
    timeout: float,
    connect_timeout: float = DEFAULT_CONNECT_TIMEOUT_SECONDS,
) -> dict:
    """One provider call, with the concierge's retry-on-transient behaviour.

    Returns the assistant message dict (`{"role","content","tool_calls"?}`).
    Raises ProbeTransportError when the model was never reached or never
    answered; returns an `unstable` classification result separately for a
    persistent token-repetition loop, which *is* a model behaviour.
    """
    try:
        provider = ProviderFactory.create(provider_code, api_key, endpoint)
    except ValueError as exc:
        # Unknown provider — a configuration fault, not a model behaviour.
        raise ProbeTransportError(f"unknown_provider:{exc}", "other")

    last_detail = ""
    last_class, last_status = "other", None
    # How many times each BUDGET KEY has already failed, so a class-specific limit can
    # be applied per class rather than to the loop as a whole (plan Item 6).
    #
    # Keyed by the class, except for token repetition, which is not a failure class —
    # it is model degeneration, detected from the text, and it keeps its own budget
    # because it has been observed to recover.
    failures_by_budget_key: dict[str, int] = {}
    for attempt in range(1 + PROBE_RETRIES):
        try:
            return await provider.call(
                messages=messages,
                model=model,
                tools=tools,
                temperature=0.1,
                max_tokens=1024,
                timeout=timeout,
                # The connect budget for this connection (plan Item 4a). Item 4 gave
                # the providers a separate connect phase; without this the probe used
                # the compiled default and a per-connection setting never reached it.
                connect_timeout=connect_timeout,
            )
        except ValueError as exc:
            # ONE branch, catching both. `ProviderError` subclasses ValueError, so the
            # retry and outcome logic below would otherwise have to be duplicated into
            # a second handler — and a duplicated tail is how the two paths drift.
            #
            # The class arrives as an attribute when the provider supplied one (plan
            # Item 5) and is `other` when it did not, which is the honest answer for a
            # plain ValueError from a test double or from ProviderFactory.
            detail = getattr(exc, "detail", str(exc))
            last_detail = detail
            last_class = getattr(exc, "failure_class", "other")
            last_status = getattr(exc, "http_status", None)
            # THE RETRY BUDGET IS A LOOKUP NOW, not a string test (plan Item 6).
            #
            # The one case still decided by text is token repetition, because it is
            # model degeneration rather than a transport failure — it has no class and
            # keeps its own ceiling. Everything else asks the table.
            degenerate = "token repeat limit" in detail
            budget_key = "token_repeat" if degenerate else last_class
            failures_by_budget_key[budget_key] = failures_by_budget_key.get(budget_key, 0) + 1
            allowed_extra = (
                PROBE_RETRIES if degenerate
                else retry_attempts(last_class, last_status)
            )
            if failures_by_budget_key[budget_key] <= allowed_extra:
                logger.warning(
                    "probe retrying after %s (attempt %d, %d extra allowed): %s",
                    budget_key, failures_by_budget_key[budget_key], allowed_extra, detail,
                )
                continue
            if "token repeat limit" in detail:
                # Persistent degeneration is a property of the model, so it is a
                # verdict — `unstable` — rather than a transport failure.
                raise _Unstable(detail)
            # A 5xx USED TO BE A VERDICT HERE (`unstable`, hence `fail` on the model),
            # decided by `_server_failed` scanning the detail for a 500-599 token.
            # Removed 2026-11-02 on the user's ruling: **capability was never measured**.
            #
            # A 5xx is the provider's own stack failing — a proxy, a worker, a gateway,
            # a quota service answering with the wrong code. From one 500 nothing can be
            # concluded about the model: it may never have been consulted. Filing it as
            # `unstable` blamed the model for a server crash, which is the same defect
            # `probe_vocabulary.INCONCLUSIVE` was introduced to prevent — a fact about
            # the run reaching the model record.
            #
            # It is still its own class, still retried once, and still reported with its
            # status (`api.user.test_http_status`). What changed is only what it may
            # write: nothing. A no-answer failure is a failure to ask the question.
            raise ProbeTransportError(last_detail, last_class, last_status)

    raise ProbeTransportError(last_detail or "provider_call_failed", last_class, last_status)


class _Unstable(Exception):
    """Internal signal: the model degenerated into a token-repetition loop."""

    def __init__(self, detail: str):
        self.detail = detail
        super().__init__(detail)


# ---------------------------------------------------------------------------
# Reading what came back
# ---------------------------------------------------------------------------

def _arguments(call: dict) -> dict:
    """Tool-call arguments, whichever shape the provider used.

    OpenAI-compatible providers send a JSON *string*; Ollama native sends an
    already-parsed object. `tool_agent.py` normalises the same way, and the
    round-trip has to preserve whichever the provider sent.
    """
    raw = (call.get("function") or {}).get("arguments") or {}
    if isinstance(raw, str):
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return {}
    return raw if isinstance(raw, dict) else {}


def _tool_name(call: dict) -> str:
    return ((call.get("function") or {}).get("name") or "").strip()


def _looks_like_code(text: str) -> bool:
    markers = ("```", "def ", "print(", "import ", "()", "=(", "json.loads(")
    return any(m in text for m in markers)


def _classify_no_tool_call(content: str, tool_name: str) -> str:
    """`describes` when the reply talks about calling the tool or shows code.

    `fabricates` when it answers as though the call had happened — the
    small-model signature: a plausible invented answer with no tool call behind
    it. Both are recorded with the reply text so a disputed verdict can be
    re-read rather than argued from memory.

    An EMPTY reply is neither. It used to fall through to `fabricates`, which
    accused a model that said nothing of inventing data — the opposite of what
    happened. It then returned `unstable`, the nearest of the five, and that
    comment recorded the gap explicitly: adding a sixth name was the user's
    decision. Item 20a took it. An empty reply is not an observation of the model
    at all — the usual cause is a budget spent before an answer — so it is
    `INCONCLUSIVE`, which `state_for` refuses and no writer may record.
    """
    text = (content or "").strip()
    if not text:
        return INCONCLUSIVE
    if tool_name in text or _looks_like_code(text):
        return DESCRIBES
    return FABRICATES


async def _first_call(
    provider_code, api_key, endpoint, model, messages, tools, timeout, expected_tool,
    connect_timeout: float = DEFAULT_CONNECT_TIMEOUT_SECONDS,
):
    """Run one round and return (outcome_or_None, call, message).

    `outcome_or_None` is None when a tool call for `expected_tool` came back;
    otherwise it is the classification for what happened instead.
    """
    try:
        message = await _call(
            provider_code, api_key, endpoint, model, messages, tools, timeout,
            connect_timeout=connect_timeout,
        )
    except _Unstable as exc:
        return ProbeOutcome(UNSTABLE, exc.detail, {"phase": "call"}), None, None

    calls = message.get("tool_calls") or []
    content = message.get("content") or ""
    obs = {"phase": "call", "content": content[:500], "tool_calls": len(calls)}

    if not calls:
        return (
            ProbeOutcome(_classify_no_tool_call(content, expected_tool), content[:200], obs),
            None,
            message,
        )

    names = [_tool_name(c) for c in calls]
    obs["names"] = names
    for call in calls:
        if _tool_name(call) == expected_tool:
            return None, call, message

    # It called something, just not what it was asked for. That is a vocabulary
    # failure rather than a silent one, and the names recorded here are what
    # make it diagnosable.
    return (
        ProbeOutcome(
            UNKNOWN_MEMBER, f"called {names} instead of {expected_tool}", obs
        ),
        None,
        message,
    )


# ---------------------------------------------------------------------------
# The probes
# ---------------------------------------------------------------------------

async def probe_tools(
    provider_code: str,
    api_key,
    endpoint,
    model: str,
    timeout: float = DEFAULT_TIMEOUT,
    connect_timeout: float = DEFAULT_CONNECT_TIMEOUT_SECONDS,
) -> ProbeOutcome:
    """Does the model emit a tool call at all?

    One tool, one instruction, no dataset. The guide's probe, run through the
    provider layer the concierges use.
    """
    messages = [
        {
            "role": "user",
            "content": "Call get_dataset_schema with dataset_id=abc123 now.",
        }
    ]
    outcome, call, message = await _first_call(
        provider_code, api_key, endpoint, model, messages, _TOOLS_SCHEMA,
        timeout, "get_dataset_schema", connect_timeout=connect_timeout,
    )
    if outcome is not None:
        return outcome

    args = _arguments(call)
    return ProbeOutcome(
        OK,
        "emitted get_dataset_schema",
        {
            "phase": "call",
            "tool": "get_dataset_schema",
            "arguments": args,
            # Recorded, not judged: whether the id is the one asked for is a
            # question about following instructions, which `competence` covers.
            "content": (message.get("content") or "")[:200],
        },
    )


async def probe_competence(
    provider_code: str,
    api_key,
    endpoint,
    model: str,
    timeout: float = DEFAULT_TIMEOUT,
    connect_timeout: float = DEFAULT_CONNECT_TIMEOUT_SECONDS,
) -> ProbeOutcome:
    """Does the model use declared values, and read what a tool returned?

    Round 1: a tool whose `operation` is an enumerated set. A value outside the
    enum is `vocabulary` — the invented-operation signature the guide records.

    Round 2: a tool that must carry the token returned by round 1. The token is
    supplied by the harness, never by the model, so passing it is evidence the
    model read its tool result.
    """
    # ---- round 1 -----------------------------------------------------------
    messages = [
        {
            "role": "user",
            "content": (
                "Call run_query for dataset abc123 using the count operation, now."
            ),
        }
    ]
    outcome, call, _message = await _first_call(
        provider_code, api_key, endpoint, model, messages, _COMPETENCE_QUERY_SCHEMA,
        timeout, "run_query", connect_timeout=connect_timeout,
    )
    if outcome is not None:
        return outcome

    args = _arguments(call)
    operation = str(args.get("operation", "")).strip().lower()
    if operation not in ("count", "sum", "mean"):
        return ProbeOutcome(
            INVALID_CHOICE,
            f"operation {operation!r} is not a declared value",
            {"phase": "round1", "arguments": args},
        )

    # ---- round 2 -----------------------------------------------------------
    # Mirror tool_agent.py: the assistant message keeps the provider's own
    # tool_calls shape, and the result goes back as a `tool` message carrying
    # the same id.
    tool_result = {"ok": True, "row_count": 42, "token": _TOKEN}
    messages.append({"role": "assistant", "content": "", "tool_calls": call.get("tool_calls") or [call]})
    messages.append(
        {
            "role": "tool",
            "tool_call_id": call.get("id"),
            "content": json.dumps(tool_result),
        }
    )
    messages.append(
        {
            "role": "user",
            "content": (
                "Now call report_token with the token the previous tool returned."
            ),
        }
    )

    outcome2, call2, message2 = await _first_call(
        provider_code, api_key, endpoint, model, messages, _COMPETENCE_REPORT_SCHEMA,
        timeout, "report_token", connect_timeout=connect_timeout,
    )
    if outcome2 is not None:
        return ProbeOutcome(
            outcome2.outcome,
            f"round 2: {outcome2.detail}",
            {**outcome2.observations, "phase": "round2", "round1_operation": operation},
        )

    args2 = _arguments(call2)
    token = str(args2.get("token", "")).strip()
    if token != _TOKEN:
        # NOT a vocabulary fault: the model reported a value that no tool returned.
        # That is the same claim the truth check exists to catch, so it is recorded as
        # fabrication rather than as a bad argument — the mis-transcription and the
        # invention are indistinguishable from outside, and both assert something untrue.
        return ProbeOutcome(
            FABRICATES,
            f"reported token {token!r}, not the one returned ({_TOKEN!r})",
            {"phase": "round2", "arguments": args2, "expected_token": _TOKEN},
        )

    return ProbeOutcome(
        OK,
        "used a declared operation and carried the returned token",
        {
            "phase": "round2",
            "round1_operation": operation,
            "round2_token": token,
            "content": (message2.get("content") or "")[:200],
        },
    )

async def probe_turn(
    provider_code: str,
    api_key,
    endpoint,
    model: str,
    timeout: float = DEFAULT_TIMEOUT,
    connect_timeout: float = DEFAULT_CONNECT_TIMEOUT_SECONDS,
) -> ProbeOutcome:
    """Does the model drive a whole concierge turn against a real dataset?

    This is the third test (plan Item 9c). It is the only one that needs a
    dataset, and the only one that can take minutes.

    WHAT IT DOES
    ------------
    Creates the synthetic dataset in `workbench_data` (Item 9b), hands it to the
    AI-test concierge (Item 9a), and asks one request a real user would make.
    The dataset is dropped however the turn ends, including on cancellation.

    WHAT A FAIL HERE MEANS, AND WHAT IT DOES NOT
    --------------------------------------------
    A failure is *not* the same evidence as a failure at `tools`. It may be the
    model, our fixture, or our idea of a usable answer. That is why the tests are
    recorded separately and why the gate does not yet act on this one.

    TRANSPORT
    ---------
    A provider that cannot be reached raises `ProbeTransportError`, so nothing is
    written — the same rule as the other two probes.
    """

    try:
        async with synthetic_dataset() as dataset:
            return await run_test_turn(
                provider_code=provider_code,
                api_key=api_key,
                endpoint=endpoint,
                model=model,
                dataset=dataset,
                timeout=timeout,
                connect_timeout=connect_timeout,
            )
    except ProbeTransportError:
        raise
    except RuntimeError as exc:
        # A dataset-side failure (pool not initialised, table collision) is a
        # fault in the harness, not an answer from the model.
        raise ProbeTransportError(f"harness:{exc}")
