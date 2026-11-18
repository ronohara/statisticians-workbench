"""
AI recipe tools — thin wrappers over existing backend functions.

Each tool's executor calls existing code (``constraints.compute_scoreboard``,
``constraints.serialize_recipe_model``, ``datasets.schema.fetch_dataset_overview``,
``recipes.save.save_session_recipe``); no validation or storage logic is
re-implemented. The granular ``set_*`` tools mutate the agent-held recipe draft
and return the scoreboard; ``save_recipe`` reads that draft rather than taking a
whole ``stages`` array.
"""
import dataclasses
import logging
import re

from fastapi import HTTPException

from src.routers.datasets.schema import fetch_dataset_overview, fetch_dataset_schema
from src.routers.datasets.crud import list_user_datasets
from src.routers.datasets.transforms import (
    TransformOperation,
    create_transform_record,
    delete_transform_record,
    fetch_dataset_transforms,
    fetch_transform,
    update_transform_record,
)
from src.chat.tool_agent import register_tool, tool_error
from src.utils.translation import t
from .constraints import (
    FIELD_DEFS,
    ColumnInfo,
    cap_choices,
    columns_of_type,
    compute_scoreboard,
    serialize_recipe_model,
    to_column_info,
)
from .save import save_session_recipe
from .translations import (
    RECIPE_SCOREBOARD_KEYS,
    recipes_chip_heading_columns,
    recipes_chip_heading_output,
    recipes_chip_heading_technique,
    ai_recipe_session_name_required,
    recipes_ai_session_not_found,
    recipes_ai_session_save_error,
)


logger = logging.getLogger(__name__)


async def _resolve_scoreboard_texts(scoreboard: dict, db_pool, language: str) -> dict:
    """Fill each pending entry's `whatText` from the key it carries, through `t()`.

    The scoreboard is a pure function and emits a KEY, not a sentence — that is
    what makes it comparable across the two backends without a database. Nothing
    resolved it before Item 11 of the recipe v2 plan: the page received
    `recipes.scoreboard.output.what` and had to build its own translation object,
    which is the form the translation rules forbid.

    Resolving here — in `_scoreboard_for`, the one place a scoreboard is built for
    an agent — is the sanctioned shape: `t()` is handed the declaration object
    itself, so the English fallback in `translations.py` is its single source and
    is what reaches the screen before the pipeline has run for these keys. The
    scoreboard stays pure; this is the boundary where a pool and a language exist.

    `what` is left in place beside `whatText` deliberately: the page may render
    either, and keeping the key is what lets a reader diagnose a missing
    translation row rather than seeing an empty string and no explanation.

    `blocked` entries are resolved here too, and carry one extra key:
    `unblocked_by` names the parent piece's own question, so a renderer can say
    what the piece is waiting on without composing a sentence from piece names.
    Its `unblockedByText` uses the *parent's* declaration — the text is identical
    ("Choose an analysis method" both asks for the technique and says what
    unblocks its fields), so reusing that declaration is the translation rule's
    reuse-by-text rather than a second key with the same English.
    """
    def _declared(key):
        declared = RECIPE_SCOREBOARD_KEYS.get(key) if key else None
        if declared is None:
            # A key the module does not declare is a defect in the scoreboard,
            # not something to paper over with the key string itself.
            logger.error("scoreboard entry names an undeclared key: %r", key)
        return declared

    for entry in scoreboard.get("pending") or []:
        declared = _declared(entry.get("what"))
        if declared is None:
            continue
        entry["whatText"] = await t(db_pool, language, declared)

    for entry in scoreboard.get("blocked") or []:
        declared = _declared(entry.get("what"))
        if declared is not None:
            entry["whatText"] = await t(db_pool, language, declared)
        unblock = _declared(entry.get("unblocked_by"))
        if unblock is not None:
            entry["unblockedByText"] = await t(db_pool, language, unblock)
    return scoreboard


def _column_info(schema: dict) -> list:
    """Project a schema dict to the shape the validator and the model consume.

    ``is_datetime`` is kept so a date/datetime column is not mistaken for an
    untyped one (a date is neither numeric nor categorical). "dtype" is the
    raw storage type, also useful to the model."""
    return [
        {
            "name": c.get("name"),
            "dtype": c.get("dtype"),
            "is_numeric": c.get("is_numeric", False),
            "is_categorical": c.get("is_categorical", False),
            "is_datetime": c.get("is_datetime", False),
        }
        for c in (schema or {}).get("columns", [])
    ]


# ── Granular builder tools — draft + scoreboard helpers ────────────

def _proposed_name(proposal) -> str:
    """The single name a proposal carries, or "" when it carries none.

    Tolerant of three shapes on purpose, mirroring the virtual concierge's reader:
    a bare string, a one-element list, and an object using one of the obvious field
    names. Virtual's schema once declared `items` as a table object, so a model
    following it sent `[{"name": ...}]` — and its reader refused, losing the chip
    over a shape the schema itself had suggested. Pydantic-style tolerance is
    cheaper than a lost affordance.

    Only the first name is kept: an `invite` answer is the user's own words, so
    more than one would make it a choice between options (`ask`), not an opening
    offer to accept or type over.
    """
    candidates = proposal if isinstance(proposal, list) else [proposal] if proposal else []
    for candidate in candidates:
        if isinstance(candidate, str):
            if candidate.strip():
                return candidate.strip()
        elif isinstance(candidate, dict):
            for key in ("name", "label", "value"):
                text = candidate.get(key)
                if isinstance(text, str) and text.strip():
                    return text.strip()
    return ""


