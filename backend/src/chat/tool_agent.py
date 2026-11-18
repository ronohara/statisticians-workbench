"""
Generic tool-calling LLM agent.

Shared by the recipe concierge and the virtual-dataset concierge. Holds the
tool registry and the tool-calling loop; each concierge subclasses
:class:`ToolAgent` and supplies its own prompts, session, and state logic.
"""

import datetime
import json
import logging
import time
from decimal import Decimal
from typing import Optional

from src.chat.language import language_instruction
from src.chat.providers import ProviderFactory
from src.routers.common.translations import CHAT
from src.utils.translation import t
from src.utils.timestamps import iso_utc

logger = logging.getLogger("uvicorn.trace")

# Tool registries, one per concierge.
#
# Why per concierge: every concierge registered into ONE shared dict, keyed by
# tool name, at module import. Two concierges declaring the same name therefore
# overwrote each other silently, and the winner depended on import order in
# main.py — `from src.routers import datasets, recipes, ...` meant recipe
# registered second and won. Measured 2026-11-04: `get_scoreboard`, `set_name`
# and `suggest_choices` were declared by BOTH the virtual and the recipe
# concierge, so a virtual-dataset session asking what was left got the RECIPE
# scoreboard back, and `set_name` wrote the recipe's `agent._goal`. The
# allow-list could not catch it: it checks the NAME, and the name was on the
# virtual list — the executor behind it was the other concierge's.
#
# `"common"` is not a fallback and not "the one you get for free". It holds the
# tools DELIBERATELY available to every concierge — today that is only
# `report_unsupported`, the "no tool fits" escape hatch. Every concierge has its
# own registry beside it, and an agent resolves from its own first, then from
# common. Registering a name that common already holds is refused, so a concierge
# cannot shadow a shared tool.
TOOL_REGISTRIES: dict = {"common": {}}

COMMON_REGISTRY = "common"

MAX_TOOL_ROUNDS = 8
LLM_REPEAT_RETRIES = 3


class ToolNameCollision(Exception):
    """Two executors claimed one tool name inside one concierge's registry.

    Raised at import time, which is the point: a duplicate name is a
    programming error, and the failure it used to produce — one concierge
    silently running another's executor — is invisible at run time. Failing
    loudly here costs a start-up and saves a session.
    """


def register_tool(registry: str, name: str, schema: dict, executor) -> None:
    """Register a tool into one concierge's registry.

    `registry` is REQUIRED and comes first, so a registration states which
    concierge owns the tool. There is no default: a default is how the two
    concierges came to share one dict and overwrite each other, and making the
    destination implicit would leave the next concierge free to repeat it.

    Re-registering the same name with the SAME executor is a no-op, so a module
    that registers at import stays safe if it is imported twice. A different
    executor under a name already taken raises: that is the collision.
    """
    reg = TOOL_REGISTRIES.setdefault(registry, {})
    existing = reg.get(name)
    if existing is not None:
        if existing["executor"] is executor:
            return
        raise ToolNameCollision(
            f"tool {name!r} is already registered in registry {registry!r} "
            f"by {existing['executor'].__module__}.{existing['executor'].__qualname__}, "
            f"and {executor.__module__}.{executor.__qualname__} tried to take it. "
            f"Two tools may share a name only across different registries."
        )
    if registry != COMMON_REGISTRY:
        shared = TOOL_REGISTRIES.get(COMMON_REGISTRY) or {}
        if name in shared:
            raise ToolNameCollision(
                f"tool {name!r} is registered in the common registry, which every "
                f"concierge resolves; registry {registry!r} may not shadow it"
            )
    reg[name] = {"schema": schema, "executor": executor}


def tool_error(tool_name: str, exc: BaseException, *, agent=None) -> dict:
    """Log a tool failure with a full traceback and session context, then return
    the model-facing error dict.

    The return value is the clean ``{"error": …}`` the executors used to build
    by hand — ``HTTPException.detail`` for FastAPI errors, the exception message
    otherwise — so the model still sees a clean message. The failure is also
    logged, with a traceback and the session/user, so a tool that errored can be
    diagnosed without reproducing it.
    """
    detail = str(getattr(exc, "detail", exc))
    sid = getattr(agent, "session_id", None)
    uid = getattr(agent, "user_id", None)
    ctx = " ".join(f"{k}={v}" for k, v in (("session", sid), ("user", uid)) if v)
    logger.error(
        f"Tool '{tool_name}' failed{(' ' + ctx) if ctx else ''}: {detail}",
        exc_info=True,
    )
    return {"error": detail}


