#!/usr/bin/env python3
"""workbench-seed.py — idempotent bootstrap of a fresh Workbench database.

A Python port of ``workbench-go/cmd/workbench-seed`` (which itself ports the
deleted ``frontend/prisma/seed.ts``). It seeds the minimum a fresh schema needs
before the application can be used:

  1. ``GlobalSettings``  — the single row (id = 1), with the welcome message
  2. ``UserGroup``       — 100 rows, "00" (Default) through "99" (unused)
  3. ``User``            — the admin and example accounts
  4. ``AIProvider``      — the four active providers, all enabled
  5. ``VisualizationType`` — the ten built-in chart types

Every step is idempotent: each statement conflicts on the schema's own unique
index, so a second run changes nothing. The whole bootstrap runs in ONE
transaction, so a failure leaves the database exactly as it was found.

NOT seeded, deliberately: ``ProviderModel``. It held a catalogue keyed by
provider code, which cannot say which server served a model. The table is
dropped by migration ``0019_drop_provider_model``, and a seeder still writing to
it would fail on the first install after that migration. What a connection
serves is discovered from the server itself
(``POST /api/user/ai-connections/{id}/models/discover``).

Usage
-----
    python3 scripts/workbench-seed.py [--version] [--help]

Reads ``DATABASE_URL`` from the environment. If it is unset, ``backend/.env``
and then the repository-root ``.env`` are consulted, so the script works from a
checkout without exporting anything.

Requires ``psycopg2-binary`` and ``bcrypt`` — both in ``backend/requirements.txt``.
"""

from __future__ import annotations

import argparse
import os
import sys
import uuid
from pathlib import Path
from urllib.parse import urlparse

PROGRAM = "workbench-seed.py"
VERSION = "1.0.0"

#: Same text the Go program seeds. Backfilled on re-seed only when the stored
#: value is NULL or empty, so an administrator's own welcome is never replaced.
DEFAULT_WELCOME = """Welcome to the Statisticians Workbench

Your installed administrator login is:

admin@example.com / admin123

You should change the password and register a real email user,
then promote that user to be your live administrator"""

#: The four providers that remain after the "reduce AI providers" change.
#: (code, name, is_local, requires_api_key, default_endpoint)
PROVIDERS = (
    ("deepseek", "DeepSeek", False, True, "https://api.deepseek.com/v1"),
    ("openrouter", "OpenRouter", False, True, "https://openrouter.ai/api/v1"),
    ("ollama-local", "Ollama (Local)", True, False, "http://localhost:11434"),
    ("ollama-remote", "Ollama (Remote)", False, True, "https://api.ollama.com/v1"),
)


