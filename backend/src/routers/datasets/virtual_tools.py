"""
AI virtual-dataset tools — thin wrappers over existing backend functions.

Each executor calls existing code (``datasets.virtual.save_virtual_dataset_record``,
``datasets.virtual.validate_virtual_dataset_definition``,
``datasets.virtual.fetch_virtual_join``); no validation or storage logic is
re-implemented.
"""

from fastapi import HTTPException

import logging

from src.chat.tool_agent import register_tool, tool_error
from src.utils.translation import t
from .browse import list_connection_tables, list_table_columns
from .connection_probe import (
    PROBE_REACHABLE,
    ProbeResult,
    _record,
    classify_connection_error,
    probe_one,
)
from .translations import DATASETS, virtual_tool_no_source, virtual_tool_no_sources_yet
from .virtual_chat_state import _same_source, merge_introspected_table
from .virtual import (
    fetch_virtual_join,
    save_virtual_dataset_record,
    validate_virtual_dataset_definition,
)

_VIRTUAL_SQL_SCHEMA = {
    "type": "object",
    "description": (
        "The virtual dataset definition built from the conversation: aliased "
        "sources, the joins between them, and the output columns."
    ),
    "properties": {
        "sources": {
            "type": "array",
            "description": "The tables feeding the join, each with a short alias.",
            "items": {
                "type": "object",
                "properties": {
                    "alias": {"type": "string"},
                    "connectionId": {"type": "integer"},
                    "tableName": {"type": "string"},
                    "storageType": {"type": "string"},
                    "datasetId": {"type": "string"},
                },
                "required": ["alias"],
            },
        },
        "joins": {
            "type": "array",
            "description": "JOIN clauses linking two sources by their aliases.",
            "items": {
                "type": "object",
                "properties": {
                    "left": {"type": "string"},
                    "leftCol": {"type": "string"},
                    "right": {"type": "string"},
                    "rightCol": {"type": "string"},
                    "type": {"type": "string"},
                },
                "required": ["left", "leftCol", "right", "rightCol"],
            },
        },
        "columns": {
            "type": "array",
            "description": "The columns to expose, each referencing a source alias.",
            "items": {
                "type": "object",
                "properties": {
                    "source": {"type": "string"},
                    "column": {"type": "string"},
                },
                "required": ["source", "column"],
            },
        },
    },
    "required": ["sources"],
}

_TOOL_SCHEMAS = [
    {
        "type": "function",
        "function": {
            "name": "save_virtual_dataset",
            "description": (
                "Create or update a virtual dataset. Validates implicitly by "
                "persisting the definition through the same path the manual "
                "editor uses; returns the dataset id."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "Dataset name"},
                    "virtualSql": _VIRTUAL_SQL_SCHEMA,
                    "materialized": {
                        "type": "boolean",
                        "description": "Persist a materialised table instead of a live view.",
                    },
                    "id": {
                        "type": "string",
                        "description": "Existing dataset id to update (omit to create new).",
                    },
                },
                "required": ["name", "virtualSql"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "validate_virtual_dataset",
            "description": (
                "Validate a virtual dataset definition (sources exist and are "
                "accessible, join columns exist, output columns reference known "
                "sources) and return {valid, errors, outputSchema?}."
            ),
            "parameters": {
                "type": "object",
                "properties": {"virtualSql": _VIRTUAL_SQL_SCHEMA},
                "required": ["virtualSql"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "preview_virtual_dataset",
            "description": (
                "Run the virtual dataset join with a small row limit and return "
                "{columns, rows, row_count} for a preview."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "virtualSql": _VIRTUAL_SQL_SCHEMA,
                    "limit": {"type": "integer", "description": "Max rows to return (default 10)."},
                },
                "required": ["virtualSql"],
            },
        },
    },
]


async def _exec_save_virtual_dataset(agent, name, virtualSql, materialized=False, **args) -> dict:
    body = {"name": name, "virtualSql": virtualSql, "materialized": bool(materialized)}
    if args.get("id"):
        body["id"] = args["id"]
    result = await save_virtual_dataset_record(agent.db_pool, agent.user_id, body, agent.language)
    setattr(agent, "saved_dataset_id", result.get("id"))
    setattr(agent, "draft_name", name)
    setattr(agent, "draft_virtual_sql", virtualSql)
    return result


async def _exec_validate_virtual_dataset(agent, virtualSql, **args) -> dict:
    result = await validate_virtual_dataset_definition(
        agent.db_pool, agent.user_id, virtualSql, agent.language
    )
    setattr(agent, "draft_virtual_sql", virtualSql)
    setattr(agent, "validation_result", result)
    return result


async def _exec_preview_virtual_dataset(agent, virtualSql, limit=10, **args) -> dict:
    # Validate first so structural mistakes (missing connectionId, unknown
    # source/column aliases) come back as structured, actionable errors instead
    # of a raw join exception mid-materialisation.
    validation = await validate_virtual_dataset_definition(
        agent.db_pool, agent.user_id, virtualSql, agent.language
    )
    setattr(agent, "draft_virtual_sql", virtualSql)
    if not validation.get("valid"):
        return validation

    columns, rows = await fetch_virtual_join(
        virtualSql, agent.user_id, agent.db_pool, agent.language, limit=int(limit)
    )
    return {
        "columns": columns,
        "rows": [[str(r[c]) if r[c] is not None else None for c in columns] for r in rows],
        "row_count": len(rows),
    }


_SOURCES_TOOL_SCHEMA = {
    "type": "function",
    "function": {
        "name": "get_sources",
        "description": (
            "List the data sources available to the user: database connections "
            "and local datasets."
        ),
        "parameters": {"type": "object", "properties": {}, "required": []},
    },
}

_TABLES_TOOL_SCHEMA = {
    "type": "function",
    "function": {
        "name": "get_tables",
        "description": "List the table names in a database connection.",
        "parameters": {
            "type": "object",
            "properties": {"connection_id": {"type": "integer", "description": "The connection id"}},
            "required": ["connection_id"],
        },
    },
}

_PROBE_TOOL_SCHEMA = {
    "type": "function",
    "function": {
        "name": "probe_connection",
        "description": "Re-check whether one database connection can be reached now, "
                       "ignoring the cached answer. Use it when a connection is reported "
                       "unreachable and you have reason to think that has changed — the "
                       "cache is at most a minute old, and a stale 'unreachable' would make "
                       "you refuse work you could do. Returns state, detail and when it was "
                       "checked.",
        "parameters": {
            "type": "object",
            "properties": {"connection_id": {"type": "integer", "description": "The connection id"}},
            "required": ["connection_id"],
        },
    },
}

_COLUMNS_TOOL_SCHEMA = {
    "type": "function",
    "function": {
        "name": "get_columns",
        "description": (
            "List the columns (name and type) of a table. For a table in a "
            "database connection pass connection_id and table_name; for a local "
            "uploaded/notebook/connection-backed dataset pass dataset_id."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "connection_id": {"type": "integer", "description": "The connection id"},
                "table_name": {"type": "string", "description": "The table name"},
                "dataset_id": {"type": "string", "description": "The dataset id from get_sources"},
            },
            "required": [],
        },
    },
}

