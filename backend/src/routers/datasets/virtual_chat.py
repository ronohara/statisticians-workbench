"""
Virtual Dataset Chatbot – State-machine-guided AI conversation for creating
PostgreSQL federated SQL join views.
"""

import json
import logging
from typing import Any, Dict, Optional
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from src.chat.connection import get_connection_details
from src.utils.timestamps import iso_utc
from src.chat.tool_agent import ToolAgent
from src.utils.connection_timeouts import resolve_connection_timeouts
from src.routers.datasets.crud import get_user_id_from_token, get_current_language, get_connection_row
from src.utils.translation import t
from src.utils.encryption import decrypt_field
from src.routers.common.translations import CHAT
from .translations import DATASETS, virtual_decision_applied, virtual_decision_no_reply
from .virtual_tools import VIRTUAL_REGISTRY, register_all_tools
from .virtual_scoreboard import (
    ScoreboardInputs,
    compute_virtual_scoreboard,
    decided_counts,
)
from .connection_probe import PROBE_UNKNOWN, probe_many
from .virtual_chat_state import (
    apply_source_selection,
    merge_context_keys,
    link_saved_dataset,
    merge_draft_pieces,
    merge_introspected_table,
    toggle_output_column,
)

_db_pool = None

def set_db_pool(pool):
    global _db_pool
    _db_pool = pool

router = APIRouter(prefix="/virtual/chat", tags=["virtual-chat"])
security = HTTPBearer()

register_all_tools()

async def _auto_introspect_if_mentioned(user_message: str, context_data: dict, user_id: str, language: str = "en") -> dict:
    """
    If the user mentions a database table by name, auto-introspect it.
    Looks for patterns like 'patients table', 'researchdata.patients', or just
    mentioning a connection name alongside a likely table name.
    """
    import re
    message_lower = user_message.lower()
    conns = context_data.get("availableSources", {}).get("databaseConnections", [])
    introspected = context_data.get("introspectedTables", {})

    # Extract potential table names from message
    stopwords = {
        "i", "want", "to", "know", "which", "have", "the", "a", "an", "is", "are",
        "high", "low", "blood", "pressure", "show", "me", "in", "on", "from", "with",
        "look", "up", "introspect", "hello", "help", "can", "you", "what", "my", "data",
        # Common English words that should never be treated as table/connection names
        "it", "for", "of", "be", "not", "this", "that", "but", "or", "and", "if", "so",
        "at", "by", "do", "we", "he", "she", "they", "all", "no", "yes", "just", "like",
        "about", "get", "out", "would", "could", "should", "how", "will", "one", "two",
        "has", "had", "was", "were", "been", "very", "more", "some", "any", "each", "than",
        "also", "there", "here", "over", "see", "use", "need", "make", "made", "first",
        "most", "popular", "model", "type", "kind", "best", "top", "common", "available",
        "list", "find", "give", "tell", "does", "mean", "different", "only", "other",
        "who", "why", "where", "when", "much", "many", "few", "into", "down", "back",
        "please", "well", "still", "now", "then", "these", "those", "something", "thing",
        "way", "after", "before", "between", "because", "example", "sample", "based",
        "used", "bike", "car", "sale", "sales", "customer", "product", "order",
        # Domain nouns that are topics, not table names (matching happens via connection name/database, not these)
    }
    words = re.findall(r'[a-z_][a-z0-9_]*', message_lower)
    potential_tables = [w for w in words if w not in stopwords and len(w) > 2]

    MAX_INTROSPECTS = 6
    count = 0

    # Check if user mentioned a connection name or database name (fuzzy match)
    import difflib
    for conn in conns:
        conn_name_lower = conn["name"].lower()
        conn_db_lower = (conn.get("database") or "").lower()
        conn_words = conn_name_lower.split()
        # Match if ANY word of the connection name appears in the message,
        # or if a message word is a substring of a connection word (e.g. "bike" matches "bikestore")
        message_words = re.findall(r'[a-z_][a-z0-9_]*', message_lower)
        is_match = any(w in message_lower for w in conn_words)
        if not is_match:
            is_match = any(
                mw in cnw or cnw in mw
                for mw in message_words for cnw in (conn_words + [conn_db_lower])
                if len(mw) >= 3 and len(cnw) >= 3
            )
        if not is_match:
            for word in words:
                if len(word) < 3:
                    continue
                name_matches = difflib.get_close_matches(word, [conn_name_lower.replace(" ", "")], n=1, cutoff=0.70)
                db_matches = difflib.get_close_matches(word, [conn_db_lower], n=1, cutoff=0.70) if conn_db_lower else []
                if name_matches or db_matches:
                    is_match = True
                    import logging
                    logging.getLogger(__name__).info(f"Fuzzy match: '{word}' → connection '{conn['name']}'")
                    break
        if is_match:
            try:
                tables = await _suggest_tables(conn["connectionId"], "", user_id=user_id, language=language)
                if tables:
                    introspected[conn["name"]] = {
                        "connectionName": conn["name"],
                        "availableTables": tables,
                    }
                    context_data["introspectedTables"] = introspected
                    import logging
                    logging.getLogger(__name__).info(f"Listed tables for connection '{conn['name']}': {tables}")
                    # Sort tables by priority: common important table names first
                    _PRIORITY = {
                        "products": 10, "orders": 9, "customers": 8, "sales": 7,
                        "order_items": 6, "transactions": 5, "items": 4,
                        "inventory": 3, "employees": 2, "staffs": 1, "stores": 1,
                    }
                    def _table_score(tbl_name: str) -> int:
                        return _PRIORITY.get(tbl_name.lower(), 0)
                    sorted_tables = sorted(tables, key=_table_score, reverse=True)
                    # Introspect top tables so the LLM has real column data
                    for tbl in sorted_tables[:5]:
                        if count >= MAX_INTROSPECTS:
                            break
                        try:
                            await _introspect_and_store(
                                conn["connectionId"], tbl, conn, user_id, context_data, language
                            )
                            count += 1
                            import logging
                            logging.getLogger(__name__).info(
                                f"Introspected matched connection table: {conn['name']}.{tbl}"
                            )
                        except Exception as intro_ex:
                            import logging
                            logging.getLogger(__name__).warning(
                                f"Matched-connection introspect failed: {conn['name']}.{tbl}: {intro_ex}"
                            )
            except Exception:
                pass

    for conn in conns:
        conn_id = conn["connectionId"]
        if count >= MAX_INTROSPECTS:
            break

        for table_candidate in potential_tables[:2]:  # Top 2 candidates per connection
            key = f"connection_{conn_id}_{table_candidate}"
            if key in introspected:
                continue
            if count >= MAX_INTROSPECTS:
                break

            try:
                await _introspect_and_store(conn_id, table_candidate, conn, user_id, context_data, language)
                introspected = context_data.get("introspectedTables", {})
                count += 1
            except Exception as e:
                # Log failure so it's debuggable
                import logging
                logging.getLogger(__name__).warning(
                    f"Auto-introspect failed: {conn['name']}.{table_candidate}: {e}"
                )
                # Do NOT store failures in context_data — avoids feeding noise to the LLM.
                # The warning log above is sufficient for debugging.

    return context_data


async def _suggest_tables(conn_id: int, table_name: str, user_id: str, language: str = "en") -> list:
    """List tables in a database and find close matches for a typo."""
    import difflib
    import logging

    full_row = await get_connection_row(conn_id, user_id, language)
    if full_row is None:
        return []

    try:
        decrypted_password = decrypt_field(full_row["password"])
    except Exception:
        decrypted_password = full_row["password"]

    all_tables = []

    if full_row["type"] == "postgresql":
        import asyncpg
        pg_conn = await asyncpg.connect(
            host=full_row["host"], port=full_row["port"],
            database=full_row["database"],
            user=full_row["username"], password=decrypted_password,
            timeout=10
        )
        try:
            rows = await pg_conn.fetch(
                "SELECT table_schema, table_name FROM information_schema.tables WHERE table_schema NOT IN ('pg_catalog', 'information_schema') ORDER BY table_name"
            )
            all_tables = [r["table_name"] for r in rows]
        finally:
            await pg_conn.close()
    elif full_row["type"] == "mysql":
        from .browse import _discover_mysql
        all_tables = [d["name"] for d in await _discover_mysql(full_row, decrypted_password)]
    elif full_row["type"] == "mssql":
        from .browse import _discover_mssql
        all_tables = [d["name"] for d in await _discover_mssql(full_row, decrypted_password)]
    elif full_row["type"] == "access":
        from .browse import _discover_access
        all_tables = [d["name"] for d in await _discover_access(full_row, decrypted_password)]

    if table_name:
        matches = difflib.get_close_matches(table_name.lower(), [t.lower() for t in all_tables], n=3, cutoff=0.6)
        if matches:
            logging.getLogger(__name__).info(f"Typo suggestion for '{table_name}': {matches}")
        return matches
    else:
        # Empty table_name = list all tables (used by connection matching)
        return all_tables


async def _introspect_and_store(conn_id: int, table_name: str, conn_row: dict, user_id: str, context_data: dict, language: str = "en"):
    """Introspect a single table and store in context. Raises on failure."""
    import logging
    db_type = conn_row.get("type", "unknown")
    logging.getLogger(__name__).info(f"Introspecting: {conn_row.get('name', '?')}.{table_name} ({db_type})")

    # Fetch full connection credentials (routed through the core).
    full_row = await get_connection_row(conn_id, user_id, language)
    if full_row is None:
        raise ValueError(f"Connection {conn_id} not found")

    # Decrypt the stored password (database stores encrypted passwords)
    try:
        decrypted_password = decrypt_field(full_row["password"])
    except Exception:
        decrypted_password = full_row["password"]

    if db_type == "postgresql":
        import asyncpg
        pg_conn = await asyncpg.connect(
            host=full_row["host"], port=full_row["port"],
            database=full_row["database"],
            user=full_row["username"], password=decrypted_password,
            timeout=10
        )
        try:
            parts = table_name.split(".", 1)
            schema = parts[0] if len(parts) > 1 else "public"
            tbl = parts[1] if len(parts) > 1 else parts[0]
            rows = await pg_conn.fetch(
                "SELECT column_name, data_type FROM information_schema.columns WHERE table_schema = $1 AND table_name = $2 ORDER BY ordinal_position",
                schema, tbl
            )
            if not rows:
                raise ValueError(f"Table '{tbl}' not found in schema '{schema}'")
            columns = [{"name": r["column_name"], "type": r["data_type"]} for r in rows]
        finally:
            await pg_conn.close()
    elif db_type == "mysql":
        from .browse import _columns_mysql
        cols = await _columns_mysql(full_row, decrypted_password, table_name)
        if not cols:
            raise ValueError(f"Table '{table_name}' not found")
        columns = [{"name": c["name"], "type": c["type"]} for c in cols]
    elif db_type == "mssql":
        from .browse import _columns_mssql
        cols = await _columns_mssql(full_row, decrypted_password, table_name)
        if not cols:
            raise ValueError(f"Table '{table_name}' not found")
        columns = [{"name": c["name"], "type": c["type"]} for c in cols]
    elif db_type == "access":
        from .browse import _columns_access
        cols = await _columns_access(full_row, decrypted_password, table_name)
        if not cols:
            raise ValueError(f"Table '{table_name}' not found")
        columns = [{"name": c["name"], "type": c["type"]} for c in cols]
    else:
        raise ValueError(f"Unsupported connection type: {db_type}")

    introspected = context_data.get("introspectedTables", {})
    key = f"connection_{conn_id}_{table_name}"
    introspected[key] = {
        "connectionId": conn_id,
        "connectionName": full_row["name"],
        "tableName": table_name,
        "type": db_type,
        "columns": columns,
    }
    context_data["introspectedTables"] = introspected


