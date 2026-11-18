"""
Server-side constraint matrix for recipe pipeline validation.

The backend MUST validate all recipe stages independently of the
frontend — the API may be called by external clients that bypass
the frontend's guardrails entirely.

The constraint knowledge lives in three canonical defs —
``FIELD_DEFS``, ``ALGORITHM_DEFS`` and ``OUTPUT_DEFS`` — one home,
no duplication. Every user-facing string in those defs is a declared
``TranslationKey``, and error messages use translation keys with
substitution parameters so they work in all supported languages.
"""

from typing import Any, Dict, List, Optional, Set
from dataclasses import dataclass, field, asdict

from .translations import (
    RECIPE_SCOREBOARD_KEYS,
    TranslationKey,
    recipes_column_type_categorical,
    recipes_column_type_numeric,
    recipes_field_label_categoryColumn,
    recipes_field_label_columns,
    recipes_field_label_dependentColumn,
    recipes_field_label_factorColumn,
    recipes_field_label_factorColumn2,
    recipes_field_label_independentColumns,
    recipes_field_label_responseColumn,
    recipes_field_label_responseColumn2,
    recipes_field_label_xColumn,
    recipes_field_label_yColumn,
    recipes_requirement_anova_one_way,
    recipes_requirement_anova_two_way,
    recipes_requirement_area,
    recipes_requirement_bar,
    recipes_requirement_chi_square,
    recipes_requirement_correlation,
    recipes_requirement_descriptive,
    recipes_requirement_distribution,
    recipes_requirement_donut,
    recipes_requirement_hbar,
    recipes_requirement_histogram,
    recipes_requirement_line,
    recipes_requirement_linear_regression,
    recipes_requirement_none,
    recipes_requirement_pie,
    recipes_requirement_scatter,
    recipes_requirement_t_test_independent,
    recipes_requirement_t_test_paired,
    recipes_requirement_table,
    recipes_technique_anova_one_way,
    recipes_technique_anova_two_way,
    recipes_technique_chi_square,
    recipes_technique_correlation,
    recipes_technique_descriptive,
    recipes_technique_linear_regression,
    recipes_technique_t_test_independent,
    recipes_technique_t_test_paired,
    recipes_result_type_numeric,
    recipes_result_type_tabular,
    recipes_validation_algorithm_required,
    recipes_validation_incompatible_algo_output,
    recipes_validation_insufficient_columns_algo,
    recipes_validation_insufficient_columns_output,
    recipes_validation_missing_algo_field,
    recipes_validation_missing_output_field,
    recipes_validation_unknown_algorithm,
    recipes_validation_unknown_columns,
    recipes_validation_unknown_field,
    recipes_validation_unknown_output,
    recipes_validation_wrong_column_type,
)


# ============================================================
# Structured error type
# ============================================================

@dataclass
class ValidationError:
    """A single validation failure. Holds a declared TranslationKey and
    parameters; the caller translates via t() before display."""
    key: TranslationKey          # declared in translations.py (carries .key + .fallback)
    params: Dict[str, Any] = field(default_factory=dict)
    # For multi-line display formatting (used before translation)
    stage: str = ""              # "statistics", "visualisation", ""
    indent_hint: str = ""        # e.g. "  → " prefix for fix lines


@dataclass
class ValidationIssue:
    """A single issue in the canonical `{source, field?, key, fallback, params}`
    shape returned by the pure `validate_recipe` validator.

    `key`/`fallback` are the translation key string and English fallback;
    `params` are scalars (or nested `{key, fallback}` dicts) for `{var}`
    substitution. `field` names the offending config field, when applicable.
    """
    source: str                  # "dataset" | "algorithm" | "output" | "compatibility"
    key: str                     # translation key string (e.g. "recipes.validation.missing_algo_field")
    fallback: str                # English fallback text
    params: Dict[str, Any] = field(default_factory=dict)
    field: Optional[str] = None  # offending field name, when applicable


# ============================================================
# Column type tracking
# ============================================================

@dataclass
class ColumnInfo:
    name: str
    dtype: str = "unknown"
    is_numeric: bool = False
    is_categorical: bool = False


#: Ways a column name marks itself as a label rather than a measurement.
#:
#: A `_id` suffix is how every driver in this tree spells an identifier, and an
#: identifier is a label in code form: a regression coefficient on `s3_brand_id`
#: has no interpretation, and a chart axis over it plots the order the rows were
#: inserted. Measured on the dataset behind a live session: of 21 numeric columns,
#: 15 were `_id` — so a six-chip row in storage order was three quarters
#: identifiers, and the two genuine measures the model had just recommended sat in
#: the withheld fifteen. The prose named the right columns and the screen showed
#: the wrong ones.
#:
#: This is a name heuristic and nothing more. The honest alternative — cardinality
#: — is unavailable: a virtual dataset's columns carry `unique_count: 0`, because
#: knowing how many distinct values a column holds needs the join to run. A name
#: rule that is right about the overwhelming majority is better than no rule, and
#: it is confined to ORDER: a column is still offered, just later.
_LABEL_SUFFIXES = ("_id",)


def _is_label_column(name: str) -> bool:
    """True when a column name reads as a code rather than a measure."""
    lowered = (name or "").lower()
    return any(lowered == suf[1:] or lowered.endswith(suf) for suf in _LABEL_SUFFIXES)