# ---------------------------------------------------------------------------
# Visualization types — ten built-ins, each with the three JSON documents the
# renderer reads. Transcribed from the Go source rather than re-invented, so a
# client sees the identical schemas whichever seeder built the database.
# ---------------------------------------------------------------------------
VISUALIZATION_TYPES = (
    {
        "name": "Text Table",
        "slug": "text_table",
        "description": "A simple text table of data",
        "inputSchema": {
            "type": "object",
            "properties": {
                "columns": {"type": "array", "items": {"type": "string"}},
                "rows": {"type": "array", "items": {"type": "array"}},
            },
            "required": ["columns", "rows"],
        },
        "parameterSchema": {
            "type": "object",
            "properties": {
                "title": {"type": "string"},
                "striped": {"type": "boolean", "default": True},
            },
        },
        "defaultParameters": {"title": "Data Table", "striped": True},
    },
    {
        "name": "Bar Chart",
        "slug": "bar_chart",
        "description": "A bar chart for categorical data",
        "inputSchema": {
            "type": "object",
            "properties": {
                "labels": {"type": "array", "items": {"type": "string"}},
                "values": {"type": "array", "items": {"type": "number"}},
            },
            "required": ["labels", "values"],
        },
        "parameterSchema": {
            "type": "object",
            "properties": {
                "title": {"type": "string"},
                "colors": {"type": "array", "items": {"type": "string"}},
                "showLegend": {"type": "boolean", "default": False},
            },
        },
        "defaultParameters": {
            "title": "Bar Chart",
            "colors": ["#3b82f6"],
            "showLegend": False,
        },
    },
    {
        "name": "Pie Chart",
        "slug": "pie_chart",
        "description": "A pie chart showing proportions",
        "inputSchema": {
            "type": "object",
            "properties": {
                "labels": {"type": "array", "items": {"type": "string"}},
                "values": {"type": "array", "items": {"type": "number"}},
            },
            "required": ["labels", "values"],
        },
        "parameterSchema": {
            "type": "object",
            "properties": {
                "title": {"type": "string"},
                "showLegend": {"type": "boolean", "default": True},
            },
        },
        "defaultParameters": {"title": "Pie Chart", "showLegend": True},
    },
    {
        "name": "Line Chart",
        "slug": "line_chart",
        "description": "A line chart for trends",
        "inputSchema": {
            "type": "object",
            "properties": {
                "labels": {"type": "array", "items": {"type": "string"}},
                "datasets": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "label": {"type": "string"},
                            "data": {"type": "array", "items": {"type": "number"}},
                        },
                    },
                },
            },
            "required": ["labels", "datasets"],
        },
        "parameterSchema": {
            "type": "object",
            "properties": {
                "title": {"type": "string"},
                "showLegend": {"type": "boolean", "default": True},
            },
        },
        "defaultParameters": {"title": "Line Chart", "showLegend": True},
    },
    {
        "name": "Scatter Plot",
        "slug": "scatter_plot",
        "description": "A scatter plot for correlation analysis",
        "inputSchema": {
            "type": "object",
            "properties": {
                "x": {"type": "array", "items": {"type": "number"}},
                "y": {"type": "array", "items": {"type": "number"}},
            },
            "required": ["x", "y"],
        },
        "parameterSchema": {
            "type": "object",
            "properties": {
                "title": {"type": "string"},
                "markerSize": {"type": "number", "default": 6},
                "markerColor": {"type": "string", "default": "#3b82f6"},
                "showLegend": {"type": "boolean", "default": False},
            },
        },
        "defaultParameters": {
            "title": "Scatter Plot",
            "markerSize": 6,
            "markerColor": "#3b82f6",
            "showLegend": False,
        },
    },
    {
        "name": "Area Chart",
        "slug": "area_chart",
        "description": "An area chart for cumulative trends",
        "inputSchema": {
            "type": "object",
            "properties": {
                "labels": {"type": "array", "items": {"type": "string"}},
                "datasets": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "label": {"type": "string"},
                            "data": {"type": "array", "items": {"type": "number"}},
                        },
                    },
                },
            },
            "required": ["labels", "datasets"],
        },
        "parameterSchema": {
            "type": "object",
            "properties": {
                "title": {"type": "string"},
                "fillOpacity": {"type": "number", "default": 0.3},
                "lineColor": {"type": "string", "default": "#3b82f6"},
                "showLegend": {"type": "boolean", "default": True},
            },
        },
        "defaultParameters": {
            "title": "Area Chart",
            "fillOpacity": 0.3,
            "lineColor": "#3b82f6",
            "showLegend": True,
        },
    },
    {
        "name": "Horizontal Bar",
        "slug": "horizontal_bar",
        "description": "A horizontal bar chart for long category labels",
        "inputSchema": {
            "type": "object",
            "properties": {
                "labels": {"type": "array", "items": {"type": "string"}},
                "values": {"type": "array", "items": {"type": "number"}},
            },
            "required": ["labels", "values"],
        },
        "parameterSchema": {
            "type": "object",
            "properties": {
                "title": {"type": "string"},
                "barColor": {"type": "string", "default": "#3b82f6"},
                "showLegend": {"type": "boolean", "default": False},
            },
        },
        "defaultParameters": {
            "title": "Horizontal Bar",
            "barColor": "#3b82f6",
            "showLegend": False,
        },
    },
    {
        "name": "Donut Chart",
        "slug": "donut_chart",
        "description": "A donut chart showing proportions with a centre hole",
        "inputSchema": {
            "type": "object",
            "properties": {
                "labels": {"type": "array", "items": {"type": "string"}},
                "values": {"type": "array", "items": {"type": "number"}},
            },
            "required": ["labels", "values"],
        },
        "parameterSchema": {
            "type": "object",
            "properties": {
                "title": {"type": "string"},
                "holeSize": {"type": "number", "default": 0.4},
                "showLegend": {"type": "boolean", "default": True},
            },
        },
        "defaultParameters": {
            "title": "Donut Chart",
            "holeSize": 0.4,
            "showLegend": True,
        },
    },
    {
        "name": "Histogram",
        "slug": "histogram",
        "description": "A histogram showing frequency distribution",
        "inputSchema": {
            "type": "object",
            "properties": {"values": {"type": "array", "items": {"type": "number"}}},
            "required": ["values"],
        },
        "parameterSchema": {
            "type": "object",
            "properties": {
                "title": {"type": "string"},
                "binCount": {"type": "number", "default": 20},
                "barColor": {"type": "string", "default": "#3b82f6"},
                "showLegend": {"type": "boolean", "default": False},
            },
        },
        "defaultParameters": {
            "title": "Histogram",
            "binCount": 20,
            "barColor": "#3b82f6",
            "showLegend": False,
        },
    },
    {
        "name": "Distribution",
        "slug": "distribution",
        "description": "A violin/box plot showing data distribution",
        "inputSchema": {
            "type": "object",
            "properties": {
                "values": {"type": "array", "items": {"type": "number"}},
                "groups": {"type": "array", "items": {"type": "string"}},
            },
            "required": ["values"],
        },
        "parameterSchema": {
            "type": "object",
            "properties": {
                "title": {"type": "string"},
                "plotType": {
                    "type": "string",
                    "enum": ["violin", "box"],
                    "default": "violin",
                },
                "showLegend": {"type": "boolean", "default": True},
            },
        },
        "defaultParameters": {
            "title": "Distribution",
            "plotType": "violin",
            "showLegend": True,
        },
    },
)