async def fetch_available_sources(db_pool, user_id: str, language: str = "en") -> dict:
    """Every dataset and database connection the caller may read — nothing cut.

    Shared by the AI ``get_sources`` and ``find_sources`` tools.

    **This used to carry a ``LIMIT 50`` and nothing said the list was cut.** The
    design (§6.3) condemns exactly that: a cap keeps the wrong half (newest-first
    drops the oldest, which is what a returning user built), and the truncation is
    silent, so a user asking about a dropped dataset is asking about something the
    assistant does not know it cannot see. The tree never had this problem because
    it reads ``GET /api/datasets`` and paginates nothing — it simply lists.

    What replaces the cap is the truth: every row, plus ``totalDatasets`` so a
    caller can see the size it is being handed, and ``excludedVirtual`` because
    virtual datasets are filtered out here and that should be a number rather
    than an absence.

    **Tables are not here, deliberately.** Listing them means opening every
    connection the account owns against external servers, which is a cost the
    tree does not pay either — it fetches a connection's tables when the reader
    expands it (``GET /api/datasets/browse/{connection_id}``). ``get_tables`` is
    the same door, and ``find_sources`` uses it.
    """
    datasets = []
    connections = []

    async with db_pool.acquire() as conn:
        # User's own datasets + shared datasets
        rows = await conn.fetch(
            """
            SELECT id, name, "sourceType", "storageType", "tableName",
                   "originalFileName", "databaseName", "userId",
                   (CASE WHEN "userId" = $1 THEN true ELSE false END) as "isOwn"
            FROM "UserDataset"
            WHERE "userId" = $1 OR ("isShared" = true AND "datasetGroup" IN (
                SELECT "userGroup" FROM "User" WHERE id = $1
            ))
            ORDER BY "createdAt" DESC
            """,
            user_id
        )
        excluded_virtual = 0
        for r in rows:
            # Virtual datasets are output artifacts, not input sources — so they
            # are excluded. Counted rather than vanished: an absence the caller
            # cannot see is what §6.3 objects to.
            if r["sourceType"] == "virtual":
                excluded_virtual += 1
                continue
            entry = {
                "id": r["id"],
                "name": r["name"],
                "sourceType": r["sourceType"],
                "storageType": r["storageType"],
                "tableName": r["tableName"],
                "isOwn": r["isOwn"],
                "columns": None,
            }
            datasets.append(entry)

        # Database connections
        conn_rows = await conn.fetch(
            """
            SELECT "connectionId", name, type, host, port, database,
                   (CASE WHEN "userId" = $1 THEN true ELSE false END) as "isOwn"
            FROM "UserDatabaseConnection"
            WHERE "userId" = $1 OR ("isShared" = true AND "dbConnectionGroup" IN (
                SELECT "userGroup" FROM "User" WHERE id = $1
            ))
            """,
            user_id
        )
        # Probe state, so a listing does not imply every connection is usable.
        #
        # Without this the model read "thirteen connections" as "thirteen I can
        # use", and discovered otherwise one call at a time — six wasted calls and
        # two invented dataset ids in the session that prompted this.
        #
        # Eager, cached and parallel: any connection whose stored answer is older
        # than PROBE_TTL_SECONDS is re-probed, at most PROBE_CONCURRENCY at once.
        # A dead host costs one deadline rather than one per connection.
        try:
            probes = await probe_many(
                db_pool, user_id, language,
                [r["connectionId"] for r in conn_rows],
            )
        except Exception as exc:  # noqa: BLE001 — a listing must survive a probe failure
            logging.getLogger(__name__).warning(
                "connection probe sweep failed; listing without state: %s", exc
            )
            probes = {}

        for r in conn_rows:
            probe = probes.get(r["connectionId"])
            # `unknown` is never stored — it is the absence of a fresh claim. A
            # row that has never been probed and one whose probe has expired read
            # the same way, and both invite a probe rather than forbidding one.
            state = probe.state if probe is not None else PROBE_UNKNOWN
            connections.append({
                "connectionId": r["connectionId"],
                "name": r["name"],
                "type": r["type"],
                "database": r["database"],
                "isOwn": r["isOwn"],
                "state": state,
                "detail": (probe.detail if probe is not None else None),
            })

    return {
        "datasets": datasets,
        "databaseConnections": connections,
        # The size of what was returned, so a caller can tell a short list from a
        # cut one — the distinction the old LIMIT 50 destroyed.
        "totalDatasets": len(datasets),
        "excludedVirtual": excluded_virtual,
        # Where tables live: one call away, per connection, exactly as the tree
        # fetches them. Said in the response so the model does not conclude that a
        # connection has no tables merely because none are listed here.
        "tablesHint": "Call get_tables with a connectionId to list that connection's tables.",
    }


async def _resolve_scoreboard_texts(scoreboard: dict, context_data: dict, language: str) -> dict:
    """Fill each pending entry's `whatText` from its declared key, through `t()`.

    The scoreboard is a pure function and emits a KEY, not a sentence — the key is
    what `_key()` returns from the module's declaration. Until now nothing resolved
    it: the frontend received `"virtual.scoreboard.columns.what"` and built its own
    TranslationKey with an empty fallback, which is the one form the translation
    rules forbid (a declaration unpacked at a call site) and which renders as
    nothing whenever the key has no database row.

    Resolving here is the sanctioned shape: `t()` is handed the declaration object
    itself, so the English fallback in `translations.py` is the single source and is
    what reaches the screen before the extract → translate → import pipeline has
    ever run for these keys. The scoreboard stays pure; this is the boundary where
    a database pool and a language exist.

    `{source}` is filled with the table the draft names for that alias, because a
    reader cannot place `s2` and the draft knows what it is.
    """
    draft = (context_data or {}).get("draft") or {}
    by_alias = {
        src.get("alias"): src
        for src in (draft.get("sources") or [])
        if src.get("alias")
    }
    for entry in scoreboard.get("pending") or []:
        key_name = entry.get("what")
        declared = DATASETS.get(key_name) if key_name else None
        if declared is None:
            # A key the module does not declare is a defect in the scoreboard, not
            # something to paper over with the key string itself.
            logging.getLogger(__name__).error(
                "scoreboard pending entry names an undeclared key: %r", key_name
            )
            continue
        alias = entry.get("source")
        source = by_alias.get(alias) or {}
        named = source.get("tableName") or source.get("datasetId") or alias
        entry["whatText"] = await t(_db_pool, language, declared, source=named)

        # A chip's label is a key too, for the one `ask` piece that offers a closed
        # set. Left unresolved it renders as `virtual.scoreboard.storage.live`,
        # which is the same defect `whatText` was added to fix.
        resolved_choices = []
        for choice in entry.get("choices") or []:
            if isinstance(choice, dict) and DATASETS.get(choice.get("label")):
                resolved_choices.append({
                    **choice,
                    "label": await t(_db_pool, language, DATASETS[choice["label"]]),
                })
            else:
                resolved_choices.append(choice)
        if resolved_choices:
            entry["choices"] = resolved_choices

    # `blocked` carries two keys — what the piece is and what would unblock it —
    # and the turn's prompt prints `needs` verbatim. Left as a key, the model is
    # told to explain the blocker and handed `virtual.scoreboard.joins.needs`
    # where the sentence should be.
    for entry in scoreboard.get("blocked") or []:
        alias = entry.get("source")
        source = by_alias.get(alias) or {}
        named = source.get("tableName") or source.get("datasetId") or alias
        what_key = entry.get("what")
        declared = DATASETS.get(what_key) if what_key else None
        if declared is not None:
            entry["whatText"] = await t(_db_pool, language, declared, source=named)
        needs_key = entry.get("needs")
        declared = DATASETS.get(needs_key) if needs_key else None
        if declared is not None:
            entry["needsText"] = await t(_db_pool, language, declared, source=named)
        elif needs_key:
            logging.getLogger(__name__).error(
                "scoreboard blocked entry names an undeclared key: %r", needs_key
            )
    return scoreboard


def _schemas_from_context(context_data: dict) -> dict:
    """The scoreboard's schema view, built from what the session already read.

    `introspectedTables` is keyed by physical identity — `connection_<id>_<table>`
    or `dataset_<id>` — which is not an alias, so this maps each entry to the
    alias the draft gave it. An alias the draft has but the cache does not is
    simply absent, and the scoreboard reports its columns as *not looked at*
    rather than as empty: the two are different answers and the scoreboard has a
    state for each.

    A dataset source is looked up under `dataset_<id>`. Until 2026-11-05 only
    connection sources were read here, so a dataset-sourced alias could never be
    cached at all — `set_source_columns` recorded its columns and the next turn
    had forgotten them.
    """
    from .virtual_scoreboard import SchemaState

    by_key = (context_data or {}).get("introspectedTables") or {}
    draft = (context_data or {}).get("draft") or {}
    schemas = {}
    for source in draft.get("sources") or []:
        alias = source.get("alias")
        if not alias:
            continue
        dataset_id = source.get("datasetId")
        connection_id = source.get("connectionId")
        table_name = source.get("tableName")
        if dataset_id:
            entry = by_key.get(f"dataset_{dataset_id}")
        elif connection_id is not None and table_name:
            entry = by_key.get(f"connection_{connection_id}_{table_name}")
        else:
            continue
        if not entry:
            continue
        names = [c.get("name") for c in entry.get("columns") or [] if c.get("name")]
        schemas[alias] = SchemaState.known(names)
    return schemas