async def _exec_get_sources(agent, **args) -> dict:
    from .virtual_chat import fetch_available_sources
    return await fetch_available_sources(agent.db_pool, agent.user_id, agent.language)


async def _exec_get_tables(agent, connection_id, **args) -> dict:
    """List a connection's tables, or say why it could not be reached.

    A raw driver message names a hostname and leaves the model to work out what to
    do with it. The classified state says what KIND of failure it was — and each
    kind implies a different next move: try another connection, stop retrying an
    auth failure, or give up because the data is there but unreadable.

    The result is also recorded, so the next `get_sources` shows the state without
    re-probing, and a second call in the same turn finds the answer already known.
    """
    try:
        tables = await list_connection_tables(
            agent.db_pool, agent.user_id, agent.language, int(connection_id)
        )
    except HTTPException:
        raise
    except Exception as exc:  # noqa: BLE001 — every driver failure is classified
        state, detail = classify_connection_error(exc)
        await _record(
            agent.db_pool, int(connection_id),
            ProbeResult(connection_id=int(connection_id), state=state, detail=detail),
        )
        return {
            "connectionId": int(connection_id),
            "state": state,
            "detail": detail,
            "advice": _STATE_ADVICE.get(state, _STATE_ADVICE[PROBE_REACHABLE]),
            # `error` as well, so the tool-error convention still holds for a
            # caller that only looks for it.
            "error": detail,
        }
    return {"tables": tables, "connectionId": int(connection_id), "state": PROBE_REACHABLE}


# What each state means for the model's next move. Kept beside the tool rather
# than in translations because it is an instruction to the model, not text shown
# to a user — the user sees the phrase from DATASETS in the interface.
_STATE_ADVICE = {
    "reachable": "Use this connection.",
    "unreachable": "Do not retry this connection in this turn. Offer another one, or say it is unavailable.",
    "auth_failed": "Retrying will not help — the credential is wrong. Tell the user it needs fixing.",
    "no_database": "The host answered but that database is not there. Try another connection.",
    "no_permission": "Connected, but this account cannot read the schema. Retrying is pointless.",
    "incomplete": "This connection's own details are incomplete — that is a data problem, not a network one.",
}


async def _exec_probe_connection(agent, connection_id, **args) -> dict:
    """Force a fresh probe of one connection.

    Its documented purpose is single: the model checking a cached negative before
    refusing work. The cache is a convenience, and the one thing it must never do
    is make the model refuse something that would have worked.
    """
    result = await probe_one(
        agent.db_pool, agent.user_id, agent.language, int(connection_id), force=True
    )
    if result is None:
        return {"error": "There is no connection with that id that you can use."}
    return {
        "connectionId": result.connection_id,
        "state": result.state,
        "detail": result.detail,
        "elapsedMs": result.elapsed_ms,
        "advice": _STATE_ADVICE.get(result.state, ""),
    }


async def _exec_get_columns(agent, connection_id=None, table_name=None, dataset_id=None, **args) -> dict:
    if dataset_id is not None:
        from .schema import fetch_dataset_schema
        try:
            schema = await fetch_dataset_schema(dataset_id, agent.user_id, agent.language)
        except HTTPException as e:
            return tool_error("get_columns", e, agent=agent)
        columns = [
            {"name": c.get("name"), "type": c.get("dtype")}
            for c in schema.get("columns", [])
        ]
        return {"columns": columns}
    columns = await list_table_columns(agent.db_pool, agent.user_id, agent.language, int(connection_id), table_name)
    return {"columns": columns}


# ── the piece tools (Item 6) ────────────────────────────────
#
# Each tool decides ONE piece and hands back the scoreboard, so the model's next
# sentence is grounded in what is now decided rather than in what it remembers.
# This replaces `set_stage`: a stage told the model where it was, which it then
# had to remember; a piece tells it what changed, which it can read.
#
# The tools do NOT write to the session. They mutate `agent.draft_pieces`, and
# the turn path persists the result through Item 5's single merge point — so a
# chip endpoint writing a different piece while this turn runs composes instead
# of being clobbered. One write per turn, and it is the only one.

def _pieces(agent) -> dict:
    """The draft being built this turn, seeded from the stored one.

    Seeded rather than empty: a turn that decides one piece must not silently
    drop the pieces earlier turns decided. The seed is a copy, so a failed turn
    leaves the stored draft untouched.
    """
    pieces = getattr(agent, "draft_pieces", None)
    if pieces is None:
        pieces = dict(getattr(agent, "draft_snapshot", None) or {})
        setattr(agent, "draft_pieces", pieces)
    return pieces


def _schemas(agent) -> dict:
    """What is known about each alias's columns this turn."""
    schemas = getattr(agent, "draft_schemas", None)
    if schemas is None:
        schemas = dict(getattr(agent, "schema_snapshot", None) or {})
        setattr(agent, "draft_schemas", schemas)
    return schemas


def _scoreboard(agent) -> dict:
    """The scoreboard for the draft as it stands. Pure; no I/O."""
    from .virtual_scoreboard import ScoreboardInputs, compute_virtual_scoreboard
    return compute_virtual_scoreboard(
        ScoreboardInputs(
            draft=_pieces(agent),
            schemas=_schemas(agent),
            validation=getattr(agent, "validation_snapshot", None),
            language=getattr(agent, "language", "en") or "en",
        )
    )


def _answer(agent, **extra) -> dict:
    """What every piece tool returns: the scoreboard, plus whatever it decided."""
    return {"scoreboard": _scoreboard(agent), **extra}


def _source_aliases(agent) -> list:
    """The aliases the draft currently holds, in the order they were added."""
    return [
        s.get("alias")
        for s in (_pieces(agent).get("sources") or [])
        if s.get("alias")
    ]


