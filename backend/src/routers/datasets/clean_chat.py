"""
Dataset Cleaning Chat – AI-powered, stateful data-cleaning concierge.

`send_chat_message` runs the dataclean tool loop over a `DataCleanChat` session
(mirroring the recipe concierge's `send_message`). The stateless single-shot
`DatasetCleanerAgent` (schema + 5 rows injected as text) is superseded by tools
that fetch real data.
"""

import logging
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from src.chat.connection import get_connection_details
from src.chat.tool_agent import ToolAgent
from src.utils.connection_timeouts import resolve_connection_timeouts
from src.utils.translation import t
from src.routers.common.translations import CHAT
from src.routers.datasets.crud import get_current_language, get_user_id_from_token
from .translations import DATASETS
from .dataclean_tools import DATACLEAN_REGISTRY, DATACLEAN_TOOL_NAMES, register_all_tools

logger = logging.getLogger(__name__)

router = APIRouter()
security = HTTPBearer()

_db_pool = None

register_all_tools()


def set_db_pool(pool):
    global _db_pool
    _db_pool = pool


def _build_system_prompt(dataset_id):
    """System prompt carrying the dataset-or-not state and the anti-hallucination guard."""
    if dataset_id:
        return (
            "You are the data-cleaning concierge of the Statisticians Workbench.\n"
            f"A dataset is selected (id {dataset_id}). Use the tools to inspect it "
            "(get_schema, sample_rows, detect_issues) and to define preparation rules "
            "(list_rules, add_rule, update_rule, delete_rule) and preview them "
            "(preview_rule). You cannot save or materialise anything yourself. When the "
            "cleaning actions are determined, create the rules and preview the effect, "
            "then tell the user to press Clean copy (to create a new cleaned dataset, "
            "suggesting a name) or Clean in place (to replace this dataset's data, for "
            "local datasets). Before creating a rule, call list_rules and re-use or "
            "update an existing rule that already performs the same operation; never "
            "create a duplicate rule.\n"
            "Report tool results faithfully and verbatim: use the exact column name each "
            "tool returned for every statistic or issue; never rename a column, move a "
            "number from one column to another, or invent values, ranges, or counts the "
            "tools did not return. If two tool results appear to disagree, state both "
            "exactly as returned instead of reconciling or guessing. Never surface "
            "internal identifiers (dataset ids, table names) to the user — use "
            "human-readable names. "
            "If the user asks for something none of your tools can do (aggregation, "
            "grouping, time-series, or anything beyond cleaning a dataset), call "
            "report_unsupported with a short description, then tell the user plainly "
            "it isn't supported yet and stop. "
            "Keep replies short and actionable."
        )
    return (
        "You are the data-cleaning concierge of the Statisticians Workbench.\n"
        "No dataset is selected. Guide the user to select one from the dropdown above the chat; "
        "do not invent schema, columns, or rows, and do not use data tools until a dataset is selected. "
        "If the user asks for something none of your tools can do, call report_unsupported, then tell "
        "them plainly it isn't supported yet."
    )


async def _run_turn(db_pool, user_id, connection_id, api_key, endpoint, model, provider, language, system_prompt, messages, tool_names):
    """Run one tool-loop turn over ``messages``; return the final assistant text (never empty)."""
    # The two budgets in force for this connection (plan Item 4a). Resolved here
    # rather than passed in, because this helper already has the pool and the id.
    # ToolAgent has always carried a `timeout` field that nothing assigned; these
    # are the first values that reach it.
    async with db_pool.acquire() as timeout_conn:
        timeouts = await resolve_connection_timeouts(timeout_conn, connection_id)
    agent = ToolAgent(
        api_key=api_key, endpoint=endpoint, model=model, provider=provider,
        language=language,
        timeout=float(timeouts.probe_seconds),
        connect_timeout=float(timeouts.connect_seconds),
        registry=DATACLEAN_REGISTRY,
    )
    agent.db_pool = db_pool
    agent.user_id = user_id
    response_text, _tool_events = await agent.run_tool_loop(system_prompt, messages, tool_names=tool_names)
    if not response_text or not response_text.strip():
        response_text = await t(db_pool, language, DATASETS["dataclean_chat.empty_response"])
        messages.append({"role": "assistant", "content": response_text})
    return response_text


async def send_chat_message(
    db_pool,
    user_id,
    chat_id,
    user_message,
    connection_id=None,
    model=None,
    language="en",
):
    """Run one turn of the dataclean tool loop over a DataCleanChat session."""
    async with db_pool.acquire() as conn:
        row = await conn.fetchrow(
            'SELECT * FROM "DataCleanChat" WHERE id = $1 AND "userId" = $2',
            chat_id, user_id,
        )
    if not row:
        raise ValueError("session_not_found")

    dataset_id = row["datasetId"]
    messages = row["messages"] or []

    try:
        details = await get_connection_details(db_pool, connection_id, user_id)
    except ValueError:
        raise HTTPException(status_code=400, detail=await t(db_pool, language, DATASETS["chat.connection_not_found"]))
    api_key, endpoint = details["apiKey"], details["endpoint"]
    provider = details["provider"]
    model = model or details["model"]

    system_prompt = _build_system_prompt(dataset_id)
    messages.append({"role": "user", "content": user_message})

    # No dataset bound → expose no data tools (the model is guided to ask the
    # user to select one). An empty allow-list, NOT None, keeps every other
    # concierge's tools out too.
    tool_names = DATACLEAN_TOOL_NAMES if dataset_id else []
    response_text = await _run_turn(
        db_pool, user_id, connection_id, api_key, endpoint, model, provider, language,
        system_prompt, messages, tool_names,
    )

    async with db_pool.acquire() as conn:
        await conn.execute(
            'UPDATE "DataCleanChat" SET messages = $2::jsonb, "updatedAt" = NOW() WHERE id = $1',
            chat_id, messages,
        )

    return {"chatId": chat_id, "datasetId": dataset_id, "response": response_text}