def _draft_of(agent) -> list:
    """The agent's in-progress recipe draft, initialised on first touch.

    ``send_message`` loads the session's stages onto the agent before the tool
    loop and persists the tool-mutated list afterwards (Item 4). A granular tool
    mutates this list in place and returns the refreshed scoreboard."""
    draft = getattr(agent, "_draft", None)
    if draft is None:
        draft = []
        agent._draft = draft
    return draft


def _draft_dataset_id(draft: list):
    """The datasetId the draft's data_selection stage names, if any."""
    for stage in draft:
        if stage.get("type") == "data_selection":
            return (stage.get("config") or {}).get("datasetId")
    return None


def _stage_config(draft: list, stage_type: str) -> dict:
    """Return (creating if needed) a stage's config dict."""
    for stage in draft:
        if stage.get("type") == stage_type:
            config = stage.get("config")
            if not isinstance(config, dict):
                config = {}
                stage["config"] = config
            return config
    stage = {"type": stage_type, "config": {}}
    draft.append(stage)
    return stage["config"]


def _to_column_info(columns: list) -> list:
    """Project column payloads to ``ColumnInfo`` — the shared conversion.

    Kept as a named local rather than inlined at its one call site because
    ``_fetch_columns`` reads as "fetch, then convert", and the conversion is the
    part that has a rule. The implementation lives in
    ``constraints.to_column_info`` so there is one definition of the two
    spellings, not a third.
    """
    return to_column_info(columns)


async def _fetch_columns(agent, dataset_id: str) -> list:
    """Fetch a dataset's columns as ColumnInfo (raises HTTPException on failure).

    ``fetch_dataset_schema``, not ``fetch_dataset_overview``: this reads only
    ``columns``, and the overview's row count costs a ``SELECT COUNT(*)`` — two
    full-table scans for a PostgreSQL table — which is thrown away here. The
    overview stays at the ``get_dataset_schema`` tool below, which does report
    ``total_rows``.
    """
    schema = await fetch_dataset_schema(dataset_id, agent.user_id, agent.language)
    return _to_column_info(_column_info(schema))


async def build_scoreboard(
    db_pool, user_id: str, language: str, draft: list, goal: str | None = None,
) -> tuple[dict, list | None, list]:
    """The scoreboard for a draft, plus the columns it was built from.

    This is the ONE computation, and both callers go through it:

    - a turn, via `_scoreboard_for`, which also stashes the columns on the agent
      so the column suggestion does not fetch the schema again;
    - `GET /ai/sessions/{id}`, added 2026-11-10, so a reopened session shows its
      progress and its next step instead of starting blank until the next turn.

    The second caller is why this is a function and not agent-bound: the route has
    a pool, a user and a language but no agent, and re-deriving the scoreboard
    there would be a second implementation of "what is decided" — the defect the
    recipe v2 plan spent Items 3 to 11 removing.

    Best-effort on the schema: a dataset that cannot be read yields
    `columns=None`, which the predicate treats as "nothing known" rather than an
    error, so a session still opens when its dataset is unreachable.

    The third value is the schema reader's `unread` list — the sources it could
    not read, and why. It is returned rather than folded into the scoreboard
    because the scoreboard is a pure function of the draft and is compared
    across the two backends; a list produced by I/O does not belong in it. It is
    returned rather than dropped because dropping it is how a turn came to show
    an empty chip row with nothing to explain it: the reason existed here and
    was discarded one call above the surface that needed it.
    """
    dataset_id = _draft_dataset_id(draft)
    columns = None
    unread: list = []
    if dataset_id:
        try:
            schema = await fetch_dataset_schema(dataset_id, user_id, language)
            columns = _to_column_info(_column_info(schema))
            unread = schema.get("unread") or []
        except HTTPException:
            columns = None

    scoreboard = compute_scoreboard(draft, columns, name=goal)
    # The scoreboard is pure and emits keys; resolving here is the boundary where
    # a pool and a language both exist. Every scoreboard a caller sees comes
    # through this function, so the page and the prompt cannot be handed a raw
    # key by one path and a sentence by another.
    return await _resolve_scoreboard_texts(scoreboard, db_pool, language), columns, unread


#: Which heading answers which chip-row piece. Only `ask` pieces appear here — the
#: four the prompt puts as questions with chips.
#:
#: Built from the declarations in `translations.py`, and living in the module that
#: resolves rather than beside them, for two reasons that happen to agree: the
#: translation rule wants a mapping built from declarations rather than an assembled
#: key, and the linter wants the declaration *names* used in a file other than the
#: one they are declared in. A map next to the declarations satisfies neither.
#:
#: `technique_fields` and `output_fields` both ask "Which columns?" and share one
#: declaration — two keys carrying one phrase is what the frontend linter reports as
#: DUPLICATE-FALLBACK, and the rule is to reuse by text.
CHIP_HEADINGS = {
    "technique": recipes_chip_heading_technique,
    "technique_fields": recipes_chip_heading_columns,
    "output": recipes_chip_heading_output,
    "output_fields": recipes_chip_heading_columns,
}

#: Pieces whose chip row deliberately carries no heading.
#:
#: A `proposal` row is introduced by the model's own sentence in the same turn —
#: "here is what I suggest, click to accept" — and a heading above it would be a
#: second voice saying what the first just said. Declaring the set keeps "no
#: heading" a decision: without it, `resolve_suggestion_heading` would log the
#: row as a defect and a reader could not tell a deliberate omission from a
#: missing entry.
HEADINGLESS_PIECES = frozenset({"proposal"})