def _stored_scoreboard(context_data: dict, language: str = "en") -> dict:
    """The scoreboard for a session's stored draft.

    `build_prompt` recomputes the scoreboard on every turn so a turn can never
    read a stale one; this is the same computation for a **read** path, where
    there is no turn — the GET handlers and the session list. It is a pure
    function of the draft and the schema cache, so calling it there cannot
    disagree with what the turn computed, which is the point: the progress strip
    and the assistant must read one number.
    """
    ctx = context_data or {}
    return compute_virtual_scoreboard(
        ScoreboardInputs(
            draft=ctx.get("draft") or {},
            schemas=_schemas_from_context(ctx),
            validation=None,
            language=language,
        )
    )


# Appended to the system prompt on the turn that FOLLOWS a chip confirm.
#
# The decision turn now reads the whole conversation, which is what made its
# answers good — and is also what let it decide, on 2026-11-05, that the draft it
# could see was debris from an earlier session. It unticked every column of two
# sources the user had just accepted, explained that it was "clearing out the
# leftover draft", and rebuilt the draft with tables of its own.
#
# This says, once and plainly, what that draft is: the thing the user just asked
# for. The guard in `remove_output_column` is the backstop for when the belief
# forms anyway; this is the attempt to stop it forming.
DECISION_TURN_NOTE = """
WHAT JUST HAPPENED

The user has just accepted a piece of this dataset in the panel — the draft above
is what their click created, and it is the current state of the work, not debris
from an earlier conversation. Nobody has asked you to tidy it up.

WHAT THE CLICK ACTUALLY CONTAINED

{accepted}

Those are the tables the user chose, and they are in the draft under the aliases
named here. If they are not what you were expecting, that is not a rogue edit and
not a stale draft — it is the answer to the offer, and it takes precedence over
anything you proposed earlier in the conversation. Say so in one line if you
disagree, and suggest the alternative; do not treat the draft as if someone else
had filled it in.

Continue from it. If a piece is still missing, take that piece next. Do not remove
sources, columns or joins the user accepted, and do not replace the draft with your
own version of it: those are their decisions, and changing one has to be something
they ask for. When you have finished what the click started, say in a sentence what
you did and what is left.
"""


def _join_pair_key(join: dict) -> tuple:
    """How a join is identified across an edit: the two sources it relates.

    The columns and the type are the parts the user edits, so neither can be
    part of the identity — a row whose type moved INNER to LEFT is one join
    changed, not one removed and another added.
    """
    return tuple(sorted({str(join.get("left") or ""), str(join.get("right") or "")}))


def _join_text(join: dict) -> str:
    """One join, in the form the row reads."""
    return (f"`{join.get('left')}.{join.get('leftCol')}` = "
            f"`{join.get('right')}.{join.get('rightCol')}` "
            f"({join.get('type') or 'inner'})")


def _join_diff_lines(before, after) -> str:
    """What an edit to the join set did, not merely what the set now holds.

    The model is told the difference because the difference is the actionable
    fact. A **removed** row matters most: the user took a join out on purpose,
    and without being told, the next turn sees a draft with one fewer join and
    may simply put it back — the removal looks like an oversight rather than a
    decision.

    Nothing is reported for a row that is identical, so an edit that only
    reordered the set reads as unchanged rather than as a change.
    """
    before_rows = [row for row in (before or []) if isinstance(row, dict)]
    after_rows = [row for row in (after or []) if isinstance(row, dict)]
    before_by = {_join_pair_key(row): row for row in before_rows}
    after_by = {_join_pair_key(row): row for row in after_rows}

    lines = []
    for key, row in after_by.items():
        was = before_by.get(key)
        if was is None:
            lines.append(f"* added: {_join_text(row)}")
        elif (was.get("leftCol") != row.get("leftCol")
              or was.get("rightCol") != row.get("rightCol")
              or (was.get("type") or "inner") != (row.get("type") or "inner")):
            lines.append(f"* changed: {_join_text(row)} — was {_join_text(was)}")
    for key, was in before_by.items():
        if key not in after_by:
            lines.append(f"* removed: {_join_text(was)}")

    return "\n".join(lines) if lines else "* the joins were confirmed unchanged"


def joins_for_reply(agent) -> list:
    """The joins a reply may attach — only if THIS turn changed them.

    `_pieces` seeds `draft_pieces` from `draft_snapshot`, so once joins exist they
    are present in `draft_pieces` on every turn. The earlier test was "is it
    non-empty", which is always true after the joins are written — so every reply
    carried the whole set, the page rendered the newest message carrying joins as
    its live editor, and the block reappeared under the name turn, the storage
    turn, and every turn after. Measured 2026-11-06, session
    vdc_79b2d2cd3b73457f.

    The test is whether the value moved, not whether it exists. Mirrors Go's
    `decisionJoinsForReply`, which takes the same two maps.

    Module level rather than inline so it can be tested with a fake agent: the
    endpoint route needs a database and a live model, and a rule reachable only
    through those is a rule whose test passes for the wrong reason — which is
    exactly what the first version of that test did.
    """
    pieces = getattr(agent, "draft_pieces", None) or {}
    seeded = getattr(agent, "draft_snapshot", None) or {}
    current = pieces.get("joins") or []
    if not current:
        return []
    if current == (seeded.get("joins") or []):
        return []
    return current


def _accepted_lines(piece: str, value, draft, previous=None) -> str:
    """What the click chose, in the terms the draft now holds.

    The note above says the draft is the user's; this says *what* it is. Without
    it the turn saw two aliases it had not named (`s1`, `s2`) over columns belonging
    to a dataset the conversation had been discussing, concluded the click "landed on
    two other order-style sources", and told the user their own confirm was a
    mismatch. The gap was information, not reasoning: the model had never been told
    what the chip payload contained.

    An alias is not a table name, so the draft is the only place the answer exists —
    the applier minted the alias and recorded the identity beside it.
    """
    if piece in ("sources", "columns"):
        by_alias = {
            s.get("alias"): s for s in (draft or {}).get("sources") or [] if s.get("alias")
        }
        lines = []
        for entry in value if isinstance(value, list) else []:
            if not isinstance(entry, dict):
                continue
            identity = entry.get("tableName") or entry.get("datasetId") or "?"
            uri = (
                f"connection {entry.get('connectionId')}"
                if entry.get("connectionId") is not None
                else "a dataset"
            )
            columns = [c for c in (entry.get("columns") or []) if isinstance(c, str)]
            alias = next(
                (
                    a
                    for a, s in by_alias.items()
                    if (s.get("tableName") == entry.get("tableName")
                        and s.get("datasetId") == entry.get("datasetId"))
                ),
                None,
            )
            where = f" (alias `{alias}`)" if alias else ""
            shown = f" — columns: {', '.join(columns[:8])}" if columns else ""
            lines.append(f"* `{identity}` from {uri}{where}{shown}")
        return "\n".join(lines) if lines else "* (nothing — the selection was empty)"

    if piece == "joins":
        # `value` is the set the click wrote, so it is the after-state by
        # construction; `previous` is the draft as it stood before the write,
        # which only this endpoint can supply — it read the row first.
        after = value if isinstance(value, list) else [value] if isinstance(value, dict) else []
        before = (previous or {}).get("joins") if isinstance(previous, dict) else None
        return _join_diff_lines(before, after)
    if piece == "name":
        return f"* the name is now `{(draft or {}).get('name') or value}`"
    if piece == "storage":
        # Say what the choice MEANS, in the words the chips used.
        #
        # The raw value is `live` or `materialized`, and the chips the model
        # offered were labelled "Live view" and "Saved table". Told that "the
        # storage piece was set to materialized", the model could not match that
        # token to either label it had shown, and answered "neither was marked as
        # chosen — which do you want?" after the user had already clicked.
        # Measured 2026-11-06, session vdc_777208a4239942e9, message [50].
        #
        # The stored value is a boolean, so read it from the draft rather than
        # trusting the token: the applier accepts "materialized", "live", a dict
        # and a bool, and only the draft says what actually resulted.
        chosen = (draft or {}).get("materialized")
        if chosen is True:
            return ("* storage: **Saved table** — the joins are written to a table when the "
                    "dataset is saved, so reads are fast and the data can lag until it is rebuilt.")
        return ("* storage: **Live view** — the join runs each time the dataset is read, so it "
                "always reflects the current source data.")
    return f"* the `{piece}` piece was set to `{value}`"


