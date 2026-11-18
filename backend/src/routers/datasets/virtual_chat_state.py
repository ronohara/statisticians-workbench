# src/routers/datasets/virtual_chat_state.py
# ============================================================
# VIRTUAL CHAT STATE — the per-piece write layer for a chat
# session's context blob (Item 5 of the v2 plan).
# ============================================================
"""Read-modify-write is what breaks a shared session row.

A virtual-dataset chat session is shared mutable memory: the turn's tools write
to it, and — from Item 7 onward — the chip endpoint writes to it too, possibly
while a turn is still running. Before this module every writer did
*read the whole `contextData` object, change one key, write the whole object
back*, so two writers in flight meant the last one silently discarded the
other's key. Nothing reported it, because both writes succeeded.

The rule is the project's own (`project-design.md` §1.4), and this module is
where it is applied to the virtual concierge: **the state blob is merged per
key, never replaced** — `contextData = contextData || $1::jsonb` — and the
draft, which is itself an object of pieces, is merged one level deeper:

    contextData = jsonb_set(contextData, '{draft}',
                            COALESCE(contextData->'draft', '{}') || $1,
                            true)

So a writer sends only the pieces it decided, and a concurrent writer touching
a different piece composes instead of clobbering. Two writes to the *same*
piece still last-one-wins, which is correct: it is the answer the user saw last.

**The draft has one door.** `merge_context_keys` refuses a `draft` key, so the
whole-object replacement this module exists to prevent cannot be reintroduced by
a caller taking the other function. That refusal is a test, not a convention.

**A tick is two pieces in one statement.** Ticking a column in the tree adds the
column to the output list *and* brings its source into being (design §4.6), so
`sources` and `columns` change together. `merge_draft_pieces` takes an arbitrary
piece map and writes it in one `UPDATE`, which is what makes that a single
transition rather than two writes that a reader could observe half-done.
"""

from typing import Any, Dict, Optional

#: The draft pieces a writer may set. Not a whitelist of values — a check that a
#: caller is writing pieces, not the whole definition.
#:
#: **The piece model is the only shape.** There is no legacy form to accommodate
#: and no migration of stored sessions: existing virtual-dataset chat records are
#: purged rather than read, so a draft holds pieces and nothing else. If a stored
#: blob still carries an older key, that key is inert — nothing reads it and this
#: set refuses to write one.
DRAFT_PIECES = frozenset(
    {
        "name",
        "goal",
        "sources",
        "joins",
        "columns",
        "materialized",
        "schemas",
    }
)

class UnknownPiece(ValueError):
    """A caller tried to write a draft piece this module does not know.

    Refused rather than written: an unknown piece is either a typo, in which case
    writing it silently creates a key nothing will ever read, or a new piece
    added without saying so, in which case the set above is the place to say it.
    """


class DraftThroughTheWrongDoor(ValueError):
    """A caller sent `draft` to `merge_context_keys`.

    Refused because that is the whole-object replacement this module exists to
    prevent, wearing a different name.
    """


async def link_saved_dataset(pool, chat_id: str, saved_dataset_id) -> bool:
    """Record the dataset a turn saved on the conversation that saved it.

    Both turn paths call this. Until 2026-11-06 only the message path did — the
    linking lived inline in `send_chat_message` and nothing called it from
    `apply_decision`. So a conversation that ended on a click saved its dataset
    and left `VirtualDatasetChat.datasetId` NULL: measured on
    `vdc_be7b3bc0175a42df`, whose dataset `vd_d31158c13fc04527` was saved at
    20:02 and whose session row still named no dataset. Every session created
    that day reads the same way. Anything that navigates session → dataset finds
    nothing for exactly the conversations that finished on a chip, which is how
    most of them finish.

    Returns True when a link was written. A turn that saved nothing writes
    nothing, which is the common case — and the reason the two callers share a
    function instead of carrying four lines each, one of which gets forgotten.
    """
    if not saved_dataset_id:
        return False
    async with pool.acquire() as conn:
        await conn.execute(
            'UPDATE "VirtualDatasetChat" SET "datasetId" = $1, "updatedAt" = NOW() WHERE id = $2',
            saved_dataset_id, chat_id,
        )
    return True