async def _refuse_unknown_source(agent, *aliases) -> dict | None:
    """An error dict when one of ``aliases`` names no source, else ``None``.

    Five tools write knowledge or decisions *about a source*: which columns it
    has, how it joins, which of its columns the result keeps. Each is a write
    against an alias, so the alias has to name something the draft holds. When
    it does not, the write lands nowhere the scoreboard can read — and it is
    worse than lost: `set_source_columns('s', A)` followed by
    `add_source('s', B)` leaves the scoreboard believing B has A's columns.

    The refusal is returned, not raised. These executors already answer the
    model with ``{"error": ...}``, and a raised exception would end the turn
    where a wrong alias should cost one call.

    It names the aliases that DO exist, because the model cannot correct itself
    against a bare "not found" — the names are the thing it needs, and it may
    never have been told them. It also logs, so a model that keeps inventing
    aliases is visible rather than merely ineffective.
    """
    known = _source_aliases(agent)
    missing = [a for a in aliases if a not in known]
    if not missing:
        return None

    alias = missing[0]
    if known:
        detail = await t(agent.db_pool, agent.language, virtual_tool_no_source,
                         alias=alias, aliases=", ".join(known))
    else:
        detail = await t(agent.db_pool, agent.language, virtual_tool_no_sources_yet,
                         alias=alias)
    logging.getLogger(__name__).info(
        "tool call named an alias that is not a source: alias=%r known=%r session=%s",
        alias, known, getattr(agent, "session_id", None),
    )
    return {"error": detail, "sources": known}


async def _exec_set_goal(agent, goal, **args) -> dict:
    _pieces(agent)["goal"] = goal
    return _answer(agent, goal=goal)


async def _exec_add_source(agent, alias, connectionId=None, tableName=None,
                           datasetId=None, storageType=None, **args) -> dict:
    """Bring a source into the draft under an alias.

    The tree does this by ticking a column (design §4.6); a typed request does it
    here. Either way, `sources` is not a question the assistant asks — it is a
    consequence of which columns were chosen.

    **Identity wins over the name the model chose.** A table already in the draft
    keeps the alias it has, whatever alias is passed here, and the answer says so.
    Before this, de-duplication was by alias only, so `add_source("o", orders)`
    over a draft holding `s1 = orders` added the same table a second time:

        sources: s1=orders, s2=order_items, o=orders, oi=order_items, ...

    Measured 2026-11-05, in the turn that followed a two-table confirm — the model
    re-added both tables under its own names, and the draft then had two aliases
    per table. Every downstream piece treats an alias as a table, so the scoreboard
    reported eight sources where the user had accepted two, and any join naming
    `o` would have been a join to a table the user could not see was a duplicate.

    The rule that the chip path already follows, applied to the tool: a table has
    ONE alias, and it is the one the draft gave it.

    **And the turn after a sources click may not add one at all.** `sources` is
    the piece that click decided, so the same rule that guards `name` and
    `storage` guards it: measured 2026-11-06 on `vdc_be7b3bc0175a42df`, the user
    ticked six tables, and the turn that click started added a seventh — `stores`,
    as `s7` — with the sentence "I've taken your selection as it stands … and
    added `stores` so the store on each order resolves to a name and location."
    The reasoning was sound and the addition was still not the user's. A source
    is something a person ticked, and a turn that believes one is missing says so
    and asks; it does not tick it on their behalf.

    `protected_sources` is the neighbouring guard and does not cover this: it
    stops the turn *deleting* what the click created, not *extending* it.

    **Identity is answered before the guard, and the order matters.** The guard
    sat at the top of this function for one turn, and the cost is on record:
    measured 2026-11-06, session vdc_b2e3eed3f5ba4d1a, the model emitted six
    `add_source` calls in ONE round — the five tables the user had ticked plus
    `stores` — and got six identical refusals. Five of those six were not
    additions at all: the draft already held the table, and the old
    `existing_alias` branch would have answered each with `already_present` and
    the alias it has. The model learned nothing from the refusals — not which
    tables were present, not which of its six was new — and spent a round
    working it out in prose.
    """
    existing_alias = next(
        (s.get("alias") for s in (_pieces(agent).get("sources") or [])
         if s.get("alias") and _same_source(s, connectionId, tableName, datasetId)),
        None,
    )
    if existing_alias is not None:
        # Already here. Answer with the alias it actually has, so the model's next
        # call names the right one rather than the name it just invented. This is
        # an *answer*, not a change, so it holds on a decision turn too: a table
        # the draft already holds has not been added.
        return _answer(agent, source={"alias": existing_alias}, already_present=True,
                       note=f"This table is already in the draft as '{existing_alias}'.")

    refusal = _refuse_if_decided(agent, "sources")
    if refusal:
        # `_answer` and not the bare refusal: every other return from a piece
        # tool carries the scoreboard, and a refusal that omits it leaves the
        # model unable to see what the draft does hold — which is what it needs
        # in order to say something useful instead of retrying.
        return {**_answer(agent), **refusal}

    source = {"alias": alias}
    if datasetId:
        source["datasetId"] = datasetId
    if connectionId is not None:
        source["connectionId"] = int(connectionId)
    if tableName:
        source["tableName"] = tableName
    if storageType:
        source["storageType"] = storageType
    sources = [s for s in (_pieces(agent).get("sources") or []) if s.get("alias") != alias]
    sources.append(source)
    _pieces(agent)["sources"] = sources
    return _answer(agent, source=source)