# ---------------------------------------------------------------------------
# Environment
# ---------------------------------------------------------------------------


def repo_root() -> Path:
    """The repository root — this file lives in ``scripts/``."""
    return Path(__file__).resolve().parent.parent


def load_database_url() -> str:
    """``DATABASE_URL`` from the environment, else from an ``.env`` file.

    Checked in order: the environment, ``backend/.env``, then the
    repository-root ``.env``. Mirrors the Go program's godotenv fallback, with
    the backend's own file first because that is where this repository keeps
    the DSN.
    """
    url = os.environ.get("DATABASE_URL", "").strip()
    if url:
        return url

    try:
        from dotenv import load_dotenv
    except ImportError:
        return ""

    for candidate in (repo_root() / "backend" / ".env", repo_root() / ".env"):
        if candidate.is_file():
            load_dotenv(candidate, override=False)
            url = os.environ.get("DATABASE_URL", "").strip()
            if url:
                return url
    return ""


def cluster_label(dsn: str) -> str:
    """``host:port`` from the DSN, as the Go program's ClusterLabel reports it.

    Parsed rather than queried, so the label is available even when the database
    is unreachable — which is exactly when it is most useful.
    """
    if not dsn:
        return "unknown (no DATABASE_URL)"
    try:
        parsed = urlparse(dsn)
    except ValueError:
        return "unknown (unparseable DATABASE_URL)"
    if not parsed.hostname:
        return "unknown (no host in DATABASE_URL)"
    return f"{parsed.hostname}:{parsed.port or 5432}"


# ---------------------------------------------------------------------------
# Seed steps — each takes a cursor and runs inside the caller's transaction
# ---------------------------------------------------------------------------


