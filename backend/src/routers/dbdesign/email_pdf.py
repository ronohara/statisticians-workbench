"""
Email PDF Router — P2 Group 5, item 27 (Prisma-removal plan).

Drop-in replacement for the frontend Prisma handler:
  frontend/app/api/dbdesign/email-pdf/route.ts  (POST /api/dbdesign/email-pdf)

The frontend handler is a THIN PROXY: session auth + user-email + GlobalSettings
+ email-translation lookups in Prisma, then an HTTP call to the backend's own
/api/dbdesign/export-pdf (forwarding Authorization) to get the PDF bytes, then
email via sendmail. The port generates the PDF IN-PROCESS (reusing
generate_analysis_pdf + PDF_REPORT_TK, exactly as report.export_pdf) — no HTTP
self-call.

Auth: security = HTTPBearer() (auto_error) + get_user_id_from_token, matching
the report.py siblings. No-token -> 401 {"detail": "Not authenticated"} (the
frontend's own {error: "Unauthorized"} 401 is dead code behind the proxy).

Language: the email CONTENT and PDF are in the report language — the frontend
uses body.language || "en" (reportLanguage), NOT the profile language. The port
mirrors that (no get_current_language dependency for content).

Failure map (D3 decision — recorded in workbench-documents/development-records/code-quirks.md):
  - malformed JSON body      -> 400 dbdesign.email_pdf.invalid_body  (DIVERGENCE:
    the reference's try/catch -> getBackendErrorResponse -> 502)
  - report missing           -> 400 dbdesign.report_data_required
  - no email / ghost         -> 400 dbdesign.email_pdf.no_email      (reference: 400)
  - PDF generation failure   -> 502 {error: <pdf_error detail>}      (the
    reference's !pdfResponse.ok branch; detail is export-pdf's pdf_error
    translation)
  - sendmail / unexpected    -> 502 {error: "dbdesign.email_pdf.send_failed", ...}
    (the reference catch, renamed in item 26 — there is no proxy hop left; the
    503 unavailable branch is dropped — structurally unreachable with no HTTP hop)

Error shape: the 400s are BARE prose ({error: "<translated>"}) routed through
t() with canonical keys (option b). The 502 catch is a CODED envelope
{error: "dbdesign.email_pdf.send_failed", message: ...} (renamed in item 26).
"""

import json

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from src.routers.datasets.crud import get_user_id_from_token
from src.routers.dbdesign.translations import EMAIL_PDF_TK
from src.utils.email import send_database_analysis_email
from src.utils.translation import t

router = APIRouter()
security = HTTPBearer()
_db_pool = None


def set_db_pool(pool):
    global _db_pool
    _db_pool = pool


async def _prose_error(status, tk, language):
    """Bare prose error ({error: "<translated>"}) — tk is a TranslationKey
    declaration object (duck-typed by t())."""
    message = await t(_db_pool, language, tk)
    return JSONResponse(status_code=status, content={"error": message})


@router.post("/email-pdf")
async def email_pdf(
    request: Request,
    credentials: HTTPAuthorizationCredentials = Depends(security),
):
    from .pdf_export import generate_analysis_pdf
    from .translations import DBDESIGN_TK, PDF_REPORT_TK

    # Malformed JSON -> 400 invalid_body (our divergence from the reference 502).
    try:
        body = json.loads(await request.body() or b"")
    except Exception:
        return await _prose_error(400, EMAIL_PDF_TK["dbdesign.email_pdf.invalid_body"], "en")
    if body is None:
        # Destructuring null throws in the reference -> catch -> 502; clean
        # validation -> 400 invalid_body (D3 divergence).
        return await _prose_error(400, EMAIL_PDF_TK["dbdesign.email_pdf.invalid_body"], "en")
    if not isinstance(body, dict):
        # Array/string/number destructure to undefined fields in JS, so report
        # is undefined -> the reference's 400 report_data_required. Mirror.
        body = {}

    report = body.get("report")
    language = body.get("language")
    if not isinstance(language, str) or not language:
        language = "en"

    if report is None:
        return await _prose_error(400, DBDESIGN_TK["dbdesign.report_data_required"], language)

    user_id = await get_user_id_from_token(credentials, _db_pool, language)

    async with _db_pool.acquire() as conn:
        user = await conn.fetchrow('SELECT email FROM "User" WHERE id = $1', user_id)
    user_email = user["email"] if user else None
    if not user_email:
        return await _prose_error(400, EMAIL_PDF_TK["dbdesign.email_pdf.no_email"], language)

    # In-process PDF generation — same prep as report.export_pdf.
    pdf_tr = {}
    for full_key, tk in PDF_REPORT_TK.items():
        pdf_tr[full_key[len("dbdesign.pdf."):]] = await t(_db_pool, language, tk)
    try:
        pdf_bytes = bytes(generate_analysis_pdf(report, pdf_tr))
    except Exception as e:
        # The reference's !pdfResponse.ok -> {error: detail} where detail is
        # export-pdf's pdf_error translation. Reproduce in-process.
        detail = await t(_db_pool, language, DBDESIGN_TK["dbdesign.pdf_error"], error=str(e))
        return JSONResponse(status_code=502, content={"error": detail})

    try:
        await send_database_analysis_email(_db_pool, user_email, language, report, pdf_bytes)
    except Exception:
        message = await t(_db_pool, language, EMAIL_PDF_TK["dbdesign.email_pdf.send_failed"])
        return JSONResponse(status_code=502, content={
            "error": "dbdesign.email_pdf.send_failed", "message": message,
        })

    success_message = await t(_db_pool, language, EMAIL_PDF_TK["ai.database.email_sent"])
    return {"success": True, "message": success_message}