def columns_of_type(columns, column_type: str) -> List[str]:
    """Column names matching a field's required type, measures before labels.

    Lives here rather than beside either caller because both need it and only one
    of them may import the other: `ai_agent` imports `ai_recipe_tools`, so a
    helper in either would make the second caller import back up the chain. It is
    a pure projection over `ColumnInfo`, which is this module's own type.

    Until 2026-11-11 it lived in `ai_agent` as `_columns_of_type`, and
    `suggest_choices` — in `ai_recipe_tools` — had no way to reach it. That is why
    the tool could not build a column row at all: the fallback could, the model's
    own call could not.

    **Measures come first, labels last, and each group keeps its own order.** The
    caller caps this list at CHIP_SET_LIMIT, so the order decides what a user can
    click: putting identifiers last is what lets the six visible chips be the six
    most useful columns rather than the first six the definition happens to list.
    A stable partition, not a sort — a column that is neither an identifier nor a
    measurement keeps the position the schema gave it, so the row stays
    predictable between turns.
    """
    cols = columns or []
    if column_type == "numeric":
        cols = [c for c in cols if c.is_numeric]
    elif column_type == "categorical":
        cols = [c for c in cols if c.is_categorical]
    names = [c.name for c in cols if c.name]
    return [n for n in names if not _is_label_column(n)] + [
        n for n in names if _is_label_column(n)
    ]


def to_column_info(columns) -> List["ColumnInfo"]:
    """Project stored or fetched columns to ``ColumnInfo``, accepting both
    spellings and objects that are already ``ColumnInfo``.

    Two payloads reach this, and neither is a mistake:

    - the stage's stored ``config.columns``, which the manual editor writes in
      camelCase (``isNumeric``, ``isCategorical``) and whose type key is ``type``;
    - the dataset-overview / schema responses, which arrive in snake_case
      (``is_numeric``, ``is_categorical``) and whose type key is ``dtype`` or
      ``data_type``.

    This function is the one place that knows that. Before it existed the
    knowledge was written out five times — in ``helpers.validate_recipe_stages``,
    ``crud._stage_column_info``, ``ai_recipe_tools._to_column_info``, the
    issue formatter's label lookup, and ``execute._relation_col_info`` — and the
    copies did not agree: the formatter read only the camelCase keys, so a
    payload in snake_case rendered its columns as ``?`` instead of their type.

    A ``ColumnInfo`` passed in is returned unchanged, so a caller that already
    holds objects does not have to convert back to dicts to satisfy this.
    """
    out: List[ColumnInfo] = []
    for c in columns or []:
        if isinstance(c, ColumnInfo):
            out.append(c)
        elif isinstance(c, dict):
            out.append(ColumnInfo(
                name=c.get("name") or c.get("column_name") or "",
                dtype=c.get("type") or c.get("dtype") or c.get("data_type") or "unknown",
                is_numeric=bool(c.get("is_numeric") or c.get("isNumeric")),
                is_categorical=bool(c.get("is_categorical") or c.get("isCategorical")),
            ))
    return out


# ============================================================
# Canonical model defs — single source of truth
# ============================================================

@dataclass
class FieldDef:
    """A selectable config field. ``label`` is a declared TranslationKey."""
    label: TranslationKey
    column_type: str = "any"    # "numeric" | "categorical" | "any"
    multi: bool = False         # True when the field holds a list of columns


@dataclass
class AlgorithmDef:
    """A statistics technique: its display name, required fields,
    column-count needs, and the output types it can be rendered as."""
    label: TranslationKey                # human-readable name (recipes.technique.*)
    description: TranslationKey           # human-readable requirement (recipes.requirement.*)
    fields: List[str] = field(default_factory=list)
    min_categorical: int = 0
    min_numeric: int = 0
    compatible_outputs: List[str] = field(default_factory=list)


@dataclass
class OutputDef:
    """An output type: its required fields and column-count needs."""
    description: TranslationKey           # human-readable requirement (recipes.requirement.*)
    fields: List[str] = field(default_factory=list)
    min_categorical: int = 0
    min_numeric: int = 0


FIELD_DEFS: Dict[str, FieldDef] = {
    "factorColumn": FieldDef(
        label=recipes_field_label_factorColumn,
        column_type="categorical",
    ),
    "responseColumn": FieldDef(
        label=recipes_field_label_responseColumn,
        column_type="numeric",
    ),
    "responseColumn2": FieldDef(
        label=recipes_field_label_responseColumn2,
        column_type="numeric",
    ),
    "dependentColumn": FieldDef(
        label=recipes_field_label_dependentColumn,
        column_type="numeric",
    ),
    "independentColumns": FieldDef(
        label=recipes_field_label_independentColumns,
        column_type="numeric",
        multi=True,
    ),
    "xColumn": FieldDef(
        label=recipes_field_label_xColumn,
        column_type="any",
    ),
    "yColumn": FieldDef(
        label=recipes_field_label_yColumn,
        column_type="numeric",
    ),
    "categoryColumn": FieldDef(
        label=recipes_field_label_categoryColumn,
        column_type="categorical",
    ),
    "factorColumn2": FieldDef(
        label=recipes_field_label_factorColumn2,
        column_type="categorical",
    ),
    "columns": FieldDef(
        label=recipes_field_label_columns,
        column_type="any",
        multi=True,
    ),
}


ALGORITHM_DEFS: Dict[str, AlgorithmDef] = {
    "descriptive": AlgorithmDef(
        label=recipes_technique_descriptive,
        description=recipes_requirement_descriptive,
        fields=["columns"],
        min_numeric=1,
        compatible_outputs=[
            "bar", "hbar", "pie", "donut", "scatter", "line", "area",
            "distribution", "histogram", "table", "none",
        ],
    ),
    "correlation": AlgorithmDef(
        label=recipes_technique_correlation,
        description=recipes_requirement_correlation,
        fields=["columns"],
        min_numeric=2,
        compatible_outputs=[
            "bar", "hbar", "pie", "donut", "scatter", "line", "area",
            "distribution", "histogram", "table", "none",
        ],
    ),
    "t_test_independent": AlgorithmDef(
        label=recipes_technique_t_test_independent,
        description=recipes_requirement_t_test_independent,
        fields=["factorColumn", "responseColumn"],
        min_categorical=1,
        min_numeric=1,
        compatible_outputs=["table", "none"],
    ),
    "t_test_paired": AlgorithmDef(
        label=recipes_technique_t_test_paired,
        description=recipes_requirement_t_test_paired,
        fields=["responseColumn", "responseColumn2"],
        min_numeric=2,
        compatible_outputs=["table", "none"],
    ),
    "anova_one_way": AlgorithmDef(
        label=recipes_technique_anova_one_way,
        description=recipes_requirement_anova_one_way,
        fields=["factorColumn", "responseColumn"],
        min_categorical=1,
        min_numeric=1,
        compatible_outputs=["table", "none"],
    ),
    "anova_two_way": AlgorithmDef(
        label=recipes_technique_anova_two_way,
        description=recipes_requirement_anova_two_way,
        fields=["factorColumn", "factorColumn2", "responseColumn"],
        min_categorical=2,
        min_numeric=1,
        compatible_outputs=["table", "none"],
    ),
    "linear_regression": AlgorithmDef(
        label=recipes_technique_linear_regression,
        description=recipes_requirement_linear_regression,
        fields=["dependentColumn", "independentColumns"],
        min_numeric=2,
        compatible_outputs=["scatter", "table", "none"],
    ),
    "chi_square": AlgorithmDef(
        label=recipes_technique_chi_square,
        description=recipes_requirement_chi_square,
        fields=["columns"],
        min_categorical=2,
        compatible_outputs=["table", "none"],
    ),
}