def seed_global_settings(cur) -> None:
    """Insert the single GlobalSettings row; backfill the welcome if empty.

    ``ON CONFLICT ... DO UPDATE ... WHERE welcome IS NULL OR welcome = ''`` is
    the whole subtlety: re-running must not overwrite a welcome an
    administrator has customised, but a row left blank by an older seed should
    still be filled.
    """
    print("Seeding global settings...")
    cur.execute(
        """
        INSERT INTO "GlobalSettings" (
            id, "demoMode", "maxRegistrations", "emailVerificationTimeout",
            "emailSender", "publicUrl", "registrationGracePeriodHours", welcome,
            "passwordPolicy", "defaultMaxUploadSizeMB", "defaultMaxUploadCount",
            "updatedAt"
        ) VALUES (
            1, true, NULL, 24, 'no-reply@replace-with-your-domain',
            'https://replace-with-your-external-host-name', 24, %s,
            'medium', 5, 5, NOW()
        )
        ON CONFLICT (id) DO UPDATE SET
            welcome = EXCLUDED.welcome
        WHERE "GlobalSettings".welcome IS NULL OR "GlobalSettings".welcome = ''
        """,
        (DEFAULT_WELCOME,),
    )


def seed_user_groups(cur) -> None:
    """The 100 groups ``00``–``99``; ``00`` is Default, the rest unused."""
    print("Seeding user groups...")
    sql = """
        INSERT INTO "UserGroup" (id, "groupId", "groupDescription", "updatedAt")
        VALUES (%s, %s, %s, NOW())
        ON CONFLICT ("groupId") DO NOTHING
    """
    for i in range(100):
        cur.execute(
            sql,
            (str(uuid.uuid4()), f"{i:02d}", "Default" if i == 0 else "unused"),
        )
    print("User groups seeded (00-99)")


def seed_providers(cur) -> None:
    """The four active AI providers, all enabled."""
    print("Seeding AI providers...")
    sql = """
        INSERT INTO "AIProvider" (
            code, name, "isLocal", "requiresApiKey", "defaultEndpoint",
            enabled, "updatedAt"
        ) VALUES (%s, %s, %s, %s, %s, true, NOW())
        ON CONFLICT (code) DO NOTHING
    """
    for code, name, is_local, requires_api_key, endpoint in PROVIDERS:
        cur.execute(sql, (code, name, is_local, requires_api_key, endpoint))
    print("AI providers seeded")


def seed_users(cur) -> None:
    """The admin and example accounts.

    Passwords are hashed with bcrypt cost 10 — the same cost the Python backend
    uses (``bcrypt.gensalt(rounds=10)``), so they verify against the algorithm
    the login handler actually checks.

    Both accounts are created if missing and left entirely alone once present.

    The admin's ``ON CONFLICT`` clause used to pin ``userGroup`` back to ``"00"``
    on every re-run, on the reasoning that a re-seed should leave the admin in
    the Default group. That is wrong for a seeder the package runs from postinst
    on every upgrade: an administrator deliberately moved to another group was
    silently moved back, and nothing reported it. A seeder creates what is
    missing; it does not overrule a decision somebody made about an existing row.
    """
    import bcrypt

    print("Seeding users...")

    admin_hash = bcrypt.hashpw(b"admin123", bcrypt.gensalt(rounds=10)).decode("utf-8")
    cur.execute(
        """
        INSERT INTO "User" (
            id, email, password, name, "isAdmin", "isGroupAdmin", "isExampleUser",
            "emailVerified", "maxUploadSizeMB", "maxUploadCount", "userGroup",
            language, "emailNotifications", "darkMode", "updatedAt"
        ) VALUES (
            %s, %s, %s, %s, true, false, false, NOW(), 0, 0, '00',
            'en', false, false, NOW()
        )
        ON CONFLICT (email) DO NOTHING
        """,
        (str(uuid.uuid4()), "admin@example.com", admin_hash, "Admin User"),
    )

    example_hash = bcrypt.hashpw(b"User1234#", bcrypt.gensalt(rounds=10)).decode("utf-8")
    cur.execute(
        """
        INSERT INTO "User" (
            id, email, password, name, "isAdmin", "isGroupAdmin", "isExampleUser",
            "emailVerified", "maxUploadSizeMB", "maxUploadCount", "userGroup",
            language, "emailNotifications", "darkMode", "updatedAt"
        ) VALUES (
            %s, %s, %s, %s, false, false, true, NOW(), 50, 10, '01',
            'en', false, false, NOW()
        )
        ON CONFLICT (email) DO NOTHING
        """,
        (
            str(uuid.uuid4()),
            "exampleuser@example.com",
            example_hash,
            "Example User",
        ),
    )

    print("Users seeded (admin@example.com, exampleuser@example.com)")


