#!/usr/bin/env python3
"""Reconcile newly-backfilled "createdAt" columns (companion to migration 0006).

After 0006 added "createdAt" (NOT NULL DEFAULT CURRENT_TIMESTAMP) to tables that
already carried a historical "updatedAt", every pre-existing row got its createdAt
stamped with the migration-time "now" — later than its real updatedAt. This script
repairs that contradiction: for each row where updatedAt < createdAt, it sets
createdAt = updatedAt (the best available lower-bound estimate of creation time).

Scope: the three Category-C tables only (Translation, GlobalSettings,
user_audio_presets) — the tables that gained a createdAt while already having an
updatedAt. Category B (gained updatedAt) and Category D (gained both) are untouched.

Idempotent: after the fix createdAt == updatedAt, so the predicate is false on re-run.

Run with the backend venv (asyncpg):  backend/venv/bin/python db/migrations/0006_reconcile_timestamps.py
"""

import asyncio
import re
from pathlib import Path

import asyncpg

TABLES = ("Translation", "GlobalSettings", "user_audio_presets")

REPO_ROOT = Path(__file__).resolve().parents[2]
ENV_PATH = REPO_ROOT / "backend" / ".env"


def read_database_url() -> str:
    text = ENV_PATH.read_text()
    match = re.search(r'^\s*DATABASE_URL\s*=\s*["\']?([^"\'\s]+)["\']?\s*$', text, re.M)
    if not match:
        raise SystemExit("DATABASE_URL not found in backend/.env")
    return match.group(1)


async def reconcile() -> None:
    dsn = read_database_url()
    conn = await asyncpg.connect(dsn)
    try:
        async with conn.transaction():
            for table in TABLES:
                quoted = f'"{table}"'
                before = await conn.fetchval(
                    f'SELECT count(*) FROM {quoted} WHERE "updatedAt" < "createdAt"'
                )
                status = await conn.execute(
                    f'UPDATE {quoted} SET "createdAt" = "updatedAt" '
                    f'WHERE "updatedAt" < "createdAt"'
                )
                # asyncpg returns "UPDATE <n>"; the trailing token is the row count.
                updated = int(str(status).rsplit(" ", 1)[-1])
                print(f"{table}: {before} rows had updatedAt < createdAt; {updated} corrected")
    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(reconcile())