def build_prompt(context_data: dict, language: str = "en", scoreboard: dict = None) -> str:
    """One prompt, in four parts, replacing the ten stage blocks.

    The ladder is gone, and with it everything that existed to keep a stage
    machine coherent: the per-stage instructions, rules 8–10 (one stage at a
    time, redirect later-stage questions, call `set_stage`), every REDIRECT
    paragraph, the canned scale sentence, the pre-loaded inventory and the
    auto-detect nudge.

    What replaces them is the design's four parts (§7), and the order matters:
    the scoreboard is the second thing the model reads, before any rule about how
    to behave, so its behaviour is grounded in the draft rather than in a
    remembered position in a sequence.

    **The scoreboard is computed, not passed in.** It is a pure function of the
    draft and the schema cache, so building the prompt recomputes it — which is
    what makes "recomputed every turn" true rather than a claim. A stale
    scoreboard is the failure mode this whole design exists to remove.

    ``scoreboard`` is that same board, already rendered: the caller resolves its
    keys through `t()` and passes it in, because this function is synchronous and
    holds no pool. It is one board either way — the argument is the rendering, not
    a second source. Omitted (the unit tests), the board is computed here and the
    pieces appear as keys.

    **There is no branch on what the user said.** The input decides pieces, and
    the scoreboard says what is left. A greeting decides nothing, so `sources` and
    `name` are shown pending and the model asks one question; a substantive
    request decides several, and the scoreboard shows what remains. That is why
    the entry matrix needs no code: it is a consequence of the scoreboard, not a
    case in it.
    """
    from .virtual_scoreboard import ScoreboardInputs, compute_virtual_scoreboard
  
    draft = context_data.get("draft") or {}
    if scoreboard is None:
        scoreboard = compute_virtual_scoreboard(
            ScoreboardInputs(
                draft=draft,
                schemas=_schemas_from_context(context_data),
                validation=None,
                language=language,
            )
        )

    def _section(name: str) -> list:
        return scoreboard.get(name) or []

    crystallised = _section("crystallised")
    pending = _section("pending")
    blocked = _section("blocked")
    errors = _section("errors")

    def _describe_piece(piece: dict) -> str:
        label = piece.get("piece", "")
        source = piece.get("source")
        if source:
            label = f"{label}:{source}"
        return label

    decided = ", ".join(
        f"{_describe_piece(p)}={json.dumps(p.get('value'), ensure_ascii=False)}"
        for p in crystallised
        if p.get("piece") != "storage"
    ) or "nothing yet"
    # The prompt no longer decides which pending pieces may be asked about — it
    # reads `surface`, which the scoreboard sets from design §4.0. The earlier
    # version of this block hard-coded `sources` as unaskable and printed a
    # separate `derived:` line; both are gone, because a field nothing reads is
    # useless and a reader without the field re-derives it.
    by_surface: Dict[str, list] = {}
    for piece in pending:
        by_surface.setdefault(piece.get("surface") or "", []).append(_describe_piece(piece))

    def _surface_line(name: str, description: str) -> str:
        pieces = by_surface.get(name) or []
        return f"  {name + ':':9s} {', '.join(pieces) if pieces else 'none'} — {description}"

    ask_lines = [
        _surface_line("ask", "closed sets; offer these as chips"),
        _surface_line("point", "the user ticks these in the tree; name them, do not question"),
        _surface_line("read", "fetch with a tool; ask nobody"),
        _surface_line("offer", "propose a computed candidate; the user accepts or ignores"),
        _surface_line("invite", "only the user can set this — propose one concrete answer they can accept or replace"),
    ]
    blocked_pieces = ", ".join(
        f"{_describe_piece(p)} (needs {p.get('needsText') or p.get('needs')})" for p in blocked
    ) or "none"

    parts = [
        # 1. The role, and the one-question rule.
        #
        # The definition is wider than a join. Measured 2026-11-06: asked for bike
        # sales trend data, the model found an uploaded table that already carried
        # every factor and offered it as ONE source — a column projection with no
        # join at all. That is a legitimate virtual dataset (the scoreboard requires
        # joins only from two sources upward, and the SQL builder emits a plain
        # FROM), but this sentence defined the thing as "a saved join", so the
        # model had to describe what it was doing as something other than the task.
        (
            "You are building a virtual dataset with the user, through conversation. "
            "A virtual dataset is a saved selection of columns over one or more tables or "
            "datasets the user can read — joined across them when more than one is needed, "
            "and a plain projection when one table already carries everything. "
            "Ask about at most ONE thing at a time."
        ),
        # 2. The scoreboard.
        (
            "THE SCOREBOARD — what this dataset currently needs:\n"
            f"  decided:  {decided}\n"
            + "\n".join(ask_lines) + "\n"
            f"  blocked:  {blocked_pieces}\n"
            f"  errors:   {'; '.join(errors) if errors else 'none'}\n"
            f"  complete: {'yes' if scoreboard.get('complete') else 'no'}"
        ),
        # 3. How to use it.
        (
            "HOW TO USE IT:\n"
            "- When the message decides something, record it with the matching tool "
            "(set_goal, add_source, set_source_columns, set_join, remove_join, "
            "set_output_columns, remove_output_column, set_name, set_storage). Never record a "
            "piece the user did not decide.\n"
            "- Raise ONE pending piece, in the manner its surface gives. An `ask` piece is a question "
            "with chips (call suggest_choices first). A `point` piece is named, not asked — say which "
            "table or column to tick. A `read` piece you fetch with a tool. An `offer` piece you propose "
            "for acceptance. An `invite` piece is the user's to set, so call suggest_choices with "
            "ONE concrete proposal and ask them to accept or change it — a name built from the goal "
            "and the tables, never a blank \"what should this be called?\".\n"
            "- Never ask about a blocked piece. Say in one line what would unblock it.\n"
            "- A piece under `decided` is settled: do not re-open it unless the user asks.\n"
            # The joins are written by set_join and then rendered by the page as
            # editable rows under this very reply. Until 2026-11-06 the prompt
            # said nothing about that, so a model that had just written seven
            # joins ended its reply by restating all seven as a markdown table —
            # the same information twice, and the copy that cannot be edited was
            # the one it spent its words on. It also then asked for the name,
            # which was the genuinely next piece, so the user saw a question
            # while looking at a control that was not the question.
            "- Joins appear as editable rows under your reply, one line each with its columns, "
            "its type and its reason. So say in one short sentence that you have joined them, and "
            "you may set them out in a markdown table as well — the table is for reading the shape, "
            "the rows below are for changing it. **That block is this turn's answer surface: do "
            "not also raise a pending piece beside it.** Finish with the joins, and raise the next "
            "piece on the turn after the user has responded to them — asking for a name while the "
            "joins are still open asks for two answers at once, and the user can only give one.\n"
            # Join type is a decision the model was making blind: nothing said which to use,
            # so it reached for the enum's first value every time. Measured 2026-11-06, on a
            # six-table bike-store draft: five joins, all `inner`, three of them hanging off
            # lookup tables (`brands`, `categories`, `stores`). An inner join to a lookup
            # silently drops every row whose key is null or unmatched — the dataset loses
            # rows without saying so, and a dataset built to measure what influences sales
            # is then measuring a biased sample.
            "- **Join type.** Use `left` when the right-hand side is a lookup - brands, "
            "categories, stores, customers, staff, or any small table that exists to name "
            "something. An `inner` join there silently drops every row whose key is null or "
            "has no match. Use `inner` only when both sides are facts that must both exist for "
            "the row to be meaningful. When in doubt, `left`.\n"
            "- `sources` is a `point` piece: it comes into being from the columns the user ticks, or "
            "from add_source when they name a table. Never put it as a QUESTION with options — the "
            "tree is where tables are browsed. You may still OFFER a set: when you have worked out "
            "which tables this dataset needs, call suggest_choices with piece=sources and a "
            "`proposal` listing them. They reach the user as chips in the message, pre-ticked — "
            "NOT in the tree, which only shows what the draft already holds, and nothing is written "
            "until they confirm. So never say you have put something in the tree; say you have "
            "offered it, or that it is below. They can adjust the ticks and accept in a single act. "
            "Offer once, after you have the columns in hand, and then go quiet — do not re-offer "
            "what it just accepted.\n"
            "- Errors come before anything else: if the draft does not hold together, fix it "
            "rather than moving on.\n"
            "- When the scoreboard is complete, call validate_virtual_dataset, then "
            "save_virtual_dataset. Saving is immediately usable — there is no publish step.\n"
            "- Call get_scoreboard when you are unsure what is left; do not guess."
        ),
        # 4. The accuracy and formatting rules that survive.
        (
            "ACCURACY — these never bend:\n"
            "- Column and table names come from the tools or from what the user chose. Never "
            "invent one, and never substitute a name you think is close.\n"
            "- Never show made-up data rows or numbers. You may show the SQL definition that "
            "will be saved, but never claim to have executed it or display fake results.\n"
            "- If you do not have a schema, call get_tables or get_columns and use exactly what "
            "it returns.\n"
            "- find_sources resolves a name the user typed. If it reports no exact match, say so "
            "and offer the closest real names — never pick one for them.\n"
            "- Remember what the user already told you. Never re-ask a decided piece.\n"
            "- If they ask for something no tool can do (aggregation, grouping, time-series "
            "analysis), call report_unsupported and say plainly it is not supported yet.\n"
            "\n"
            "FORMATTING: GitHub-style markdown. Render tabular data as markdown tables, use "
            "[text](url) for links and **bold** for emphasis. Do not wrap a whole reply in a "
            "code block."
        ),
    ]

    return "\n\n".join(parts)



# ── LLM Call ─────────────────────────────────────────────────

# _call_llm was here: a second model path that posted straight to the provider
# instead of going through ToolAgent.run_tool_loop. It had no callers — every
# virtual-dataset turn reaches the model through the loop — and it bypassed the
# loop's language prepend, the timeout budgets and the tool-call handling, so a
# future caller would have got a turn nobody configured. Removed 2026-11-11.
async def _handle_introspect_action(chat_id: str, user_id: str, connection_id: int, table_name: str, language: str = "en"):
    """Introspect a database table and inject its schema into the chat context."""
    global _db_pool

    async with _db_pool.acquire() as conn:
        row = await conn.fetchrow(
            'SELECT * FROM "VirtualDatasetChat" WHERE id = $1 AND "userId" = $2',
            chat_id, user_id
        )
        if not row:
            raise HTTPException(status_code=404, detail=await t(_db_pool, language, DATASETS["virtual_chat.chat_session_not_found"]))

        context_data = row["contextData"] or {}

    # Fetch connection details (routed through the core).
    conn_row = await get_connection_row(connection_id, user_id, language)
    if conn_row is None:
        raise HTTPException(status_code=404, detail=await t(_db_pool, language, DATASETS["virtual_chat.connection_not_found"]))

    db_type = conn_row["type"]

    # Introspect the table — reuse the shared browse helper (peer of the manual editor).
    from .browse import list_table_columns
    try:
        cols = await list_table_columns(_db_pool, user_id, language, connection_id, table_name)
        if not cols:
            raise ValueError(f"Table '{table_name}' not found")
        columns = [{"name": c["name"], "type": c["type"]} for c in cols]
    except Exception as e:
        raise HTTPException(status_code=500, detail=await t(_db_pool, language, DATASETS["virtual_chat.introspection_failed"], error=str(e)))

    # Persist the introspection under its own key, merged in the statement.
    # Reading the whole map, adding an entry and writing the map back would let
    # two tables introspected at once lose one of them — the same defect the
    # draft had, one level down.
    key = f"connection_{connection_id}_{table_name}"
    await merge_introspected_table(
        _db_pool,
        chat_id,
        user_id,
        key,
        {
            "connectionId": connection_id,
            "connectionName": conn_row["name"],
            "tableName": table_name,
            "type": db_type,
            "columns": columns,
        },
    )

    return {
        "chatId": chat_id,
        "action": "introspect",
        "introspected": {"connectionName": conn_row["name"], "tableName": table_name, "columns": columns},
    }


# ── POST: Send message ───────────────────────────────────────

# The turn's response shape.
#
# ONE constructor, because the two backends must return the same body and the only
# way that stays true is if the fields are written in one place.
#
# It was assembled inline until 2026-11-06. When `decided` and `suggestion` were
# added here, the Go copy of the handler was not updated: the same conversation
# offered an acceptance chip on the Python backend and nothing on the Go one, and
# the progress count stopped moving. Nothing failed — a missing key in a JSON body
# is not an error in either language — so it was found by running the product, not
# by a check.
#
# `TURN_RESPONSE_FIELDS` is the list both sides declare, literally and in the same
# order, so the two can be diffed side by side. The tests in each suite assert
# their own constructor against it. (`check-port-parity.py` proves a symbol exists
# and cannot see a field, which is exactly why this pair exists.)

TURN_RESPONSE_FIELDS = (
    "chatId",
    "stage",
    "response",
    "draft",
    "scoreboard",
    "decided",
    "suggestion",
    "joins",
    "datasetId",
)