def seed_visualization_types(cur) -> None:
    """The ten built-in types, upserted by slug.

    ``DO UPDATE`` rather than ``DO NOTHING``: the schemas are code, and a
    corrected schema must reach a database seeded by an older version of this
    script. Only the definition is replaced — a row's identity and any column
    not named here are left as they are.
    """
    from psycopg2.extras import Json

    print("Seeding visualization types...")
    sql = """
        INSERT INTO "VisualizationType" (
            name, slug, description, renderer, "inputSchema",
            "parameterSchema", "defaultParameters", enabled,
            "createdAt", "updatedAt"
        ) VALUES (%s, %s, %s, 'client', %s, %s, %s, true, NOW(), NOW())
        ON CONFLICT (slug) DO UPDATE SET
            name = EXCLUDED.name,
            description = EXCLUDED.description,
            "inputSchema" = EXCLUDED."inputSchema",
            "parameterSchema" = EXCLUDED."parameterSchema",
            "defaultParameters" = EXCLUDED."defaultParameters",
            renderer = EXCLUDED.renderer,
            enabled = EXCLUDED.enabled,
            "updatedAt" = NOW()
    """
    for viz in VISUALIZATION_TYPES:
        cur.execute(
            sql,
            (
                viz["name"],
                viz["slug"],
                viz["description"],
                Json(viz["inputSchema"]),
                Json(viz["parameterSchema"]),
                Json(viz["defaultParameters"]),
            ),
        )
    print("Visualization types seeded")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def seed() -> int:
    """Run the whole bootstrap in one transaction. Returns a process exit code.

    One transaction, not five: a half-seeded database is worse than an empty
    one, because the application can start against it and fail somewhere far
    from the cause. Any exception rolls the lot back.
    """
    try:
        import psycopg2
    except ImportError:
        print(
            "workbench-seed: psycopg2 is not installed.\n"
            "  Install the backend requirements: "
            "backend/venv/bin/pip install -r backend/requirements.txt",
            file=sys.stderr,
        )
        return 1

    database_url = load_database_url()
    if not database_url:
        print(
            "workbench-seed: DATABASE_URL is not set, and no .env was found "
            "in backend/ or the repository root.",
            file=sys.stderr,
        )
        return 1

    print(f"Workbench database cluster: {cluster_label(database_url)}")

    try:
        conn = psycopg2.connect(database_url)
    except Exception as exc:  # connection refused, bad password, no such db
        print(f"Seed failed: could not connect: {exc}", file=sys.stderr)
        return 1

    try:
        with conn:  # commits on success, rolls back on any exception
            with conn.cursor() as cur:
                seed_global_settings(cur)
                seed_user_groups(cur)
                seed_users(cur)
                seed_providers(cur)
                seed_visualization_types(cur)
    except Exception as exc:
        print(f"Seed failed: {exc}", file=sys.stderr)
        return 1
    finally:
        conn.close()

    print("Workbench database seeded.")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog=PROGRAM,
        description=(
            "Idempotently seed a fresh Workbench database with bootstrap data: "
            "global settings, 100 user groups, the admin and example users, "
            "the AI providers, and the built-in visualization types."
        ),
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"{PROGRAM} {VERSION}",
    )
    parser.parse_args(argv)
    return seed()


if __name__ == "__main__":
    sys.exit(main())