async def merge_draft_pieces(
    pool,
    chat_id: str,
    user_id: str,
    pieces: Dict[str, Any],
) -> Optional[dict]:
    """Merge `pieces` into the session's draft, in one statement.

    Returns the merged draft, or ``None`` when the session is not the caller's
    (the ``UPDATE`` matches nothing, so nothing is written and the caller can
    answer 404 without a second query).

    One statement, not a read followed by a write: the merge happens inside the
    database, so a concurrent writer's piece is composed rather than overwritten.
    """
    if not pieces:
        return None
    unknown = set(pieces) - DRAFT_PIECES
    if unknown:
        raise UnknownPiece(f"unknown draft piece(s): {', '.join(sorted(unknown))}")

    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            UPDATE "VirtualDatasetChat"
               SET "contextData" = jsonb_set(
                       "contextData",
                       '{draft}',
                       COALESCE("contextData"->'draft', '{}'::jsonb) || $1::jsonb,
                       true),
                   "updatedAt" = NOW()
             WHERE id = $2 AND "userId" = $3
            RETURNING "contextData"->'draft' AS draft
            """,
            # Bound as a plain object: the pool's json codecs serialise it. A
            # pre-serialised string would be encoded twice and the column would
            # become an array (project-design.md §3.1).
            pieces,
            chat_id,
            user_id,
        )
    return row["draft"] if row else None


async def merge_context_keys(
    pool,
    chat_id: str,
    user_id: str,
    keys: Dict[str, Any],
) -> Optional[dict]:
    """Merge top-level context keys, in one statement.

    For state that is not part of the definition — today the tree's fold. The
    same per-key rule applies at this level: ``contextData || $1``, so a key this
    caller does not own is left alone.

    ``draft`` is refused (see :class:`DraftThroughTheWrongDoor`). An unknown key
    is *not* refused here, because this level is the blob itself and a future
    reader may add a key without touching this module; the draft pieces are the
    set that has to stay closed.

    ``panelCollapsed`` — the fold of the docked tree, scoped to the session so a
    reader who folds it keeps it folded (design §9.4) — is written through this
    function rather than the draft door. Nothing calls it with that key yet: the
    panel that needs it is Item 14's, and the capability is here so that item has
    one place to write to.
    """
    if not keys:
        return None
    if "draft" in keys:
        raise DraftThroughTheWrongDoor(
            "contextData.draft is merged piece by piece — use merge_draft_pieces"
        )

    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            UPDATE "VirtualDatasetChat"
               SET "contextData" = "contextData" || $1::jsonb,
                   "updatedAt" = NOW()
             WHERE id = $2 AND "userId" = $3
            RETURNING "contextData" AS context
            """,
            keys,
            chat_id,
            user_id,
        )
    return row["context"] if row else None


async def load_context(pool, chat_id: str, user_id: str) -> Optional[dict]:
    """The session's context blob, or ``None`` when it is not the caller's.

    Reads for a caller that only needs to look — the turn path already has the
    row, so this exists for the tests and for any future reader that needs the
    blob without loading messages too.
    """
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            'SELECT "contextData" FROM "VirtualDatasetChat" WHERE id = $1 AND "userId" = $2',
            chat_id,
            user_id,
        )
    return row["contextData"] if row else None


