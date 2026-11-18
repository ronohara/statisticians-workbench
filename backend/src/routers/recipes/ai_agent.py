"""
Stateful AI Recipe Agent — Phase 2.2

Session-scoped agent that guides users through building a statistical recipe.
Navigation is driven by a tool-managed scoreboard (what is crystallised and what
is needed next), not by a stage machine; the recipe name is a scoreboard piece
set by the set_name tool, like every other decision.
"""

import json
import re
import logging
from typing import Dict, Optional

from src.chat.tool_agent import ToolAgent
from src.utils.translation import t
from .ai_agent_state import AgentState
from .ai_recipe_tools import (
    RECIPE_REGISTRY,
    _scoreboard_for,
    apply_field_column,
    apply_output_decision,
    apply_technique_decision,
    current_field_value,
    resolve_suggestion_heading,
)
from .constraints import (
    ALGORITHM_DEFS,
    FIELD_DEFS,
    RECIPE_PIECES,
    cap_choices,
    columns_of_type,
)
from src.routers.datasets.crud import list_user_datasets

logger = logging.getLogger("uvicorn.trace")

_GOAL_PATTERN = re.compile(r"\[DECISION:goal=(.+?)\]")


def _strip_goal_markers(text: str) -> str:
    """Strip a stray [DECISION:goal=...] marker so it doesn't leak into the
    chat. The name is set by the set_name tool, never by this marker."""
    return _GOAL_PATTERN.sub("", text).strip()


def _completion_confidence(scoreboard: dict) -> float:
    """Project the scoreboard onto the 0–1 completion_confidence: 1.0 when
    complete, otherwise the fraction of the declared pieces that are decided.

    "Decided" is the scoreboard's own definition and needs no filtering: every
    entry in `crystallised` is decided, valid and complete (constraints.py), so
    its length *is* the count. This used to sum a per-piece `valid` flag instead,
    which made the model's confidence and the user's progress label two different
    fractions of the same draft — the label counted every entry, this counted the
    valid ones, and on a half-filled technique they read 4 of 6 and 3 of 6. One
    list, one count: `len(RECIPE_PIECES)` is the denominator both use.
    """
    if scoreboard["complete"]:
        return 1.0
    decided = len(scoreboard.get("crystallised", []))
    return min(1.0, decided / len(RECIPE_PIECES))


#: How each surface is put to the user, as the prompt states it. The wording is the
#: virtual concierge's, adopted so a model meeting either page is told the same
#: thing about the same word (§3.11). `read` and `offer` have no recipe piece —
#: recorded in constraints.PIECE_SURFACE — but they are listed here so the block is
#: the whole vocabulary rather than the half this concierge happens to use.
SURFACE_INSTRUCTIONS = (
    ("ask", "a closed set — call suggest_choices(piece) first so the options appear as clickable chips, then ask"),
    ("point", "the page already shows the control — name it and say what picking one would settle; do not list options"),
    ("read", "you fetch it with a tool; ask nobody"),
    ("offer", "you propose a computed candidate; the user accepts or ignores it"),
    ("invite", "the user's own words — propose one concrete answer they can accept or replace, never a blank question. For the name piece, call suggest_choices(piece=\"name\", proposal=[\"<the name>\"]) so it arrives as an editable field the user can accept or change"),
)


def _prompt_pending_lines(scoreboard: dict) -> str:
    """The scoreboard's pending and blocked pieces, grouped by surface.

    One line per surface rather than one JSON blob, because the instruction a model
    needs differs per surface and a blob makes it re-derive which is which — the
    same reason the virtual concierge does it this way.

    `blocked` is printed as its own section with what unblocks each piece, because
    the fact a model could not previously know is *why* a piece is not askable. The
    sentence it needs is "technique_fields waits on the technique", and before Item
    16 the piece was simply absent from every list.
    """
    # A complete draft says so. Printing five "none" lines and an empty blocked
    # section leaves the model to infer the state from absences, and the one thing
    # it must do then — save — is the one instruction a wall of "none" buries.
    if scoreboard.get("complete"):
        return (
            "  pending:  none — every piece is decided.\n"
            "  blocked:  none\n"
            "  The draft is COMPLETE: call save_recipe() and give the user the link it "
            "returns. Do not raise a piece that is already decided.\n"
        )

    pending = scoreboard.get("pending") or []
    blocked = scoreboard.get("blocked") or []

    by_surface: Dict[str, list] = {}
    for entry in _prompt_pending(scoreboard):
        by_surface.setdefault(entry.get("surface") or "", []).append(entry.get("piece", ""))

    lines = ["  pending:\n"]
    for name, instruction in SURFACE_INSTRUCTIONS:
        pieces = by_surface.get(name) or []
        lines.append(
            f"    {name + ':':9s} {', '.join(pieces) if pieces else 'none'} — {instruction}\n"
        )

    if blocked:
        described = ", ".join(
            f"{entry.get('piece')} (waits on {entry.get('blocked_by')}: "
            f"{entry.get('unblockedByText') or entry.get('unblocked_by')})"
            for entry in blocked
        )
        lines.append(f"  blocked:  {described} — never ask about these\n")
    else:
        lines.append("  blocked:  none\n")
    return "".join(lines)


def _prompt_pending(scoreboard: dict) -> list:
    """The pending pieces as the PROMPT sees them: sentences, never keys.

    The scoreboard emits a key so it can stay pure, and the boundary resolves it
    into `whatText`. Handing the model `recipes.scoreboard.output.what` invites
    exactly one behaviour — repeating it to the user verbatim — so `what` is
    replaced by the resolved sentence and the key is dropped from this view. The
    response keeps both, which is what lets the page diagnose a missing row.

    A piece with no `whatText` keeps its key rather than disappearing: an
    unresolved piece is a defect to be seen, not one to be hidden by omission.
    """
    return [
        {**{k: v for k, v in entry.items() if k != "whatText"},
         "what": entry.get("whatText") or entry.get("what")}
        for entry in scoreboard.get("pending") or []
    ]


def _derive_suggestion(scoreboard: dict, columns=None):
    """The suggestion chips for a turn, derived deterministically from the
    scoreboard: the first pending technique/output piece, or the first pending
    field piece (a column suggestion). Used when the model lists choices in
    prose without calling suggest_choices — the scoreboard is the source of
    truth either way."""
    for piece in ("technique", "output"):
        for p in scoreboard.get("pending", []):
            if p.get("piece") == piece and (p.get("choices") or []):
                return {"piece": piece, **cap_choices(p["choices"])}
    for piece in ("technique_fields", "output_fields"):
        for p in scoreboard.get("pending", []):
            if p.get("piece") == piece and (p.get("choices") or []):
                field_name = p["choices"][0]
                fdef = FIELD_DEFS.get(field_name)
                if fdef is None:
                    return None
                capped = cap_choices(columns_of_type(columns, fdef.column_type))
                # No columns of the required type is not an offer — it is an
                # empty row. Returning one put a heading over nothing on screen
                # (the page drops empty rows, so it rendered as no row at all)
                # and hid the fact that the schema was unknown: the turn looked
                # as if it had simply forgotten to ask.
                if not capped["choices"]:
                    return None
                return {
                    "piece": piece,
                    "field": field_name,
                    "columnType": fdef.column_type,
                    "multi": fdef.multi,
                    **capped,
                }
    return None