OUTPUT_DEFS: Dict[str, OutputDef] = {
    "bar": OutputDef(
        description=recipes_requirement_bar,
        fields=["xColumn", "yColumn"],
        min_categorical=1,
        min_numeric=1,
    ),
    "hbar": OutputDef(
        description=recipes_requirement_hbar,
        fields=["xColumn", "yColumn"],
        min_categorical=1,
        min_numeric=1,
    ),
    "pie": OutputDef(
        description=recipes_requirement_pie,
        fields=["categoryColumn"],
        min_categorical=1,
    ),
    "donut": OutputDef(
        description=recipes_requirement_donut,
        fields=["categoryColumn"],
        min_categorical=1,
    ),
    "line": OutputDef(
        description=recipes_requirement_line,
        fields=["xColumn", "yColumn"],
        min_numeric=2,
    ),
    "area": OutputDef(
        description=recipes_requirement_area,
        fields=["xColumn", "yColumn"],
        min_numeric=2,
    ),
    "scatter": OutputDef(
        description=recipes_requirement_scatter,
        fields=["xColumn", "yColumn"],
        min_numeric=2,
    ),
    "distribution": OutputDef(
        description=recipes_requirement_distribution,
        fields=["yColumn"],
        min_numeric=1,
    ),
    "histogram": OutputDef(
        description=recipes_requirement_histogram,
        fields=["xColumn"],
        min_numeric=1,
    ),
    "table": OutputDef(
        description=recipes_requirement_table,
        fields=[],
    ),
    "none": OutputDef(
        description=recipes_requirement_none,
        fields=[],
    ),
}


#: Every piece a recipe draft is made of, in the order a scoreboard reads them.
#:
#: **Six, and stated from the first turn**, which is the point of the list. A draft
#: with nothing decided reports four pending pieces, because the two field pieces
#: appear only once their parent is chosen — so a denominator counted from what is
#: visible would start at four and grow to six, moving the goalposts mid-task. This
#: list is the shape of the job, not a snapshot of it.
#:
#: It is also the definition the "complete" assertion uses: a finished scoreboard has
#: exactly this many crystallised pieces and none pending, so the constant and the
#: behaviour cannot separate. Go declares the same order in `recipePieces`.
def _key(name: str) -> str:
    """The declared translation key, by its canonical name.

    Mirrors `datasets/virtual_scoreboard.py`'s `_key`: the declaration is the
    single source, so this returns the key string the boundary resolves and a
    mistyped name fails at import rather than shipping a key nothing declares.

    The scoreboard is a pure function — no pool, no language — so it cannot
    translate. It emits a key; `_resolve_scoreboard_texts` turns it into a
    sentence where a pool and a language both exist.
    """
    return RECIPE_SCOREBOARD_KEYS[name].key


RECIPE_PIECES = (
    "dataset",
    "technique",
    "technique_fields",
    "output",
    "output_fields",
    "name",
)


#: How each piece is put to the user. The five values are the virtual scoreboard's
#: vocabulary, adopted whole (§3.11, D1 = (b)) so a reader moving between the two
#: pages meets one set of words rather than learning a second.
#:
#: .   `point`  — the page already shows the control; name it, do not list options
#: .   `ask`    — a closed set, put as a question with chips
#: .   `invite` — the user's own words; a chip would put a vocabulary in their mouth
#: .   `read`   — the assistant fetches it and nobody is asked
#: .   `offer`  — accept or ignore a computed candidate
#:
#: `read` and `offer` have no recipe piece and are deliberately idle. The recipe's
#: two field pieces choose columns rather than fetching them, which is why they
#: surface as `ask`; and the recipe has no deterministic candidate to offer. They
#: stay in the vocabulary because the vocabulary is shared, not because they are
#: needed here — a later reader who finds them unused is told here why, so they do
#: not invent a piece to justify them.
SURFACE_POINT = "point"
SURFACE_ASK = "ask"
SURFACE_INVITE = "invite"
SURFACE_READ = "read"
SURFACE_OFFER = "offer"

SURFACES = (SURFACE_POINT, SURFACE_ASK, SURFACE_INVITE, SURFACE_READ, SURFACE_OFFER)


#: How many chips a suggestion row shows before it stops.
#:
#: Six is the width the narrowest layout holds: the chips wrap, and a seventh
#: pushes the row past the panel at the smallest supported width. It is a
#: presentation limit, not a product one — every choice remains available by
#: asking for it, and the count withheld travels beside the row so a short row
#: never reads as a complete one.
CHIP_SET_LIMIT = 6