async def merge_introspected_table(
    pool,
    chat_id: str,
    user_id: str,
    key: str,
    entry: Dict[str, Any],
) -> Optional[dict]:
    """Merge ONE entry into ``contextData.introspectedTables``.

    The same clobbering defect lives one level below the draft: this route used
    to read the whole ``introspectedTables`` map, add its entry and write the map
    back, so two tables introspected at once lost one of them. The merge is done
    inside the statement, keyed by the entry's own name, so concurrent
    introspections of different tables compose.

    ``introspectedTables`` is not a draft piece — it is the cache of what the
    schema reader has seen, which is why it has its own door rather than going
    through ``merge_draft_pieces``.
    """
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            UPDATE "VirtualDatasetChat"
               SET "contextData" = jsonb_set(
                       "contextData",
                       '{introspectedTables}',
                       COALESCE("contextData"->'introspectedTables', '{}'::jsonb)
                           || jsonb_build_object($1::text, $2::jsonb),
                       true),
                   "updatedAt" = NOW()
             WHERE id = $3 AND "userId" = $4
            RETURNING "contextData"->'introspectedTables' AS tables
            """,
            key,
            entry,
            chat_id,
            user_id,
        )
    return row["tables"] if row else None


# ── the tick ─────────────────────────────────────────────────
#
# Ticking a column is ONE gesture that decides two pieces (design §4.6): the
# column joins the output list and its source comes into being. On the AI page
# that has to be a write, because the draft lives in the session's context blob —
# the manual editor holds it in component state, so its tree can do this locally
# and this page's cannot.
#
# The two pieces therefore go in ONE statement, which is what `merge_draft_pieces`
# is for. What it cannot do is MINT AN ALIAS, because that depends on the draft as
# it stands: read, decide, write. So the read takes a row lock (`FOR UPDATE`) in
# the same transaction as the write, and a second tick arriving concurrently waits
# rather than minting the alias the first one just took.
#
# The semantics are the tool layer's, not a second opinion about them:
# `_exec_add_source` brings a source in by alias, `_exec_remove_output_column`
# untickes one column and treats "the source's last column went" as the source
# leaving — pruning its joins with it. This is the same rule, reached by a click.


def _next_alias(sources: list) -> str:
    """The first free `sN`, which is the manual editor's own naming."""
    used = {s.get("alias") for s in sources if s.get("alias")}
    n = 1
    while f"s{n}" in used:
        n += 1
    return f"s{n}"


def _same_source(source: dict, connection_id, table_name, dataset_id) -> bool:
    """Whether a stored source IS the one the caller named.

    A dataset source and a connection source are different things even when they
    share a table name, so the identity is checked by kind first. `connectionId`
    is compared as an int because it arrives from a URL as an int and sits in the
    blob as an int, while a careless caller may send it as a string.
    """
    if dataset_id:
        return source.get("datasetId") == dataset_id
    if source.get("datasetId"):
        return False
    if source.get("tableName") != table_name:
        return False
    try:
        return int(source.get("connectionId")) == int(connection_id)
    except (TypeError, ValueError):
        return False


async def toggle_output_column(
    pool,
    chat_id: str,
    user_id: str,
    *,
    action: str,
    column: str,
    connection_id=None,
    table_name: str = "",
    dataset_id: str = "",
    storage_type: str = "",
) -> Optional[dict]:
    """Tick or untick one column, deciding `sources` and `columns` together.

    Returns ``{"draft", "alias", "ticked", "removedSource"}``, or ``None`` when the
    session is not the caller's — the same answer a missing session gives, so a
    caller who may not write cannot learn that the row exists.

    Unticking a column the draft does not have writes nothing and reports what the
    draft holds, which is the honest answer: the click asked for a state the
    session is already in.
    """
    if action not in ("tick", "untick"):
        raise ValueError(f"unknown action {action!r}")

    async with pool.acquire() as conn:
        async with conn.transaction():
            row = await conn.fetchrow(
                'SELECT "contextData"->\'draft\' AS draft FROM "VirtualDatasetChat" '
                'WHERE id = $1 AND "userId" = $2 FOR UPDATE',
                chat_id,
                user_id,
            )
            if row is None:
                return None

            draft = dict(row["draft"] or {})
            sources = [dict(s) for s in (draft.get("sources") or [])]
            columns = [dict(c) for c in (draft.get("columns") or [])]
            alias = next(
                (s.get("alias") for s in sources
                 if _same_source(s, connection_id, table_name, dataset_id)),
                None,
            )
            removed_source = False

            if action == "tick":
                if alias is None:
                    alias = _next_alias(sources)
                    source = {"alias": alias}
                    if dataset_id:
                        source["datasetId"] = dataset_id
                    else:
                        source["connectionId"] = int(connection_id)
                        source["tableName"] = table_name
                    if storage_type:
                        source["storageType"] = storage_type
                    sources.append(source)
                if not any(c.get("source") == alias and c.get("column") == column for c in columns):
                    columns.append({"source": alias, "column": column})
            else:
                if alias is None:
                    # Nothing to untick. No write: reporting the draft as it
                    # stands is truer than a success that changed nothing.
                    return {"draft": draft, "alias": None, "ticked": False,
                            "removedSource": False}
                columns = [c for c in columns
                           if not (c.get("source") == alias and c.get("column") == column)]
                # The source leaves with its last column (§4.6) — and a join that
                # names a source which no longer exists is debris the scoreboard
                # would report as broken.
                if not any(c.get("source") == alias for c in columns):
                    sources = [s for s in sources if s.get("alias") != alias]
                    removed_source = True

            pieces = {"sources": sources, "columns": columns}
            if removed_source:
                pieces["joins"] = [j for j in (draft.get("joins") or [])
                                   if j.get("left") != alias and j.get("right") != alias]

            merged = await conn.fetchrow(
                """
                UPDATE "VirtualDatasetChat"
                   SET "contextData" = jsonb_set(
                           "contextData",
                           '{draft}',
                           COALESCE("contextData"->'draft', '{}'::jsonb) || $1::jsonb,
                           true),
                       "updatedAt" = NOW()
                 WHERE id = $2 AND "userId" = $3
                RETURNING "contextData"->'draft' AS draft
                """,
                pieces,
                chat_id,
                user_id,
            )
    if merged is None:
        return None
    return {
        "draft": merged["draft"],
        "alias": alias,
        "ticked": action == "tick",
        "removedSource": removed_source,
    }


