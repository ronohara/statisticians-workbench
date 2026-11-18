"""
SSE streaming endpoint for AI-augmented database analysis.

Provides a real-time event stream so the frontend can show an incremental
log of each analysis step — schema extraction, mechanical analysis, AI
specialist progress, normalisation, and completion.

Format: Server-Sent Events (text/event-stream)
Each event is a JSON object: {"event": "...", "message": "...", ...}
Final event is: {"event": "complete", "report": {...}}
Error events: {"event": "error", "message": "..."}
"""

import asyncio
import json
import logging
from fastapi import APIRouter, Depends, HTTPException, Request, Query
from fastapi.responses import StreamingResponse
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from typing import Optional

from src.utils.translation import t
from src.utils.encryption import decrypt_field
from .translations import DBDESIGN_TK, TranslationKey
from src.routers.datasets.crud import (
    get_user_id_from_token,
    get_current_language,
    get_connection_row,
)

logger = logging.getLogger(__name__)

router = APIRouter()
security = HTTPBearer()

_db_pool = None


def set_db_pool(pool):
    global _db_pool
    _db_pool = pool


def _sse(data: dict) -> str:
    """Format a dict as an SSE event."""
    return f"data: {json.dumps(data, default=str)}\n\n"


def _hint_if_context_limit(error_msg: str) -> str:
    """Append a model recommendation if the error suggests a context-window issue."""
    ctx_indicators = ("empty content", "context", "token", "truncat", "too large")
    if any(ind in error_msg.lower() for ind in ctx_indicators):
        return f"{error_msg} — try switching to deepseek-v4-pro for larger context window."
    return error_msg


async def _emit(queue: Optional[asyncio.Queue], **data):
    """Emit an SSE event. Uses a queue for async or yields directly."""
    if queue is not None:
        await queue.put(data)


# ── Streaming endpoint ────────────────────────────────────────────────