# ── Agent class ────────────────────────────────────────────────

def _name_row_if_pending(scoreboard: dict, suggestion):
    """The naming field, when the name is the thing still open.

    Returns the existing suggestion untouched when there is one. Otherwise, if the
    `name` piece is pending, returns a name row with no proposal — the page renders
    an EDITABLE field from it, empty, so the user can type their own name.

    **This is the guarantee, and it is why it is not model-driven.** Mirroring the
    virtual concierge exactly would mean the field appears only if the model
    remembered to call `suggest_choices(piece="name")`. Measured 2026-11-11: a
    session reached the end of its draft, the model asked "what should this be
    called?" in prose, and the only way to answer was the composer at the bottom of
    the page. The user's requirement is that they must be able to supply or edit a
    name, so the affordance cannot depend on a tool call that is not required to
    happen.

    A proposal, when the model does make one, is what the field opens with — the
    model's suggestion is the opening offer, and the fallback only ensures there is
    always something to accept.
    """
    if suggestion:
        return suggestion
    if any(p.get("piece") == "name" for p in scoreboard.get("pending") or []):
        return {"piece": "name", "choices": [], "withheld": 0}
    return None


class AIChefAgent(ToolAgent):
    """Stateful conversational agent for building statistical recipes."""

    def __init__(
        self,
        db_pool,
        user_id: str,
        *,
        session_id: Optional[str] = None,
        api_key: Optional[str] = None,
        endpoint: Optional[str] = None,
        model: Optional[str] = None,
        provider: Optional[str] = None,
        language: str = "en",
    ):
        super().__init__(
            api_key=api_key, endpoint=endpoint, model=model, provider=provider, language=language,
            registry=RECIPE_REGISTRY,
        )
        self.db_pool = db_pool
        self.user_id = user_id
        self.session_id = session_id

    # ── Persistence ────────────────────────────────────────────

    async def _persist_turn(
        self, session_id: str, messages: list, state: "AgentState",
    ) -> None:
        """Write the conversation and the turn's state keys together.

        Every turn path calls this and nothing else. A path that writes the
        messages alone leaves whatever the model's tools changed in the response
        and out of the database — which reads correctly until the session is
        reloaded, and then shows the change gone with no error anywhere.

        Only the keys this turn owns are written, as a jsonb merge, so a save or
        a rename landing while the turn runs is not undone on the way out:

        - ``goal`` — the name, set by the ``set_name`` tool;
        - ``expertise_level`` — from detection;
        - ``completion_confidence`` — derived from the scoreboard;
        - ``stages`` — the tool-mutated draft.

        ``schemaSnapshot`` is deliberately not written here. This turn does not
        own it — ``create_session`` and ``PATCH /dataset`` capture it when a
        dataset is attached — and writing it here put NULL over the captured
        schema on every turn, which is why schema-change detection never fired.

        The state value is a plain dict, not ``json.dumps(...)``: the pool
        registers a jsonb codec (``main.py``, ``_init_connection``) whose encoder
        is ``json.dumps``, so a pre-serialised string is encoded twice and
        ``state || <jsonb string>`` turns the column into the array
        ``[{}, "{...}"]`` rather than an object.
        """
        async with self.db_pool.acquire() as conn:
            await conn.execute(
                """
                UPDATE "AIRecipeSession"
                SET messages = $1, state = state || $2::jsonb,
                    "updatedAt" = NOW()
                WHERE id = $3
                """,
                messages,
                {
                    "goal": state.goal,
                    "expertise_level": state.expertise_level,
                    "completion_confidence": state.completion_confidence,
                    "stages": state.stages,
                },
                session_id,
            )

    # ── Session lifecycle ──────────────────────────────────────

    async def create_session(
        self, dataset_id: Optional[str] = None
    ) -> str:
        """Create a new AIRecipeSession row and return its id.

        If a dataset_id is provided, captures the initial column schema
        as a snapshot for later change detection."""
        import uuid

        session_id = str(uuid.uuid4())

        # Capture initial schema snapshot
        schema_snapshot = None
        if dataset_id:
            schema = await self._capture_schema(dataset_id)
            if schema:
                schema_snapshot = schema

        async with self.db_pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO "AIRecipeSession"
                    (id, "userId", "datasetId", "schemaSnapshot", "updatedAt")
                VALUES ($1, $2, $3, $4, NOW())
                """,
                session_id, self.user_id, dataset_id, schema_snapshot,
            )
        return session_id

    async def send_message(
        self, session_id: str, user_message: str
    ) -> dict:
        """
        Process a user message and return the AI response with updated state.

        Returns:
            {"response": str, "state": dict, "scoreboard": dict, "schema_changes": list}
        """
        # Load session
        async with self.db_pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT * FROM "AIRecipeSession"
                WHERE id = $1 AND "userId" = $2
                """,
                session_id, self.user_id,
            )
        if not row:
            raise ValueError("Session not found")

        raw_msgs = row["messages"]
        raw_state = row["state"]

        messages = raw_msgs or []
        state = AgentState.model_validate(
            raw_state or {}
        )

        # The goal doubles as the recipe's name; carry it on the agent so the
        # scoreboard (and its "name" piece) reflects the session's goal.
        self._goal = state.goal

        # Check for schema changes
        schema_changes = await self.detect_schema_changes(session_id)

        # Build the system prompt — the scoreboard, not a stage.
        system_prompt = await self._build_system_prompt(
            state, schema_changes, session_id,
            dataset_id=row["datasetId"],
        )

        # Append user message
        messages.append({"role": "user", "content": user_message})

        # Detect expertise from first 2-3 messages if still default
        if state.expertise_level == "novice":
            user_msg_count = sum(1 for m in messages if m["role"] == "user")
            if user_msg_count <= 3:
                detected = self._detect_expertise(user_message)
                state.expertise_level = detected

        # Load the recipe draft onto the agent so the granular set_* tools
        # mutate it in place — state.stages is the same list, so after the loop
        # the mutations are already visible. The tools own the draft; this turn
        # only carries and commits it.
        self._draft = state.stages

        # Reset this turn's dataset suggestions before the tool loop. The recipe
        # page renders the list_datasets candidates as clickable chips, and a
        # stale list from an earlier turn must not leak into this response.
        self._dataset_suggestions = []
        self._suggestion = None

        # Run the LLM with the tool-calling loop.
        response_text, _tool_events = await self.run_tool_loop(system_prompt, messages)

        # The name is set by the set_name tool, which mutates self._goal during
        # the loop — so save_recipe sees it the moment it is recorded, unlike a
        # text marker parsed only after the loop. Read the name back and compute
        # the scoreboard for the (tool-mutated) draft.
        updated_state = state.model_copy(deep=True)
        updated_state.goal = getattr(self, "_goal", None)
        clean_response = _strip_goal_markers(response_text)
        scoreboard = await _scoreboard_for(self, updated_state.stages)
        updated_state.completion_confidence = _completion_confidence(scoreboard)

        # Summarise if conversation grows too large
        messages = self._summarise_if_needed(messages)

        # Attach the chips to the final assistant message so a reloaded session
        # re-renders them from the stored conversation (the chips are derived
        # from this turn's tools, not persisted anywhere else).
        dataset_suggestions = getattr(self, "_dataset_suggestions", []) or []
        suggestion = _name_row_if_pending(
            scoreboard,
            getattr(self, "_suggestion", None) or _derive_suggestion(scoreboard, getattr(self, "_columns", None)),
        )
        # The row's heading, resolved where a pool and a language exist. The row is
        # built in two places, so this asks the piece which heading it carries
        # rather than attaching one at each build site.
        suggestion = await resolve_suggestion_heading(suggestion, self.db_pool, self.language)
        if messages and messages[-1].get("role") == "assistant":
            if dataset_suggestions:
                messages[-1]["dataset_suggestions"] = dataset_suggestions
            if suggestion:
                messages[-1]["suggestion"] = suggestion

        # Persist through the one helper (§3.1). It writes the four keys this
        # turn owns and the conversation together, so a tool the model called
        # during the loop reaches the database rather than only the response.
        await self._persist_turn(session_id, messages, updated_state)

        return {
            "response": clean_response,
            "state": updated_state.model_dump(),
            "scoreboard": scoreboard,
            "schema_changes": schema_changes,
            "dataset_suggestions": dataset_suggestions,
            "suggestion": suggestion,
            "unread": getattr(self, "_unread", []) or [],
        }

    async def handle_dataset_selected(self, session_id: str) -> dict:
        """Acknowledge a newly selected dataset in one short turn.

        The dataset is already attached to the session (PATCH /dataset persists
        the id and schema snapshot); this runs the tool loop so the model
        re-grounds itself and replies, without persisting a synthetic user
        message into the visible history.
        """
        async with self.db_pool.acquire() as conn:
            row = await conn.fetchrow(
                'SELECT * FROM "AIRecipeSession" WHERE id = $1 AND "userId" = $2',
                session_id, self.user_id,
            )
        if not row:
            raise ValueError("Session not found")

        messages = row["messages"] or []
        state = AgentState.model_validate(row["state"] or {})
        dataset_id = row["datasetId"]

        # Load the draft onto the agent so the granular tools (suggest_choices
        # in particular) read the real state, and clear this turn's suggestion.
        self._goal = state.goal
        self._draft = state.stages
        self._suggestion = None

        dataset_name = None
        if dataset_id:
            async with self.db_pool.acquire() as conn:
                drow = await conn.fetchrow(
                    """
                    SELECT name FROM "UserDataset"
                    WHERE id = $1 AND ("userId" = $2 OR ("isShared" = true AND "datasetGroup" IN (
                        SELECT "userGroup" FROM "User" WHERE id = $2
                    )))
                    """,
                    dataset_id, self.user_id
                )
            dataset_name = drow["name"] if drow else None

        schema_changes = await self.detect_schema_changes(session_id)
        system_prompt = await self._build_system_prompt(
            state, schema_changes, session_id, dataset_id=dataset_id,
        )
        system_prompt += (
            "\n\nThe user has just selected a dataset"
            + (f' ("{dataset_name}")' if dataset_name else "")
            + ". It is now selected and linked to this session — do NOT ask the "
            "user to select or pick a dataset. Immediately call the "
            "get_dataset_schema tool (with the dataset id above) and report its "
            "columns back to the user, then ask what analysis they'd like and "
            "call suggest_choices('technique') so the choices appear as "
            "clickable chips. Keep the reply short."
        )

        # Run the loop against a working copy so the synthetic trigger is not
        # written into the visible message history.
        working = list(messages)
        working.append({"role": "user", "content": "A dataset was just selected from the dropdown."})
        response_text, _tool_events = await self.run_tool_loop(
            system_prompt, working,
        )

        clean_response = _strip_goal_markers(response_text)

        # Derive the suggestion chips (the model's explicit suggest_choices call,
        # or the scoreboard's first pending technique/output piece) and attach it
        # to the message so a reloaded session re-renders the chips.
        scoreboard = await _scoreboard_for(self, self._draft)
        suggestion = _name_row_if_pending(
            scoreboard,
            getattr(self, "_suggestion", None) or _derive_suggestion(scoreboard, getattr(self, "_columns", None)),
        )
        # The row's heading, resolved where a pool and a language exist. The row is
        # built in two places, so this asks the piece which heading it carries
        # rather than attaching one at each build site.
        suggestion = await resolve_suggestion_heading(suggestion, self.db_pool, self.language)
        assistant_msg = {"role": "assistant", "content": clean_response}
        if suggestion:
            assistant_msg["suggestion"] = suggestion
        messages.append(assistant_msg)

        # Persist through the one helper (§3.1). The draft goes back on the state
        # because the tools this turn ran may have changed it — and the returned
        # state is the same object, so the response and the row cannot disagree.
        updated_state = state.model_copy(deep=True)
        updated_state.stages = self._draft
        await self._persist_turn(session_id, messages, updated_state)

        return {
            "response": clean_response,
            "state": updated_state.model_dump(),
            "schema_changes": schema_changes,
            "suggestion": suggestion,
            "unread": getattr(self, "_unread", []) or [],
        }

    async def handle_decision(self, session_id: str, piece: str, value: str) -> dict:
        """Apply a decision the user made by clicking a suggestion chip, then re-ground.

        Mirrors the dataset flow (a direct apply path that bypasses the model): the
        decision is written into the draft with the same mutation the
        set_technique / set_visualisation tools perform, persisted, and then the
        model runs one short turn acknowledging it and asking for the next
        pending piece.
        """
        async with self.db_pool.acquire() as conn:
            row = await conn.fetchrow(
                'SELECT * FROM "AIRecipeSession" WHERE id = $1 AND "userId" = $2',
                session_id, self.user_id,
            )
        if not row:
            raise ValueError("Session not found")

        messages = row["messages"] or []
        state = AgentState.model_validate(row["state"] or {})
        draft = state.stages or []
        self._goal = state.goal
        self._draft = draft
        self._suggestion = None

        # The same mutation the granular tools perform, applied to the loaded draft.
        if piece == "technique":
            apply_technique_decision(draft, value)
        elif piece == "output":
            apply_output_decision(draft, value)
        elif piece == "name":
            # The name is the draft's goal, held on the state rather than inside a
            # stage — the same place set_name writes it, so a clicked name and a
            # typed one cannot land in two different fields.
            self._goal = value.strip()
            state.goal = self._goal
        else:
            raise ValueError(f"Unknown decision piece: {piece}")

        # Persist the mutated draft before re-grounding, so the scoreboard the
        # prompt embeds already reflects the applied decision.
        #
        # A name decision changes `goal`, not a stage, so the stages-only write left
        # it in memory — and a model call that failed afterwards (measured
        # 2026-11-11, a 502 on a session with no AI connection) discarded the name
        # the user had just accepted. The write carries every key this decision
        # owns, not just the one most decisions touch.
        applied_state = {"stages": draft}
        if piece == "name":
            applied_state["goal"] = self._goal
        async with self.db_pool.acquire() as conn:
            await conn.execute(
                'UPDATE "AIRecipeSession" SET state = state || $1::jsonb, "updatedAt" = NOW() '
                'WHERE id = $2 AND "userId" = $3',
                applied_state, session_id, self.user_id,
            )

        dataset_id = row["datasetId"]
        schema_changes = await self.detect_schema_changes(session_id)
        system_prompt = await self._build_system_prompt(
            state, schema_changes, session_id, dataset_id=dataset_id,
        )
        tool_name = {
            "technique": "set_technique",
            "output": "set_visualisation",
            "name": "set_name",
        }[piece]
        system_prompt += (
            f"\n\nThe user has just chosen \"{value}\" for the {piece} (they clicked a "
            "suggestion instead of typing it). It is already recorded in the draft — do "
            f"NOT call {tool_name}. Acknowledge briefly, then ask for the next needed "
            "piece shown in the scoreboard. Keep the reply short."
        )

        working = list(messages)
        working.append({
            "role": "user",
            "content": f"A {piece} choice was just selected: {value}.",
        })
        response_text, _tool_events = await self.run_tool_loop(
            system_prompt, working,
        )

        clean_response = _strip_goal_markers(response_text)

        scoreboard = await _scoreboard_for(self, draft)
        suggestion = _name_row_if_pending(
            scoreboard,
            getattr(self, "_suggestion", None) or _derive_suggestion(scoreboard, getattr(self, "_columns", None)),
        )
        # The row's heading, resolved where a pool and a language exist. The row is
        # built in two places, so this asks the piece which heading it carries
        # rather than attaching one at each build site.
        suggestion = await resolve_suggestion_heading(suggestion, self.db_pool, self.language)
        assistant_msg = {"role": "assistant", "content": clean_response}
        if suggestion:
            assistant_msg["suggestion"] = suggestion
        messages.append(assistant_msg)

        # Persist through the one helper (§3.1). The pre-loop write above still
        # stands — it is what makes the click visible to the model's prompt — but
        # anything a tool changed during the loop reaches the database only here.
        updated_state = state.model_copy(deep=True)
        updated_state.stages = draft
        await self._persist_turn(session_id, messages, updated_state)

        return {
            "response": clean_response,
            "state": updated_state.model_dump(),
            "scoreboard": scoreboard,
            "schema_changes": schema_changes,
            "suggestion": suggestion,
            "unread": getattr(self, "_unread", []) or [],
        }

    async def handle_proposal(self, session_id: str, fields: list) -> dict:
        """Apply a proposal the user accepted by clicking its chip, then re-ground.

        **Only the fields still undecided are applied.** A proposal is a snapshot
        of the draft at the moment the model offered it, and the user may have
        changed one of those fields since — by typing, or by clicking a different
        chip. Replaying the snapshot over that choice would undo a decision the
        user made deliberately, and the chip's label ("Go with that") gives no
        hint that it is about to do so. A field already holding a value is kept,
        and named in `skipped` so the acknowledgement can say what was kept.

        This is the same mutation the `/field-column` route performs, applied once
        per field, so a proposal and a column chip cannot disagree about what it
        means to record a column.
        """
        async with self.db_pool.acquire() as conn:
            row = await conn.fetchrow(
                'SELECT * FROM "AIRecipeSession" WHERE id = $1 AND "userId" = $2',
                session_id, self.user_id,
            )
        if not row:
            raise ValueError("Session not found")

        messages = row["messages"] or []
        state = AgentState.model_validate(row["state"] or {})
        draft = state.stages or []
        self._goal = state.goal
        self._draft = draft
        self._suggestion = None

        applied: list = []
        skipped: list = []
        for entry in fields or []:
            if not isinstance(entry, dict):
                continue
            piece = entry.get("piece")
            field = entry.get("field")
            column = entry.get("column")
            if piece == "technique_fields":
                stage_type = "statistics"
            elif piece == "output_fields":
                stage_type = "visualisation"
            else:
                continue
            fdef = FIELD_DEFS.get(field) if field else None
            if fdef is None or not column:
                continue
            existing = current_field_value(draft, stage_type, field, fdef.multi)
            if existing:
                skipped.append({"field": field, "column": column, "kept": existing})
                continue
            apply_field_column(draft, stage_type, field, column, fdef.multi)
            applied.append({"field": field, "column": column})

        # Persist before re-grounding, so the scoreboard the prompt embeds already
        # reflects the applied fields — the same ordering /decision uses.
        async with self.db_pool.acquire() as conn:
            await conn.execute(
                'UPDATE "AIRecipeSession" SET state = state || $1::jsonb, "updatedAt" = NOW() '
                'WHERE id = $2 AND "userId" = $3',
                {"stages": draft}, session_id, self.user_id,
            )

        dataset_id = row["datasetId"]
        schema_changes = await self.detect_schema_changes(session_id)
        system_prompt = await self._build_system_prompt(
            state, schema_changes, session_id, dataset_id=dataset_id,
        )
        applied_text = ", ".join(f"{a['field']} = {a['column']}" for a in applied) or "none"
        skipped_text = ", ".join(
            (f"{s['field']} (kept {s['kept']})" if not isinstance(s["kept"], list)
             else f"{s['field']} (kept {', '.join(s['kept'])})")
            for s in skipped
        ) or "none"
        system_prompt += (
            "\n\nThe user accepted a proposal you made, by clicking its chip. It is "
            f"already recorded in the draft. Applied: {applied_text}. "
            f"Kept as they were, because the user had already chosen them: {skipped_text}. "
            "Do NOT call set_technique_fields or set_visualisation_fields. "
            "Acknowledge briefly, mention anything you kept, then ask for the next "
            "needed piece shown in the scoreboard. Keep the reply short."
        )

        working = list(messages)
        working.append({"role": "user", "content": "I accepted your proposal."})
        response_text, _tool_events = await self.run_tool_loop(system_prompt, working)

        clean_response = _strip_goal_markers(response_text)

        scoreboard = await _scoreboard_for(self, draft)
        suggestion = _name_row_if_pending(
            scoreboard,
            getattr(self, "_suggestion", None) or _derive_suggestion(
                scoreboard, getattr(self, "_columns", None)
            ),
        )
        suggestion = await resolve_suggestion_heading(suggestion, self.db_pool, self.language)
        assistant_msg = {"role": "assistant", "content": clean_response}
        if suggestion:
            assistant_msg["suggestion"] = suggestion
        messages.append(assistant_msg)

        updated_state = state.model_copy(deep=True)
        updated_state.stages = draft
        await self._persist_turn(session_id, messages, updated_state)

        return {
            "response": clean_response,
            "state": updated_state.model_dump(),
            "scoreboard": scoreboard,
            "schema_changes": schema_changes,
            "suggestion": suggestion,
            "applied": applied,
            "skipped": skipped,
            "unread": getattr(self, "_unread", []) or [],
        }

    async def handle_field_column(
        self, session_id: str, piece: str, field: str, column: str = None, action: str = "commit",
    ) -> dict:
        """Handle a column decision.

        - "commit" (single field): apply the column, persist, re-ground.
        - "toggle" (multi field): toggle the column, persist, no re-ground.
        - "done" (multi field): re-ground only — the columns are already persisted.
        """
        async with self.db_pool.acquire() as conn:
            row = await conn.fetchrow(
                'SELECT * FROM "AIRecipeSession" WHERE id = $1 AND "userId" = $2',
                session_id, self.user_id,
            )
        if not row:
            raise ValueError("Session not found")

        messages = row["messages"] or []
        state = AgentState.model_validate(row["state"] or {})
        draft = state.stages or []
        self._goal = state.goal
        self._draft = draft
        self._suggestion = None

        fdef = FIELD_DEFS.get(field)
        if fdef is None:
            raise ValueError(f"Unknown field: {field}")
        stage_type = "statistics" if piece == "technique_fields" else "visualisation"

        # Apply the mutation (commit/toggle) and persist before any re-ground.
        if action in ("commit", "toggle") and column:
            apply_field_column(draft, stage_type, field, column, fdef.multi)
            async with self.db_pool.acquire() as conn:
                await conn.execute(
                    'UPDATE "AIRecipeSession" SET state = state || $1::jsonb, "updatedAt" = NOW() '
                    'WHERE id = $2 AND "userId" = $3',
                    {"stages": draft}, session_id, self.user_id,
                )

        if action == "toggle":
            # Persist-only: no re-ground, no new message — the column click is
            # silent so the multi-select chips stay open until Done.
            updated_state = state.model_copy(deep=True)
            updated_state.stages = draft
            scoreboard = await _scoreboard_for(self, draft)
            return {
                "success": True,
                "state": updated_state.model_dump(),
                "scoreboard": scoreboard,
                "unread": getattr(self, "_unread", []) or [],
            }

        # Re-ground (commit or done).
        dataset_id = row["datasetId"]
        schema_changes = await self.detect_schema_changes(session_id)
        system_prompt = await self._build_system_prompt(
            state, schema_changes, session_id, dataset_id=dataset_id,
        )
        if action == "done":
            system_prompt += (
                f"\n\nThe user has finished choosing the columns for the {field} field "
                "(they clicked Done). The choice is already recorded in the draft. "
                "Acknowledge briefly, then ask for the next needed piece shown in the "
                "scoreboard. Keep the reply short."
            )
            trigger = f"Column selection finished for {field}."
        else:
            system_prompt += (
                f"\n\nThe user has just chosen the column \"{column}\" for the {field} field "
                "(they clicked a suggestion instead of typing it). It is already "
                "recorded in the draft. Acknowledge briefly, then ask for the next "
                "needed piece shown in the scoreboard. Keep the reply short."
            )
            trigger = f"Column selected: {field} = {column}."

        working = list(messages)
        working.append({"role": "user", "content": trigger})
        response_text, _tool_events = await self.run_tool_loop(
            system_prompt, working,
        )

        clean_response = _strip_goal_markers(response_text)

        scoreboard = await _scoreboard_for(self, draft)
        suggestion = _name_row_if_pending(
            scoreboard,
            getattr(self, "_suggestion", None) or _derive_suggestion(scoreboard, getattr(self, "_columns", None)),
        )
        # The row's heading, resolved where a pool and a language exist. The row is
        # built in two places, so this asks the piece which heading it carries
        # rather than attaching one at each build site.
        suggestion = await resolve_suggestion_heading(suggestion, self.db_pool, self.language)
        assistant_msg = {"role": "assistant", "content": clean_response}
        if suggestion:
            assistant_msg["suggestion"] = suggestion
        messages.append(assistant_msg)

        # Persist through the one helper (§3.1). As in handle_decision, the
        # pre-loop write stays; this call is what carries anything the tool loop
        # changed, and it is the only write that carries the conversation.
        updated_state = state.model_copy(deep=True)
        updated_state.stages = draft
        await self._persist_turn(session_id, messages, updated_state)

        return {
            "response": clean_response,
            "state": updated_state.model_dump(),
            "scoreboard": scoreboard,
            "schema_changes": schema_changes,
            "suggestion": suggestion,
            "unread": getattr(self, "_unread", []) or [],
        }

    async def handle_recipe_loaded(self, session_id: str) -> dict:
        """Acknowledge a session cloned from a saved recipe, in one short turn.

        The clone already carries the recipe's stages as its draft
        (POST /sessions/from-recipe), so there is nothing to build — and nothing
        to read either, because a cloned session has no conversation of its own.
        This runs the tool loop so the model says what the recipe does and offers
        to change it, which is also what fills the otherwise empty chat, without
        persisting a synthetic user message into the visible history.
        """
        async with self.db_pool.acquire() as conn:
            row = await conn.fetchrow(
                'SELECT * FROM "AIRecipeSession" WHERE id = $1 AND "userId" = $2',
                session_id, self.user_id,
            )
        if not row:
            raise ValueError("Session not found")

        messages = row["messages"] or []
        state = AgentState.model_validate(row["state"] or {})
        dataset_id = row["datasetId"]
        # The draft goes onto the agent before the loop, as it does on every
        # other turn path: the granular tools read it through _draft_of, which
        # creates an EMPTY list when the attribute is absent. Persisting after a
        # loop that saw no draft would then write [] over the stages the clone
        # copied in — the same lost write this path is being fixed for, with a
        # worse outcome.
        self._draft = state.stages
        self._suggestion = None
        # displayName is written to the row by SQL — the rename endpoint, and the
        # clone that copied the recipe's name in — not modelled on AgentState, so
        # it is read from the raw state.
        recipe_name = (row["state"] or {}).get("displayName")

        dataset_name = None
        if dataset_id:
            async with self.db_pool.acquire() as conn:
                drow = await conn.fetchrow(
                    """
                    SELECT name FROM "UserDataset"
                    WHERE id = $1 AND ("userId" = $2 OR ("isShared" = true AND "datasetGroup" IN (
                        SELECT "userGroup" FROM "User" WHERE id = $2
                    )))
                    """,
                    dataset_id, self.user_id
                )
            dataset_name = drow["name"] if drow else None

        schema_changes = await self.detect_schema_changes(session_id)
        system_prompt = await self._build_system_prompt(
            state, schema_changes, session_id, dataset_id=dataset_id,
        )
        system_prompt += (
            "\n\nThis session was just created by cloning an existing recipe"
            + (f' ("{recipe_name}")' if recipe_name else "")
            + (f' on the dataset "{dataset_name}"' if dataset_name else "")
            + ". Its stages are already the draft, and the user has not asked for "
            "anything yet. Summarise what the recipe does in plain terms — name "
            "the dataset and the stages — and ask whether they want to change "
            "anything. Do not re-ask the goal-setting questions."
        )

        # Run the loop against a working copy so the synthetic trigger is not
        # written into the visible message history.
        working = list(messages)
        working.append({
            "role": "user",
            "content": "An existing recipe was just loaded into this session.",
        })
        response_text, _tool_events = await self.run_tool_loop(
            system_prompt, working,
        )

        clean_response = _strip_goal_markers(response_text)
        messages.append({"role": "assistant", "content": clean_response})

        # Loading a recipe is not an answer to a question — do not advance the
        # stage or re-extract decision state. But the tools may still have run,
        # so the draft is persisted through the one helper (§3.1) along with the
        # conversation, and the returned state is the same object that was
        # written, so the response and the row cannot disagree.
        updated_state = state.model_copy(deep=True)
        updated_state.stages = self._draft
        await self._persist_turn(session_id, messages, updated_state)

        return {
            "response": clean_response,
            "state": updated_state.model_dump(),
            "schema_changes": schema_changes,
        }

    # ── User context ─────────────────────────────────────────

    async def _fetch_user_context(self) -> dict:
        """Fetch datasets and database connections available to the user."""
        datasets = []
        db_connections = []
        try:
            datasets = await list_user_datasets(self.db_pool, self.user_id)

            async with self.db_pool.acquire() as conn:
                db_rows = await conn.fetch(
                    """
                    SELECT "connectionId", name, type, host, port, database
                    FROM "UserDatabaseConnection"
                    WHERE "userId" = $1
                    LIMIT 10
                    """,
                    self.user_id,
                )
                db_connections = [
                    {
                        "name": r["name"] or f"{r['type']} ({r['host']})",
                        "type": r["type"],
                        "database": r["database"],
                    }
                    for r in db_rows
                ]
        except Exception as e:
            logger.warning(f"Failed to fetch user context: {e}")

        return {"datasets": datasets, "db_connections": db_connections}

    # ── System prompt ───────────────────────────────────────────

    async def _build_system_prompt(
        self, state: AgentState, schema_changes: list,
        session_id: str = "", dataset_id: Optional[str] = None,
    ) -> str:
        """Build the system prompt: the scoreboard (what is crystallised and
        what is needed next) plus the tool and formatting rules. One prompt —
        no stage machine."""

        # Fetch user context for data-aware prompts
        ctx = await self._fetch_user_context()
        datasets = ctx["datasets"]
        db_connections = ctx["db_connections"]
        dataset_count = len(datasets)
        db_conn_count = len(db_connections)

        # Build a concise dataset summary for the prompt — a count only; the
        # model resolves names by calling the list_datasets tool, never from a
        # list baked into the prompt.
        if dataset_count > 0:
            dataset_summary = f"The user has {dataset_count} dataset(s) available."
        else:
            dataset_summary = "The user has NO datasets yet."

        if db_conn_count > 0:
            conn_list = [f"{c['name']} ({c['type']})" for c in db_connections[:5]]
            dataset_summary += (
                f" They also have {db_conn_count} database connection(s): {', '.join(conn_list)}"
                f"{' and more' if db_conn_count > 5 else ''}. "
                "These connections may contain tables not yet imported as datasets — "
                "encourage the user to browse them via "
                "[Virtual Datasets](/datasets/virtual?returnTo=ai-recipe-{sessionId}) "
                "if they want to explore those tables."
            )

        if dataset_id is None:
            dataset_summary += (
                " No dataset is linked to this session yet — encourage them to "
                "select or create one."
            )

        technique_parts = []
        for key, defn in ALGORITHM_DEFS.items():
            label = await t(self.db_pool, self.language, defn.label)
            technique_parts.append(f"{key} ({label})")
        technique_list = ", ".join(technique_parts)

        is_expert = state.expertise_level in ("expert", "intermediate")
        mode = "technical (concise, assume knowledge)" if is_expert else "educational (explain from first principles)"

        # Deep-link targets for the prose: only the ones whose ids are known.
        # A link to a recipe that has not been saved, or to a dataset that is not
        # selected, is a dead link the model would faithfully reproduce — the
        # template it used to be handed carried an unfilled {recipeId} straight
        # into the reply. The URLs themselves come from _generate_deep_link, so
        # their shape lives in one place rather than in the prompt as well.
        targets = []
        if session_id:
            targets = [
                ("Virtual Datasets", "go to Virtual Datasets", "virtual", {}),
                ("Upload Data", "upload your data", "upload", {}),
            ]
            if dataset_id:
                targets.append(
                    ("Transforms", "create a transform", "transforms",
                     {"datasetId": dataset_id})
                )
            if state.saved_recipe_id:
                targets.append(
                    ("Recipe Editor", "open in editor", "recipe",
                     {"recipeId": state.saved_recipe_id})
                )
        target_lines = "".join(
            f"  {label}: [{text}]({self._generate_deep_link(page, session_id, **kwargs)})\n"
            for label, text, page, kwargs in targets
        )

        # The scoreboard — the deterministic view over the current draft.
        scoreboard = await _scoreboard_for(self, state.stages)

        base = (
            "You are a statistical analysis concierge for Statisticians Workbench. "
            "Your job is to help the user design an analysis recipe through "
            "conversation — one decision at a time.\n\n"
            + dataset_summary + "\n\n"
            f"The user's expertise level is {state.expertise_level}. "
            f"Use {mode} response style.\n\n"
            "Available techniques: " + technique_list + "\n\n"
            "CURRENT SCOREBOARD:\n"
            f"  crystallised: {json.dumps(scoreboard['crystallised'], ensure_ascii=False)}\n"
            + _prompt_pending_lines(scoreboard)
            + f"  errors: {json.dumps(scoreboard['errors'], ensure_ascii=False)}\n"
            f"  warnings: {json.dumps(scoreboard['warnings'], ensure_ascii=False)}\n\n"
            "Use the scoreboard to decide what to do this turn:\n"
            "  - Decisions can be made in ANY order. Raise ONE pending piece, in the "
            "manner its surface gives (below), then record the choice with the "
            "matching set_* tool.\n"
            "  - Never ask about a piece under 'blocked'. It cannot be decided yet; say "
            "in one line what would unblock it, and move on to a pending piece. Asking "
            "a question the user cannot answer costs a turn and teaches them nothing.\n"
            "  - If a crystallised piece is invalid, or there are 'errors', fix them "
            "(errors block saving). 'warnings' should also be fixed.\n"
            "  - If there are no 'pending' pieces and no errors, the draft is "
            "complete — call save_recipe() (the name is the one you recorded "
            "with set_name) and give the user the recipe link it returns.\n"
            "  - Do NOT re-litigate a crystallised piece that is valid — change it "
            "only if the user asks.\n"
        )

        # Columns come from the get_dataset_schema tool when a dataset is linked.
        if dataset_id:
            base += (
                "\nA dataset IS selected and linked to this session (id "
                f"{dataset_id}). Never ask the user to select a dataset. Call "
                "the get_dataset_schema tool to see its columns (name, "
                "is_numeric, is_categorical).\n"
            )
        elif dataset_count > 0:
            base += (
                "\nNO DATASET SELECTED: The session has no dataset attached, so you "
                "cannot see column details. The user can select one from the dataset "
                "dropdown above the chat, OR you can resolve one yourself with the "
                "list_datasets tool. When the user names data in words (e.g. \"find "
                "me my bike sales data\"), call list_datasets(search=...) with their "
                "words; if it returns an exact match, record it with set_dataset. If "
                "it returns only partial matches, offer the top candidates and ask "
                "which one they mean. If it returns nothing, say so plainly and point "
                "them at the Virtual Datasets page. Never invent a dataset name and "
                "never force a match.\n"
            )

        if schema_changes:
            base += f"\n⚠ SCHEMA CHANGES DETECTED: {'; '.join(schema_changes)}\n"

        base += (
            "\nRECIPE DRAFT (built with the tools, never typed by you)\n"
            "The draft is a list of stages the tools maintain. Record each "
            "decision with the matching set_* tool; every tool returns the "
            "refreshed scoreboard, so check it after each call. Column names come "
            "from get_dataset_schema(); algorithm/output keys and their required "
            "fields come from get_recipe_model().\n\n"
            "TOOLS\n"
            "  list_datasets(search) — list the user's datasets, optionally filtered by a name substring.\n"
            "  suggest_choices(piece) — offer the valid technique/output choices as clickable chips.\n"
            "  suggest_choices(piece, field) — for 'technique_fields' / 'output_fields', the column chips for one field.\n"
            "  offer_proposal(label, fields) — put a complete set of column choices on screen as ONE chip the user clicks to accept.\n"
            "  suggest_choices('name', proposal=[\"<the name>\"]) — offer a name as one editable field the user accepts or edits.\n"
            "  set_dataset(dataset_id) — record the dataset.\n"
            "  set_technique(algorithm_type) — record the analysis method (clears its columns).\n"
            "  set_technique_fields(fields) — record the method's required columns.\n"
            "  set_visualisation(output_type) — record the chart/output (clears its columns).\n"
            "  set_visualisation_fields(fields) — record the output's columns.\n"
            "  set_transforms(transform_ids) — record the transforms to apply (optional).\n"
            "  set_name(name) — record the recipe's name (ask the user first).\n"
            "  get_scoreboard() — re-read the scoreboard without changing anything.\n"
            "  get_recipe_model() — the algorithms, their required fields, and output types.\n"
            "  get_dataset_schema(dataset_id) — the dataset's columns.\n"
            "  save_recipe() — validate and save the current draft (errors block, warnings don't).\n"
            "  get_dataset_transforms(dataset_id) — list the transforms available.\n"
            "  get_transform(dataset_id, transform_id) — one transform.\n"
            "  create_transform / update_transform / delete_transform — manage transforms.\n\n"
            "NAMING A CHIP: suggest_choices returns `choices` (everything valid) and "
            "`shown` (what the chip row is currently rendering — it caps at six). If "
            "you tell the user to click a chip, name one from `shown`. If your "
            "recommendation is in the withheld set, either call offer_proposal with "
            "it, or say the list has more options and they can expand it — never "
            "name a chip that is not on screen. Measured 2026-11-11: a reply said "
            "'click Linear Regression', which was seventh of eight algorithms with "
            "the cap at six, and the user had no chip to click.\n\n"
            "OFFERING A PROPOSAL: if your reply names the specific columns you "
            "recommend for a field — even as a suggestion inside a sentence — you MUST "
            "call offer_proposal(label, fields) in the same turn, with those exact "
            "columns. A recommendation with no chip is a recommendation the user "
            "cannot accept: measured 2026-11-11, a reply said 'I have put it on screen "
            "as one chip: click it to record' after calling suggest_choices, which "
            "offers a row of individual columns and no way to accept the set. Do not "
            "describe an affordance you have not created. The chip is the acceptance "
            "path; a sentence asking the user to type 'go with that' is not. Write the "
            "label in the language the user writes in.\n\n"
            "TRANSFORMS VS ANALYSIS: transforms (create/update/delete_transform and "
            "their operations) are for CLEANING only — row-level preparation. A "
            "question about trends, comparisons, or relationships is an ANALYSIS: "
            "record it with set_technique (get_recipe_model to pick the right key), "
            "never by creating transforms to aggregate or group data.\n\n"
            "ANALYSIS VS OUTPUT: if the user asks for a chart or visualisation (a "
            "pie chart, bar chart, scatter plot, line chart, table, etc.), that is "
            "the OUTPUT piece, not the analysis — IMMEDIATELY record it with "
            "set_visualisation (get_recipe_model to pick the right key, e.g. 'pie', "
            "'bar', 'scatter'), then ask for the remaining pieces. Do NOT just "
            "acknowledge the chart in words — call the tool so the choice is "
            "stored.\n\n"
            "ERROR HANDLING: if a tool returns an error, state plainly what failed "
            "and switch approach — never repeat the same plan, and never ask the "
            "user to re-select or re-do something already done.\n\n"
            "UNSUPPORTED: if the user asks for something none of your tools can do "
            "(aggregation, grouping, time-series, or anything not covered), call "
            "report_unsupported with a short description, then tell the user "
            "plainly it isn't supported yet and stop — never invent an operation.\n\n"
            "FORMATTING: Use GitHub-style markdown — render tabular data as markdown "
            "tables (| col | col |), use **bold** for emphasis, and markdown links "
            "([text](url)) for URLs. Do not wrap your whole reply in a code block.\n\n"
            "When you recommend the user visit another tool, use a markdown link with the "
            "returnTo parameter so they can come back. Available targets:\n"
            + target_lines + "\n"
            "After save_recipe succeeds, give the user the recipe link that call returns, "
            "as a markdown link, in that same reply.\n"
        )

        prompt = base
        if session_id:
            prompt = prompt.replace("{sessionId}", session_id)
        prompt = prompt.replace("{datasetId}", dataset_id or "")
        return prompt

    # ── Expertise detection ─────────────────────────────────────

    _TECHNICAL_TERMS = [
        "p-value", "p value", "r²", "r-squared", "heteroscedasticity",
        "multicollinearity", "residual", "confidence interval", "anova",
        "regression coefficient", "effect size", "null hypothesis",
        "type i error", "type ii error", "statistical power", "covariate",
        "normality", "homogeneity of variance", "post hoc", "bonferroni",
        "tukey", "mann-whitney", "kruskal-wallis", "wilcoxon",
        "logistic regression", "poisson", "mixed effects", "bayesian",
    ]

    _BASIC_TERMS = [
        "average", "compare", "which is bigger", "difference",
        "relationship", "trend", "pattern", "summary", "describe",
        "show me", "what is", "how many", "count", "breakdown",
    ]

    def _detect_expertise(self, user_message: str) -> str:
        """Analyse a user message for statistical vocabulary level.

        Returns one of: 'expert', 'intermediate', 'novice'."""
        msg_lower = user_message.lower()

        tech_hits = sum(1 for t in self._TECHNICAL_TERMS if t in msg_lower)
        basic_hits = sum(1 for t in self._BASIC_TERMS if t in msg_lower)

        if tech_hits >= 2:
            return "expert"
        if tech_hits >= 1 and basic_hits >= 1:
            return "intermediate"
        return "novice"

    # ── Deep-link generation (Phase 6.1) ─────────────────────────

    _DEEP_LINK_TARGETS = {
        "virtual": "/datasets/virtual",
        "upload": "/datasets/upload",
        "clean": "/datasets/clean",
        "transforms": "/datasets/{datasetId}/transforms",
        "recipe": "/recipes/{recipeId}",
    }

    def _generate_deep_link(self, page: str, session_id: str, **kwargs) -> str:
        """Generate a deep link with return context.

        Args:
            page: Target page key (virtual, upload, clean, transforms, recipe)
            session_id: The AI session to return to
            **kwargs: Template variables (datasetId, recipeId)

        Returns:
            Full relative URL with ?returnTo=ai-recipe-{sessionId}
        """
        template = self._DEEP_LINK_TARGETS.get(page, "/")
        url = template.format(sessionId=session_id, **kwargs)
        separator = "&" if "?" in url else "?"
        return f"{url}{separator}returnTo=ai-recipe-{session_id}"

    # ── Schema change detection ─────────────────────────────────

    async def detect_schema_changes(self, session_id: str) -> list:
        """Compare current dataset schema against stored snapshot."""
        async with self.db_pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT "schemaSnapshot", "datasetId"
                FROM "AIRecipeSession"
                WHERE id = $1
                """,
                session_id,
            )
        if not row or not row["datasetId"] or not row["schemaSnapshot"]:
            return []

        stored = row["schemaSnapshot"]

        dataset_id = row["datasetId"]
        current = await self._capture_schema(dataset_id)
        if not current:
            return []

        changes = []
        stored_by_name = {c["column_name"]: c for c in stored}
        current_by_name = {c["column_name"]: c for c in current}

        for name, col in current_by_name.items():
            if name not in stored_by_name:
                changes.append(f"column '{name}' ({col['data_type']}) added")
            elif col["data_type"] != stored_by_name[name]["data_type"]:
                changes.append(
                    f"column '{name}' type changed "
                    f"({stored_by_name[name]['data_type']} → {col['data_type']})"
                )

        for name in stored_by_name:
            if name not in current_by_name:
                changes.append(f"column '{name}' removed")

        return changes

    async def _capture_schema(self, dataset_id: str) -> list:
        """Fetch current column schema for a dataset."""
        try:
            async with self.db_pool.acquire() as conn:
                rows = await conn.fetch(
                    """
                    SELECT column_name, data_type
                    FROM information_schema.columns
                    WHERE table_name = (
                        SELECT "tableName" FROM "UserDataset"
                        WHERE id = $1 AND ("userId" = $2 OR ("isShared" = true AND "datasetGroup" IN (
                            SELECT "userGroup" FROM "User" WHERE id = $2
                        )))
                    )
                    ORDER BY ordinal_position
                    """,
                    dataset_id, self.user_id,
                )
            if not rows:
                return []
            return [{"column_name": r["column_name"], "data_type": r["data_type"]} for r in rows]
        except Exception:
            return []

    # ── Conversation summarisation ──────────────────────────────

    def _summarise_if_needed(self, messages: list, max_messages: int = 40) -> list:
        """Trim old messages if the conversation grows too long.

        For now this is a simple trim — a full LLM summarisation pass
        can be added later (Phase 5)."""
        if len(messages) <= max_messages:
            return messages
        # Keep system context + last max_messages
        return messages[-max_messages:]

    async def summarise(self, messages: list, max_tokens: int = 4000) -> str:
        """Compress conversation history into a short summary (stub)."""
        if not messages:
            return ""
        # Simple heuristic: concatenate first 100 chars of each message
        parts = []
        for m in messages[-10:]:
            content = m.get("content", "")[:100]
            parts.append(f"[{m.get('role', '?')}]: {content}")
        return "\n".join(parts)