# The shared "no tool fits" escape hatch, exposed by every concierge. When a
# request has no home in the toolset, the model reports the gap instead of
# hallucinating an operation (the `group_by` failure).
_REPORT_UNSUPPORTED_SCHEMA = {
    "type": "function",
    "function": {
        "name": "report_unsupported",
        "description": (
            "Last resort — use ONLY when the user asks for something no other "
            "tool can do (aggregation, grouping, time-series analysis, etc.). "
            "Say what was asked and why no tool fits, then tell the user "
            "plainly it isn't supported yet and stop. Never invent an operation."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "request": {
                    "type": "string",
                    "description": "What the user asked for and why no tool can do it.",
                },
            },
            "required": ["request"],
        },
    },
}


async def _exec_report_unsupported(agent, request: str = "", **args) -> dict:
    """Log an unsupported request (the product gap) and return a clean result."""
    sid = getattr(agent, "session_id", None)
    uid = getattr(agent, "user_id", None)
    ctx = " ".join(f"{k}={v}" for k, v in (("session", sid), ("user", uid)) if v)
    logger.warning(f"UNSUPPORTED{(' ' + ctx) if ctx else ''}: {request}")
    return {
        "supported": False,
        "message": f"This isn't supported by the Workbench yet: {request}",
    }


register_tool(COMMON_REGISTRY, "report_unsupported", _REPORT_UNSUPPORTED_SCHEMA, _exec_report_unsupported)


def _json_default(obj):
    """Serialize values JSON can't handle natively (asyncpg Decimal, datetimes, sets)."""
    if isinstance(obj, Decimal):
        return float(obj)
    if isinstance(obj, datetime.datetime):
        return iso_utc(obj)
    if isinstance(obj, (set, frozenset)):
        return list(obj)
    return str(obj)


