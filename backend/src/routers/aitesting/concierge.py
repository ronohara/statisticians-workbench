"""
The AI-test concierge — an instrument, not a feature.

Plan Item 9a. It exists so that the `turn` test has something stable to drive.
The recipe concierge measures the recipe concierge: its prompt, its nine tools,
its draft model. A test built on it would change meaning every time that prompt
was tuned, and a failure could never be attributed. This one has a fixed prompt
and three tools, so what it measures is "can this model drive a tool loop at
all", which is the question the test is asking.

WHAT IT REUSES, AND WHAT IT DOES NOT
------------------------------------
It subclasses `ToolAgent`, so the LLM call, the tool dispatch, the loop and the
retry-on-transient behaviour are the same code the other concierges run — a peer
of them, not a parallel implementation. It reuses none of their prompts.

WHAT IT DOES NOT DO
-------------------
It keeps no session row. A test that leaves a session behind leaves litter
nobody asked for, and the plan says so. Its state lives on the instance for the
duration of one turn.

OUTCOME CLASSIFICATION
----------------------
`run_test_turn` returns a `ProbeOutcome` from `chat/probe_vocabulary.py`, so the
`turn` test speaks the same closed vocabulary as the other two probes and the
endpoint writes it through the same writer. The vocabulary lives in its own
module precisely so this one does not import `model_probe` — which imports this,
for `probe_turn`.

A transport failure raises `ProbeTransportError` — the model was never asked, so
there is no verdict to record.
"""

import json
import logging
import re

from src.chat.probe_vocabulary import (
    DEFAULT_TIMEOUT,
    DESCRIBES,
    FABRICATES,
    INCONCLUSIVE,
    INVALID_CHOICE,
    OK,
    UNSTABLE,
    UNKNOWN_MEMBER,
    ProbeOutcome,
    ProbeTransportError,
)
from src.chat.tool_agent import ToolAgent
from src.utils.connection_timeouts import DEFAULT_CONNECT_TIMEOUT_SECONDS

from .tools import AITESTING_REGISTRY
from .translations import SYSTEM_PROMPT, TOOL_NAMES, USER_REQUEST

logger = logging.getLogger(__name__)

# One turn is bounded. A model that has not finished in this many tool rounds is
# not going to, and the harness must not hang on it.
MAX_ROUNDS = 6


class TestConcierge(ToolAgent):
    """A tool-loop agent whose only job is to be measured."""

    def __init__(self, dataset=None, **kwargs):
        super().__init__(**kwargs)
        # The dataset this turn may read. See tools.py for the shape; Item 9b
        # supplies the real one, a fixture can supply a tiny one.
        self.test_dataset = dataset
        # Set by the report tool when the model calls it.
        self.test_finding = ""


def _is_server_failure(detail: str) -> bool:
    """True when a provider error string carries a 5xx status.

    ToolAgent wraps provider failures as `ai_provider_error:<detail>`, and the
    provider's own detail carries the status (`OLLAMA_HTTP_ERROR:500:…`), so the
    status is in the string. A 5xx is the server answering and failing — Item 9
    — while a timeout or a refused connection is transport.
    """
    for token in detail.replace(":", " ").split():
        if token.isdigit() and 500 <= int(token) <= 599:
            return True
    return False