async def _exec_remove_output_column(agent, source, column, **args) -> dict:
    """Untick one output column.

    Named for what it does rather than `remove_source`, because unticking the
    last column of a source is what removes the source — the tree has no
    separate remove either (design §4.6). That behaviour stands.

    **Except in the turn that follows a confirm.** The draft the user has just
    accepted is not the turn's to delete, and on 2026-11-05 a turn did exactly
    that: it unticked every column of two confirmed sources, called the result
    "clearing out the leftover draft", and replaced it with tables of its own.
    The prune is the mechanism; the wrong belief was the cause, and option 2 (the
    prompt) addresses that. This is the backstop for when the belief forms anyway:
    a source the user's click created cannot be removed by the turn that click
    started. A later turn, or the tree, removes it as before.
    """
    refusal = await _refuse_unknown_source(agent, source)
    if refusal:
        return refusal

    protected = getattr(agent, "protected_sources", None) or set()
    remaining_for_source = [
        c for c in (_pieces(agent).get("columns") or [])
        if c.get("source") == source and c.get("column") != column
    ]
    if source in protected and not remaining_for_source:
        return {
            "error": (
                f"Not removing the last column of '{source}': the user just accepted it, "
                "and unticking its last column would delete the table. Leave it in the "
                "draft and continue with the next piece — or say plainly that the table "
                "should go, for the user to confirm."
            ),
            "source": source,
            "protected": True,
        }

    columns = [c for c in (_pieces(agent).get("columns") or [])
               if not (c.get("source") == source and c.get("column") == column)]
    _pieces(agent)["columns"] = columns
    # Only THIS source is a candidate for removal. Pruning every source with no
    # columns would delete a source the caller did not name — and a source added
    # by add_source but not yet ticked has no columns by definition.
    if not any(c.get("source") == source for c in columns):
        sources = [s for s in (_pieces(agent).get("sources") or []) if s.get("alias") != source]
        _pieces(agent)["sources"] = sources
    remaining = {s.get("alias") for s in (_pieces(agent).get("sources") or [])}
    # A join or schema state for a source that no longer exists is debris.
    joins = [j for j in (_pieces(agent).get("joins") or [])
             if j.get("left") in remaining and j.get("right") in remaining]
    _pieces(agent)["joins"] = joins
    if source not in remaining:
        _schemas(agent).pop(source, None)
    return _answer(agent)


async def _persist_schema(agent, alias: str, names: list) -> None:
    """Fold a source's columns into the session's introspection cache.

    ``_schemas(agent)`` is the turn's view and dies with it. ``introspectedTables``
    is the session's, and it is what ``_schemas_from_context`` rebuilds from on
    the next turn. Without this the model re-reads every source on every turn:
    the scoreboard reports `columns` as unread each time, so each turn pays a
    tool round-trip and a full schema read for knowledge the session already has.

    The key is the physical identity, which is what that cache is keyed by —
    ``dataset_<id>`` or ``connection_<id>_<table>``. A source naming neither
    cannot be cached, and nothing is written for it.

    A failed write is logged and otherwise ignored: the knowledge is still good
    for the turn in hand, and losing the cache must not fail the tool.
    """
    source = next(
        (s for s in (_pieces(agent).get("sources") or []) if s.get("alias") == alias),
        None,
    )
    if not source:
        return
    dataset_id = source.get("datasetId")
    connection_id = source.get("connectionId")
    table_name = source.get("tableName")
    if dataset_id:
        key = f"dataset_{dataset_id}"
    elif connection_id is not None and table_name:
        key = f"connection_{connection_id}_{table_name}"
    else:
        return

    chat_id = getattr(agent, "session_id", None)
    pool = getattr(agent, "db_pool", None)
    if not chat_id or pool is None:
        return
    try:
        await merge_introspected_table(
            pool, chat_id, agent.user_id, key,
            {"columns": [{"name": n} for n in names]},
        )
    except Exception as exc:  # noqa: BLE001 — the cache is an optimisation
        logging.getLogger(__name__).warning(
            "could not persist the schema cache for %r: %s", key, exc,
        )


async def _exec_set_source_columns(agent, alias, columns, **args) -> dict:
    """Record what an alias's table contains.

    This is the schema cache the scoreboard reads — it is not a decision, it is
    knowledge, which is why it does not appear as a piece in the draft."""
    refusal = await _refuse_unknown_source(agent, alias)
    if refusal:
        return refusal
    from .virtual_scoreboard import SchemaState
    names = [c if isinstance(c, str) else c.get("name") for c in (columns or [])]
    kept = [n for n in names if n]
    _schemas(agent)[alias] = SchemaState.known(kept)
    await _persist_schema(agent, alias, kept)
    return _answer(agent, alias=alias, columns=names)


async def _exec_set_join(agent, left, leftCol, right, rightCol, type="inner",
                         reason=None, **args) -> dict:
    """Write one join into the draft, keeping the reason it was chosen.

    The reason is carried into the draft so the message can render the row as a
    sentence with its justification at the end. It is optional: a model that
    states only the pair still gets a usable row, and the row simply has no
    reason rather than an invented one.
    """
    refusal = await _refuse_unknown_source(agent, left, right)
    if refusal:
        return refusal
    joins = [j for j in (_pieces(agent).get("joins") or [])
             if not {j.get("left"), j.get("right")} == {left, right}]
    join = {"left": left, "leftCol": leftCol, "right": right,
            "rightCol": rightCol, "type": type or "inner"}
    if isinstance(reason, str) and reason.strip():
        join["reason"] = reason.strip()
    joins.append(join)
    _pieces(agent)["joins"] = joins
    return _answer(agent)


async def _exec_remove_join(agent, left, right, **args) -> dict:
    refusal = await _refuse_unknown_source(agent, left, right)
    if refusal:
        return refusal
    joins = [j for j in (_pieces(agent).get("joins") or [])
             if not {j.get("left"), j.get("right")} == {left, right}]
    _pieces(agent)["joins"] = joins
    return _answer(agent)


async def _exec_set_output_columns(agent, columns, **args) -> dict:
    refusal = await _refuse_unknown_source(
        agent, *[c.get("source") for c in (columns or []) if c.get("source")]
    )
    if refusal:
        return refusal
    _pieces(agent)["columns"] = [
        {"source": c.get("source"), "column": c.get("column")}
        for c in (columns or [])
        if c.get("source") and c.get("column")
    ]
    return _answer(agent)


def _refuse_if_decided(agent, piece: str):
    """Refuse to rewrite the piece the user just clicked.

    The decision turn is told, in DECISION_TURN_NOTE, that the click takes
    precedence over anything it proposed and that it must not replace the draft
    with its own version. Told, and not enforced — so measured 2026-11-06, session
    vdc_d4e7972173bc4121, a model did both:

      * the user typed `Bike Sales Factors` over the offered name; the turn called
        `set_name` with **its own** suggestion, `Bike Sales Factor Analysis`;
      * the user clicked **Saved table**; the turn called `set_storage` with
        `materialized: false`, its earlier recommendation.

    Both writes succeeded, the dataset was saved as the model preferred, and the
    transcript said so — the user's answer appeared in the decision record and
    nowhere else.

    This is the same shape as `protected_sources`, which exists because a turn
    once deleted the sources a click had just created. `protected_sources` guards
    a set of aliases; this guards the one piece the click decided. Returns a
    refusal dict, or None to let the call through.
    """
    decided = getattr(agent, "decided_piece", None)
    if decided != piece:
        return None
    # `error` is the key the tool loop reads to mark the call failed
    # (chat/tool_agent.py: `ok = not result.get("error")`). A refusal that wrote
    # `refused` instead would be reported to the model as a success — the tool
    # would look like it ran, the value would silently not change, and the model
    # would carry on believing the draft holds its own version. Same shape as
    # the `protected_sources` refusal above.
    return {
        "error": (
            f"Not changing `{piece}`: the user has just decided it by clicking. Their answer "
            f"is the dataset's value now, and this turn may not replace it. Continue with the "
            f"next piece, or say in one sentence what you did."
        ),
        "refused": True,
        "reason": "the_user_decided_this",
        "piece": piece,
    }