async def resolve_suggestion_heading(suggestion, db_pool, language: str):
    """Fill a chip row's `heading` and `headingText` from the piece it asks about.

    The row is built in two places — the model's `suggest_choices` call and
    `_derive_suggestion` when it does not — so the heading is looked up from the
    piece here, once, rather than being attached at both build sites. That is what
    makes the piece→declaration map load-bearing: a piece that reaches a chip row
    without an entry is a defect, and this says so instead of returning a row with
    no heading.

    `heading` (the key) travels beside `headingText` for the same reason `what`
    travels beside `whatText`: the page renders the sentence, and the key stays
    diagnosable when a translation row is missing.

    A suggestion with no piece (or a null one) is passed through unchanged — the
    caller may legitimately have nothing to show.
    """
    if not suggestion:
        return suggestion
    piece = suggestion.get("piece")
    if piece in HEADINGLESS_PIECES:
        return suggestion
    declared = CHIP_HEADINGS.get(piece) if piece else None
    if declared is None:
        logger.error("chip row names a piece with no heading declared: %r", piece)
        return suggestion
    suggestion["heading"] = declared.key
    suggestion["headingText"] = await t(db_pool, language, declared)
    return suggestion


async def _scoreboard_for(agent, draft: list) -> dict:
    """Compute the scoreboard for the current draft (best-effort schema fetch)."""
    scoreboard, columns, unread = await build_scoreboard(
        agent.db_pool, agent.user_id, agent.language, draft,
        getattr(agent, "_goal", None),
    )
    # Stash the columns so the column suggestion (the field pieces) can filter
    # them by the field's required type without a second schema fetch, and the
    # unread list so a turn can say which sources it could not read rather than
    # offering an empty row with no explanation.
    agent._columns = columns
    agent._unread = unread
    return scoreboard


async def _exec_get_recipe_model(agent, **args) -> dict:
    return serialize_recipe_model()


async def _exec_get_dataset_schema(agent, dataset_id: str, **args) -> dict:
    try:
        schema = await fetch_dataset_overview(dataset_id, agent.user_id, agent.language)
    except HTTPException as e:
        return tool_error("get_dataset_schema", e, agent=agent)
    return {
        "columns": _column_info(schema),
        "total_rows": schema.get("total_rows"),
        "source_type": schema.get("source_type"),
        "storage_type": schema.get("storage_type"),
    }


_NAME_SEPARATORS = re.compile(r"[\s_.\-]+")

# Generic words dropped from a search phrase before matching: they occur in
# nearly every dataset name ("data", "table", …) and would otherwise match
# everything (e.g. "bike sales data" matching internal_replicator_data on
# "data" alone).
_SEARCH_STOPWORDS = {
    "a", "an", "and", "are", "data", "dataset", "datasets", "find", "for",
    "get", "give", "in", "info", "information", "is", "list", "me", "my",
    "of", "on", "or", "please", "record", "records", "show", "some", "table",
    "tables", "the", "to",
}


def _normalise_name(text: str) -> str:
    """Fold a dataset name or search phrase to a comparable form — lowercase,
    with spaces, underscores, hyphens and dots collapsed to single spaces."""
    return _NAME_SEPARATORS.sub(" ", (text or "").lower()).strip()


def _match_datasets(datasets: list, search: str) -> dict:
    """Rank datasets against a search phrase (the list_datasets tool's matching).

    Normalises both sides, then scores each dataset by how many of the phrase's
    words appear as substrings of its normalised name. Every dataset with at
    least one matching word is returned, most relevant first, each with its
    ``score`` and an ``exact`` flag for a full-phrase match. An empty phrase
    lists everything unranked."""
    query = _normalise_name(search)
    tokens = [t for t in query.split(" ") if t]
    meaningful_tokens = [t for t in tokens if t not in _SEARCH_STOPWORDS]

    if not tokens:
        matches = [
            {
                "id": d["id"],
                "name": d["name"],
                "sourceType": d["sourceType"],
                "storageType": d["storageType"],
                "exact": False,
                "score": 0,
            }
            for d in datasets
        ]
        return {"count": len(matches), "datasets": matches}

    scored = []
    for d in datasets:
        norm_name = _normalise_name(d["name"])
        score = sum(1 for t in meaningful_tokens if t in norm_name)
        if score == 0:
            continue
        scored.append({
            "id": d["id"],
            "name": d["name"],
            "sourceType": d["sourceType"],
            "storageType": d["storageType"],
            "exact": query in norm_name,
            "score": score,
        })

    # Exact matches first, then higher word overlap, then name for stability.
    scored.sort(key=lambda m: (not m["exact"], -m["score"], (m["name"] or "").lower()))
    return {"count": len(scored), "datasets": scored}


async def _exec_list_datasets(agent, search: str = None, **args) -> dict:
    """List the datasets the user can see, narrowed by a search phrase.

    The same query the manual editor's dataset list runs (list_user_datasets in
    datasets/crud.py) — one query, two callers. The model resolves a dataset the
    user names in words to its id here, then records it with set_dataset. The
    match is fuzzy (normalised, word-based) so "bike sales data" still surfaces
    "bike_sales_detail" and other near matches, ranked by relevance."""
    datasets = await list_user_datasets(agent.db_pool, agent.user_id)
    result = _match_datasets(datasets, search or "")
    # Surface the ranked candidates so the caller (the recipe page) can render
    # them as clickable "select this dataset" chips. The ids come from the tool
    # result, never from the model's prose; the last non-empty search in the
    # turn wins. An empty search ("list everything") offers nothing clickable.
    if (search or "").strip():
        agent._dataset_suggestions = [
            {"id": d["id"], "name": d["name"], "sourceType": d["sourceType"], "storageType": d["storageType"]}
            for d in result["datasets"][:8]
        ]
    return result