def cap_choices(choices: Optional[List[str]]) -> Dict[str, Any]:
    """Trim a choice list to the chip width, and say how many were withheld.

    One function because there are two routes to a chip set — the model calling
    `suggest_choices`, and `_derive_suggestion` filling in when it does not — and
    two copies of a cap is two chances for the rows to differ in length. The
    withheld count is part of the contract, not a nicety: a row that silently
    shows six of eleven says "these are the options" when it means "these are
    some of them", and the difference matters to whoever is choosing.

    An exactly-full row reports `withheld: 0` rather than omitting the key, so a
    reader can tell a full row from a truncated one without knowing the limit, and
    carries an empty `overflow` for the same reason — a reader should not have to
    know the limit to tell "nothing withheld" from "no key here".
    """
    items = list(choices or [])
    if len(items) <= CHIP_SET_LIMIT:
        return {"choices": items, "withheld": 0, "overflow": []}
    return {
        "choices": items[:CHIP_SET_LIMIT],
        "withheld": len(items) - CHIP_SET_LIMIT,
        # The remainder itself, so the row can expand. A count alone made the cap
        # a silent loss of function rather than a display limit: measured
        # 2026-11-11, the model told the user to click "Linear Regression" and it
        # was seventh of eight algorithms, so no such chip existed and the
        # conversation dead-ended. A withheld choice a user cannot reach is not
        # withheld, it is missing.
        "overflow": items[CHIP_SET_LIMIT:],
    }


#: Which surface answers which pending piece.
#:
#: The dataset is `point` because the page already carries a selector for it: the
#: assistant names what is on screen and says what picking one would settle, rather
#: than offering a chip list of every dataset the user owns. The name is `invite`
#: because it is the one piece that is the user's by definition.
#: Which piece must be settled before a conditional piece can even be asked about.
#:
#: The other four pieces are always in `crystallised` or `pending`, so a piece
#: absent from both is one of these two — or a defect, which the partition asserts.
CONDITIONAL_PARENT = {
    "technique_fields": "technique",
    "output_fields": "output",
}

PIECE_SURFACE = {
    "dataset": SURFACE_POINT,
    "technique": SURFACE_ASK,
    "technique_fields": SURFACE_ASK,
    "output": SURFACE_ASK,
    "output_fields": SURFACE_ASK,
    "name": SURFACE_INVITE,
}


# Result-type labels used by the cross-stage compatibility message.
RESULT_TYPE_KEYS = {
    "tabular": recipes_result_type_tabular,
    "numeric": recipes_result_type_numeric,
}

# Algorithms whose result is tabular (vs numeric) — drives the
# "produces {tabular|numeric} results" wording in compatibility messages.
INFERENCE_ALGOS = {
    "t_test_independent", "t_test_paired",
    "anova_one_way", "anova_two_way", "chi_square",
}


def serialize_recipe_model() -> Dict[str, Any]:
    """Serialize the canonical model (fields/algorithms/outputs) with labels and
    descriptions as ``{key, fallback}`` pairs — the same shape the
    ``/api/recipes/recipe-model`` endpoint serves and the AI tools consume."""
    def _tk(tk):
        return {"key": tk.key, "fallback": tk.fallback}

    return {
        "fields": {
            name: {"label": _tk(fdef.label), "columnType": fdef.column_type, "multi": fdef.multi}
            for name, fdef in FIELD_DEFS.items()
        },
        "algorithms": {
            name: {
                "label": _tk(adef.label),
                "description": _tk(adef.description),
                "fields": adef.fields,
                "minCategorical": adef.min_categorical,
                "minNumeric": adef.min_numeric,
                "compatibleOutputs": adef.compatible_outputs,
            }
            for name, adef in ALGORITHM_DEFS.items()
        },
        "outputs": {
            name: {
                "description": _tk(odef.description),
                "fields": odef.fields,
                "minCategorical": odef.min_categorical,
                "minNumeric": odef.min_numeric,
            }
            for name, odef in OUTPUT_DEFS.items()
        },
    }


# ============================================================
# Validation helpers (sync logic only, no strings)
# ============================================================

def satisfies_requirement(
    columns: List[ColumnInfo],
    min_categorical: int = 0,
    min_numeric: int = 0,
) -> bool:
    if not columns:
        return False
    cat = sum(1 for c in columns if c.is_categorical)
    num = sum(1 for c in columns if c.is_numeric)
    if cat < min_categorical:
        return False
    if num < min_numeric:
        return False
    return True


def get_available_algorithms(columns: List[ColumnInfo]) -> List[str]:
    if not columns:
        return []
    return [
        key for key, d in ALGORITHM_DEFS.items()
        if satisfies_requirement(columns, d.min_categorical, d.min_numeric)
    ]


def offered_outputs(
    columns: List[ColumnInfo],
    technique: Optional[str] = None,
) -> List[str]:
    """The outputs this draft may choose: satisfiable by the columns **and**
    allowed by the technique.

    With no technique yet the second test cannot be asked, so the answer is
    every output the columns allow — deliberate, and stated here rather than
    left to a fallback in a caller. An empty ``columns`` list means the dataset
    is not attached yet, so nothing is known about the columns and they do not
    constrain the answer; an unknown technique does not constrain it either.

    This is the one implementation of the predicate. ``get_available_outputs``
    (the validator's message) and ``compute_scoreboard`` (the chips) both call
    it, because when they each filtered by half the question the scoreboard
    offered seven chips of eleven the validator then refused.
    """
    allowed = [
        key for key, d in OUTPUT_DEFS.items()
        if not columns
        or satisfies_requirement(columns, d.min_categorical, d.min_numeric)
    ]
    if technique is None:
        return allowed
    adef = ALGORITHM_DEFS.get(technique)
    if adef is None:
        return allowed
    return [key for key in allowed if key in adef.compatible_outputs]


def get_available_outputs(columns: List[ColumnInfo]) -> List[str]:
    """The outputs the columns alone allow — ``offered_outputs`` with no
    technique chosen."""
    return offered_outputs(columns)


# ============================================================
# Validation functions — return List[ValidationError] with keys
# ============================================================

