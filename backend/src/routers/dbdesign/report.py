"""
Complete analysis endpoint: extracts schema and runs structured analysis.
"""

import asyncio
import logging
from typing import Dict, Any, List, Optional

logger = logging.getLogger(__name__)
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.responses import Response

from src.utils.translation import t
from src.utils.encryption import decrypt_field
from src.routers.datasets.crud import (
    get_user_id_from_token,
    get_current_language,
    get_connection_row,
)
from src.routers.datasets.translations import DATASETS
from .schema import extract_postgresql_schema
from .analysis import analyze_schema
from .translations import DBDESIGN_TK

router = APIRouter()
security = HTTPBearer()
_db_pool = None


def set_db_pool(pool):
    """Set the database pool for this router."""
    global _db_pool
    _db_pool = pool


@router.post("/analyze/{connection_id}")
async def analyze_database(
    connection_id: int,
    request: Request,
    credentials: HTTPAuthorizationCredentials = Depends(security),
    language: str = Depends(get_current_language),
):
    """Analyze a connected database and return a structured report."""
    global _db_pool
    
    if _db_pool is None:
        raise HTTPException(
            status_code=500,
            detail=await t(_db_pool, language, DBDESIGN_TK["error.database.pool_not_initialized"]),
        )
    
    user_id = await get_user_id_from_token(credentials)
    
    try:
        conn_details = await get_connection_row(connection_id, user_id, language)
    except HTTPException as e:
        raise e
    
    if conn_details is None:
        raise HTTPException(
            status_code=404,
            detail=await t(_db_pool, language, DATASETS["database.connection_not_found"])
        )
    
    # Decrypt password (keep-original on failure)
    decrypted_password = conn_details["password"]
    try:
        decrypted_password = decrypt_field(conn_details["password"])
    except Exception as e:
        logger.warning("Password decryption failed (will try raw): %s", e)
    
    db_type = conn_details["type"].lower()
    
    try:
        # Step 1: Extract schema
        from .schema import extract_postgresql_schema, extract_mysql_schema, extract_mssql_schema, extract_access_schema
        if db_type in ("postgresql", "postgres"):
            schema = await extract_postgresql_schema(
                host=conn_details["host"],
                port=conn_details["port"],
                database=conn_details["database"],
                username=conn_details["username"],
                password=decrypted_password,
                language=language,
            )
        elif db_type == "mysql":
            schema = await extract_mysql_schema(
                host=conn_details["host"],
                port=conn_details["port"],
                database=conn_details["database"],
                username=conn_details["username"],
                password=decrypted_password,
                language=language,
            )
        elif db_type == "mssql":
            schema = await extract_mssql_schema(
                host=conn_details["host"],
                port=conn_details["port"],
                database=conn_details["database"],
                username=conn_details["username"],
                password=decrypted_password,
                language=language,
            )
        elif db_type == "access":
            schema = extract_access_schema(
                host=conn_details["host"],
                port=conn_details["port"],
                database=conn_details["database"],
                username=conn_details["username"],
                password=decrypted_password,
            )
        else:
            raise HTTPException(
                status_code=400,
                detail=await t(_db_pool, language, DBDESIGN_TK["dbdesign.unsupported_type"]),
            )
        
        # Add zero-tables warning if connection succeeded but no tables found
        if schema.get('total_tables', 0) == 0:
            schema['_warnings'] = [(
                "No tables found. This usually means the database user does not have "
                "SELECT permissions. Ask your database administrator to run:\n"
                "  GRANT USAGE ON SCHEMA public TO <user>;\n"
                "  GRANT SELECT ON ALL TABLES IN SCHEMA public TO <user>;\n"
                "  ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT ON TABLES TO <user>;"
            )]
        
        # Parse optional AI connection from request body
        body = {}
        try:
            body = await request.json()
        except Exception:
            pass
        ai_connection_id = body.get("ai_connection_id")
        ai_model = body.get("model")
        use_ai = body.get("use_ai", False)
    
        # Step 2: Run structured analysis (AI-augmented if use_ai=True)
        analysis = await analyze_schema(
            schema, _db_pool, language,
            use_ai=use_ai,
            user_id=user_id,
            connection_id=ai_connection_id,
            sample_values=schema.get("samples"),
            model=ai_model,
        )
        
        # Step 2.5: Run semi-structured analysis on text columns
        from .semistructured import analyze_semi_structured, generate_normalisation_suggestions
        samples = schema.pop("samples", {})
        semi_structured = await analyze_semi_structured(schema, samples, _db_pool, language) if samples else None
        
        # Step 2.6: Generate normalisation suggestions from semi-structured findings (AI-powered)
        # Run with a timeout so a slow AI provider doesn't block the main response
        normalisation_suggestions = []
        if semi_structured and samples:
            try:
                normalisation_suggestions = await asyncio.wait_for(
                    generate_normalisation_suggestions(
                        semi_structured, _db_pool, samples, language,
                        ai_connection_id=ai_connection_id, ai_model=ai_model
                    ),
                    timeout=90.0,
                )
            except asyncio.TimeoutError:
                logger.warning("Normalisation suggestions timed out after 90s — skipping")
            except Exception as e:
                logger.warning("Normalisation suggestions failed: %s", e)
        
        # Resolve AI provider name if applicable
        ai_provider = None
        ai_model_resolved = ai_model
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

        # Step 3: Return combined report
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
        if semi_structured:
            result["semi_structured"] = semi_structured
        if normalisation_suggestions:
            result["normalisation_suggestions"] = normalisation_suggestions

        # AI-augmented sections (from coordinator merge when use_ai=True)
        if use_ai and analysis.get("ai_status"):
            result["ai_status"] = analysis["ai_status"]
            if analysis.get("health"):
                result["health"] = analysis["health"]
            if analysis.get("semantic"):
                result["semantic"] = analysis["semantic"]
            if analysis.get("integration"):
                result["integration"] = analysis["integration"]

        return result
        
    except HTTPException as e:
        # Re-raise HTTP exceptions from schema extraction
        raise e
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=await t(_db_pool, language, DBDESIGN_TK["dbdesign.analyze_error"], error=str(e)),
        )