class ToolAgent:
    """Generic LLM agent with a tool-calling loop.

    Subclasses supply their own prompts/state; the LLM call, tool dispatch, and
    tool loop live here and are shared."""

    def __init__(
        self,
        *,
        api_key: Optional[str] = None,
        endpoint: Optional[str] = None,
        model: Optional[str] = None,
        provider: Optional[str] = None,
        language: str = "en",
        timeout: Optional[float] = None,
        connect_timeout: Optional[float] = None,
        registry: str = COMMON_REGISTRY,
    ):
        # LLM config — resolved from the user's AI connection by the caller;
        # there is no environment-variable fallback. The endpoint is passed
        # through unmodified: each provider class appends its own protocol
        # suffix (/api/chat for local Ollama, /chat/completions for the
        # OpenAI-compatible providers).
        self.api_key = api_key or ""
        self.endpoint = endpoint
        self.provider = provider
        self.model = model
        # What the provider actually ran, as opposed to what was requested. Empty
        # until call_llm has made a call; `TOOL_LOOP` reads it so a turn that took a
        # provider default is recorded with the model it really used.
        self.model_used: str = ""
        self.language = language
        # The two budgets for ONE provider call in the loop (plan Item 4a of
        # workbench-AI-timeout-policy-plan.html).
        #
        # They are parameters rather than constants for the reason the class has
        # always needed: this class cannot resolve the workbench defaults itself — it
        # has no pool and no connection id, and the tests construct it bare — and
        # inventing a constant here would be a tier nobody can see. Every caller that
        # has a connection resolves and passes them.
        #
        # None still means "let the provider layer use its own default". That is not a
        # silent fallback: the provider's default is the compiled 10 s connect budget,
        # so a None here leaves a bounded call either way. What it does not do is honour
        # a per-connection setting, which is why every real caller now passes a value.
        self.timeout = timeout
        self.connect_timeout = connect_timeout
        self._allowed_tools: Optional[set] = None
        # Which concierge's tools this agent may see and call. The registry is
        # chosen at construction because that is the only moment the caller knows
        # which concierge it is building; a default keeps every existing caller
        # working unchanged.
        self.registry_name = registry

    def _registry(self) -> dict:
        """This agent's own registry. An unknown name is a wiring error, not an
        empty toolset: falling back to `common` would reintroduce the very
        cross-concierge bleed the split exists to remove."""
        reg = TOOL_REGISTRIES.get(self.registry_name)
        if reg is None:
            raise ToolNameCollision(
                f"no tool registry named {self.registry_name!r}; "
                f"known registries: {sorted(TOOL_REGISTRIES)}"
            )
        return reg

    def _registry_with_common(self) -> dict:
        """The agent's own tools plus the ones deliberately shared by all
        concierges. Own first, so a name can only come from one place —
        register_tool refuses a concierge that shadows a common tool."""
        reg = dict(TOOL_REGISTRIES.get(COMMON_REGISTRY) or {})
        reg.update(self._registry())
        return reg

    async def call_llm(self, system_prompt: str, messages: list, tools: Optional[list] = None) -> dict:
        """Call the LLM and return the assistant message dict
        (``{"role", "content", "tool_calls"?}``)."""
        if not self.provider:
            raise RuntimeError(await t(getattr(self, "db_pool", None), self.language, CHAT["chat.connection_not_found"]))
        system_prompt = language_instruction(self.language) + system_prompt
        payload = [{"role": "system", "content": system_prompt}]
        window = messages[-20:]
        # Drop leading tool messages: their preceding assistant tool_calls
        # message was trimmed away, and the provider rejects an orphaned tool.
        while window and window[0].get("role") == "tool":
            window = window[1:]
        for msg in window:
            entry = {"role": msg.get("role", "user"), "content": msg.get("content", "")}
            if msg.get("tool_calls"):
                entry["tool_calls"] = msg["tool_calls"]
            if msg.get("tool_call_id"):
                entry["tool_call_id"] = msg["tool_call_id"]
            payload.append(entry)

        try:
            provider = ProviderFactory.create(self.provider, self.api_key, self.endpoint)
        except ValueError as e:
            # Unknown provider — shouldn't happen (guarded by self.provider), but
            # report it the same way as any provider failure.
            detail = str(e)
            logger.error(f"LLM error: {detail}")
            raise RuntimeError(f"ai_provider_error:{detail}")

        for attempt in range(1 + LLM_REPEAT_RETRIES):
            try:
                result = await provider.call(
                    messages=payload, model=self.model, tools=tools,
                    # 0.1 is a reliability requirement for tool calling, not a tuning
                    # preference: a tool-calling turn at 0.7 picks the wrong tool far
                    # more often. So the pair's temperature deliberately does NOT
                    # override these two — only the timeout is taken from the caller,
                    # because a hung call is a hung call whatever the sampling.
                    temperature=0.1, max_tokens=8192,
                    **({"timeout": self.timeout} if self.timeout else {}),
                    **({"connect_timeout": self.connect_timeout}
                       if self.connect_timeout else {}),
                )
                # The model the provider actually used. The caller cannot work this
                # out: `model` is None whenever the connection has no stored default,
                # and each provider substitutes its own — so what the agent ASKED for
                # and what ran are different values, and only the provider knows the
                # second. Read here rather than assumed, so `TOOL_LOOP` can name it.
                self.model_used = getattr(provider, "last_model", "") or self.model or ""
                return result
            except ValueError as e:
                # Kept on the failure path too: the expensive turns are the ones that
                # fail, and a record that appears only on success measures the cheap
                # half. The provider resolved its model before it made the request, so
                # `last_model` is populated even when the request then failed.
                self.model_used = getattr(provider, "last_model", "") or self.model or ""
                # The provider layer reports its own failures (missing key/endpoint,
                # an HTTP status, a timeout) as ValueError with a coded detail.
                detail = str(e)
                # A token-repetition loop and a timeout are both transient —
                # retry a few times, then surface a distinct prefix the caller
                # maps to a graceful message.
                if "token repeat limit" in detail or "TIMEOUT" in detail:
                    if attempt < LLM_REPEAT_RETRIES:
                        logger.warning(
                            f"LLM transient failure (attempt {attempt + 1}/{LLM_REPEAT_RETRIES}): {detail}; retrying"
                        )
                        continue
                    if "token repeat limit" in detail:
                        logger.error(f"LLM repeat loop persisted after {LLM_REPEAT_RETRIES} retries: {detail}")
                        raise RuntimeError(f"ai_repeat_loop:{detail}")
                    logger.error(f"LLM timeout persisted after {LLM_REPEAT_RETRIES} retries: {detail}")
                    raise RuntimeError(f"ai_timeout:{detail}")
                logger.error(f"LLM error: {detail}")
                raise RuntimeError(f"ai_provider_error:{detail}")
            except Exception as e:
                self.model_used = getattr(provider, "last_model", "") or self.model or ""
                logger.error(f"LLM request failed: {e}")
                raise RuntimeError(f"LLM request failed: {e}")

    async def execute_tool(self, name: str, args: dict) -> dict:
        """Execute a registered tool, returning a JSON-serialisable result."""
        tool = self._registry_with_common().get(name)
        if tool is None:
            return {"error": f"Unknown tool: {name}"}
        if self._allowed_tools is not None and name not in self._allowed_tools:
            return {"error": f"Tool '{name}' is not available in this conversation"}
        try:
            return await tool["executor"](self, **args)
        except Exception as e:
            return tool_error(name, e, agent=self)

    async def run_tool_loop(self, system_prompt: str, messages: list, tool_names: Optional[list] = None,
                            tools_for_round=None) -> tuple:
        """Run the LLM, executing tool calls and feeding results back until
        the model returns a final text turn.

        ``tool_names`` is an optional allow-list of tool names to expose this
        turn. When omitted, every registered tool is available (backward
        compatible); when provided, only those tools' schemas are passed to the
        LLM and only those tools may execute.

        ``tools_for_round`` makes the offer depend on how far the turn has got.
        It takes the transcript so far and returns the names offerable in the
        next round; returning ``tool_names`` unchanged — or omitting the hook —
        reproduces the static behaviour exactly, which is why the other three
        concierges are unaffected. The `turn` test uses it to withhold
        `test_report_finding` until a query has returned data: a model that can
        answer before it has looked will answer from nothing, and no amount of
        post-hoc checking makes that a good measurement.

        Appends assistant + tool messages to ``messages`` and returns
        ``(final_text, tool_events)`` where ``tool_events`` is a list of
        ``(name, args)`` tuples in execution order — so callers can capture
        tool arguments (e.g. the recipe draft's stages)."""

        def offer(names):
            """Apply one round's allow-list; returns the schemas to send."""
            reg = self._registry_with_common()
            if names is not None:
                allowed = [n for n in names if n in reg]
                self._allowed_tools = set(allowed)
                return [reg[n]["schema"] for n in allowed] or None
            self._allowed_tools = None
            return [t["schema"] for t in reg.values()] or None

        last_text = ""
        tool_events = []
        # ── turn timing (2026-11-03) ──────────────────────────
        #
        # Why this exists: a virtual-dataset turn was measured at 136 s and
        # nobody could say where the time went, because the loop recorded
        # nothing. Three separate explanations were offered for it and all
        # three were wrong or unprovable — the number of provider round trips
        # is the obvious candidate and there was no way to check it.
        #
        # So each provider call and each tool call is timed and ONE line is
        # logged when the loop ends, in both backends, with the same field
        # names. It is a record, not a control: nothing reads it back, no
        # budget changes, and the return value is untouched (aitesting
        # consumes the `(name, args)` pairs, and the HTTP response bodies stay
        # identical, which the parity family compares).
        #
        # `finally` on purpose — the expensive turns are the ones that fail, and
        # a record that only appears on success measures the cheap half.
        started = time.perf_counter()
        llm_ms_total = 0.0
        tool_ms_total = 0.0
        calls: list = []
        rounds = 0
        try:
            for _ in range(MAX_TOOL_ROUNDS):
                names = tool_names if tools_for_round is None else tools_for_round(messages)
                tools = offer(names)
                llm_started = time.perf_counter()
                try:
                    msg = await self.call_llm(system_prompt, messages, tools=tools)
                finally:
                    llm_ms_total += (time.perf_counter() - llm_started) * 1000.0
                    rounds += 1
                messages.append(msg)
                tool_calls = msg.get("tool_calls") or []
                if not tool_calls:
                    return msg.get("content") or "", tool_events
                last_text = msg.get("content") or last_text
                for call in tool_calls:
                    fn = call.get("function", {})
                    name = fn.get("name")
                    # `arguments` is a JSON string from the OpenAI-compatible
                    # providers, and an already-parsed object from Ollama native.
                    # Accept both so the round-trip preserves whichever shape the
                    # provider sent (Ollama rejects a stringified object on return).
                    raw = fn.get("arguments") or {}
                    if isinstance(raw, str):
                        try:
                            args = json.loads(raw)
                        except json.JSONDecodeError:
                            args = {}
                    else:
                        args = raw
                    tool_events.append((name, args))
                    tool_started = time.perf_counter()
                    ok = True
                    try:
                        result = await self.execute_tool(name, args)
                        ok = not (isinstance(result, dict) and result.get("error"))
                    except BaseException:
                        ok = False
                        raise
                    finally:
                        took = (time.perf_counter() - tool_started) * 1000.0
                        tool_ms_total += took
                        calls.append(f"{name}:{took:.0f}:{'ok' if ok else 'err'}")
                    messages.append({
                        "role": "tool",
                        "tool_call_id": call.get("id"),
                        "content": json.dumps(result, ensure_ascii=False, default=_json_default),
                    })
            # Defensive fallback: the model never stopped calling tools.
            return last_text, tool_events
        finally:
            total_ms = (time.perf_counter() - started) * 1000.0
            logger.info(
                "TOOL_LOOP session=%s user=%s model=%s rounds=%d llm_ms=%.0f "
                "tool_ms=%.0f total_ms=%.0f calls=%s",
                getattr(self, "session_id", None) or "-",
                getattr(self, "user_id", None) or "-",
                self.model_used or self.model or "-",
                rounds,
                llm_ms_total,
                tool_ms_total,
                total_ms,
                ",".join(calls) if calls else "none",
            )