async def _exec_set_name(agent, name, **args) -> dict:
    refusal = _refuse_if_decided(agent, "name")
    if refusal:
        return refusal
    _pieces(agent)["name"] = name
    return _answer(agent, name=name)


async def _exec_set_storage(agent, materialized=False, **args) -> dict:
    refusal = _refuse_if_decided(agent, "storage")
    if refusal:
        return refusal
    _pieces(agent)["materialized"] = bool(materialized)
    return _answer(agent, materialized=bool(materialized))


async def _exec_get_scoreboard(agent, **args) -> dict:
    return _answer(agent)


async def _sources_proposal(agent, proposal) -> tuple:
    """Resolve the model's proposed tables against what the user may actually read.

    Returns ``(choices, refused)``. Each choice is an object — the contract the
    page needs for a multi-select, and the reason `choices` stops being a list of
    strings for this piece only:

        {"key": <stable id>, "label": <table name>, "value": {<draft identity>},
         "columns": [...]}

    **Nothing here trusts the model.** `fetch_available_sources` is the one
    function that answers "what may this user read", and every entry is matched
    against it: a dataset by id, a connection table by connection id plus a name
    the connection's own listing returns. A proposal naming anything else is
    refused whole — offering a chip that the confirm would then reject is worse
    than offering none, because the user has already clicked it.
    """
    from .virtual_chat import fetch_available_sources

    if not isinstance(proposal, list) or not proposal:
        return [], ["empty proposal"]

    available = await fetch_available_sources(agent.db_pool, agent.user_id, agent.language)
    datasets = {d.get("id"): d for d in (available.get("datasets") or []) if d.get("id")}
    connections = {c.get("connectionId"): c for c in (available.get("databaseConnections") or [])}

    # One table listing per distinct connection the proposal names, because a
    # table name alone cannot be checked against anything — the connection has to
    # say what it holds, exactly as the tree asks it on expand.
    listings = {}

    choices, refused = [], []
    for entry in proposal:
        if not isinstance(entry, dict):
            refused.append("an entry that is not an object")
            continue

        dataset_id = entry.get("datasetId")
        connection_id = entry.get("connectionId")
        table_name = (entry.get("tableName") or "").strip()

        if dataset_id:
            source = datasets.get(dataset_id)
            if source is None:
                refused.append(f"dataset {dataset_id}")
                continue
            identity = {"datasetId": dataset_id}
            label = source.get("name") or dataset_id
            if source.get("storageType"):
                identity["storageType"] = source["storageType"]
            key = f"dataset:{dataset_id}"
        elif connection_id is not None and table_name:
            try:
                connection_id = int(connection_id)
            except (TypeError, ValueError):
                refused.append(f"connection {connection_id!r}")
                continue
            if connection_id not in connections:
                refused.append(f"connection {connection_id}")
                continue
            if connection_id not in listings:
                try:
                    rows = await list_connection_tables(
                        agent.db_pool, agent.user_id, agent.language, connection_id
                    )
                    listings[connection_id] = {r.get("name") for r in rows or [] if r.get("name")}
                except Exception as exc:  # noqa: BLE001 — see the note below
                    # NOT folded into "no such table". A connection that cannot be
                    # listed — a down server, a bad password, a missing row — is a
                    # different fact from a table that is not in it, and telling
                    # the model the second when the first is true sends it hunting
                    # for another table name instead of reporting a connection
                    # problem. The refusal says which one happened.
                    logging.getLogger(__name__).warning(
                        "could not list connection %s for a proposed source: %s",
                        connection_id, exc,
                    )
                    refused.append(f"connection {connection_id} could not be read")
                    listings[connection_id] = set()
                    continue
            if table_name not in listings[connection_id]:
                refused.append(f"{table_name} on connection {connection_id}")
                continue
            identity = {"connectionId": connection_id, "tableName": table_name}
            label = table_name
            key = f"connection:{connection_id}:{table_name}"
        else:
            refused.append("an entry naming no table")
            continue

        columns = [
            c for c in (entry.get("columns") or [])
            if isinstance(c, str) and c.strip()
        ]
        choices.append({"key": key, "label": label, "value": identity, "columns": columns})

    if refused:
        # All or nothing, for the reason the confirm is: a set with holes asks
        # the user to accept something that is not what the model proposed.
        return [], refused
    return choices, []