def validate_algorithm_config(
    algorithm_type: str, config: Dict
) -> List[ValidationError]:
    errors: List[ValidationError] = []

    if algorithm_type not in ALGORITHM_DEFS:
        errors.append(ValidationError(
            key=recipes_validation_unknown_algorithm,
            params={
                "type": algorithm_type,
                "options": ", ".join(sorted(ALGORITHM_DEFS.keys())),
            },
            stage="statistics",
        ))
        return errors

    inner = config.get("config", {}) if isinstance(config.get("config"), dict) else {}
    required = ALGORITHM_DEFS[algorithm_type].fields

    for field_name in required:
        val = inner.get(field_name)
        if not val or (isinstance(val, list) and len(val) == 0):
            errors.append(ValidationError(
                key=recipes_validation_missing_algo_field,
                params={
                    "algo": algorithm_type,
                    "field": field_name,
                    "label_key": FIELD_DEFS[field_name].label,
                },
                stage="statistics",
            ))

    unknown = [k for k in inner if k not in required]
    if unknown:
        errors.append(ValidationError(
            key=recipes_validation_unknown_field,
            params={
                "field": ", ".join(sorted(unknown)),
                "type": algorithm_type,
                "options": ", ".join(sorted(required)),
            },
            stage="statistics",
        ))

    return errors


def validate_output_config(
    output_type: str, config: Dict
) -> List[ValidationError]:
    errors: List[ValidationError] = []

    if output_type == "none":
        return errors

    if output_type not in OUTPUT_DEFS:
        errors.append(ValidationError(
            key=recipes_validation_unknown_output,
            params={
                "type": output_type,
                "options": ", ".join(sorted(OUTPUT_DEFS.keys())),
            },
            stage="visualisation",
        ))
        return errors

    inner = config.get("config", {}) if isinstance(config.get("config"), dict) else {}
    required = OUTPUT_DEFS[output_type].fields

    for field_name in required:
        val = inner.get(field_name)
        if not val or (isinstance(val, list) and len(val) == 0):
            errors.append(ValidationError(
                key=recipes_validation_missing_output_field,
                params={
                    "output": output_type,
                    "field": field_name,
                    "label_key": FIELD_DEFS[field_name].label,
                },
                stage="visualisation",
            ))

    unknown = [k for k in inner if k not in required]
    if unknown:
        errors.append(ValidationError(
            key=recipes_validation_unknown_field,
            params={
                "field": ", ".join(sorted(unknown)),
                "type": output_type,
                "options": ", ".join(sorted(required)),
            },
            stage="visualisation",
        ))

    return errors


def validate_column_references(
    columns: List[ColumnInfo],
    stage_configs: List[Dict],
) -> List[ValidationError]:
    if not columns:
        return []

    col_names = {c.name for c in columns}
    errors: List[ValidationError] = []

    for stage in stage_configs:
        config = stage.get("config", {})
        inner = config.get("config", {}) if isinstance(config.get("config"), dict) else {}
        stage_type = stage.get("type", "")

        refs: Set[str] = set()
        for field_name, fdef in FIELD_DEFS.items():
            v = inner.get(field_name)
            if fdef.multi:
                if isinstance(v, list):
                    refs.update(str(x) for x in v if x)
            else:
                if v and isinstance(v, str):
                    refs.add(v)

        missing = refs - col_names
        if missing:
            sorted_names = sorted(col_names)
            available = ", ".join(sorted_names[:10])
            if len(sorted_names) > 10:
                available += "…"
            errors.append(ValidationError(
                key=recipes_validation_unknown_columns,
                params={
                    "stage": stage_type,
                    "columns": ", ".join(sorted(missing)),
                    "available": available,
                },
                stage=stage_type,
            ))

    return errors


def validate_column_types(
    columns: List[ColumnInfo],
    stage_configs: List[Dict],
) -> List[ValidationError]:
    """Check that each bound column matches its field's required column_type.

    Reads the field defs (FIELD_DEFS[*].column_type) and flags any bound
    column whose type does not match (e.g. a categorical field bound to a
    numeric column). Existence is handled separately by
    validate_column_references; this only checks the type of columns that
    exist.
    """
    if not columns:
        return []

    col_by_name = {c.name: c for c in columns}
    errors: List[ValidationError] = []

    for stage in stage_configs:
        config = stage.get("config", {})
        inner = config.get("config", {}) if isinstance(config.get("config"), dict) else {}
        stage_type = stage.get("type", "")

        for field_name, fdef in FIELD_DEFS.items():
            if fdef.column_type == "any":
                continue

            v = inner.get(field_name)
            bound_names: List[str] = []
            if fdef.multi:
                if isinstance(v, list):
                    bound_names = [str(x) for x in v if x]
            elif v and isinstance(v, str):
                bound_names = [v]

            for col_name in bound_names:
                col = col_by_name.get(col_name)
                if col is None:
                    continue  # existence checked by validate_column_references

                if fdef.column_type == "numeric" and col.is_numeric:
                    continue
                if fdef.column_type == "categorical" and col.is_categorical:
                    continue

                expected_key = (
                    recipes_column_type_numeric
                    if fdef.column_type == "numeric"
                    else recipes_column_type_categorical
                )
                errors.append(ValidationError(
                    key=recipes_validation_wrong_column_type,
                    params={
                        "field": field_name,
                        "label_key": fdef.label,
                        "column": col_name,
                        "expected_key": expected_key,
                    },
                    stage=stage_type,
                ))

    return errors


def validate_algorithm_output_compatibility(
    algorithm_type: Optional[str],
    output_type: Optional[str],
) -> List[ValidationError]:
    errors: List[ValidationError] = []

    if not algorithm_type or not output_type or output_type == "none":
        return errors

    d = ALGORITHM_DEFS.get(algorithm_type)
    if d is None:
        return errors

    if output_type not in d.compatible_outputs:
        suggestions = [t for t in d.compatible_outputs if t != "none"]
        result_type_id = "tabular" if algorithm_type in INFERENCE_ALGOS else "numeric"
        errors.append(ValidationError(
            key=recipes_validation_incompatible_algo_output,
            params={
                "algo": algorithm_type,
                "result_type_key": RESULT_TYPE_KEYS[result_type_id],
                "output": output_type,
                "options": ", ".join(suggestions),
            },
        ))

    return errors


