"""
Public languages + translations router — P2 Group 6, items 23 + 24
(Prisma-removal plan).

Drop-in replacements for the frontend Prisma handlers:
  frontend/app/api/languages/route.ts     (GET /api/languages?viewer=<code>)
  frontend/app/api/translations/route.ts  (GET /api/translations?language=<code>)

PUBLIC (no auth — the frontend proxy lists both in publicPaths). No try/catch
in either reference; a DB failure raises into the framework's 500.

Languages contract:
  - viewer = query param, JS-falsy default "en" ("" or missing -> "en"; a
    non-shipped viewer like "xx" is used as-is).
  - codes = distinct `language` values in Translation, "en" force-added, sorted.
  - names come from the `language.name.*` Translation rows (autonym + localized).
  - response is a bare JSON array of {code, name}.

Translations contract:
  - language = query param, JS-falsy default "en".
  - returns a flat {key: value} map of EVERY Translation row for that language;
    an unshipped language -> {} (empty object, not null).

No new translation keys: every returned string is itself a Translation row.
"""

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from src.utils.translation import t
from src.routers.translations import ROUTERS

router = APIRouter(tags=["languages-translations"])
_db_pool = None


def set_db_pool(pool):
    global _db_pool
    _db_pool = pool


async def _load_error(language: str, code: str) -> JSONResponse:
    return JSONResponse(status_code=500, content={
        "error": code,
        "message": await t(_db_pool, language, ROUTERS[code]),
    })


@router.get("/api/languages")
async def get_languages(request: Request):
    viewer = request.query_params.get("viewer") or "en"
    try:
        async with _db_pool.acquire() as conn:
            rows = await conn.fetch('SELECT DISTINCT language FROM "Translation"')
        codes = [r["language"] for r in rows]
        if "en" not in codes:
            codes.append("en")
        codes.sort()

        async with _db_pool.acquire() as conn:
            name_rows = await conn.fetch(
                'SELECT key, value, language FROM "Translation" '
                "WHERE key LIKE 'language.name.%' AND language = ANY($1)",
                codes + [viewer],
            )

        viewer_names = {}
        native_names = {}
        for row in name_rows:
            lang_code = row["key"].replace("language.name.", "")
            if row["language"] == viewer:
                viewer_names[lang_code] = row["value"]
            if row["language"] == lang_code:
                native_names[lang_code] = row["value"]

        result = []
        for code in codes:
            native = native_names.get(code) or viewer_names.get(code) or code.upper()
            if code == viewer:
                result.append({"code": code, "name": native})
            else:
                localized = viewer_names.get(code)
                name = f"{localized} ({native})" if localized else native
                result.append({"code": code, "name": name})

        return result
    except Exception:
        return await _load_error(viewer, "api.languages_load_error")


@router.get("/api/translations")
async def get_translations(request: Request):
    language = request.query_params.get("language") or "en"
    try:
        async with _db_pool.acquire() as conn:
            rows = await conn.fetch(
                'SELECT key, value FROM "Translation" WHERE language = $1', language
            )

        result = {row["key"]: row["value"] for row in rows}
        return JSONResponse(content=result)
    except Exception:
        return await _load_error(language, "api.translations_load_error")