def turn_response(
    *,
    chat_id: str,
    stage: str,
    response: str,
    draft,
    scoreboard: dict,
    suggestion,
    joins,
    saved_dataset_id=None,
) -> dict:
    """The body a turn returns. Mirrors Go's `ChatTurnResponse`."""
    result = {
        "chatId": chat_id,
        "stage": stage,
        "response": response,
        "draft": draft or {},
        "scoreboard": scoreboard,
        "decided": decided_counts(scoreboard),
        # `None`, not absent: the page clears the chip row on a turn that offered
        # nothing, and an absent key cannot express that.
        "suggestion": suggestion,
        # The joins this turn wrote, so the block renders without a reload. `None`
        # when the turn wrote none — a turn that only talked must not put an editor
        # under its reply pointing at joins an earlier turn decided.
        "joins": joins,
    }
    if saved_dataset_id:
        result["datasetId"] = saved_dataset_id
    return result


@router.post("")
async def send_chat_message(
    body: dict,
    request: Request,
    credentials: HTTPAuthorizationCredentials = Depends(security),
    language: str = Depends(get_current_language)
):
    """Send a message in the guided virtual dataset chat."""
    global _db_pool
    if _db_pool is None:
        raise HTTPException(status_code=500, detail=await t(_db_pool, language, DATASETS["database.pool_not_initialized"]))

    user_id = await get_user_id_from_token(credentials)
    chat_id = body.get("chatId")
    user_message = body.get("message", "")
    verbose = body.get("verbose", False)
    action = body.get("action")
    connection_id = body.get("connectionId")
    selected_model = body.get("model")

    # Resolve AI connection details (user-selected or fallback) through the
    # shared resolver: owned or shared, with the provider's default endpoint.
    try:
        details = await get_connection_details(_db_pool, connection_id, user_id)
    except ValueError:
        raise HTTPException(status_code=400, detail=await t(_db_pool, language, DATASETS["chat.connection_not_found"]))
    llm_api_key, llm_endpoint = details["apiKey"], details["endpoint"]
    llm_provider = details["provider"]
    llm_model = selected_model or details["model"]

    # Handle introspection action before normal message flow
    if action == "introspect":
        return await _handle_introspect_action(chat_id, user_id, body.get("connectionId"), body.get("tableName"), language)

    async with _db_pool.acquire() as conn:
        if chat_id:
            row = await conn.fetchrow(
                'SELECT * FROM "VirtualDatasetChat" WHERE id = $1 AND "userId" = $2',
                chat_id, user_id
            )
            if not row:
                raise HTTPException(status_code=404, detail=await t(_db_pool, language, DATASETS["virtual_chat.chat_session_not_found"]))
        else:
            # Create new chat session
            import uuid
            chat_id = f"vdc_{uuid.uuid4().hex[:16]}"
            await conn.execute(
                """
                INSERT INTO "VirtualDatasetChat" (id, "userId", "currentStage", "contextData", "messages", "updatedAt")
                VALUES ($1, $2, 'entry', '{}'::jsonb, '[]'::jsonb, NOW())
                """,
                chat_id, user_id
            )
            row = await conn.fetchrow(
                'SELECT * FROM "VirtualDatasetChat" WHERE id = $1', chat_id
            )

    current_stage = row["currentStage"]
    context_data = row["contextData"] or {}
    messages = row["messages"] or []

    # Append user message
    messages.append({"role": "user", "content": user_message, "timestamp": None})

    # ── the turn's shape (Item 10) ──────────────────────────
    #
    # load the session and draft  →  append the message  →  let the model resolve
    # any named source  →  compute the scoreboard (inside build_prompt)  →  build
    # the prompt  →  run the tool loop  →  persist the pieces that changed  →
    # recompute and return.
    #
    # **The inventory is gone from this path.** `fetch_available_sources` used to
    # run here on five stages: it selected the account's visible datasets with
    # `LIMIT 50`, skipped virtual ones afterwards, and handed the result to the
    # prompt as an "available sources" block whose truncation was never mentioned.
    # The prompt has carried no inventory since Item 9, so the call was fetching
    # fifty rows into a context key nothing read.
    #
    # Its window still exists for the tree, which reads the endpoints directly
    # and can show what a capped list cannot. Resolution on a turn is now a *tool
    # call* — `find_sources`, then `set_source_columns` — not a pre-computed list:
    # the model asks for the name it heard and gets an exact match or an honest
    # miss, instead of matching against whatever survived a truncation.
    #
    # The auto-introspect pass that read that inventory goes with it. It matched a
    # mentioned table against `availableSources.databaseConnections`, so with the
    # inventory gone it had nothing to match against; the same work now happens
    # when the model calls `find_sources` and then `set_source_columns`.

    # Build system prompt for current stage. The board is the same one
    # `_stored_scoreboard` computes, resolved so the blocked pieces carry the
    # sentence that says what would unblock them rather than the key for it.
    system_prompt = build_prompt(
        context_data,
        language,
        scoreboard=await _resolve_scoreboard_texts(
            _stored_scoreboard(context_data, language), context_data, language
        ),
    )

    # Call the LLM with the tool-calling loop. Persistence happens through the
    # save_virtual_dataset tool; a piece is recorded by its own set_* tool. There
    # are no [SAVE]/[NEXT]/[BACK]/[STAGE] markers to parse — and, since Item 6, no
    # set_stage tool either.
    # The two budgets in force for this connection (plan Item 4a). `connection_id` is
    # the value read from the body above; `resolve_connection_timeouts` falls through
    # to the workbench defaults when it is None or names a connection that no longer
    # exists, so an absent id is not a special case.
    async with _db_pool.acquire() as timeout_conn:
        _timeouts = await resolve_connection_timeouts(timeout_conn, connection_id)
    agent = ToolAgent(
        api_key=llm_api_key, endpoint=llm_endpoint, model=llm_model,
        provider=llm_provider, language=language,
        timeout=float(_timeouts.probe_seconds),
        connect_timeout=float(_timeouts.connect_seconds),
        registry=VIRTUAL_REGISTRY,
    )
    agent.db_pool = _db_pool
    agent.user_id = user_id
    agent.saved_dataset_id = None
    # Names this turn in the TOOL_LOOP line the loop logs when it ends. No
    # virtual tool reads `session_id`; it exists so a slow turn can be traced to
    # the conversation that produced it, which is the question 2026-11-03 could
    # not answer.
    agent.session_id = chat_id
    # Item 6: the pieces the tools decide this turn, seeded from the stored draft
    # so a turn that changes one piece does not drop what earlier turns decided.
    # The seed is a copy — a turn that fails leaves the stored draft untouched.
    agent.draft_snapshot = dict(context_data.get("draft") or {})
    agent.draft_pieces = None
    agent.draft_schemas = None
    agent.schema_snapshot = _schemas_from_context(context_data)
    agent.validation_snapshot = None

    try:
        assistant_response, _tool_events = await agent.run_tool_loop(system_prompt, messages)
    except RuntimeError as e:
        # A repeat-loop abort and a provider failure get a graceful message;
        # anything else keeps its own translated detail — never a bare 500.
        error_msg = str(e)
        if error_msg.startswith("ai_repeat_loop:"):
            raise HTTPException(
                status_code=502,
                detail=await t(_db_pool, language, CHAT["chat.ai_repeat_loop"]),
            )
        if error_msg.startswith("ai_timeout:"):
            raise HTTPException(
                status_code=502,
                detail=await t(_db_pool, language, CHAT["chat.ai_timeout"]),
            )
        if error_msg.startswith("ai_provider_error:"):
            raise HTTPException(
                status_code=502,
                detail=await t(_db_pool, language, CHAT["chat.ai_service_failed"]),
            )
        raise HTTPException(
            status_code=400,
            detail=await t(_db_pool, language, DATASETS["error.ai.call_failed"], error=error_msg),
        )

    # Link any dataset the save_virtual_dataset tool persisted to this session.
    saved_dataset_id = agent.saved_dataset_id
    await link_saved_dataset(_db_pool, chat_id, saved_dataset_id)

    # Persist the pieces the tools decided, through the per-piece merge.
    #
    # Only the pieces this turn actually touched are sent, so a chip endpoint
    # writing a different piece while the turn was running composes instead of
    # being overwritten. `draft_pieces` is None when no piece tool ran, which is
    # a turn that only talked — nothing to write.
    draft = None
    # Did THIS turn write the joins? That is a different question from "does the
    # draft have joins" — the draft keeps every piece an earlier turn decided,
    # so answering the second question attaches a snapshot to every later turn
    # and the transcript grows a block per message. Only the turn that wrote
    # them carries them.
    wrote_joins = False
    changed = getattr(agent, "draft_pieces", None)
    if changed:
        before = getattr(agent, "draft_snapshot", None) or {}
        touched = {key: value for key, value in changed.items() if before.get(key) != value}
        wrote_joins = "joins" in touched
        if touched:
            draft = await merge_draft_pieces(_db_pool, chat_id, user_id, touched)
            context_data["draft"] = draft or {}
    if draft is None:
        draft = getattr(agent, "draft_pieces", None) or context_data.get("draft")

    # Guard against an empty final response.
    if not assistant_response or not assistant_response.strip():
        assistant_response = await t(_db_pool, language, DATASETS["virtual_chat.empty_response"])

    # Persist the messages. The context blob is NOT written here any more: it is
    # merged per key by the writers that own each key (the draft through
    # merge_draft_pieces above), so writing this turn's whole snapshot back would
    # undo whatever a chip endpoint wrote while the turn was running — the very
    # clobbering Item 5 exists to remove.
    #
    # The offer is part of the conversation and is stored with it. The agent said
    # "here are five tables, accept them" — that sentence's chips belong to the
    # message that made it, so reopening the chat finds them still there. Until
    # 2026-11-05 `suggestion` was a response field only: it existed in the tab
    # that ran the turn and vanished on reload, and the loader's
    # `suggestion: m.suggestion` mapped a field nothing ever wrote.
    _suggestion = getattr(agent, "_suggestion", None)
    if _suggestion:
        for message in reversed(messages):
            if message.get("role") == "assistant" and not message.get("tool_calls"):
                message["suggestion"] = _suggestion
                break

    # The joins as this turn left them, on the message that did the work. See
    # the decision endpoint's copy of this for why a snapshot per message rather
    # than a pointer at the draft: the draft moves, and a transcript that shows
    # today's joins under yesterday's sentence is the defect this avoids.
    joins_now = (draft or {}).get("joins") or []
    if wrote_joins and joins_now:
        for message in reversed(messages):
            if message.get("role") == "assistant" and not message.get("tool_calls"):
                message["joins"] = joins_now
                break

    async with _db_pool.acquire() as conn:
        await conn.execute(
            'UPDATE "VirtualDatasetChat" SET messages = $2::jsonb, "updatedAt" = NOW() WHERE id = $1',
            chat_id, messages
        )

    # After a successful save, transition to the complete stage
    if saved_dataset_id:
        current_stage = "complete"
        async with _db_pool.acquire() as conn:
            await conn.execute(
                """UPDATE "VirtualDatasetChat"
                SET "currentStage" = $1, "updatedAt" = NOW()
                WHERE id = $2""",
                "complete", chat_id
            )

    # ── recompute and return (Item 10) ──────────────────────
    #
    # The scoreboard is computed from the draft as it now stands, *after* the
    # pieces were persisted — so the client renders what the session holds, not
    # what the turn believed on the way in. It is returned on every turn,
    # including one that decided nothing: a caller that only gets it sometimes
    # cannot render a progress strip without a second request.
    _schemas = _schemas_from_context(context_data)
    # The model's own schema reads win over the session's cache: `set_source_columns`
    # is this turn's knowledge, and the cache may predate it.
    _schemas.update(getattr(agent, "draft_schemas", None) or {})
    from .virtual_scoreboard import ScoreboardInputs, compute_virtual_scoreboard
    scoreboard = compute_virtual_scoreboard(
        ScoreboardInputs(
            draft=draft or {},
            schemas=_schemas,
            validation=None,
            language=language,
        )
    )

    scoreboard = await _resolve_scoreboard_texts(scoreboard, context_data, language)

    result = turn_response(
        chat_id=chat_id,
        stage=current_stage,
        response=assistant_response,
        draft=draft,
        scoreboard=scoreboard,
        suggestion=getattr(agent, "_suggestion", None),
        joins=joins_now if wrote_joins else None,
        saved_dataset_id=saved_dataset_id,
    )
    return result