async def run_test_turn(
    provider_code: str,
    api_key,
    endpoint,
    model: str,
    dataset: dict,
    language: str = "en",
    timeout: float = DEFAULT_TIMEOUT,
    connect_timeout: float = DEFAULT_CONNECT_TIMEOUT_SECONDS,
) -> ProbeOutcome:
    """Drive one concierge turn and classify what happened.

    The dataset is required: without one, the tools have nothing to read and the
    turn would measure the model's reaction to an empty world rather than its
    ability to use tools.
    """
    if not dataset:
        raise ValueError("run_test_turn requires a dataset")

    # The test tools register at module import (tools.py).

    # The budgets travel to the agent (plan Item 4a). Until this was wired, BOTH
    # parameters were inert: `timeout` was never used in this function's body, and
    # `ToolAgent.timeout` was declared and read but never assigned — so a `turn` probe
    # ran on the provider's own default no matter what the caller asked for.
    agent = TestConcierge(
        dataset=dataset,
        api_key=api_key,
        endpoint=endpoint,
        model=model,
        provider=provider_code,
        language=language,
        timeout=timeout,
        connect_timeout=connect_timeout,
        registry=AITESTING_REGISTRY,
    )

    messages = [{"role": "user", "content": USER_REQUEST}]

    try:
        final_text, tool_events = await agent.run_tool_loop(
            SYSTEM_PROMPT, messages, tool_names=TOOL_NAMES,
            tools_for_round=_offered_tools,
        )
    except RuntimeError as exc:
        # ToolAgent raises RuntimeError for several different things, and they
        # are not the same kind of event. Collapsing them all into "transport"
        # would record a model that degenerated into a repeat loop as if nothing
        # had happened at all — which is what this code did before 2026-10-30.
        detail = str(exc)
        if "ai_repeat_loop" in detail or _is_server_failure(detail):
            # Both are the model (or its server) answering badly: Item 9 records
            # them as `unstable`, a verdict rather than an absence of one.
            return ProbeOutcome(
                UNSTABLE, detail[:200], {"phase": "turn", "error": detail}
            )
        raise ProbeTransportError(detail)
    except ValueError as exc:
        raise ProbeTransportError(str(exc))

    spent = getattr(agent, "tokens_spent", None)
    observations = {
        "phase": "turn",
        "tool_calls": [name for name, _args in tool_events],
        "tool_call_count": len(tool_events),
        "finding": getattr(agent, "test_finding", ""),
        "content": (final_text or "")[:500],
    }
    if spent is not None:
        observations["tokens"] = spent

    # --- classify ----------------------------------------------------------
    if not tool_events:
        # No tool was called at all: the model answered from nothing, and the
        # distinction between showing how and inventing an answer is the one
        # Item 9 cares about.
        reason = _classify_without_tools(final_text or "")
        return ProbeOutcome(reason, "no tool call in the turn", observations)

    # --- truth check --------------------------------------------------------
    # Did the model report numbers the tools never produced?
    #
    # Tools ran, so there are results to compare against. This is what separates
    # "used a column name that does not exist" from "invented the answer", and it
    # exists because the instrument could not tell them apart: a measured run
    # called the right tools, received {"value": 6} and {"value": 151.93}, then
    # reported "1000 rows, mean 50.0" — and was recorded OK, because the classifier
    # only asked whether tools ran and whether anything was said.
    #
    # It runs BEFORE the tool-error check on purpose. A turn where a tool errored
    # and the model then invented an answer is a fabrication, not a vocabulary
    # slip; vocabulary is left for the honest case, where the model reports that
    # it could not compute the answer.
    asserted = " ".join(
        part for part in (getattr(agent, "test_finding", ""), final_text or "") if part
    )
    unsupported = _unsupported_numbers(asserted, _tool_numbers(messages))
    if unsupported:
        observations["unsupported_numbers"] = unsupported
        return ProbeOutcome(
            FABRICATES,
            "reported numbers no tool returned: " + ", ".join(unsupported),
            observations,
        )

    # A tool call that the executor refused. WHAT MATTERS IS WHERE THE TURN ENDED,
    # not whether it ever stumbled: a model that is refused a column, reads the
    # schema again and answers correctly has done the job a concierge has to do.
    #
    # Measured 2026-11-02, and it is why this reads the way it does: qwen2.5:14b was
    # refused a column, tried again, and reported "the mean value of the 'amount'
    # column is approximately 151.93" — exactly right, checked against the fixture —
    # and was recorded `fail / unknown_member` because an error appeared anywhere in
    # the transcript. Meanwhile the user's calibration is that recovery is normal:
    # "credit recovery will happen when really using the model, so it should be used".
    #
    # `_query_returned_data` is the same test the offerable-tools rule already uses,
    # and asking it here is what makes the two agree about what "the turn worked"
    # means.
    error = _first_tool_error(messages)
    if error is not None:
        kind = str(error.get("error"))
        recovered = _query_returned_data(messages)
        observations["tool_error"] = kind
        if error.get("column"):
            # The executor names what it refused, so the evidence and the sentence can
            # both say WHICH member did not exist instead of printing the code.
            observations["tool_error_column"] = error["column"]
        if recovered:
            observations["recovered_from"] = kind
        else:
            if kind == "unknown_operation":
                return ProbeOutcome(
                    INVALID_CHOICE,
                    "chose a value outside the declared set",
                    observations,
                )
            return ProbeOutcome(
                UNKNOWN_MEMBER,
                _member_message(error),
                observations,
            )

    if not (final_text or "").strip():
        # Tools ran, then the model produced no answer. This is a fact about the
        # RUN, not about the model: the measured case is deepseek-r1:8b spending
        # its whole 1024-token budget thinking. It was `unstable`, the nearest of
        # five closed reasons; Item 20a gave it its own name so that a writer
        # cannot record a slow machine as a model that cannot act.
        return ProbeOutcome(
            INCONCLUSIVE,
            "tools ran but the turn ended with no answer",
            observations,
        )

    return ProbeOutcome(
        OK,
        f"called {len(tool_events)} tool(s) and answered",
        observations,
    )