async def _exec_suggest_choices(agent, piece, proposal=None, **args) -> dict:
    """Return the choices a chip set may offer for one pending piece.

    Only an ``ask`` piece has choices. The other four surfaces answer differently,
    and the answer says which — silence was the defect: an empty list is
    indistinguishable from "this piece has no options", so a model asking for
    chips on a `point` piece got a plausible-looking nothing and offered the user
    a question whose answer was a tick in the tree.

    The choices are the scoreboard's own — nothing here invents an option, which
    is what makes a chip trustworthy: a user can only click a name that exists and
    that they may read."""
    scoreboard = _scoreboard(agent)
    entry = next(
        (p for p in scoreboard.get("pending", []) if p.get("piece") == piece), None
    )
    if entry is None:
        # Not pending: either decided already or not a piece at all. Saying which
        # is the difference between "you have what you need" and "I mistyped".
        decided = [p for p in scoreboard.get("crystallised", []) if p.get("piece") == piece]
        return {
            "piece": piece,
            "surface": None,
            "choices": [],
            "answer": "already decided" if decided else "no such piece is pending",
            "scoreboard": scoreboard,
        }

    surface = entry.get("surface")

    # A proposal turns a `point` piece into a multi-select: the model names the
    # tables, the server checks them, the user adjusts and confirms. This is
    # ADDITIONAL to the tree, which stays the browsing surface — nobody is asked
    # a question about a piece the tree owns, which is what `point` protects.
    if proposal and piece == "sources":
        offered, refused = await _sources_proposal(agent, proposal)
        if refused:
            return {
                "piece": piece,
                "surface": surface,
                "multi": False,
                "choices": [],
                "refused": refused,
                "answer": (
                    "None of these can be offered, because at least one is not something "
                    "this user may read: " + ", ".join(refused) +
                    ". Offer only tables from get_sources or find_sources, and name the "
                    "connection as well as the table."
                ),
                "scoreboard": scoreboard,
            }
        setattr(agent, "_suggestion",
                {"piece": piece, "choices": offered, "multi": True,
                 "selected": [c["key"] for c in offered]})
        return {
            "piece": piece,
            "surface": surface,
            "multi": True,
            "choices": offered,
            "selected": [c["key"] for c in offered],
            "answer": (
                "Offered as one multi-select, pre-ticked. The user may untick any of them "
                "before confirming, and the confirm writes them all in one act."
            ),
            "scoreboard": scoreboard,
        }

    # An `invite` piece has no enumerated choices in the scoreboard — the answer
    # is the user's own words — so the one suggestion has to come from the model,
    # through `proposal`. The prompt tells it to send one; a proposal that is not
    # a single non-empty string is refused rather than coerced, because a chip
    # with no label is a chip the user cannot judge.
    if piece == "name":
        proposed = proposal if isinstance(proposal, list) else [proposal] if proposal else []
        named = []
        for candidate in proposed:
            if isinstance(candidate, str):
                if candidate.strip():
                    named.append(candidate.strip())
            elif isinstance(candidate, dict):
                # An object rather than a string. The schema used to declare
                # `items` as a table object, so a model following it sent
                # `[{"name": ...}]` — and this branch then read the array as
                # "a proposal that is not a string", refused, and answered in
                # prose. Accepting the obvious field names is cheaper than
                # losing the chip over a shape the schema itself suggested.
                for key in ("name", "label", "value"):
                    text = candidate.get(key)
                    if isinstance(text, str) and text.strip():
                        named.append(text.strip())
                        break
        if not named:
            # No proposal is NOT an invalid proposal, and must not read like one.
            #
            # The first version folded the two together, so a call with no
            # proposal returned "A name proposal must be one non-empty string" —
            # which a model reads as "the tool cannot do this", and it stopped
            # trying. Measured 2026-11-06, session vdc_777208a4239942e9.
            return {
                "piece": piece, "surface": surface, "choices": [],
                "answer": "Pass the name you want to suggest as `proposal`, for example "
                          "[\"Bike Sales Trend Analysis\"], and it will appear as one chip the "
                          "user can accept or replace. Without one there is nothing to offer.",
                "scoreboard": scoreboard,
            }
        # The key is the name itself, not `name::<name>`: the page prefixes the
        # piece when it builds the chip (`${piece}::${key}`), so a prefixed key
        # would arrive at the decision route as `name::name::<name>`.
        choice = {"key": named[0], "label": named[0], "value": named[0]}
        setattr(agent, "_suggestion", {"piece": piece, "choices": [choice]})
        return {
            "piece": piece, "surface": surface, "choices": [choice],
            "answer": "Offered as one suggestion the user may accept, or replace by typing their "
                      "own name. Only the first proposal is offered.",
            "scoreboard": scoreboard,
        }

    choices = list(entry.get("choices") or [])

    # An `invite` piece may carry ONE suggested answer as a chip.
    #
    # The guidance below has said "at most one suggestion may be offered" since
    # this surface was defined, while the code three lines above it attached a
    # suggestion only for `ask` — so the promise was never kept and the name
    # piece could only ever arrive as a question in prose. Measured 2026-11-06:
    # a run finished its joins, the user pressed Done, and the model asked "what
    # should this dataset be called?" with nothing to click.
    #
    # One, not many: an `invite` answer is the user's own words, so a proposal
    # here is an opening offer to accept or type over — not a closed set to pick
    # from. More than one would make it an `ask`.
    #
    # **The labels are resolved here, because this is where a key becomes one.**
    # A choice's `label` for an `ask` piece is a *declaration key* —
    # `virtual.scoreboard.storage.live` — and the chip renders whatever string it
    # is given. `_resolve_scoreboard_texts` rewrites the scoreboard the handler
    # builds, but this function returns a *different* object: it calls
    # `_scoreboard(agent)` itself, and its answer and its `_suggestion` were never
    # passed through that resolver. So on 2026-11-06 session vdc_b2e3eed3f5ba4d1a
    # the user was shown the two literal keys at the storage question, with every
    # translation present in the database and a pipeline run minutes earlier.
    #
    # `t()` against the declaration is the sanctioned shape: the English fallback
    # in `translations.py` is the single source, so this resolves correctly before
    # any pipeline run has ever happened for a key. The check is the same one the
    # scoreboard resolver uses — only a label that names a declaration is
    # translated, so a table name or a user proposal passes through untouched.
    resolved_choices = []
    for choice in choices:
        declared = DATASETS.get(choice.get("label")) if isinstance(choice, dict) else None
        if declared is not None:
            resolved_choices.append({
                **choice,
                "label": await t(agent.db_pool, agent.language, declared),
            })
        else:
            resolved_choices.append(choice)
    choices = resolved_choices

    if surface == "ask":
        suggestion = {"piece": piece, "choices": choices}
    elif surface == "invite" and choices:
        suggestion = {"piece": piece, "choices": choices[:1]}
    else:
        suggestion = None
    setattr(agent, "_suggestion", suggestion)

    guidance = {
        "ask": "",
        "point": "Not chips: say which table or column to tick in the tree.",
        "read": "Not chips: call get_tables and get_columns and use exactly what it returns.",
        "offer": "Not chips: the join is in the draft and shown as an editable row — "
                 "state it in one line and let the user adjust it there.",
        "invite": "Propose one concrete answer they can accept or replace; the answer is theirs to set.",
    }
    return {
        "piece": piece,
        "surface": surface,
        "choices": choices,
        "answer": guidance.get(surface, ""),
        "scoreboard": scoreboard,
    }