def validate_column_requirements(
    columns: List[ColumnInfo],
    algorithm_type: Optional[str],
    output_type: Optional[str],
) -> List[ValidationError]:
    errors: List[ValidationError] = []
    # Pass raw column info so the formatter can translate type labels
    col_info_for_formatter = columns[:12] if len(columns) > 12 else columns

    if algorithm_type and algorithm_type in ALGORITHM_DEFS:
        d = ALGORITHM_DEFS[algorithm_type]
        if not satisfies_requirement(columns, d.min_categorical, d.min_numeric):
            available = get_available_algorithms(columns)
            alts = [a for a in available if a != algorithm_type]
            errors.append(ValidationError(
                key=recipes_validation_insufficient_columns_algo,
                params={
                    "algo": algorithm_type,
                    "requirement_key": d.description,
                    "columns": "",  # filled by formatter
                    "_col_info": col_info_for_formatter,
                    "options": ", ".join(alts) if alts else "…",
                },
                stage="statistics",
            ))

    if output_type and output_type != "none" and output_type in OUTPUT_DEFS:
        d = OUTPUT_DEFS[output_type]
        if not satisfies_requirement(columns, d.min_categorical, d.min_numeric):
            available = get_available_outputs(columns)
            alts = [o for o in available if o != output_type and o != "none"]
            errors.append(ValidationError(
                key=recipes_validation_insufficient_columns_output,
                params={
                    "output": output_type,
                    "requirement_key": d.description,
                    "columns": "",  # filled by formatter
                    "_col_info": col_info_for_formatter,
                    "options": ", ".join(alts) if alts else "…",
                },
                stage="visualisation",
            ))

    return errors


# ============================================================
# Pure validator — canonical {errors, warnings} shape
# ============================================================

def _to_issue(
    e: ValidationError,
    source: str,
    field_name: Optional[str] = None,
) -> ValidationIssue:
    """Convert a ValidationError into the canonical ValidationIssue shape.

    Nested TranslationKeys (label_key / requirement_key / result_type_key)
    become ``{key, fallback}`` dicts, and ``_col_info`` becomes a serializable
    column list.
    """
    params: Dict[str, Any] = {}
    for k, v in e.params.items():
        if k in ("label_key", "requirement_key", "result_type_key", "expected_key"):
            # strip the "_key" suffix: label_key -> label, expected_key -> expected
            params[k[:-4]] = {"key": v.key, "fallback": v.fallback}
        elif k == "_col_info":
            params["columns"] = [
                {
                    "name": c.name,
                    "isNumeric": c.is_numeric,
                    "isCategorical": c.is_categorical,
                }
                for c in v
            ]
        elif k == "columns":
            # formatter placeholder ("") — replaced by _col_info above
            continue
        else:
            params[k] = v
    return ValidationIssue(
        source=source,
        key=e.key.key,
        fallback=e.key.fallback,
        params=params,
        field=field_name,
    )


def validate_recipe(
    model: Optional[Dict[str, Any]] = None,
    columns: Optional[List[ColumnInfo]] = None,
    algorithm: Optional[Dict] = None,
    output: Optional[Dict] = None,
) -> Dict[str, List[ValidationIssue]]:
    """Pure recipe validator driven entirely by the defs.

    ``algorithm``/``output`` are the stage config dicts
    (``{"algorithmType"|"outputType": ..., "config": {...}}``); ``columns`` is
    a list of ColumnInfo. ``model`` is accepted for API parity with the
    TypeScript port and is unused here — the underlying validators read the
    module-level FIELD_DEFS / ALGORITHM_DEFS / OUTPUT_DEFS.

    Returns ``{"errors": [...], "warnings": [...]}`` of ValidationIssue.

    errors   = a required input is missing/broken (unknown type, missing
               field, or a bound column no longer exists).
    warnings = the combination can't run but the choice is preserved (unmet
               column-count requirement, or an algorithm↔output incompatibility).
    """
    errors: List[ValidationIssue] = []
    warnings: List[ValidationIssue] = []

    algo_type = algorithm.get("algorithmType") if isinstance(algorithm, dict) else None
    out_type = output.get("outputType") if isinstance(output, dict) else None

    # Algorithm config (errors). An algorithm is required: a statistics stage
    # with no method — or no statistics stage at all — is not a complete recipe,
    # and the executor would otherwise run the empty stage as the default
    # technique and fail on its missing fields.
    if algo_type:
        for e in validate_algorithm_config(algo_type, algorithm or {}):
            errors.append(_to_issue(e, source="algorithm", field_name=e.params.get("field")))
    else:
        errors.append(_to_issue(
            ValidationError(key=recipes_validation_algorithm_required),
            source="algorithm",
        ))

    # Output config (errors)
    if out_type:
        for e in validate_output_config(out_type, output or {}):
            errors.append(_to_issue(e, source="output", field_name=e.params.get("field")))

    # Algorithm ↔ output compatibility (warnings)
    for e in validate_algorithm_output_compatibility(algo_type, out_type):
        warnings.append(_to_issue(e, source="compatibility"))

    if columns:
        stage_configs: List[Dict] = []
        if isinstance(algorithm, dict):
            stage_configs.append({"type": "statistics", "config": algorithm})
        if isinstance(output, dict):
            stage_configs.append({"type": "visualisation", "config": output})

        # Bound columns no longer in the dataset (errors)
        for e in validate_column_references(columns, stage_configs):
            errors.append(_to_issue(e, source="dataset"))

        # Bound columns of the wrong type (errors)
        for e in validate_column_types(columns, stage_configs):
            errors.append(_to_issue(e, source="dataset", field_name=e.params.get("field")))

        # Column-count requirements unmet (warnings)
        for e in validate_column_requirements(columns, algo_type, out_type):
            warnings.append(_to_issue(e, source="dataset"))

    return {"errors": errors, "warnings": warnings}