def _generate_summary(schema: Dict, analysis: Dict, semi_structured: Optional[Dict] = None) -> Dict:
    """Generate a human-readable summary of the analysis."""
    tables = schema.get("tables", [])
    issues_raw = analysis.get("issues", [])
    # When AI-augmented, the coordinator wraps issues in a dict with 'items' key
    if isinstance(issues_raw, dict):
        issues = issues_raw.get("items", [])
    else:
        issues = issues_raw
    
    # Group issues by table
    by_table = {}
    for issue in issues:
        tbl = issue.get("table", "unknown")
        if tbl not in by_table:
            by_table[tbl] = []
        by_table[tbl].append(issue)
    
    return {
        "total_tables": schema.get("total_tables", 0),
        "total_columns": schema.get("total_columns", 0),
        "total_rows": sum(t.get("row_count", 0) for t in tables),
        "issue_count": len(issues),
        "tables_with_issues": len(by_table),
        "risk_summary": {
            "high": issues_raw.get("critical", 0) + issues_raw.get("high", 0) if isinstance(issues_raw, dict) else sum(1 for i in issues if i.get("severity") in ("CRITICAL", "HIGH")),
            "medium": issues_raw.get("medium", 0) if isinstance(issues_raw, dict) else sum(1 for i in issues if i.get("severity") == "MEDIUM"),
            "low": issues_raw.get("low", 0) if isinstance(issues_raw, dict) else sum(1 for i in issues if i.get("severity") == "LOW"),
        },
        "top_recommendations": _get_top_recommendations(issues, 5),
        "semi_structured_columns": semi_structured.get("columns_with_findings", 0) if semi_structured else 0,
        "code_systems_detected": len([
            f for f in (semi_structured.get("findings", []) if semi_structured else [])
            if f.get("code_systems")
        ]),
    }


def _get_top_recommendations(issues: List[Dict], limit: int = 5) -> List[str]:
    """Get the top N recommendations (highest severity first)."""
    severity_order = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3}
    sorted_issues = sorted(issues, key=lambda i: severity_order.get(i.get("severity", "LOW"), 4))
    
    seen = set()
    recs = []
    for issue in sorted_issues:
        rec = issue.get("recommendation", "")
        if rec and rec not in seen:
            seen.add(rec)
            recs.append(rec)
            if len(recs) >= limit:
                break
    
    return recs