async def _exec_suggest_choices(
    agent, piece: str, field: str = None, proposal=None, **args,
) -> dict:
    """Return the valid choices for one decision piece, and register them so
    the recipe page renders them as clickable chips. The choices come from the
    scoreboard's pending pieces — the same set the prompt embeds — so the model
    never invents options.

    A **field** piece is answered differently, because its choice set is not a
    list of names the scoreboard already holds: the scoreboard says *which* fields
    are still empty (`["dependentColumn"]`), and the chips have to be the columns
    of that field's required type. Until this branch existed the model could not
    offer a column row at all — the tool read the scoreboard, found field names
    where it expected options, and discarded them — so every column chip came from
    `_derive_suggestion`'s fallback: the first six numeric columns in storage
    order, whatever the model had just recommended in prose. The model named
    `s1_quantity` in a sentence while the screen offered `s1_customer_id`.

    `field` is optional and, when omitted or not among the pending fields, the
    first pending field is used — the same choice the fallback makes. That keeps
    the call working when the model knows it wants a column row but not which of
    several empty fields to fill first.
    """
    scoreboard = await _scoreboard_for(agent, _draft_of(agent))

    if piece in ("technique", "output"):
        choices = []
        for p in scoreboard.get("pending", []):
            if p.get("piece") == piece:
                choices = p.get("choices") or []
                break
        # The model keeps the FULL list — it may describe an option the row cannot
        # show — while the chip row is capped and carries the count it left out. Both
        # numbers travel, so neither consumer is told a half-truth: the page can say
        # "6 of 11" and the model can still name the other five.
        capped = cap_choices(choices)
        if choices:
            agent._suggestion = {"piece": piece, **capped}
        else:
            agent._suggestion = None
        # `shown` is what the chip row actually renders, and the model needs it:
        # it is told the full choice list, so without this it can tell the user to
        # click an option the row is not showing. Measured 2026-11-11 — "click
        # Linear Regression", seventh of eight, cap at six, no such chip, dead end.
        return {
            "piece": piece,
            "choices": choices,
            "shown": capped["choices"],
            "withheld": capped["withheld"],
        }

    if piece in ("technique_fields", "output_fields"):
        missing = []
        for p in scoreboard.get("pending", []):
            if p.get("piece") == piece:
                missing = p.get("choices") or []
                break
        field_name = field if field in missing else (missing[0] if missing else None)
        fdef = FIELD_DEFS.get(field_name) if field_name else None
        if fdef is None:
            agent._suggestion = None
            return {"piece": piece, "field": field_name, "choices": [], "withheld": 0}
        columns = columns_of_type(getattr(agent, "_columns", None), fdef.column_type)
        capped = cap_choices(columns)
        # Registered even when the list is empty: an empty row is not a row, and
        # the caller (a turn) drops it before it reaches the page — but registering
        # it here keeps one rule for "what the model asked for" rather than a
        # second guess about whether it is worth honouring.
        agent._suggestion = {
            "piece": piece,
            "field": field_name,
            "columnType": fdef.column_type,
            "multi": fdef.multi,
            **capped,
        }
        return {
            "piece": piece,
            "field": field_name,
            "choices": columns,
            "shown": capped["choices"],
            "withheld": capped["withheld"],
        }

    if piece == "name":
        # The name is an `invite` piece: its answer is the user's own words, so the
        # scoreboard holds no choices. The model's proposal is the opening offer,
        # and it arrives as an EDITABLE field — not a closed set of one. The
        # virtual concierge learned this the expensive way (its own component
        # records it): a single chip made the offer look like the whole choice, and
        # a user accepted by typing "that name is fine" because the chip looked
        # final.
        named = _proposed_name(proposal)
        if named:
            agent._suggestion = {
                "piece": "name",
                "choices": [named],
                "withheld": 0,
            }
            return {
                "piece": "name",
                "choices": [named],
                "shown": [named],
                "withheld": 0,
                "answer": (
                    "Offered as one suggested name the user may accept, or replace "
                    "with their own."
                ),
            }
        # No proposal is NOT an invalid proposal. Virtual's entry records what
        # folding the two together cost: the model read the refusal as "the tool
        # cannot do this" and stopped trying, so the user had to type their
        # acceptance of a suggestion that should have been one click.
        agent._suggestion = None
        return {
            "piece": "name",
            "choices": [],
            "answer": (
                "Pass the name you want to suggest as `proposal`, for example "
                '[\"Bike Sales Trend Analysis\"], and it will appear as one field the '

                "user can accept or edit. Without one, ask in prose — the field still "
                "appears, empty, so the user can type a name."
            ),
        }

    agent._suggestion = None
    return {"piece": piece, "choices": [], "withheld": 0}