# ============================================================
# Scoreboard — the deterministic "what's next" view
# ============================================================

def compute_scoreboard(
    stages: Optional[List[Dict[str, Any]]],
    columns: Optional[List[ColumnInfo]] = None,
    name: Optional[str] = None,
) -> Dict[str, Any]:
    """Compute the recipe-construction scoreboard: a deterministic view over a
    recipe draft that says what is decided (crystallised), what is still to be
    decided (pending), and whether it is complete.

    Decisions can be collected in any order, like the manual editor — pick a
    chart before the algorithm and the scoreboard constrains what is compatible
    rather than refusing. ``pending`` is therefore a *set* of undecided pieces
    (each with its valid choices), not an ordered "next". ``name`` is the recipe
    name (the user's goal doubles as it); when absent, the name is itself a
    pending piece.

    Returns ``{"crystallised", "pending", "complete", "errors", "warnings"}``:

    - ``crystallised`` — the decided pieces, each carrying its value(s) and a
      ``valid`` flag (decided and structurally complete).
    - ``pending`` — the undecided pieces, each ``{"piece", "what", "choices"}``.
    - ``complete`` — True when there are no pending pieces and no errors.
    - ``errors`` / ``warnings`` — the ``ValidationIssue`` dicts from
      ``validate_recipe`` (errors block; warnings do not).
    """
    dataset_id: Optional[str] = None
    transform_ids: List[str] = []
    algorithm: Optional[Dict[str, Any]] = None
    output: Optional[Dict[str, Any]] = None
    for stage in stages or []:
        stage_type = stage.get("type")
        config = stage.get("config") or {}
        if stage_type == "data_selection":
            dataset_id = config.get("datasetId")
            transform_ids = config.get("transformIds") or []
        elif stage_type == "statistics":
            algorithm = config
        elif stage_type == "visualisation":
            output = config

    algo_type = algorithm.get("algorithmType") if isinstance(algorithm, dict) else None
    out_type = output.get("outputType") if isinstance(output, dict) else None
    algo_inner = (algorithm.get("config") or {}) if isinstance(algorithm, dict) else {}
    out_inner = (output.get("config") or {}) if isinstance(output, dict) else {}

    adef = ALGORITHM_DEFS.get(algo_type) if algo_type else None
    odef = OUTPUT_DEFS.get(out_type) if out_type else None
    # "The technique cannot display this output" is a claim only a chosen technique
    # can make. With none chosen, compatibility is *unknown*, not false — the draft
    # is built in any order, so an output picked before its technique is decided
    # and not yet judged. Reading it as incompatible put the output in pending with
    # a sentence about a technique that does not exist.
    out_rejected = (
        adef is not None
        and odef is not None
        and out_type != "none"
        and out_type not in adef.compatible_outputs
    )
    out_compatible = odef is not None and not out_rejected
    missing_algo = [f for f in adef.fields if not algo_inner.get(f)] if adef else []
    missing_out = [f for f in odef.fields if not out_inner.get(f)] if odef else []

    result = validate_recipe(None, columns, algorithm, output)
    errors = [asdict(i) for i in result["errors"]]
    warnings = [asdict(i) for i in result["warnings"]]

    # --- crystallised: the decided pieces, in stage order ---
    # "Decided" means decided *and* valid *and* needing nothing more (§3.3). A choice
    # the validator rejects — an unknown technique, an unknown output, an output its
    # technique cannot display — leaves this list and appears only in pending, with
    # the sentence that repairs it; `errors` says which choice was rejected. The
    # draft still holds what was chosen: the state is not lost, it is not counted as
    # decided. Keeping it here with `valid: False` made `len(crystallised)` overstate
    # the progress, and put one piece in two lists at once.
    #
    # The FIELD pieces follow their parent: a field piece exists only once its parent
    # is settled, and it is crystallised only once its own fields are complete.
    # Otherwise `technique_fields` sat in both lists on a technique with empty
    # fields, and the two consumers of this list — the progress label and
    # `_completion_confidence` — counted it differently: the label counted every
    # entry, the confidence counted only `valid` ones. One list, two denominators.
    # Because every entry here is now decided and complete, no piece carries a
    # `valid` flag: a field that is always true is a second way to count.
    crystallised: List[Dict[str, Any]] = []
    if dataset_id:
        crystallised.append({
            "piece": "dataset",
            "datasetId": dataset_id,
            "transformIds": transform_ids,
        })
    if algo_type and adef is not None:
        crystallised.append({
            "piece": "technique",
            "algorithmType": algo_type,
        })
        if not missing_algo:
            crystallised.append({
                "piece": "technique_fields",
                "fields": algo_inner,
            })
    if out_type and out_compatible:
        crystallised.append({
            "piece": "output",
            "outputType": out_type,
        })
        if odef is not None and not missing_out:
            crystallised.append({
                "piece": "output_fields",
                "fields": out_inner,
            })
    if name:
        crystallised.append({"piece": "name", "name": name})

    # --- pending: the undecided pieces, in any order ---
    cols = columns or []
    algo_choices = get_available_algorithms(cols)
    out_choices = offered_outputs(cols, algo_type)

    pending: List[Dict[str, Any]] = []
    if not dataset_id:
        pending.append({"piece": "dataset", "surface": SURFACE_POINT, "what": _key("recipes.scoreboard.dataset.what"), "choices": []})
    if algo_type is None:
        pending.append({
            "piece": "technique",
            "surface": SURFACE_ASK,
            "what": _key("recipes.scoreboard.technique.what"),
            "choices": algo_choices,
        })
    elif adef is None:
        pending.append({
            "piece": "technique",
            "surface": SURFACE_ASK,
            "what": _key("recipes.scoreboard.technique_unknown.what"),
            "choices": list(ALGORITHM_DEFS.keys()),
        })
    elif missing_algo:
        pending.append({
            "piece": "technique_fields",
            "surface": SURFACE_ASK,
            "what": _key("recipes.scoreboard.technique_fields.what"),
            "choices": missing_algo,
        })
    if out_type is None:
        pending.append({
            "piece": "output",
            "surface": SURFACE_ASK,
            "what": _key("recipes.scoreboard.output.what"),
            "choices": out_choices,
        })
    elif odef is None:
        pending.append({
            "piece": "output",
            "surface": SURFACE_ASK,
            "what": _key("recipes.scoreboard.output_unknown.what"),
            "choices": out_choices,
        })
    elif out_rejected:
        pending.append({
            "piece": "output",
            "surface": SURFACE_ASK,
            "what": _key("recipes.scoreboard.output_incompatible.what"),
            "choices": out_choices,
        })
    elif missing_out:
        pending.append({
            "piece": "output_fields",
            "surface": SURFACE_ASK,
            "what": _key("recipes.scoreboard.output_fields.what"),
            "choices": missing_out,
        })
    if not name:
        pending.append({"piece": "name", "surface": SURFACE_INVITE, "what": _key("recipes.scoreboard.name.what"), "choices": []})

    # --- blocked: pieces that cannot be decided yet, present rather than absent ---
    #
    # The two field pieces do not exist until their parent is chosen, and until Item
    # 16 they were simply omitted — so an empty draft reported four pieces while the
    # denominator said six, and a reader could reasonably ask which was wrong. Now
    # the six are always accounted for: decided, pending, or blocked.
    #
    # "Blocked" means *cannot be decided yet* — never asked about, with what would
    # unblock it. It is not the other candidate meaning, "a piece whose choice set is
    # empty": that state is a decision already made and rejected, which §3.3 reports
    # in `errors` and asks again in `pending`. Two states for one condition is the
    # defect Items 13 and 15 removed, so the two meanings stay apart.
    #
    # `what` is the piece's own question and `unblocked_by` names the parent's, so a
    # renderer can say "requires columns — waiting on: choose an analysis method"
    # without composing a sentence from piece names. Both are keys, not sentences:
    # the scoreboard is pure, and the boundary resolves them.
    # Derived as a partition rather than written as a second set of conditions:
    # every declared piece is in exactly one of the three lists. Writing the blocked
    # cases by hand missed one — a *rejected* output leaves `output_fields` settled
    # by neither list, because its parent is neither unchosen nor acceptable — so the
    # six were accounted for by four conditions that had to agree, which is the same
    # shape as the two-counts defect Items 13 to 15 removed.
    #
    # Only the two field pieces can be blocked: their parent names what unblocks
    # them. An unconditional piece missing from both lists is a builder defect, and
    # the assertion below makes it loud rather than silent.
    declared = {p["piece"] for p in crystallised} | {p["piece"] for p in pending}
    blocked: List[Dict[str, Any]] = []
    for piece in RECIPE_PIECES:
        if piece in declared:
            continue
        parent = CONDITIONAL_PARENT.get(piece)
        assert parent is not None, f"{piece} is in neither list and has no parent to unblock it"
        blocked.append({
            "piece": piece,
            "surface": PIECE_SURFACE[piece],
            "what": _key(f"recipes.scoreboard.{piece}.what"),
            "blocked_by": parent,
            "unblocked_by": _key(f"recipes.scoreboard.{parent}.what"),
        })

    # `complete` needs no blocked term: a blocked piece is only ever produced by an
    # unchosen parent, and that parent is itself pending, so this is already False.
    complete = not pending and not errors

    return {
        "crystallised": crystallised,
        "pending": pending,
        "blocked": blocked,
        "complete": complete,
        "errors": errors,
        "warnings": warnings,
        # The denominator a progress label needs, travelling with the answer so no
        # caller types a number. A caller counting what is visible would say four on
        # an empty draft and six on a complete one — the same job, two totals.
        "total": len(RECIPE_PIECES),
    }