# ── GET: Load session ────────────────────────────────────────

@router.get("/{chat_id}")
async def get_chat_session(
    chat_id: str,
    request: Request,
    credentials: HTTPAuthorizationCredentials = Depends(security),
    language: str = Depends(get_current_language)
):
    """Load a virtual dataset chat session."""
    user_id = await get_user_id_from_token(credentials)

    async with _db_pool.acquire() as conn:
        row = await conn.fetchrow(
            'SELECT * FROM "VirtualDatasetChat" WHERE id = $1 AND "userId" = $2',
            chat_id, user_id
        )
        if not row:
            raise HTTPException(status_code=404, detail=await t(_db_pool, language, DATASETS["virtual_chat.chat_session_not_found"]))

        raw_msgs = row["messages"]
        raw_ctx = row["contextData"]
        # The same scoreboard the turn returns, computed from the stored draft —
        # one source for "how far along is this session", so the progress strip
        # cannot disagree with the assistant.
        scoreboard = _stored_scoreboard(raw_ctx, language)
        scoreboard = await _resolve_scoreboard_texts(scoreboard, raw_ctx or {}, language)
        return {
            "chatId": row["id"],
            "datasetId": row["datasetId"],
            "currentStage": row["currentStage"],
            "contextData": raw_ctx or {},
            "messages": raw_msgs or [],
            "status": row["status"],
            "scoreboard": scoreboard,
            "decided": decided_counts(scoreboard),
        }


# ── GET: List chats ──────────────────────────────────────────

@router.get("")
async def list_chats(
    request: Request,
    credentials: HTTPAuthorizationCredentials = Depends(security),
    language: str = Depends(get_current_language)
):
    """List all virtual dataset chats for the current user."""
    user_id = await get_user_id_from_token(credentials)

    async with _db_pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT id, "datasetId", "currentStage", "contextData", status,
                   "createdAt", "updatedAt"
            FROM "VirtualDatasetChat"
            WHERE "userId" = $1
            ORDER BY "updatedAt" DESC
            """,
            user_id
        )

        chats = []
        for r in rows:
            chats.append({
                "chatId": r["id"],
                "datasetId": r["datasetId"],
                "stage": r["currentStage"],
                # Same count as the open chat shows for the same session, from
                # the same function and the same stored draft.
                "decided": decided_counts(_stored_scoreboard(r["contextData"], language)),
                "status": r["status"],
                "createdAt": iso_utc(r["createdAt"]),
                "updatedAt": iso_utc(r["updatedAt"]),
            })

        return {"chats": chats}


# ── DELETE: Delete chat session ──────────────────────────────

@router.delete("/{chat_id}")
async def delete_chat(
    chat_id: str,
    request: Request,
    credentials: HTTPAuthorizationCredentials = Depends(security),
    language: str = Depends(get_current_language)
):
    """Delete a virtual dataset chat session (does not delete the dataset)."""
    user_id = await get_user_id_from_token(credentials)

    async with _db_pool.acquire() as conn:
        await conn.execute(
            'DELETE FROM "VirtualDatasetChat" WHERE id = $1 AND "userId" = $2',
            chat_id, user_id
        )

    return {"success": True}


# ── POST: tick / untick a column in the tree ────────────────
#
# The AI page mounts the manual editor's tree, and its ticks have to decide the
# `point` piece the way the manual editor's do (design §4.6) — a source and an
# output column in one transition. The manual editor holds the draft in component
# state and writes it locally; this page's draft is the session's context blob, so
# the gesture needs a route.
#
# It is its own route rather than a `column` piece on /decision, deliberately.
# That endpoint's applier table maps a value to pieces without reading the draft —
# `name`, `storage`, `joins`, `goal` all answer from the value alone. A tick cannot:
# it has to mint an alias against the draft as it stands. Adding it there would make
# the table mean "value to pieces, except this one", and the next reader would copy
# the exception.


@router.post("/{chat_id}/columns")
async def toggle_column(
    chat_id: str,
    body: dict,
    request: Request,
    credentials: HTTPAuthorizationCredentials = Depends(security),
    language: str = Depends(get_current_language),
):
    """Tick or untick one column, writing `sources` and `columns` together."""
    global _db_pool
    if _db_pool is None:
        raise HTTPException(status_code=500, detail=await t(_db_pool, language, DATASETS["database.pool_not_initialized"]))

    user_id = await get_user_id_from_token(credentials, _db_pool, language)

    action = body.get("action")
    if action not in ("tick", "untick"):
        raise HTTPException(
            status_code=400,
            detail=await t(_db_pool, language, DATASETS["virtual.column.unknown_action"], action=str(action or "")),
        )

    column = body.get("column")
    if not isinstance(column, str) or not column.strip():
        raise HTTPException(
            status_code=400,
            detail=await t(_db_pool, language, DATASETS["virtual.column.missing_column"]),
        )

    dataset_id = body.get("datasetId") or ""
    connection_id = body.get("connectionId")
    table_name = body.get("tableName") or ""
    # One of the two identities, and a connection source needs both halves —
    # a connectionId with no table names no table, and a tableName with no
    # connection names one on every connection at once.
    if not dataset_id and (connection_id in (None, "") or not table_name):
        raise HTTPException(
            status_code=400,
            detail=await t(_db_pool, language, DATASETS["virtual.column.missing_source"]),
        )

    try:
        result = await toggle_output_column(
            _db_pool, chat_id, user_id,
            action=action, column=column.strip(),
            connection_id=connection_id, table_name=table_name,
            dataset_id=dataset_id, storage_type=body.get("storageType") or "",
        )
    except (TypeError, ValueError) as exc:
        raise HTTPException(
            status_code=400,
            detail=await t(_db_pool, language, DATASETS["virtual.decision.invalid_value"], piece="columns", error=str(exc)),
        )
    if result is None:
        raise HTTPException(status_code=404, detail=await t(_db_pool, language, DATASETS["virtual_chat.chat_session_not_found"]))

    # The count the strip and the session list read, from the same function the
    # turn and the decision endpoint use, so a tick cannot make them disagree.
    async with _db_pool.acquire() as conn:
        row = await conn.fetchrow(
            'SELECT "contextData" FROM "VirtualDatasetChat" WHERE id = $1 AND "userId" = $2',
            chat_id, user_id,
        )
    context_data = (row["contextData"] if row else None) or {}

    return {
        "chatId": chat_id,
        "draft": result["draft"],
        "alias": result["alias"],
        "ticked": result["ticked"],
        "removedSource": result["removedSource"],
        "decided": decided_counts(_stored_scoreboard(context_data, language)),
    }


# ── PATCH: the docked panel's fold ───────────────────────────
#
# The source panel can be folded away, and the fold belongs to THIS session —
# the user's decision of 2026-11-03, "foldable = this session" (design §9.4).
# Component state alone would re-open a panel the user deliberately closed on
# every reload, which makes the control untrustworthy; a User column would
# remember it across sessions and machines, which is a schema change for a
# preference nobody asked to keep.
#
# The key is `contextData.panelCollapsed`, written through
# `merge_context_keys` — the one door for top-level context state. That matters
# here rather than being tidiness: a turn may be writing the draft at the same
# moment, and the per-key merge composes where a whole-blob write would discard
# whichever arrived second.


@router.patch("/{chat_id}/panel")
async def set_panel_collapsed(
    chat_id: str,
    body: dict,
    request: Request,
    credentials: HTTPAuthorizationCredentials = Depends(security),
    language: str = Depends(get_current_language),
):
    """Store the source panel's fold for this chat session."""
    global _db_pool
    if _db_pool is None:
        raise HTTPException(status_code=500, detail=await t(_db_pool, language, DATASETS["database.pool_not_initialized"]))

    user_id = await get_user_id_from_token(credentials, _db_pool, language)

    collapsed = body.get("collapsed")
    # A bool, and only a bool: "false" is a string and would be truthy in the
    # jsonb value the page then reads back, so a caller sending it is refused
    # rather than quietly given the opposite of what it asked for.
    if not isinstance(collapsed, bool):
        raise HTTPException(
            status_code=400,
            detail=await t(_db_pool, language, DATASETS["virtual.panel.collapsed_required"]),
        )

    merged = await merge_context_keys(_db_pool, chat_id, user_id, {"panelCollapsed": collapsed})
    if merged is None:
        # Not the caller's session, or gone: the UPDATE matched nothing and
        # nothing was written.
        raise HTTPException(
            status_code=404,
            detail=await t(_db_pool, language, DATASETS["virtual_chat.chat_session_not_found"]),
        )

    return {"panelCollapsed": bool(merged.get("panelCollapsed", collapsed))}