async def _exec_find_sources(agent, name, connection_id=None, **args) -> dict:
    """Resolve a typed name against the sources the tree can show.

    The tree is two levels deep and this mirrors it: datasets and connections are
    listed cheaply, and a connection's tables are read when the reader expands it.
    So a table name can only be matched inside a named connection — searching
    every connection would open every external server on the account, which the
    tree does not do either.

    **A defect this replaces.** The first version looped
    ``connection["tables"]``, a key ``fetch_available_sources`` never sets, so it
    could never match a table at all — only datasets — while reporting
    "Nothing on this account matches that name". That is the false negative the
    design calls the worst available answer: not a guess, but a confident no.

    Three outcomes, and each says which it is:

    - **exact** — one or more sources carry the name.
    - **connection needed** — no dataset or connection matches, but there are
      connections that might hold a table by that name. The reply names them and
      asks for one, rather than claiming the table does not exist.
    - **nothing** — no dataset, connection or (when a connection was named) table
      matches. Only now is "nothing matches" true.
    """
    from .virtual_chat import fetch_available_sources

    available = await fetch_available_sources(agent.db_pool, agent.user_id, agent.language)
    wanted = (name or "").strip().lower()
    exact, close = [], []

    # ── level 1: datasets and connections, both uncapped ──
    for dataset in (available or {}).get("datasets", []) or []:
        dataset_name = (dataset.get("name") or "").lower()
        if dataset_name == wanted:
            exact.append({"kind": "dataset", "datasetId": dataset.get("id"),
                          "name": dataset.get("name")})
        elif wanted and wanted in dataset_name:
            close.append({"kind": "dataset", "datasetId": dataset.get("id"),
                          "name": dataset.get("name")})

    connections = (available or {}).get("databaseConnections", []) or []
    for connection in connections:
        connection_name = (connection.get("name") or "").lower()
        if connection_name == wanted:
            exact.append({"kind": "connection",
                          "connectionId": connection.get("connectionId"),
                          "name": connection.get("name")})

    # ── level 2: one connection's tables, only when the caller named it ──
    searched_connection = None
    if connection_id is not None:
        from .browse import list_connection_tables
        try:
            tables = await list_connection_tables(
                agent.db_pool, agent.user_id, agent.language, int(connection_id)
            )
        except Exception as exc:
            return {
                "found": False,
                "matches": [],
                "note": f"Could not read the tables of connection {connection_id}: {exc}. "
                        "Say so rather than assuming it has none.",
            }
        searched_connection = int(connection_id)
        connection_name = next(
            (c.get("name") for c in connections if c.get("connectionId") == searched_connection),
            str(searched_connection),
        )
        for table in tables or []:
            table_name = table.get("name") or table.get("tableName") or ""
            if table_name.lower() == wanted:
                exact.append({"kind": "table", "connectionId": searched_connection,
                              "connectionName": connection_name, "tableName": table_name})
            elif wanted and wanted in table_name.lower():
                close.append({"kind": "table", "connectionId": searched_connection,
                              "connectionName": connection_name, "tableName": table_name})

    if exact:
        return {"found": True, "matches": exact, "note": ""}

    if close:
        return {
            "found": False,
            "matches": close[:5],
            "note": "No exact match; the closest real names are listed. "
                    "Ask the user which they meant rather than assuming.",
        }

    if connection_id is None and connections:
        # Not a "no": tables are one level down, and this tool has not looked.
        names = ", ".join(f"{c.get('name')} ({c.get('connectionId')})" for c in connections[:8])
        more = "" if len(connections) <= 8 else f" and {len(connections) - 8} more"
        return {
            "found": False,
            "matches": [],
            "note": f"No dataset or connection is called that. Tables live inside a connection — "
                    f"call find_sources again with a connection_id to search one. "
                    f"Connections: {names}{more}.",
        }

    scope = f"connection {searched_connection}" if searched_connection is not None else "this account"
    return {
        "found": False,
        "matches": [],
        "note": f"Nothing in {scope} matches that name.",
    }