# ============================================================
# Async translation formatter
# ============================================================

async def format_recipe_issues(
    issues: List[ValidationIssue],
    db_pool,
    language: str,
) -> str:
    """Translate ValidationIssues into a multi-line display string.

    Nested ``{key, fallback}`` params are resolved via t(), and the
    ``columns`` param is rendered as a translated ``"name (type), …"`` list
    before substitution.

    The columns arrive as dicts in either spelling — ``isNumeric`` from the
    issue's own projection, ``is_numeric`` from any caller that passes a schema
    payload — and are normalised through ``to_column_info`` rather than having
    their flags read off the dict here. Reading ``c.get("isNumeric")`` inline
    meant a snake_case payload rendered every column as ``?``: the column was
    known and its type was not, which reads as a defect in the data rather than
    in the formatter.
    """
    if not issues:
        return ""

    from src.utils.translation import t as translate

    lines = []
    for i, issue in enumerate(issues, 1):
        params: Dict[str, Any] = {}
        for k, v in issue.params.items():
            if isinstance(v, dict) and "key" in v and "fallback" in v:
                params[k] = await translate(
                    db_pool, language, TranslationKey(v["key"], v["fallback"])
                )
            elif k == "columns" and isinstance(v, list):
                cat_label = await translate(db_pool, language, recipes_column_type_categorical)
                num_label = await translate(db_pool, language, recipes_column_type_numeric)
                cols = to_column_info(v)
                items = []
                for c in cols[:12]:
                    t = num_label if c.is_numeric else (cat_label if c.is_categorical else "?")
                    items.append(f"{c.name} ({t})")
                suffix = "…" if len(v) > 12 else ""
                params[k] = ", ".join(items) + suffix if items else "—"
            else:
                params[k] = v

        msg = await translate(
            db_pool, language, TranslationKey(issue.key, issue.fallback), **params
        )
        source_prefix = f"[{issue.source}] " if issue.source else ""
        lines.append(f"{i}. {source_prefix}{msg}")

    return "\n".join(lines)