@router.get("/analyze/{connection_id}/stream")
async def stream_analyze(
    connection_id: int,
    request: Request,
    token: str = Query(...),
    use_ai: bool = Query(False),
    ai_connection_id: Optional[int] = Query(None),
    model: Optional[str] = Query(None),
    language: str = Query("en"),
):
    """Stream analysis progress via SSE. Auth via query parameter `token`."""
    global _db_pool

    if _db_pool is None:
        raise HTTPException(status_code=500, detail=await t(_db_pool, language, DBDESIGN_TK["error.database.pool_not_initialized"]))

    # Validate token manually (EventSource can't send Authorization header)
    from fastapi.security import HTTPAuthorizationCredentials
    creds = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)
    try:
        user_id = await get_user_id_from_token(creds, _db_pool, language)
    except HTTPException:
        raise HTTPException(status_code=401, detail=await t(_db_pool, language, DBDESIGN_TK["dbdesign.invalid_token"]))

    # Pre-flight: fetch + gate before the stream starts. A disabled type raises
    # a real 403; a missing connection ends the stream silently (no events).
    conn_details = await get_connection_row(connection_id, user_id, language)
    if conn_details is None:
        async def _empty_stream():
            if False:
                yield
        return StreamingResponse(
            _empty_stream(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            },
        )

    async def event_stream():
        nonlocal use_ai

        async def _tr(key: TranslationKey, **kwargs) -> str:
            """Shortcut for t() with the current db_pool and language."""
            return await t(_db_pool, language, key, **kwargs)

        try:
            # ── Step 0: Get connection ────────────────────────────────
            yield _sse({"event": "status", "phase": "connect",
                        "message": await _tr(DBDESIGN_TK["dbdesign.stream_connecting"])})

            decrypted_password = conn_details["password"]
            try:
                decrypted_password = decrypt_field(conn_details["password"])
            except Exception:
                pass

            db_type = conn_details["type"].lower()
            db_name = conn_details.get("database", "unknown")

            yield _sse({"event": "status", "phase": "connect",
                        "message": await _tr(DBDESIGN_TK["dbdesign.stream_connected"],
                                            db_type=db_type, db_name=db_name)})

            # ── Step 1: Extract schema ────────────────────────────────
            yield _sse({"event": "status", "phase": "schema",
                        "message": await _tr(DBDESIGN_TK["dbdesign.stream_extracting_schema"],
                                            db_type=db_type)})

            from .schema import (
                extract_postgresql_schema, extract_mysql_schema,
                extract_mssql_schema, extract_access_schema,
            )

            if db_type in ("postgresql", "postgres"):
                schema = await extract_postgresql_schema(
                    host=conn_details["host"], port=conn_details["port"],
                    database=conn_details["database"],
                    username=conn_details["username"],
                    password=decrypted_password, language=language,
                )
            elif db_type == "mysql":
                schema = await extract_mysql_schema(
                    host=conn_details["host"], port=conn_details["port"],
                    database=conn_details["database"],
                    username=conn_details["username"],
                    password=decrypted_password, language=language,
                )
            elif db_type == "mssql":
                schema = await extract_mssql_schema(
                    host=conn_details["host"], port=conn_details["port"],
                    database=conn_details["database"],
                    username=conn_details["username"],
                    password=decrypted_password, language=language,
                )
            elif db_type == "access":
                schema = extract_access_schema(
                    host=conn_details["host"], port=conn_details["port"],
                    database=conn_details["database"],
                    username=conn_details["username"],
                    password=decrypted_password,
                )
            else:
                yield _sse({"event": "error",
                            "message": await _tr(DBDESIGN_TK["dbdesign.stream_unsupported_type"],
                                                db_type=db_type)})
                return

            tables_n = schema.get("total_tables", 0)
            cols_n = schema.get("total_columns", 0)
            yield _sse({"event": "schema_done", "phase": "schema",
                        "message": await _tr(DBDESIGN_TK["dbdesign.stream_schema_done"],
                                            tables=tables_n, columns=cols_n),
                        "detail": {"tables": tables_n, "columns": cols_n}})

            # ── Step 2: Mechanical analysis ──────────────────────────
            yield _sse({"event": "status", "phase": "mechanical",
                        "message": await _tr(DBDESIGN_TK["dbdesign.stream_mechanical_start"])})

            from .analysis import analyze_schema
            samples = schema.get("samples", {})
            analysis = await analyze_schema(
                schema, _db_pool, language,
                use_ai=False,  # mechanical only here
                user_id=user_id,
                connection_id=None,
                sample_values=samples,
            )

            issue_count = 0
            issues = analysis.get("issues", [])
            if isinstance(issues, dict):
                issue_count = issues.get("total", len(issues.get("items", [])))
            elif isinstance(issues, list):
                issue_count = len(issues)

            yield _sse({"event": "mechanical_done", "phase": "mechanical",
                        "message": await _tr(DBDESIGN_TK["dbdesign.stream_mechanical_done"],
                                            count=issue_count),
                        "detail": {"issue_count": issue_count}})

            # ── Step 3: AI specialists (if enabled) ──────────────────
            AI_ISSUE_LIMIT = 500
            ai_skipped_reason = None
            if use_ai and ai_connection_id and issue_count > AI_ISSUE_LIMIT:
                ai_skipped_reason = await _tr(
                    DBDESIGN_TK["dbdesign.ai_skipped_reason"],
                    count=issue_count, limit=AI_ISSUE_LIMIT,
                )
                skipped_msg = await _tr(
                    DBDESIGN_TK["dbdesign.ai_skipped_message"],
                    count=issue_count, limit=AI_ISSUE_LIMIT,
                )
                yield _sse({"event": "ai_skipped", "phase": "ai",
                            "message": skipped_msg,
                            "detail": {"issue_count": issue_count, "limit": AI_ISSUE_LIMIT}})
                logger.info("AI analysis skipped: %d issues exceeds limit of %d", issue_count, AI_ISSUE_LIMIT)
                use_ai = False  # skip the AI block below

            if use_ai and ai_connection_id:
                yield _sse({"event": "ai_start", "phase": "ai",
                            "message": await _tr(DBDESIGN_TK["dbdesign.stream_ai_start"])})

                from .schema_ai import analyze as schema_ai_analyze
                from .semantic_ai import analyze as semantic_ai_analyze
                from .integration_ai import analyze as integration_ai_analyze
                from .coordinator import merge

                progress = asyncio.Queue()

                async def run_schema_ai():
                    await progress.put({"event": "ai_progress", "phase": "ai",
                                        "specialist": "schema", "status": "started",
                                        "message": await _tr(DBDESIGN_TK["dbdesign.stream_ai_schema_start"],
                                                            tables=tables_n)})
                    try:
                        result = await schema_ai_analyze(
                            schema, analysis, db_pool=_db_pool, user_id=user_id,
                            connection_id=ai_connection_id, language=language,
                            model=model,
                        )
                        if result.get("status") == "error":
                            err = result.get("error", "unknown error")
                            await progress.put({"event": "ai_progress", "phase": "error",
                                                "specialist": "schema", "status": "error",
                                                "message": _hint_if_context_limit(f"Schema AI failed: {err}")})
                            return result
                        else:
                            score = result.get("health_score", "?")
                            await progress.put({"event": "ai_progress", "phase": "ai",
                                                "specialist": "schema", "status": "done",
                                                "result": result,
                                                 "message": await _tr(DBDESIGN_TK["dbdesign.stream_ai_schema_done"],
                                                                     score=score)})
                            return result
                    except Exception as e:
                        logger.warning("Schema AI crashed: %s", e)
                        await progress.put({"event": "ai_progress", "phase": "error",
                                            "specialist": "schema", "status": "error",
                                            "message": _hint_if_context_limit(f"Schema AI failed: {e}")})
                        return {"status": "error", "error": str(e)}

                async def run_semantic_ai():
                    await progress.put({"event": "ai_progress", "phase": "ai",
                                        "specialist": "semantic", "status": "started",
                                        "message": await _tr(DBDESIGN_TK["dbdesign.stream_ai_semantic_start"],
                                                            tables=tables_n)})
                    try:
                        result = await semantic_ai_analyze(
                            schema, samples, db_pool=_db_pool, user_id=user_id,
                            connection_id=ai_connection_id, language=language,
                            model=model,
                        )
                        if result.get("status") == "error":
                            err = result.get("error", "unknown error")
                            await progress.put({"event": "ai_progress", "phase": "error",
                                                "specialist": "semantic", "status": "error",
                                                "message": _hint_if_context_limit(f"Semantic AI failed: {err}")})
                            return result
                        else:
                            cols_n = len(result.get("columns", []))
                            domains_n = len(result.get("domains", []))
                            await progress.put({"event": "ai_progress", "phase": "ai",
                                                "specialist": "semantic", "status": "done",
                                                "result": result,
                                                "message": await _tr(DBDESIGN_TK["dbdesign.stream_ai_semantic_done"],
                                                                    columns=cols_n, domains=domains_n)})
                            return result
                    except Exception as e:
                        logger.warning("Semantic AI crashed: %s", e)
                        await progress.put({"event": "ai_progress", "phase": "error",
                                            "specialist": "semantic", "status": "error",
                                            "message": _hint_if_context_limit(f"Semantic AI failed: {e}")})
                        return {"status": "error", "error": str(e)}

                async def run_integration_ai():
                    await progress.put({"event": "ai_progress", "phase": "ai",
                                        "specialist": "integration", "status": "started",
                                        "message": await _tr(DBDESIGN_TK["dbdesign.stream_ai_integration_start"])})
                    try:
                        result = await integration_ai_analyze(
                            schema, None, db_pool=_db_pool, user_id=user_id,
                            connection_id=ai_connection_id, language=language,
                            model=model,
                        )
                        if result.get("status") == "error":
                            err = result.get("error", "unknown error")
                            await progress.put({"event": "ai_progress", "phase": "error",
                                                "specialist": "integration", "status": "error",
                                                "message": _hint_if_context_limit(f"Integration AI failed: {err}")})
                            return result
                        else:
                            rels_n = len(result.get("implicit_relationships", []))
                            caps_n = len(result.get("research_capabilities", []))
                            await progress.put({"event": "ai_progress", "phase": "ai",
                                                "specialist": "integration", "status": "done",
                                                "result": result,
                                                "message": await _tr(DBDESIGN_TK["dbdesign.stream_ai_integration_done"],
                                                                    relationships=rels_n, capabilities=caps_n)})
                            return result
                    except Exception as e:
                        logger.warning("Integration AI crashed: %s", e)
                        await progress.put({"event": "ai_progress", "phase": "error",
                                            "specialist": "integration", "status": "error",
                                            "message": _hint_if_context_limit(f"Integration AI failed: {e}")})
                        return {"status": "error", "error": str(e)}

                # Run all three in parallel, yielding progress events as they arrive
                tasks = [
                    asyncio.create_task(run_schema_ai()),
                    asyncio.create_task(run_semantic_ai()),
                    asyncio.create_task(run_integration_ai()),
                ]

                # Poll progress queue while tasks are running
                pending = set(tasks)
                while pending:
                    # Wait for either a progress event or task completion
                    done, pending = await asyncio.wait(
                        pending, timeout=0.5,
                        return_when=asyncio.FIRST_COMPLETED,
                    )
                    # Drain progress queue
                    while not progress.empty():
                        evt = await progress.get()
                        yield _sse(evt)
                    # Yield any done tasks (no output needed, just cleanup)
                    for task in done:
                        try:
                            await task  # propagate exceptions if any
                        except Exception:
                            pass

                # Drain any remaining progress events
                while not progress.empty():
                    evt = await progress.get()
                    yield _sse(evt)

                s_ai, sem_ai, i_ai = await asyncio.gather(*tasks, return_exceptions=True)
                if isinstance(s_ai, Exception):
                    s_ai = {"status": "error", "error": str(s_ai)}
                if isinstance(sem_ai, Exception):
                    sem_ai = {"status": "error", "error": str(sem_ai)}
                if isinstance(i_ai, Exception):
                    i_ai = {"status": "error", "error": str(i_ai)}

                analysis = merge(analysis, s_ai, sem_ai, i_ai)
                ai_status = analysis.get("ai_status", "unknown")
                yield _sse({"event": "ai_done", "phase": "ai",
                            "message": await _tr(DBDESIGN_TK["dbdesign.stream_ai_done"],
                                                status=ai_status),
                            "detail": {"ai_status": ai_status}})

            # ── Step 4: Semi-structured + normalisation ──────────────
            from .semistructured import analyze_semi_structured, generate_normalisation_suggestions
            schema_samples = schema.pop("samples", {})
            semi_structured = None
            if schema_samples:
                yield _sse({"event": "status", "phase": "semistructured",
                            "message": await _tr(DBDESIGN_TK["dbdesign.stream_semistructured_start"])})
                semi_structured = await analyze_semi_structured(schema, schema_samples, _db_pool, language)

            normalisation_suggestions = []
            if semi_structured and schema_samples and use_ai and ai_connection_id:
                yield _sse({"event": "status", "phase": "normalisation",
                            "message": await _tr(DBDESIGN_TK["dbdesign.stream_normalisation_start"])})
                try:
                    normalisation_suggestions = await asyncio.wait_for(
                        generate_normalisation_suggestions(
                            semi_structured, _db_pool, schema_samples, language,
                            ai_connection_id=ai_connection_id, ai_model=model,
                        ),
                        timeout=90.0,
                    )
                    yield _sse({"event": "normalisation_done", "phase": "normalisation",
                                "message": await _tr(DBDESIGN_TK["dbdesign.stream_normalisation_done"],
                                                    count=len(normalisation_suggestions))})
                except asyncio.TimeoutError:
                    logger.warning("Normalisation suggestions timed out")
                    yield _sse({"event": "normalisation_done", "phase": "normalisation",
                                "message": await _tr(DBDESIGN_TK["dbdesign.stream_normalisation_timeout"])})
                except Exception as e:
                    logger.warning("Normalisation failed: %s", e)
                    yield _sse({"event": "normalisation_done", "phase": "normalisation",
                                "message": await _tr(DBDESIGN_TK["dbdesign.stream_normalisation_skipped"],
                                                    error=str(e))})

            # ── Step 5: Build final report ────────────────────────────
            from .report import _generate_summary
            # Resolve AI provider
            ai_provider = None
            ai_model_resolved = model
            if use_ai and ai_connection_id:
                try:
                    async with _db_pool.acquire() as conn:
                        row = await conn.fetchrow(
                            'SELECT provider, "defaultModel" FROM "UserAIConnection" WHERE "connectionId" = $1',
                            ai_connection_id,
                        )
                        if row:
                            ai_provider = row["provider"]
                            if not ai_model_resolved:
                                ai_model_resolved = row["defaultModel"]
                except Exception:
                    pass

            result = {
                "connection_id": connection_id,
                "connection_name": conn_details.get("name", ""),
                "database_name": conn_details.get("database", ""),
                "database_type": schema["database_type"],
                "ai_provider": ai_provider,
                "ai_model": ai_model_resolved if use_ai else None,
                "schema": schema,
                "analysis": analysis,
                "summary": _generate_summary(schema, analysis, semi_structured),
            }
            if ai_skipped_reason:
                result["ai_skipped"] = True
                result["ai_skipped_reason"] = ai_skipped_reason
            if semi_structured:
                result["semi_structured"] = semi_structured
            if normalisation_suggestions:
                result["normalisation_suggestions"] = normalisation_suggestions
            if use_ai and analysis.get("ai_status"):
                result["ai_status"] = analysis["ai_status"]
                if analysis.get("health"):
                    result["health"] = analysis["health"]
                if analysis.get("semantic"):
                    result["semantic"] = analysis["semantic"]
                if analysis.get("integration"):
                    result["integration"] = analysis["integration"]

            complete_msg = await _tr(DBDESIGN_TK["dbdesign.analysis_complete"])
            yield _sse({"event": "complete",
                        "message": complete_msg,
                        "report": result})
            logger.info(
                "Analysis complete: %d tables, %d issues → %s",
                tables_n, issue_count,
                "ai_augmented" if use_ai else "mechanical_only",
            )

        except asyncio.CancelledError:
            cancelled_msg = await _tr(DBDESIGN_TK["dbdesign.analysis_cancelled"])
            logger.warning(cancelled_msg)
        except HTTPException:
            raise
        except Exception as e:
            logger.error("Analysis stream failed: %s", e)
            yield _sse({"event": "error",
                        "message": await _tr(DBDESIGN_TK["dbdesign.stream_analysis_failed"],
                                            error=str(e))})

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # disable nginx buffering
        },
    )