@router.post("/export-pdf")
async def export_pdf(
    request: Request,
    credentials: HTTPAuthorizationCredentials = Depends(security),
    language: str = Depends(get_current_language),
):
    """Generate a PDF from the analysis report data provided in the request body."""
    from .pdf_export import generate_analysis_pdf
    from .translations import PDF_REPORT_TK
    
    try:
        body = await request.json()
        report = body.get("report")
        # Use the language from the request body if provided, otherwise fall back to user preference
        request_language = body.get("language")
        if request_language:
            language = request_language
        if not report:
            raise HTTPException(
                status_code=400,
                detail=await t(_db_pool, language, DBDESIGN_TK["dbdesign.report_data_required"]),
            )
        
        # Pre-translate all PDF strings
        pdf_tr = {}
        for full_key, tk in PDF_REPORT_TK.items():
            pdf_tr[full_key[len("dbdesign.pdf."):]] = await t(_db_pool, language, tk)
        
        pdf_bytes = generate_analysis_pdf(report, pdf_tr)
        pdf_bytes = bytes(pdf_bytes)  # fpdf returns bytearray; Response needs bytes
        
        db_name = report.get("database_name", report.get("connection_name", "")).replace(" ", "-")
        conn_id = report.get("connection_id", "unknown")
        filename = f"database-analysis-{db_name}-{conn_id}-{datetime.now().strftime('%Y%m%d-%H%M%S')}.pdf"
        
        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={
                "Content-Disposition": f'attachment; filename="{filename}"',
            },
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error("PDF export failed: %s", e)
        raise HTTPException(
            status_code=500,
            detail=await t(_db_pool, language, DBDESIGN_TK["dbdesign.pdf_error"], error=str(e)),
        )



@router.post("/rag-query/{connection_id}")
async def rag_query_endpoint(
    connection_id: int,
    request: Request,
    credentials: HTTPAuthorizationCredentials = Depends(security),
    language: str = Depends(get_current_language),
):
    """Run a RAG query against a connected database's text columns."""
    global _db_pool
    
    if _db_pool is None:
        raise HTTPException(
            status_code=500,
            detail=await t(_db_pool, language, DBDESIGN_TK["error.database.pool_not_initialized"]),
        )
    
    user_id = await get_user_id_from_token(credentials)
    
    try:
        conn_details = await get_connection_row(connection_id, user_id, language)
    except HTTPException as e:
        raise e
    
    if conn_details is None:
        raise HTTPException(
            status_code=404,
            detail=await t(_db_pool, language, DATASETS["database.connection_not_found"])
        )
    
    body = await request.json()
    question = body.get("question", "").strip()
    ai_connection_id = body.get("ai_connection_id")
    ai_model = body.get("model")
    if not question:
        raise HTTPException(status_code=400, detail=await t(_db_pool, language, DBDESIGN_TK["dbdesign.question_required"]))
    
    db_type = conn_details["type"].lower()
    if db_type == "mssql":
        # MSSQL RAG not yet supported; return empty
        return dict(answer="", sources=[])
    if db_type not in ("postgresql", "postgres"):
        return dict(
            answer=await t(_db_pool, language, DBDESIGN_TK["dbdesign.rag_not_available"]),
            sources=[],
        )
    
    try:
        decrypted_password = decrypt_field(conn_details["password"])
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=await t(_db_pool, language, DBDESIGN_TK["dbdesign.schema_error_2"], error=str(e)),
        )
    
    import asyncpg
    pg_conn = await asyncpg.connect(
        host=conn_details["host"],
        port=conn_details["port"],
        database=conn_details["database"],
        user=conn_details["username"],
        password=decrypted_password,
    )
    try:
        table_rows = await pg_conn.fetch("""
            SELECT t.table_schema, t.table_name
            FROM information_schema.tables t
            WHERE t.table_schema NOT IN ('pg_catalog', 'information_schema')
              AND t.table_type = 'BASE TABLE'
        """)
        tables = []
        for trow in table_rows:
            cols = await pg_conn.fetch("""
                SELECT column_name, data_type
                FROM information_schema.columns
                WHERE table_schema = $1 AND table_name = $2
                ORDER BY ordinal_position
            """, trow["table_schema"], trow["table_name"])
            tables.append({
                "schema": trow["table_schema"],
                "name": trow["table_name"],
                "columns": [{"name": c["column_name"], "type": c["data_type"]} for c in cols],
            })
        schema = {"tables": tables}
    finally:
        await pg_conn.close()
    
    from .rag import rag_query
    try:
        result = await rag_query(_db_pool, conn_details, schema, question, connection_id, language,
                                 ai_connection_id=ai_connection_id, ai_model=ai_model)
        return result
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=await t(_db_pool, language, DBDESIGN_TK["dbdesign.rag_error"], error=str(e)),
        )