async def handle_dataset_selected(
    db_pool,
    user_id,
    chat_id,
    dataset_id,
    connection_id=None,
    model=None,
    language="en",
):
    """Bind a dataset to a session and run one short re-grounding turn.

    Binds ``datasetId``, then runs the tool loop (get_schema + detect_issues)
    against a working copy so the synthetic trigger is not written into the
    visible history — only the assistant reply is persisted.
    """
    async with db_pool.acquire() as conn:
        row = await conn.fetchrow(
            'SELECT * FROM "DataCleanChat" WHERE id = $1 AND "userId" = $2',
            chat_id, user_id,
        )
    if not row:
        raise ValueError("session_not_found")

    messages = row["messages"] or []

    # Gap A: the dataset is validated *before* it is bound to the session. Binding is a
    # read — the tools behind the session then inspect this dataset's schema — so the
    # rule is the visibility predicate (own, or shared to the caller's group), not the
    # edit rule: case 3 may clean a shared dataset, and the result is always a new
    # dataset of their own (Decision 3). A dataset the caller cannot see is refused
    # with the not-found answer, so the binding cannot be used to discover ids.
    dataset_name = None
    if dataset_id:
        async with db_pool.acquire() as conn:
            drow = await conn.fetchrow(
                """
                SELECT name FROM "UserDataset"
                WHERE id = $1 AND ("userId" = $2 OR ("isShared" = true AND "datasetGroup" IN (
                    SELECT "userGroup" FROM "User" WHERE id = $2
                )))
                """,
                dataset_id, user_id,
            )
        if drow is None:
            raise HTTPException(
                status_code=404,
                detail=await t(db_pool, language, DATASETS["error.dataset.not_found_2"], id=dataset_id),
            )
        dataset_name = drow["name"]

    async with db_pool.acquire() as conn:
        await conn.execute(
            'UPDATE "DataCleanChat" SET "datasetId" = $2, "updatedAt" = NOW() WHERE id = $1',
            chat_id, dataset_id,
        )

    try:
        details = await get_connection_details(db_pool, connection_id, user_id)
    except ValueError:
        raise HTTPException(status_code=400, detail=await t(db_pool, language, DATASETS["chat.connection_not_found"]))
    api_key, endpoint = details["apiKey"], details["endpoint"]
    provider = details["provider"]
    model = model or details["model"]

    system_prompt = _build_system_prompt(dataset_id)
    system_prompt += (
        "\n\nThe user has just selected a dataset"
        + (f' ("{dataset_name}")' if dataset_name else "")
        + ". Inspect it — call get_schema, detect_issues and list_rules — then give a short, "
        "actionable reply: the data's shape, the top data-quality issues, the existing "
        "preparation rules (re-use them instead of creating duplicates), a suggested "
        "cleaning plan, and one question to confirm the next step."
    )

    working = list(messages)
    working.append({"role": "user", "content": "A dataset was just selected from the dropdown."})
    response_text = await _run_turn(
        db_pool, user_id, connection_id, api_key, endpoint, model, provider, language,
        system_prompt, working, DATACLEAN_TOOL_NAMES,
    )

    messages.append({"role": "assistant", "content": response_text})
    async with db_pool.acquire() as conn:
        await conn.execute(
            'UPDATE "DataCleanChat" SET messages = $2::jsonb, "updatedAt" = NOW() WHERE id = $1',
            chat_id, messages,
        )

    return {"chatId": chat_id, "datasetId": dataset_id, "response": response_text}


@router.post("/clean-chat/{chat_id}/message")
async def clean_chat_message(
    chat_id: str,
    body: dict,
    request: Request,
    credentials: HTTPAuthorizationCredentials = Depends(security),
    language: str = Depends(get_current_language),
):
    """Send a message in the stateful data-cleaning chat."""
    if _db_pool is None:
        raise HTTPException(
            status_code=500,
            detail=await t(_db_pool, language, DATASETS["database.pool_not_initialized"]),
        )

    user_id = await get_user_id_from_token(credentials, _db_pool, language)
    user_message = (body.get("message") or "").strip()
    if not user_message:
        raise HTTPException(
            status_code=400,
            detail=await t(_db_pool, language, DATASETS["dataclean_chat.message_required"]),
        )

    try:
        return await send_chat_message(
            _db_pool,
            user_id,
            chat_id,
            user_message,
            connection_id=body.get("connectionId"),
            model=body.get("model"),
            language=language,
        )
    except ValueError as e:
        if str(e) == "session_not_found":
            raise HTTPException(
                status_code=404,
                detail=await t(_db_pool, language, DATASETS["dataclean_chat.chat_session_not_found"]),
            )
        raise HTTPException(status_code=400, detail=str(e))
    except RuntimeError as e:
        logger.error(f"LLM error for chat {chat_id}: {e}")
        error_msg = str(e)
        if error_msg.startswith("ai_repeat_loop:"):
            detail = await t(_db_pool, language, CHAT["chat.ai_repeat_loop"])
        elif error_msg.startswith("ai_timeout:"):
            detail = await t(_db_pool, language, CHAT["chat.ai_timeout"])
        elif error_msg.startswith("ai_provider_error:"):
            detail = await t(_db_pool, language, CHAT["chat.ai_service_failed"])
        else:
            detail = await t(_db_pool, language, DATASETS["error.ai.call_failed"], error=error_msg)
        raise HTTPException(status_code=502, detail=detail)