# ── POST: Apply a chip decision ──────────────────────────────
#
# The clickable counterpart to typing a choice. Design §6.4 states the contract,
# and it is deliberately NOT the recipe's:
#
#   piece applied, model replied   200  draft, scoreboard, suggestion, response
#   piece applied, model failed    200  the same, response empty, respondError set
#   unknown piece / bad payload    400  nothing written
#   session missing or not mine    404  nothing written
#
# The write happens BEFORE the model call and the 200 stands whatever the model
# does, because the resource was updated. The recipe answers 502 when the follow-up
# call fails, so its client never receives the draft it just wrote — the user has
# to guess that a refetch would show their click. That is the defect this endpoint
# is written to avoid.
#
# The recipe also maps every ValueError to "session not found", including the one
# raised for an unknown piece — so a request naming a piece that does not exist
# reports a missing session that exists. A `piece -> applier` lookup cannot make
# that mistake: a miss is a miss, and it is reported as what it is.

def _materialised(value) -> bool:
    """Read a storage chip's value however it was spelled."""
    if isinstance(value, bool):
        return value
    return str(value).lower() in ("materialized", "materialised", "true")


# ONE table: piece -> a function turning the chip's value into the pieces to
# merge. Not a set of names plus a separate if-chain — two structures can
# disagree, and a name the endpoint accepts but the applier does not would be
# reported as an unknown piece the routing had just said was known.
#
# The plan asks for "a piece -> applier table rather than an if", and this is it.


def _joins_piece(value):
    """The pieces a joins click writes: one row, or the whole set.

    One row is the shape the single-join chip sends and it is still accepted. A
    list is what the join editor sends, because editing a row means re-stating
    the set rather than appending to it — the editor holds every row on screen,
    so what it posts IS the joins the user decided on.

    ``None`` means the payload could not be read as joins, and `_apply_piece`
    turns that into a 400 rather than writing half a set.
    """
    if isinstance(value, dict):
        return {"joins": [value]}
    if isinstance(value, list) and all(isinstance(row, dict) for row in value):
        return {"joins": value}
    return None


_PIECE_APPLIERS = {
    # A name is whatever the user typed.
    "name": lambda value: {"name": value},
    "set_name": lambda value: {"name": value},
    # Storage accepts a boolean or either spelling a chip might send.
    "storage": lambda value: {"materialized": _materialised(value)},
    "set_storage": lambda value: {"materialized": _materialised(value)},
    # A join row carries {"left","leftCol","right","rightCol","type"} and may
    # carry the `reason` it was chosen. See `_joins_piece`.
    "joins": _joins_piece,
    "join_type": _joins_piece,
    "goal": lambda value: {"goal": value},
    "set_goal": lambda value: {"goal": value},
}


def _log_decision(chat_id: str, piece: str, result: dict) -> None:
    """One line per decision turn, whatever the turn did.

    The evidence that was missing when a live click rendered no join block.

    Measured 2026-11-07: a user confirmed the offered tables, saw the join rows
    and no Done control, and the question "did the response carry the joins?"
    could not be answered from anything that was written down. The transcript
    said four, the database said four, and the response — the thing the page
    actually renders from — was recorded nowhere. Reproducing it needed a fresh
    model conversation and a browser the harness cannot drive.

    Three failure modes, all distinguishable here:

      joins=0          the turn wrote none, so no block is expected
      joins>0 text=0   written but no prose — the client must still append
      respondError=…   the turn failed and the reply is absent by design

    **Called at every exit, and that is the point.** The line first lived at the
    end of the handler, below two early `return result` statements — so a
    decision that failed before reaching the model left no trace at all, which
    is the case most worth recording. An absent line reads as "no decision
    happened". Measured: two probe calls returning `respondError` wrote nothing.

    A new exit path must call this. The Go port has three exits and calls it at
    each; if one side gains an exit the other does not, the logs stop agreeing,
    which is what makes the divergence visible rather than silent.
    """
    logging.getLogger(__name__).info(
        "DECISION session=%s piece=%s joins=%d text=%d suggestion=%s respondError=%s",
        chat_id, piece, len(result.get("joins") or []), len(result.get("response") or ""),
        bool(result.get("suggestion")), bool(result.get("respondError")),
    )


async def _apply_piece(pool, chat_id: str, user_id: str, piece: str, value) -> Optional[dict]:
    """Apply one chip's choice to the draft, through the per-piece merge.

    Returns the merged draft, or None when the session is not the caller's.

    ``sources`` is not an applier lambda like the others: it writes two pieces
    (the sources and the columns ticked on them) as one act, and needs a
    transaction to do it. See `apply_source_selection` for why that matters.
    """
    if piece in ("sources", "columns"):
        applied = await apply_source_selection(pool, chat_id, user_id, value)
        # The applier reports the aliases it derived alongside the draft; the
        # endpoint's contract is that `draft` IS the draft, so the wrapper is
        # unwrapped here rather than every caller learning a second shape.
        return applied["draft"] if applied else None
    pieces = _PIECE_APPLIERS[piece](value)
    if pieces is None:
        raise ValueError("a join decision needs the pair and its columns")
    return await merge_draft_pieces(pool, chat_id, user_id, pieces)


def _decision_record(piece: str, value, draft) -> dict:
    """What a chip click DID, in the terms the transcript can honestly show.

    A chip is an act, not a sentence, so the stored turn carries the act rather
    than quoting the user. The page renders this; the model reads `content`,
    which is the sentence a person would have typed if this were a chat message.

    ``chosen`` counts what the act covered, because that is the fact a reader
    wants from an act: five tables, two joins, one name.
    """
    record: dict = {"piece": piece}

    if piece in ("sources", "columns"):
        selections = value if isinstance(value, list) else []
        tables = []
        for entry in selections:
            if not isinstance(entry, dict):
                continue
            name = entry.get("tableName") or entry.get("datasetId")
            if name:
                tables.append(str(name))
        record["chosen"] = len(selections)
        record["tables"] = tables[:12]
    elif piece == "joins":
        rows = value if isinstance(value, list) else [value] if isinstance(value, dict) else []
        record["chosen"] = len(rows)
        # `pair` is the single-join case, which is what the older chip sent and
        # what `act_join` renders. A set has no single pair to name, so it
        # reports its size and the page says "Joined 6 pairs".
        if len(rows) == 1 and isinstance(rows[0], dict):
            one = rows[0]
            record["pair"] = (f"{one.get('left')}.{one.get('leftCol')} = "
                              f"{one.get('right')}.{one.get('rightCol')}")
    else:
        record["chosen"] = 1

    # The name is the one piece whose value is worth showing: it is short, and
    # "named it <x>" says more than "named it".
    if piece == "name" and isinstance(draft, dict) and draft.get("name"):
        record["name"] = draft["name"]
    # Storage is the other: `chosen: 1` on a two-chip question says nothing about
    # which chip, and the transcript showed an act the reader could not interpret.
    if piece == "storage" and isinstance(draft, dict):
        record["storage"] = "materialized" if draft.get("materialized") is True else "live"
    return record