_PIECE_TOOL_SCHEMAS = [
    {
        "type": "function",
        "function": {
            "name": "set_goal",
            "description": "Record what the dataset should show, in the user's words. "
                           "Recorded when offered; never ask for it on its own and never block on it.",
            "parameters": {
                "type": "object",
                "properties": {"goal": {"type": "string"}},
                "required": ["goal"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "add_source",
            "description": "Bring a table or dataset into the definition under a short alias. "
                           "Usually the tree does this by the user ticking a column; call this "
                           "when the user names a table in conversation.",
            "parameters": {
                "type": "object",
                "properties": {
                    "alias": {"type": "string", "description": "Short name used by joins and columns, e.g. 'o'."},
                    "connectionId": {"type": "integer"},
                    "tableName": {"type": "string"},
                    "datasetId": {"type": "string"},
                    "storageType": {"type": "string"},
                },
                "required": ["alias"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "remove_output_column",
            "description": "Untick one output column. Unticking the last column of a source "
                           "removes that source, which is what the tree does too.",
            "parameters": {
                "type": "object",
                "properties": {
                    "source": {"type": "string"},
                    "column": {"type": "string"},
                },
                "required": ["source", "column"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "set_source_columns",
            "description": "Record which columns a source has. This is knowledge, not a decision: "
                           "call it after reading a table so the scoreboard can offer real choices.",
            "parameters": {
                "type": "object",
                "properties": {
                    "alias": {"type": "string"},
                    "columns": {"type": "array", "items": {"type": "string"}},
                },
                "required": ["alias", "columns"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "set_join",
            # The join goes into the draft, and the message that carries the
            # reply renders it as an editable row. Until 2026-11-06 this said
            # "never apply one the user did not accept", while the executor
            # wrote it anyway — the description described a gate that did not
            # exist. What actually gates it is the row: the user sees every
            # join on one line with its columns, its type and the reason, and
            # edits it there. So the honest instruction is to record the join
            # and say why, because the reason is what makes the row reviewable.
            "description": "Join two sources on a column pair. The join appears in the chat as "
                           "an editable row, so state it plainly and give a short `reason` — "
                           "the user reviews and changes it there.",
            "parameters": {
                "type": "object",
                "properties": {
                    "left": {"type": "string"},
                    "leftCol": {"type": "string"},
                    "right": {"type": "string"},
                    "rightCol": {"type": "string"},
                    "type": {
                        "type": "string",
                        "enum": ["inner", "left", "right", "full"],
                        # Described here as well as in the prompt, because this is
                        # where the choice is made. Until 2026-11-06 this property
                        # carried no description at all, so `inner` — the first
                        # enum value — was what the model reached for on every
                        # join, including joins to lookup tables where it silently
                        # drops rows.
                        "description": "`left` keeps every row of the left source — use it for a "
                                       "lookup table (brands, categories, stores, customers, "
                                       "staff). `inner` drops rows with no match; use it only "
                                       "when both sides must both exist. When in doubt, `left`.",
                    },
                    "reason": {
                        "type": "string",
                        "description": "Why this pair — a few words, shown at the end of the "
                                       "row (for example \"line items to their order\").",
                    },
                },
                "required": ["left", "leftCol", "right", "rightCol"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "remove_join",
            "description": "Remove the join between two sources.",
            "parameters": {
                "type": "object",
                "properties": {"left": {"type": "string"}, "right": {"type": "string"}},
                "required": ["left", "right"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "set_output_columns",
            "description": "Set the full list of columns the result contains.",
            "parameters": {
                "type": "object",
                "properties": {
                    "columns": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {"source": {"type": "string"}, "column": {"type": "string"}},
                            "required": ["source", "column"],
                        },
                    },
                },
                "required": ["columns"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "set_name",
            "description": "Name the dataset.",
            "parameters": {
                "type": "object",
                "properties": {"name": {"type": "string"}},
                "required": ["name"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "set_storage",
            "description": "Live view or materialised table. Live is the default; only call this "
                           "when the user asks for something else.",
            "parameters": {
                "type": "object",
                "properties": {"materialized": {"type": "boolean"}},
                "required": ["materialized"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_scoreboard",
            "description": "Read what is decided, pending, blocked and broken. Call it before "
                           "asking the user anything, so the question is the one that is actually open.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "suggest_choices",
            "description": "Return the valid choices for one pending piece so they can be shown as "
                           "clickable chips. Call this when you are about to ask the user to choose. "
                           "For the `sources` piece the choices are tables, and passing `proposal` "
                           "offers them pre-ticked as one multi-select the user can adjust and "
                           "confirm in a single act.",
            "parameters": {
                "type": "object",
                "properties": {
                    "piece": {"type": "string"},
                    "proposal": {
                        "type": "array",
                        # The ITEMS are deliberately untyped.
                        #
                        # Two pieces accept a proposal and they are different
                        # shapes: `sources` takes table objects, `name` takes a
                        # plain string. Declaring `items` as the table-object
                        # schema made the name unpassable — the prompt tells the
                        # model to "call suggest_choices with ONE concrete
                        # proposal", and the schema then refused the only form a
                        # name can take. Measured 2026-11-06, session
                        # vdc_777208a4239942e9: the model called the tool for
                        # `name` with no proposal, got a refusal, and asked in
                        # prose — so the user had to type their acceptance of a
                        # suggestion that should have been one click.
                        "description": "The proposal to offer. "
                                       "For `sources`: an array of table objects — each names a "
                                       "dataset (datasetId), or a connection and one of its tables "
                                       "(connectionId + tableName), plus the columns to tick on it. "
                                       "Every entry is checked against what the user may read; if "
                                       "any fails, none are offered. "
                                       "For `name`: an array holding the single name you are "
                                       "suggesting, as a plain string — for example "
                                       "[\"Bike Sales Trend Analysis\"]. It arrives as one chip the "
                                       "user can accept, or type over.",
                        "items": {},
                    },
                },
                "required": ["piece"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "find_sources",
            "description": "Resolve a name the user typed against the sources the tree can show. "
                           "Searches datasets and connection names; to search a connection's tables, "
                           "pass its connection_id (tables are read per connection, exactly as the "
                           "tree reads them on expand). Returns exact matches, or the closest real "
                           "names — never a guess.",
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "connection_id": {
                        "type": "integer",
                        "description": "Optional. Search this connection's tables too.",
                    },
                },
                "required": ["name"],
            },
        },
    },
]

_PIECE_EXECUTORS = {
    "set_goal": _exec_set_goal,
    "add_source": _exec_add_source,
    "remove_output_column": _exec_remove_output_column,
    "set_source_columns": _exec_set_source_columns,
    "set_join": _exec_set_join,
    "remove_join": _exec_remove_join,
    "set_output_columns": _exec_set_output_columns,
    "set_name": _exec_set_name,
    "set_storage": _exec_set_storage,
    "get_scoreboard": _exec_get_scoreboard,
    "suggest_choices": _exec_suggest_choices,
    "find_sources": _exec_find_sources,
}

# The virtual concierge's own registry (Item 22a). Before this, every concierge
# registered into one shared dict, so `get_scoreboard`, `set_name` and
# `suggest_choices` — declared by both the virtual and the recipe concierge —
# resolved to whichever module registered last, and `main.py` imports datasets
# before recipes, so the recipe won. A virtual session asking what was left got
# the RECIPE scoreboard; `set_name` wrote the recipe's state.
VIRTUAL_REGISTRY = "virtual"


def register_all_tools() -> None:
    """Register the virtual-dataset tools into the virtual concierge's registry.

    One call per tool. The registry IS the concierge's scope now, so there is no
    allow-list to keep in step and no table to iterate — `run_tool_loop` is
    called without `tool_names`, and everything registered here is what this
    concierge can see.

    `report_unsupported` is not registered here: it lives in the common registry,
    which every agent resolves after its own.
    """
    register_tool(VIRTUAL_REGISTRY, "save_virtual_dataset", _TOOL_SCHEMAS[0], _exec_save_virtual_dataset)
    register_tool(VIRTUAL_REGISTRY, "validate_virtual_dataset", _TOOL_SCHEMAS[1], _exec_validate_virtual_dataset)
    register_tool(VIRTUAL_REGISTRY, "preview_virtual_dataset", _TOOL_SCHEMAS[2], _exec_preview_virtual_dataset)
    register_tool(VIRTUAL_REGISTRY, "get_sources", _SOURCES_TOOL_SCHEMA, _exec_get_sources)
    register_tool(VIRTUAL_REGISTRY, "get_tables", _TABLES_TOOL_SCHEMA, _exec_get_tables)
    register_tool(VIRTUAL_REGISTRY, "probe_connection", _PROBE_TOOL_SCHEMA, _exec_probe_connection)
    register_tool(VIRTUAL_REGISTRY, "get_columns", _COLUMNS_TOOL_SCHEMA, _exec_get_columns)
    for schema in _PIECE_TOOL_SCHEMAS:
        name = schema["function"]["name"]
        register_tool(VIRTUAL_REGISTRY, name, schema, _PIECE_EXECUTORS[name])