def _classify_without_tools(text: str) -> str:
    """`describes` when the reply shows how, `fabricates` when it invents."""
    lowered = text.lower()
    shows_how = any(
        marker in lowered
        for marker in ("test_run_query", "test_dataset_schema", "```", "print(", "=")
    )
    return DESCRIBES if shows_how else FABRICATES


def _offered_tools(messages: list) -> list:
    """Tools offerable in the next round: the report, only once a query worked.

    A model that can file a finding before it has looked at the data will file one
    anyway. Measured on 2026-11-01: llama3.1:8b returned both queries and the report
    in a single batch, so its finding was composed before any result existed, and it
    repeated the invented numbers on the next round with the correct ones in context.

    Withholding the tool rather than rejecting the call is deliberate. A rejection is
    a second failure the model has to recover from, and it would land in the tool-error
    classification — muddying the vocabulary that exists to describe bad arguments.
    Removing the opportunity is cleaner, and it makes the measurement honest: a model
    cannot score well by guessing.

    The cost, accepted knowingly: a model that never queries can never report, so it
    runs to the round limit with no answer and is recorded `inconclusive` — "tools ran
    but the turn ended with no answer". That is the right verdict for a run that never
    produced one.
    """
    if _query_returned_data(messages):
        return list(TOOL_NAMES)
    return [name for name in TOOL_NAMES if name != "test_report_finding"]


def _query_returned_data(messages: list) -> bool:
    """True when a query tool has answered with a result rather than an error."""
    for message in messages:
        if message.get("role") != "tool":
            continue
        try:
            payload = json.loads(message.get("content") or "{}")
        except (json.JSONDecodeError, TypeError):
            continue
        if not isinstance(payload, dict) or "error" in payload:
            continue
        if payload.get("operation") in ("count", "sum", "mean"):
            return True
    return False