def _introspection_key(selection) -> Optional[str]:
    """The cache key a selection's columns belong under, or None.

    Same physical identity the reader resolves — `dataset_<id>` or
    `connection_<id>_<table>` — so the chip path writes exactly what
    `_schemas_from_context` looks for. A selection naming neither cannot be
    cached, and nothing is written for it.
    """
    if not isinstance(selection, dict):
        return None
    dataset_id = selection.get("datasetId")
    if isinstance(dataset_id, str) and dataset_id.strip():
        return f"dataset_{dataset_id.strip()}"
    connection_id = selection.get("connectionId")
    table_name = selection.get("tableName")
    if connection_id not in (None, "") and isinstance(table_name, str) and table_name.strip():
        try:
            return f"connection_{int(connection_id)}_{table_name.strip()}"
        except (TypeError, ValueError):
            return None
    return None


async def apply_source_selection(
    pool,
    chat_id: str,
    user_id: str,
    selections,
) -> Optional[dict]:
    """Decide several sources, and their columns, as ONE act.

    ``selections`` is what a multi-select chip confirmed — one entry per source::

        {"datasetId": "…", "columns": ["a", "b"], "storageType": "postgresql"}
        {"connectionId": 3, "tableName": "orders", "columns": ["order_id"]}

    Each entry is self-contained on purpose. A flat list of sources plus a flat
    list of columns would have to agree about aliases before the function that
    assigns them had run, and the alias is the thing this function decides.

    **All-or-nothing.** A confirm is one act, so a half-applied set is worse than
    a refused one: the draft would hold tables the user never accepted beside the
    ones they did, and the scoreboard would report the result as decided. The
    read holds the row, the loop only builds a value in memory, and the write is
    one statement — so a failure anywhere leaves the draft exactly as it was.

    Aliases are derived here with the tree's own rules (``_same_source`` to
    recognise a table already in the draft, ``_next_alias`` to name a new one).
    That is what keeps the two surfaces agreeing about what ``s1`` means: a chip
    that invented its own alias would make the same table answer to two names
    depending on which surface added it.

    Returns ``{"draft", "aliases"}``, or ``None`` when the session is not the
    caller's. Raises ``ValueError`` on a selection that names no table.
    """
    if not isinstance(selections, list) or not selections:
        raise ValueError("a source selection needs at least one source")

    async with pool.acquire() as conn:
        async with conn.transaction():
            row = await conn.fetchrow(
                'SELECT "contextData"->\'draft\' AS draft FROM "VirtualDatasetChat" '
                'WHERE id = $1 AND "userId" = $2 FOR UPDATE',
                chat_id,
                user_id,
            )
            if row is None:
                return None

            draft = dict(row["draft"] or {})
            sources = [dict(s) for s in (draft.get("sources") or [])]
            columns = [dict(c) for c in (draft.get("columns") or [])]
            aliases = []

            for selection in selections:
                if not isinstance(selection, dict):
                    raise ValueError("a source selection must be an object")

                dataset_id = (selection.get("datasetId") or "").strip() if isinstance(selection.get("datasetId"), str) else selection.get("datasetId")
                connection_id = selection.get("connectionId")
                table_name = (selection.get("tableName") or "").strip()

                if not dataset_id and (connection_id in (None, "") or not table_name):
                    # The same rule the tick endpoint applies: one of the two
                    # identities, and a connection source needs both halves.
                    raise ValueError(
                        "a source selection needs datasetId, or connectionId and tableName"
                    )

                alias = next(
                    (s.get("alias") for s in sources
                     if _same_source(s, connection_id, table_name, dataset_id)),
                    None,
                )
                if alias is None:
                    alias = _next_alias(sources)
                    source = {"alias": alias}
                    if dataset_id:
                        source["datasetId"] = dataset_id
                    else:
                        source["connectionId"] = int(connection_id)
                        source["tableName"] = table_name
                    storage_type = selection.get("storageType")
                    if storage_type:
                        source["storageType"] = storage_type
                    sources.append(source)

                if alias not in aliases:
                    aliases.append(alias)

                for column in selection.get("columns") or []:
                    name = column if isinstance(column, str) else (column or {}).get("name")
                    name = (name or "").strip() if isinstance(name, str) else ""
                    if not name:
                        continue
                    if not any(c.get("source") == alias and c.get("column") == name
                               for c in columns):
                        columns.append({"source": alias, "column": name})

            pieces = {"sources": sources, "columns": columns}
            merged = await conn.fetchrow(
                """
                UPDATE "VirtualDatasetChat"
                   SET "contextData" = jsonb_set(
                           "contextData",
                           '{draft}',
                           COALESCE("contextData"->'draft', '{}'::jsonb) || $1::jsonb,
                           true),
                       "updatedAt" = NOW()
                 WHERE id = $2 AND "userId" = $3
                RETURNING "contextData"->'draft' AS draft
                """,
                pieces,
                chat_id,
                user_id,
            )

            # The columns the user accepted are the source's schema, so they go
            # into the same cache `set_source_columns` writes — in the SAME
            # transaction, because a draft that names columns the cache does not
            # know leaves the scoreboard reporting the source's columns as
            # unread. That was the first live experiment's finding: five sources
            # and fifteen columns in the draft, five `columns` pieces still
            # pending, because only the tool wrote the cache and the chip did not.
            for selection, alias in zip(selections, aliases):
                names = [
                    c if isinstance(c, str) else (c or {}).get("name")
                    for c in (selection.get("columns") or [])
                ]
                names = [n.strip() for n in names if isinstance(n, str) and n.strip()]
                if not names:
                    continue
                cache_key = _introspection_key(selection)
                if cache_key is None:
                    continue
                entry = await conn.fetchval(
                    """
                    UPDATE "VirtualDatasetChat"
                       SET "contextData" = jsonb_set(
                               "contextData",
                               '{introspectedTables}',
                               COALESCE("contextData"->'introspectedTables', '{}'::jsonb)
                                 || jsonb_build_object($1::text, $2::jsonb),
                               true)
                     WHERE id = $3 AND "userId" = $4
                    RETURNING true
                    """,
                    cache_key,
                    {"columns": [{"name": n} for n in names]},
                    chat_id,
                    user_id,
                )
                if not entry:
                    # The row vanished mid-transaction; undo the draft too, so
                    # the confirm stays all-or-nothing.
                    raise ValueError("the session row is no longer the caller's")

    if merged is None:
        return None
    return {"draft": merged["draft"], "aliases": aliases}