async def _exec_offer_proposal(agent, label: str, fields: list = None, **args) -> dict:
    """Put a concrete, complete proposal on screen as one chip the user can accept.

    The concierge could already offer a *closed set* of single choices — one chip
    per technique, one per column — but not the thing it most often does in prose:
    name a set of fields together and invite "go with that". A live turn ended on
    exactly that sentence with no chip under it, so the only way to accept was to
    type the words back at a model that had already stopped listening for them.

    **The label is the model's, and it is not translated.** It is written in this
    turn, in the user's language, by the same model that wrote the sentence beside
    it. A declared key would resolve from the session's stored `language` column
    while the sentence followed the language the user *writes in* — so for an
    English-preference user writing Thai the row would be an English chip under
    Thai prose. The distinction, recorded in the design's §3.12a: a machine value
    needs a key because a value is not language; a heading needs a key because we
    wrote it; the model's own offer takes none because the model wrote it.

    That is also why `label` is required with **no default**: a default would be an
    English string of ours wearing the model's name, which is the one thing this
    path must not contain.
    """
    label = (label or "").strip()
    cleaned: list = []
    for entry in fields or []:
        if not isinstance(entry, dict):
            continue
        piece = entry.get("piece")
        field = entry.get("field")
        column = entry.get("column")
        if piece not in ("technique_fields", "output_fields") or not field or not column:
            continue
        cleaned.append({"piece": piece, "field": field, "column": column})

    if not label or not cleaned:
        # Nothing to accept. The model is told so rather than being handed a chip
        # that would apply nothing — a chip whose click changes no state is worse
        # than no chip, because it reads as an action that succeeded.
        agent._suggestion = None
        return {
            "accepted": False,
            "reason": "a label and at least one field are required",
        }

    agent._suggestion = {
        "piece": "proposal",
        "label": label,
        "fields": cleaned,
        # `choices` carries the label so the generic row guard in the page (a
        # suggestion with a non-empty choices list) treats this like any other
        # chip, and `withheld` states zero rather than being absent.
        "choices": [label],
        "withheld": 0,
    }
    return {"accepted": True, "label": label, "fields": cleaned}


async def _exec_save_recipe(
    agent, dataset_id: str = None, **args
) -> dict:
    # The draft is owned by the granular set_* tools (held on the agent), so the
    # save reads it rather than taking a whole stages array. The shared path
    # (recipes/save.py) is otherwise unchanged: one validation gate, one insert,
    # and both complete the session.
    #
    # The name comes from the conversation goal (the scoreboard's "name" piece),
    # never from a name the model invents. Derive it here and fail when unset, so
    # the model is steered to ask the user for a name first.
    stages = _draft_of(agent)
    name = (getattr(agent, "_goal", None) or "").strip()
    if not name:
        return {
            "error": await t(
                agent.db_pool, agent.language, ai_recipe_session_name_required
            )
        }
    result = await save_session_recipe(
        agent.db_pool, agent.user_id, agent.language, agent.session_id,
        stages, name, dataset_id=dataset_id,
    )

    if result["status"] == "invalid":
        return {
            "error": result["message"],
            "errors": [dataclasses.asdict(i) for i in result["issues"]],
        }
    if result["status"] == "http_error":
        return {"error": result["message"]}
    if result["status"] == "not_found":
        return {
            "error": await t(
                agent.db_pool, agent.language, recipes_ai_session_not_found
            )
        }
    if result["status"] == "error":
        return {
            "error": await t(
                agent.db_pool, agent.language, recipes_ai_session_save_error
            )
        }

    recipe_id = result["recipe_id"]
    return {
        "recipe_id": recipe_id,
        "name": result["name"],
        # The link comes back with the result on purpose. The prompt is built
        # before this tool runs, so on the saving turn the "Recipe Editor"
        # target is not in it yet — saved_recipe_id is unset until this call
        # writes it — and the session completes, so there is no later turn in
        # which it appears. Handing the link back here is what lets the model
        # offer it in the same reply. The URL itself still comes from
        # _generate_deep_link, so its shape lives in one place.
        "url": agent._generate_deep_link(
            "recipe", agent.session_id, recipeId=recipe_id
        ),
    }


def _as_operations(ops: list) -> list:
    """Convert the LLM's operation dicts into TransformOperation models."""
    return [TransformOperation(**op) for op in (ops or [])]


async def _exec_get_dataset_transforms(agent, dataset_id: str, **args) -> dict:
    try:
        return await fetch_dataset_transforms(dataset_id, agent.user_id, agent.language)
    except HTTPException as e:
        return tool_error("get_dataset_transforms", e, agent=agent)


async def _exec_get_transform(agent, dataset_id: str, transform_id: str, **args) -> dict:
    try:
        return await fetch_transform(dataset_id, transform_id, agent.user_id, agent.language)
    except HTTPException as e:
        return tool_error("get_transform", e, agent=agent)


async def _exec_create_transform(
    agent, dataset_id: str, name: str, operations: list,
    description: str = None, shared: bool = False, **args
) -> dict:
    try:
        return await create_transform_record(
            dataset_id, agent.user_id, name, description,
            _as_operations(operations), shared, agent.language,
        )
    except HTTPException as e:
        return tool_error("create_transform", e, agent=agent)


async def _exec_update_transform(
    agent, dataset_id: str, transform_id: str,
    name: str = None, description: str = None, operations: list = None,
    rule_group: str = None, **args
) -> dict:
    try:
        return await update_transform_record(
            dataset_id, transform_id, agent.user_id,
            name, description,
            _as_operations(operations) if operations is not None else None,
            rule_group, agent.language,
        )
    except HTTPException as e:
        return tool_error("update_transform", e, agent=agent)


async def _exec_delete_transform(agent, dataset_id: str, transform_id: str, **args) -> dict:
    try:
        return await delete_transform_record(dataset_id, transform_id, agent.user_id, agent.language)
    except HTTPException as e:
        return tool_error("delete_transform", e, agent=agent)