def _first_tool_error(messages: list):
    """The first tool error's whole payload, or None.

    `run_tool_loop` returns only `(name, args)` pairs, but it appends each tool's
    result to the message list as a `role: "tool"` entry. That is where an
    executor's `{"error": kind, …}` is visible, so the check reads the transcript
    rather than keeping a second record beside it.

    IT RETURNS THE PAYLOAD, NOT THE KIND. The executor sends more than a code —
    `{"error": "no_numeric_values", "column": "numeric_column"}` — and the earlier
    version kept only `payload["error"]`, so the sentence read "named something that
    does not exist: no_numeric_values": the ERROR CODE printed where the invented
    member's name belonged. The payload is what lets the message name the member
    and the evidence record it.
    """
    for message in messages:
        if message.get("role") != "tool":
            continue
        try:
            payload = json.loads(message.get("content") or "{}")
        except (json.JSONDecodeError, TypeError):
            continue
        if isinstance(payload, dict) and "error" in payload:
            return payload
    return None


def _member_message(error: dict) -> str:
    """The sentence for a member that does not exist, naming the member.

    `unknown_operation` never reaches this: it has a closed set of values, and the
    value is quoted from the attempt rather than from a refused name.
    """
    kind = str(error.get("error"))
    column = error.get("column")
    if kind == "no_numeric_values" and column:
        return (
            f"named {column!r}, which is not a numeric column of this dataset "
            f"(no_numeric_values)"
        )
    if column:
        return f"named {column!r}, which does not exist ({kind})"
    return f"named something that does not exist: {kind}"


# --- the truth check -------------------------------------------------------
#
# The model's answer is a claim, and a claim about data can be checked against the
# data. These helpers do that with no judgement of prose: numbers in the answer are
# compared with numbers the tools returned.

# A number as written in prose: an optional sign, thousands separators, an optional
# fractional part. `$500.00` and `1,000` both arrive here as their digits.
_NUMBER = re.compile(r"-?\d+(?:,\d{3})*(?:\.\d+)?")


def _numbers_written(text: str) -> list:
    """Every number in `text`, as the literal string it was written as."""
    return [m.group(0) for m in _NUMBER.finditer(text or "")]


def _collect_numbers(value, out: set) -> None:
    if isinstance(value, bool):
        return
    if isinstance(value, (int, float)):
        out.add(float(value))
    elif isinstance(value, dict):
        for item in value.values():
            _collect_numbers(item, out)
    elif isinstance(value, list):
        for item in value:
            _collect_numbers(item, out)


def _tool_numbers(messages: list) -> set:
    """Numeric values the tools actually returned.

    ONLY JSON NUMBERS COUNT. The report tool echoes the model's own finding back as
    a string, and reading digits out of that string would let a model certify its own
    invention — it reports "1000 rows", the tool stores and echoes "1000 rows", and
    the check finds 1000 among the tool output. Strings are skipped entirely.
    """
    out: set = set()
    for message in messages:
        if message.get("role") != "tool":
            continue
        try:
            payload = json.loads(message.get("content") or "{}")
        except (json.JSONDecodeError, TypeError):
            continue
        _collect_numbers(payload, out)
    return out


def _is_supported(written: str, tool_values: set) -> bool:
    """True when `written` is a tool value, allowing for rounding.

    `151.93` is a legitimate rendering of 151.9333…; `50.0` is not. The tolerance is
    half a unit in the last place of what was WRITTEN, so a claim's own precision
    decides how much slack it gets — a rounded claim may differ by rounding, and a
    coarse claim is not thereby licensed to say something else.
    """
    try:
        claim = float(written.replace(",", ""))
    except ValueError:
        return True  # not a number after all; nothing to check
    decimals = len(written.split(".")[1]) if "." in written else 0
    tolerance = 0.5 * (10 ** -decimals) + 1e-9
    return any(abs(claim - value) <= tolerance for value in tool_values)


def _unsupported_numbers(text: str, tool_values: set) -> list:
    """Numbers the text asserts that no tool returned, in the order written.

    Deduplicated: the finding and the closing sentence usually make the same claim, so
    a per-occurrence list would report "1000, 50.0, 1000, 50.0" for one invention made
    twice. What matters is which numbers were unsupported, not how often.
    """
    out = []
    for written in _numbers_written(text):
        if written not in out and not _is_supported(written, tool_values):
            out.append(written)
    return out