@router.post("/{chat_id}/decision")
async def apply_decision(
    chat_id: str,
    body: dict,
    request: Request,
    credentials: HTTPAuthorizationCredentials = Depends(security),
    language: str = Depends(get_current_language),
):
    """Apply a choice the user made by clicking a chip, then let the model say what is next."""
    global _db_pool
    if _db_pool is None:
        raise HTTPException(status_code=500, detail=await t(_db_pool, language, DATASETS["database.pool_not_initialized"]))

    user_id = await get_user_id_from_token(credentials, _db_pool, language)

    piece = body.get("piece")
    value = body.get("value")

    # An unknown piece is refused before anything is read, let alone written.
    # `sources` and `columns` are decided by `apply_source_selection`, not by an
    # applier lambda, so they are named here rather than in _PIECE_APPLIERS.
    if piece not in _PIECE_APPLIERS and piece not in ("sources", "columns"):
        raise HTTPException(
            status_code=400,
            detail=await t(_db_pool, language, DATASETS["virtual.decision.unknown_piece"], piece=piece or ""),
        )
    if value is None or value == "":
        raise HTTPException(
            status_code=400,
            detail=await t(_db_pool, language, DATASETS["virtual.decision.missing_value"], piece=piece),
        )

    async with _db_pool.acquire() as conn:
        row = await conn.fetchrow(
            'SELECT "contextData", messages FROM "VirtualDatasetChat" WHERE id = $1 AND "userId" = $2',
            chat_id, user_id,
        )
    if not row:
        raise HTTPException(status_code=404, detail=await t(_db_pool, language, DATASETS["virtual_chat.chat_session_not_found"]))

    # 1. Record the decision. This happens first and is persisted before anything
    #    is said about it — a lost click is worse than a silent assistant.
    #
    # The draft as it stood BEFORE the write, kept so the follow-up turn can be
    # told what the click changed rather than only what the draft now holds. An
    # edit to the join set has to say which row went: a removal is a decision,
    # and a turn that is not told reads the shorter set as an accident and may
    # put the row back. Read from `row`, which was fetched above and therefore
    # precedes this write.
    previous_draft = (row["contextData"] or {}).get("draft") or {}
    try:
        draft = await _apply_piece(_db_pool, chat_id, user_id, piece, value)
    except (KeyError, ValueError) as exc:
        raise HTTPException(
            status_code=400,
            detail=await t(_db_pool, language, DATASETS["virtual.decision.invalid_value"], piece=piece, error=str(exc)),
        )
    if draft is None:
        # The row vanished between the SELECT and the UPDATE — still not the
        # caller's, so still a 404, and still nothing written.
        raise HTTPException(status_code=404, detail=await t(_db_pool, language, DATASETS["virtual_chat.chat_session_not_found"]))

    context_data = row["contextData"] or {}
    context_data["draft"] = draft

    # Re-read the context's other keys, because the apply just changed one.
    #
    # `row` was read BEFORE the piece was applied, so it cannot hold what that
    # write did. The source selection writes the schema cache in the same
    # transaction as the draft — so scoring the board from the old blob reported
    # every column piece as unread immediately after the user accepted them.
    # Measured 2026-11-05: five sources and fifteen columns in the draft, five
    # `columns` pieces pending, cache correctly written and invisible to the
    # response that was meant to show it.
    async with _db_pool.acquire() as conn:
        refreshed = await conn.fetchrow(
            'SELECT "contextData"->\'introspectedTables\' AS cached '
            'FROM "VirtualDatasetChat" WHERE id = $1 AND "userId" = $2',
            chat_id, user_id,
        )
    if refreshed is not None and refreshed["cached"] is not None:
        context_data["introspectedTables"] = refreshed["cached"]

    # 2. The scoreboard for the draft as it now stands.
    from .virtual_scoreboard import ScoreboardInputs, compute_virtual_scoreboard
    scoreboard = compute_virtual_scoreboard(
        ScoreboardInputs(
            draft=draft,
            schemas=_schemas_from_context(context_data),
            validation=None,
            language=language,
        )
    )

    scoreboard = await _resolve_scoreboard_texts(scoreboard, context_data, language)

    result = {
        "chatId": chat_id,
        "draft": draft,
        "scoreboard": scoreboard,
        # The strip's two numbers. `turn_response` has always carried them; this
        # dict did not, and the page guards on `if (data.decided)`, so every chip
        # click updated the scoreboard and left the count at whatever the last
        # MESSAGE turn set. Measured 2026-11-07, session vdc_24c28d832d3945be: a
        # complete, saved dataset with "1 of 5 decided" in the strip — the value
        # from the opening turn.
        "decided": decided_counts(scoreboard),
        "suggestion": None,
        "response": "",
        "respondError": None,
    }
    # The joins the click just wrote, reported before anything else can fail.
    #
    # The write has already happened by this point — that is this endpoint's whole
    # A decision reply carries NO block, and this is the second half of that rule
    # — see the note where the model's own rewrite is attached, below.
    #
    # It was set to the draft's joins here until 2026-11-06, to fix a real symptom
    # (a click with no model answered `joins: null`). That fix did not work — with
    # no reply there is no message to hang a block on — and it caused a worse one:
    # every Done returned the set, the page appended a reply carrying it, the
    # newest joins message became the live block, and Done was offered again.
    # Measured 2026-11-06, session vdc_1065e907102548cf: message [42] is a Done
    # reply reading "Joins are settled as shown" and carrying seven joins.
    result["joins"] = None

    # 3. Ask the model what is next. A failure here leaves the 200 standing,
    #    because the write succeeded — the client is told the assistant could not
    #    respond, and it still has the draft it just asked for.
    connection_id = body.get("connectionId")
    selected_model = body.get("model")
    try:
        details = await get_connection_details(_db_pool, connection_id, user_id)
    except (ValueError, TypeError):
        result["respondError"] = await t(_db_pool, language, DATASETS["virtual.decision.no_connection"])
        # Logged before the return: this is the exit that used to leave no trace.
        _log_decision(chat_id, piece, result)
        return result

    try:
        async with _db_pool.acquire() as timeout_conn:
            _timeouts = await resolve_connection_timeouts(timeout_conn, connection_id)
        agent = ToolAgent(
            api_key=details["apiKey"], endpoint=details["endpoint"],
            model=selected_model or details["model"], provider=details["provider"],
            language=language,
            timeout=float(_timeouts.probe_seconds),
            connect_timeout=float(_timeouts.connect_seconds),
            registry=VIRTUAL_REGISTRY,
        )
        agent.db_pool = _db_pool
        agent.user_id = user_id
        # As on the message turn: the TOOL_LOOP line's correlation key, and the
        # same starting point for the dataset a save in this turn would create.
        # Without this the attribute does not exist and the read at the end of
        # the turn raises AttributeError — the message turn has always set it.
        agent.session_id = chat_id
        agent.saved_dataset_id = None
        agent.draft_snapshot = dict(draft)
        agent.draft_pieces = None
        agent.draft_schemas = None
        # The sources this click created are not this turn's to delete. The guard
        # in remove_output_column reads this; without it a turn unticked every
        # column of two confirmed sources and called the result "clearing out the
        # leftover draft" (measured 2026-11-05).
        agent.protected_sources = {
            s.get("alias") for s in (draft.get("sources") or []) if s.get("alias")
        }
        # The piece this click decided is not this turn's to rewrite either.
        #
        # `protected_sources` guards a set of aliases; this guards the one value
        # the user just chose. Measured 2026-11-06: a turn called `set_name` with
        # its own suggestion after the user had typed a different name, and
        # `set_storage` with `false` after the user had clicked Saved table. Both
        # writes were accepted, and the dataset was saved as the model preferred.
        # The note tells it not to; `_refuse_if_decided` is what makes that true.
        agent.decided_piece = piece
        agent.schema_snapshot = _schemas_from_context(context_data)
        agent.validation_snapshot = None
        # The turn runs on the STORED CONVERSATION, not on a single sentence.
        #
        # Until 2026-11-05 it was given one message — `body.get("message")` or
        # "Applied: sources" — and nothing else. So a chip click asked the model
        # to continue a conversation it could not see: it still had the system
        # prompt and the scoreboard, which is why the answers sounded plausible,
        # but it had never read a word of what it or the user had said.
        #
        # `run_tool_loop` appends the reply (and any tool traffic) to the list it
        # is given, so the same list is what gets persisted below.
        history = list(row["messages"] or [])
        typed = body.get("message")
        if typed:
            history.append({"role": "user", "content": typed})
        else:
            # A chip is an ACT, not speech. The user clicked; they did not type.
            #
            # The turn still needs a user message — the model must be asked what
            # is next, and role alternation is what the provider expects — so the
            # record says what happened rather than putting words in the user's
            # mouth. The earlier fallback ("Use the selection above.") was an
            # accurate summary and still a fabrication: reloaded, the transcript
            # showed the user saying something they never said.
            #
            # `content` is the human-readable rendering so the model reads a
            # sentence; `decision` marks the turn as an act, with what was chosen
            # and how much of it, so the page can render it as one.
            history.append({
                "role": "user",
                "content": await t(_db_pool, language, virtual_decision_applied),
                "decision": _decision_record(piece, value, draft),
            })
        answer, _events = await agent.run_tool_loop(
            build_prompt(
                context_data,
                language,
                scoreboard=await _resolve_scoreboard_texts(
                    _stored_scoreboard(context_data, language), context_data, language
                ),
            ) + DECISION_TURN_NOTE.format(accepted=_accepted_lines(piece, value, draft, previous_draft)),
            history,
        )
        result["response"] = answer or ""
        # An empty reply is not a success. The message endpoint replaces one with
        # a fallback sentence; this endpoint had no equivalent, so a turn that
        # spent every round calling tools and never produced text returned
        # HTTP 200 with `response: ""` and `respondError: None` — the user saw the
        # draft change and no explanation. Measured 2026-11-05.
        #
        # `respondError`, not `response`: the choice WAS saved, so this is not a
        # failure of the chip; it is the assistant declining to explain itself,
        # and the page has a place for that.
        if not (answer or "").strip():
            result["respondError"] = await t(
                _db_pool, language, virtual_decision_no_reply
            )
        suggestion = getattr(agent, "_suggestion", None)
        if suggestion:
            result["suggestion"] = suggestion

        # The turn's reply is part of the conversation, so it is stored with it.
        #
        # Until 2026-11-05 this endpoint wrote nothing to `messages`: a chip click
        # produced an answer that existed only in the tab that made it. Reload,
        # or pick the chat again from the list, and the answer was gone while the
        # message that prompted it — now marked applied — was still there.
        # Measured 2026-11-05: 24 stored messages, the last one the *offer*, and
        # the reply the user had just read absent.
        #
        # Only the assistant message is appended. The chip itself is the user's
        # turn, and it is already visible in two places — the draft, as a decided
        # piece, and the offer message above, marked applied. A synthesised
        # "Applied: sources" line would be a third copy of that fact, in English,
        # in a transcript that is otherwise the model's own words.
        if suggestion:
            # The offer belongs to the message that made it, exactly as on the
            # message endpoint: find the reply the loop just appended.
            for message in reversed(history):
                if message.get("role") == "assistant" and not message.get("tool_calls"):
                    message["suggestion"] = suggestion
                    break
        # The joins this turn left behind, stored with the reply. The block in
        # the chat is rendered from the newest message that carries them, and
        # every older one renders its own rows read-only — so a reopened
        # transcript shows what was decided when, instead of a sentence that
        # refers to a control which is no longer there.
        #
        # Stored per message rather than once, deliberately: a snapshot is the
        # only form that stays honest after the draft has moved on. Six joins
        # with reasons is well under a kilobyte, and only turns that touched
        # joins pay it.
        #
        # A block belongs to the turn that PROPOSED the joins, not to the turn
        # that confirmed them. So a reply gets one only when the model itself
        # rewrote the set in its follow-up — never because the user clicked Done
        # or Apply, which would hand the user a fresh editor to confirm again.
        #
        # The click case used to be included, on the reasoning that the applier
        # had written the set so the draft held it. That is what looped: every
        # Done returned the joins, the page appended the reply carrying them, the
        # newest joins message became the live block, and Done was offered again.
        # The model's joins, but only if THIS turn changed them.
        #
        # `_pieces` seeds `draft_pieces` from `draft_snapshot` — a turn that
        # decides one piece must not drop the pieces earlier turns decided — so
        # `draft_pieces["joins"]` is non-empty on every turn once joins exist. A
        # truthiness test therefore attached the whole set to every reply, and the
        # page renders the newest message carrying joins as the live editor. That
        # is the loop the user saw on 2026-11-06: the join block reappearing under
        # each answer while the conversation moved on to the name and storage.
        #
        # The test is the same one the persistence below uses: did the value move?
        joins_now = joins_for_reply(agent)
        result["joins"] = joins_now if joins_now else result.get("joins")
        if joins_now and (answer or "").strip():
            for message in reversed(history):
                if message.get("role") == "assistant" and not message.get("tool_calls"):
                    message["joins"] = joins_now
                    break
        if (answer or "").strip():
            async with _db_pool.acquire() as conn:
                await conn.execute(
                    'UPDATE "VirtualDatasetChat" SET messages = $2::jsonb, "updatedAt" = NOW() WHERE id = $1',
                    chat_id, history,
                )
        # Link the dataset this turn saved, exactly as the message turn does.
        #
        # This is the path a conversation actually finishes on: the storage chip
        # is the last decision, so the save and the link happen on the same
        # click. The message path had the linking and this one did not, so the
        # session kept no pointer to the dataset it had just created.
        if await link_saved_dataset(_db_pool, chat_id, agent.saved_dataset_id):
            result["datasetId"] = agent.saved_dataset_id

        # The model may itself have decided a piece while answering; persist those
        # through the same merge, and report the draft as it ended up.
        changed = getattr(agent, "draft_pieces", None)
        if changed:
            touched = {k: v for k, v in changed.items() if draft.get(k) != v}
            if touched:
                merged = await merge_draft_pieces(_db_pool, chat_id, user_id, touched)
                if merged is not None:
                    result["draft"] = merged
    except RuntimeError as exc:
        logging.getLogger(__name__).error(f"Virtual decision LLM error: {exc}")
        result["respondError"] = await t(_db_pool, language, DATASETS["virtual.decision.model_failed"], error=str(exc))

    # One line, every decision turn — the comment on `_log_decision` says why it
    # exists and what it distinguishes. Called here and at the early return
    # above; the Go port calls its own at three exits. A new exit must call it.
    _log_decision(chat_id, piece, result)

    return result