# ── Granular builder tools ─────────────────────────────────────────

async def _exec_set_dataset(agent, dataset_id: str, **args) -> dict:
    try:
        columns = await _fetch_columns(agent, dataset_id)
    except HTTPException as e:
        return tool_error("set_dataset", e, agent=agent)

    draft = _draft_of(agent)
    if _draft_dataset_id(draft) != dataset_id:
        # A different dataset: the statistics/visualisation stages reference the
        # old dataset's columns — reset the draft to a single data_selection stage.
        draft.clear()
        draft.append({
            "type": "data_selection",
            "config": {"datasetId": dataset_id, "transformIds": []},
        })
    else:
        config = _stage_config(draft, "data_selection")
        config["datasetId"] = dataset_id
        config.setdefault("transformIds", [])

    # Keep the session in sync with the draft — set its datasetId and schema
    # snapshot and drop the stale saved recipe id, the same thing the PATCH
    # /dataset endpoint does, so the conversational path and the dropdown agree.
    schema_snapshot = None
    try:
        schema = await agent._capture_schema(dataset_id)
        if schema:
            schema_snapshot = schema
    except Exception:
        schema_snapshot = None
    async with agent.db_pool.acquire() as conn:
        await conn.execute(
            """
            UPDATE "AIRecipeSession"
            SET "datasetId" = $1, "schemaSnapshot" = $2,
                state = state || jsonb_build_object('saved_recipe_id', null),
                "updatedAt" = NOW()
            WHERE id = $3 AND "userId" = $4
            """,
            dataset_id, schema_snapshot, agent.session_id, agent.user_id,
        )

    return compute_scoreboard(draft, columns)


def apply_technique_decision(draft: list, algorithm_type: str) -> None:
    """Set the statistics stage's algorithmType, clearing its fields (they
    depend on the method). Shared by the set_technique tool and the /decision
    endpoint — one mutation, two callers."""
    config = _stage_config(draft, "statistics")
    config["algorithmType"] = algorithm_type
    config["config"] = {}


def apply_output_decision(draft: list, output_type: str) -> None:
    """Set the visualisation stage's outputType, clearing its fields (they
    depend on the output). Shared by the set_visualisation tool and the
    /decision endpoint."""
    config = _stage_config(draft, "visualisation")
    config["outputType"] = output_type
    config["config"] = {}


def apply_field_column(draft: list, stage_type: str, field: str, column: str, multi: bool) -> None:
    """Record a column choice on a field of the technique/output config — the
    single- vs multi-column accumulation the manual editor's column picker does.
    Shared by the /field-column endpoint; the set_*_fields tools merge a whole
    fields dict and stay as they are."""
    config = _stage_config(draft, stage_type)
    inner = config.setdefault("config", {})
    if multi:
        existing = inner.get(field)
        if not isinstance(existing, list):
            existing = [existing] if existing else []
        if column in existing:
            existing.remove(column)
        else:
            existing.append(column)
        inner[field] = existing
    else:
        inner[field] = column


def current_field_value(draft: list, stage_type: str, field: str, multi: bool):
    """What the draft already records for a field, or None when it is undecided.

    A **read**, so it must not go through `_stage_config`: that function creates
    the stage when it is absent, and asking a question should not change the
    draft. It walks the list directly.

    Used by a proposal click to keep a choice the user has made since the model
    offered its snapshot. A multi-column field is undecided only when its list is
    empty; a single field is undecided when it holds nothing.
    """
    for stage in draft or []:
        if stage.get("type") != stage_type:
            continue
        config = stage.get("config")
        inner = config.get("config") if isinstance(config, dict) else None
        if not isinstance(inner, dict):
            return None
        value = inner.get(field)
        if multi:
            return list(value) if isinstance(value, list) and value else None
        return value or None
    return None


async def _exec_set_technique(agent, algorithm_type: str, **args) -> dict:
    draft = _draft_of(agent)
    apply_technique_decision(draft, algorithm_type)
    return await _scoreboard_for(agent, draft)


async def _exec_set_technique_fields(agent, fields: dict, **args) -> dict:
    draft = _draft_of(agent)
    config = _stage_config(draft, "statistics")
    config.setdefault("config", {}).update(fields or {})
    return await _scoreboard_for(agent, draft)


async def _exec_set_visualisation(agent, output_type: str, **args) -> dict:
    draft = _draft_of(agent)
    apply_output_decision(draft, output_type)
    return await _scoreboard_for(agent, draft)


async def _exec_set_visualisation_fields(agent, fields: dict, **args) -> dict:
    draft = _draft_of(agent)
    config = _stage_config(draft, "visualisation")
    config.setdefault("config", {}).update(fields or {})
    return await _scoreboard_for(agent, draft)


async def _exec_set_transforms(agent, transform_ids: list, **args) -> dict:
    draft = _draft_of(agent)
    config = _stage_config(draft, "data_selection")
    config["transformIds"] = list(transform_ids or [])
    return await _scoreboard_for(agent, draft)


async def _exec_get_scoreboard(agent, **args) -> dict:
    return await _scoreboard_for(agent, _draft_of(agent))


async def _exec_set_name(agent, name: str, **args) -> dict:
    """Record the recipe's name (the scoreboard's 'name' piece).

    The name lives on the agent so it is immediately visible to save_recipe —
    which the text marker [DECISION:goal=...] never was, because a marker is
    only parsed after the tool loop and save_recipe runs during it. A tool sets
    the name at the moment it is called, like every other set_* piece."""
    agent._goal = (name or "").strip()
    return await _scoreboard_for(agent, _draft_of(agent))


_TOOL_SCHEMAS = [
    {
        "type": "function",
        "function": {
            "name": "get_recipe_model",
            "description": (
                "Return the canonical recipe constraint model: the available "
                "analysis algorithms, their required fields, and the output "
                "types, with labels and descriptions."
            ),
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_dataset_schema",
            "description": "Return the columns (name, is_numeric, is_categorical) of a dataset.",
            "parameters": {
                "type": "object",
                "properties": {"dataset_id": {"type": "string", "description": "Dataset id"}},
                "required": ["dataset_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "save_recipe",
            "description": (
                "Validate and save the current recipe draft (built with the "
                "set_* tools) to the workbench. The recipe name is the one "
                "recorded with set_name — do not pass a name. Errors block the "
                "save; warnings do not."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "dataset_id": {"type": "string", "description": "Optional override; the draft's dataset is used when omitted."},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_dataset_transforms",
            "description": "List the transforms (preparation rules) available for a dataset, with their ids, names, descriptions and operations.",
            "parameters": {
                "type": "object",
                "properties": {"dataset_id": {"type": "string", "description": "Dataset id"}},
                "required": ["dataset_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_transform",
            "description": "Get a single transform by id.",
            "parameters": {
                "type": "object",
                "properties": {
                    "dataset_id": {"type": "string", "description": "Dataset id"},
                    "transform_id": {"type": "string", "description": "Transform id"},
                },
                "required": ["dataset_id", "transform_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "create_transform",
            "description": (
                "Create a new transform (preparation rule) for a dataset. "
                "operations is a list of steps; each step has a type and type-specific fields. "
                "Valid types: filter (column, operator, value), "
                "fill_missing (column, method: mean|median|mode|constant|drop, value), "
                "convert_type (column, target_type: numeric|datetime|string|boolean), "
                "normalize (columns), standardize (columns), "
                "encode (column, encoding: one_hot|label), "
                "drop_duplicates (columns), drop_columns (columns), rename_column (column, new_name)."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "dataset_id": {"type": "string"},
                    "name": {"type": "string"},
                    "description": {"type": "string"},
                    "operations": {"type": "array", "items": {"type": "object"}},
                    "shared": {"type": "boolean"},
                },
                "required": ["dataset_id", "name", "operations"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "update_transform",
            "description": (
                "Update a transform (name, description, operations, rule_group). "
                "Omit a field to leave it unchanged. operations uses the same "
                "step types as create_transform."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "dataset_id": {"type": "string"},
                    "transform_id": {"type": "string"},
                    "name": {"type": "string"},
                    "description": {"type": "string"},
                    "operations": {"type": "array", "items": {"type": "object"}},
                    "rule_group": {"type": "string"},
                },
                "required": ["dataset_id", "transform_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "delete_transform",
            "description": "Delete a transform from a dataset (fails if any recipe still uses it).",
            "parameters": {
                "type": "object",
                "properties": {
                    "dataset_id": {"type": "string"},
                    "transform_id": {"type": "string"},
                },
                "required": ["dataset_id", "transform_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "set_dataset",
            "description": (
                "Set the dataset this recipe analyses (the data_selection stage). "
                "Returns the refreshed scoreboard."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "dataset_id": {"type": "string", "description": "Dataset id"},
                },
                "required": ["dataset_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "set_technique",
            "description": (
                "Set the analysis method (the statistics stage's algorithmType). "
                "Clears any previously chosen columns, since they depend on the "
                "method. Returns the refreshed scoreboard."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "algorithm_type": {
                        "type": "string",
                        "description": "An algorithm key from get_recipe_model (e.g. descriptive, t_test_independent).",
                    },
                },
                "required": ["algorithm_type"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "set_technique_fields",
            "description": (
                "Set the statistics stage's columns (the chosen method's required "
                "fields). Merges into any fields already set. Returns the refreshed "
                "scoreboard."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "fields": {
                        "type": "object",
                        "description": "Field name to column name (or list of column names), e.g. {\"columns\": [\"oi_quantity\"]}.",
                    },
                },
                "required": ["fields"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "set_visualisation",
            "description": (
                "Set the chart/output type (the visualisation stage's outputType). "
                "Clears any previously chosen output columns. Returns the refreshed "
                "scoreboard."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "output_type": {
                        "type": "string",
                        "description": "An output key from get_recipe_model (e.g. bar, scatter, table).",
                    },
                },
                "required": ["output_type"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "set_visualisation_fields",
            "description": (
                "Set the visualisation stage's columns (the chosen output's required "
                "fields). Merges into any fields already set. Returns the refreshed "
                "scoreboard."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "fields": {
                        "type": "object",
                        "description": "Field name to column name mapping, e.g. {\"xColumn\": \"b_brand_name\", \"yColumn\": \"oi_quantity\"}.",
                    },
                },
                "required": ["fields"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "set_transforms",
            "description": (
                "Set the transforms (preparation rules) applied to the dataset before "
                "analysis. Optional. Returns the refreshed scoreboard."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "transform_ids": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Transform ids to apply, in order.",
                    },
                },
                "required": ["transform_ids"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_scoreboard",
            "description": (
                "Return the current scoreboard: what is decided (crystallised) and "
                "what is needed next, with the valid choices. Use it to re-orient "
                "without changing anything."
            ),
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "set_name",
            "description": (
                "Set the recipe's name (the scoreboard's 'name' piece). Ask the "
                "user what to call the recipe first, then record it with this tool. "
                "Returns the refreshed scoreboard."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "The recipe name."},
                },
                "required": ["name"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_datasets",
            "description": (
                "List the datasets available to the user, optionally narrowed by "
                "a case-insensitive substring match on the name. Use it to resolve "
                "a dataset the user names in words (e.g. 'find me my bike sales "
                "data') to its id before calling set_dataset. Pass the user's words "
                "as search; call with no search to list everything."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "search": {
                        "type": "string",
                        "description": "Optional substring matched against dataset names (case-insensitive).",
                    },
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "suggest_choices",
            "description": (
                "Return the valid choices for a decision the user needs to make, so "
                "they can be offered as clickable chips. Call this when you are "
                "about to ask the user to choose one. For 'technique' and 'output' "
                "the choices are the methods and chart types. For a field piece "
                "('technique_fields' / 'output_fields') the choices are the columns "
                "of that field's type — pass `field` when more than one field is "
                "still empty, or omit it to be given the first one."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "piece": {
                        "type": "string",
                        "enum": ["technique", "output", "technique_fields", "output_fields"],
                        "description": "Which decision to offer choices for.",
                    },
                    "field": {
                        "type": "string",
                        "description": (
                            "Only for a field piece: which field the column chips are "
                            "for. Optional — omitted, the first still-empty field is used."
                        ),
                    },
                },
                "required": ["piece"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "offer_proposal",
            "description": (
                "Offer a concrete, complete proposal as ONE clickable chip the user "
                "can accept instead of typing. Use it whenever you have specific "
                "column choices to put forward together — for example a dependent "
                "column plus its predictors — so the user does not have to reply "
                "'go with that' in words. The chip applies every field it names. "
                "Write `label` in the user's own language: it is the chip's text."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "label": {
                        "type": "string",
                        "description": (
                            "The chip's text, in the language the user writes in "
                            "(for example 'Go with that')."
                        ),
                    },
                    "fields": {
                        "type": "array",
                        "description": "The field choices the chip applies together.",
                        "items": {
                            "type": "object",
                            "properties": {
                                "piece": {
                                    "type": "string",
                                    "enum": ["technique_fields", "output_fields"],
                                },
                                "field": {"type": "string"},
                                "column": {"type": "string"},
                            },
                            "required": ["piece", "field", "column"],
                        },
                    },
                },
                "required": ["label", "fields"],
            },
        },
    },
]


# The recipe concierge's own registry.
RECIPE_REGISTRY = "recipe"


def register_all_tools() -> None:
    """Register the recipe tools into the recipe concierge's registry.

    One call per tool. The registry IS the concierge's scope now, so there is no
    allow-list to keep in step and no table to iterate — `run_tool_loop` is
    called without `tool_names`.

    RECIPE_REGISTRY rather than the shared `default`: every concierge now has its
    own, so a tool name two of them declare can no longer collide.
    """
    register_tool(RECIPE_REGISTRY, "get_recipe_model", _TOOL_SCHEMAS[0], _exec_get_recipe_model)
    register_tool(RECIPE_REGISTRY, "get_dataset_schema", _TOOL_SCHEMAS[1], _exec_get_dataset_schema)
    register_tool(RECIPE_REGISTRY, "save_recipe", _TOOL_SCHEMAS[2], _exec_save_recipe)
    register_tool(RECIPE_REGISTRY, "get_dataset_transforms", _TOOL_SCHEMAS[3], _exec_get_dataset_transforms)
    register_tool(RECIPE_REGISTRY, "get_transform", _TOOL_SCHEMAS[4], _exec_get_transform)
    register_tool(RECIPE_REGISTRY, "create_transform", _TOOL_SCHEMAS[5], _exec_create_transform)
    register_tool(RECIPE_REGISTRY, "update_transform", _TOOL_SCHEMAS[6], _exec_update_transform)
    register_tool(RECIPE_REGISTRY, "delete_transform", _TOOL_SCHEMAS[7], _exec_delete_transform)
    register_tool(RECIPE_REGISTRY, "set_dataset", _TOOL_SCHEMAS[8], _exec_set_dataset)
    register_tool(RECIPE_REGISTRY, "set_technique", _TOOL_SCHEMAS[9], _exec_set_technique)
    register_tool(RECIPE_REGISTRY, "set_technique_fields", _TOOL_SCHEMAS[10], _exec_set_technique_fields)
    register_tool(RECIPE_REGISTRY, "set_visualisation", _TOOL_SCHEMAS[11], _exec_set_visualisation)
    register_tool(RECIPE_REGISTRY, "set_visualisation_fields", _TOOL_SCHEMAS[12], _exec_set_visualisation_fields)
    register_tool(RECIPE_REGISTRY, "set_transforms", _TOOL_SCHEMAS[13], _exec_set_transforms)
    register_tool(RECIPE_REGISTRY, "get_scoreboard", _TOOL_SCHEMAS[14], _exec_get_scoreboard)
    register_tool(RECIPE_REGISTRY, "set_name", _TOOL_SCHEMAS[15], _exec_set_name)
    register_tool(RECIPE_REGISTRY, "list_datasets", _TOOL_SCHEMAS[16], _exec_list_datasets)
    register_tool(RECIPE_REGISTRY, "suggest_choices", _TOOL_SCHEMAS[17], _exec_suggest_choices)
    register_tool(RECIPE_REGISTRY, "offer_proposal", _TOOL_SCHEMAS[18], _exec_offer_proposal)

