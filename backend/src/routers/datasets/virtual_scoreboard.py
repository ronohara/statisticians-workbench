# src/routers/datasets/virtual_scoreboard.py
# ============================================================
# VIRTUAL DATASET SCOREBOARD
# The pure computation behind the v2 virtual-dataset concierge
# (workbench-AI-virtual-datasets-v2-design.html §4-§5).
# ============================================================
"""What is decided, what is pending, what is blocked, what is broken.

The ladder asked the model to remember which stage it was on. This asks the
draft instead, and the answer is computed rather than stored: the same draft,
schemas and validation snapshot always produce the same scoreboard, so a turn
cannot stall in a state that no longer exists.

**Pure by construction.** Nothing here opens a connection, reads a row or
writes anything. Every input arrives as an argument, which is what makes the
whole thing testable without a database and comparable between the two
backends for the same inputs (the parity family in Item 3 of the plan).

**`language` is carried, not read.** The scoreboard emits translation *keys*
for each piece's question and its unblocking condition, never the rendered
text, because a pure function cannot query the `Translation` table. The two
renderers — the prompt builder and the page — own the language. The field is
in the input type so that the contract stays one object as the design
specifies (§5), not because this function localises anything.

Four states, and the third is the one that earns the design its keep:

    crystallised  decided and usable — report it, do not re-litigate it
    pending       decidable now, not yet decided — may be asked about
    blocked       cannot be decided yet — never asked about, say what unblocks it
    error         not a list here: a decided piece carries ``valid: false``
                  and the validation snapshot's messages are reported verbatim

An *error* has two sources and they are deliberately kept apart. A structural
fault the draft itself shows — a join missing a side, an output column with no
name — is a ``valid: false`` on the piece that holds it. A fault only the
validating function can see — a table that does not resolve, a column that is
not there — arrives in the snapshot and is reported unaltered, because the
scoreboard is not a second validator (§5, third rule). ``None`` means the
validation was not run, and a scoreboard computed from ``None`` reports no
errors rather than claiming there are none.
"""

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Sequence, Tuple

from .translations import DATASETS

# The three states a source's columns can be in. A missing alias and an
# introspected-but-empty table are different facts, and without the third state
# they would both arrive as "no columns" (design §5.2, cost 6).
SCHEMA_KNOWN = "known"
SCHEMA_FAILED = "failed"
SCHEMA_NOT_LOOKED_AT = "not_looked_at"

# How many chip candidates one question may offer (design §6.3).
#
# Six is the small end of the scannable range, which suits a chat bubble's width.
# **Deliberately not Miller's 7±2**: that measures short-term recall — how many
# items a person can hold once they are gone — and a chip set is a recognition
# task, with every option on screen. Applying a recall limit to a visible list is
# a category error, and the figure is contested anyway (Cowan 2001 puts capacity
# nearer four). What does bear on the number is scannability: a set should be
# taken in without scrolling and without grouping, which lands around seven to
# ten. Hick's law (decision time grows with the logarithm of the choices) is why
# a slightly longer list is not the disaster it feels like, and chunking is why a
# grouped list is not a long list of choices at all — under headings the count
# that matters is per group. Choice overload is deliberately not cited: the
# meta-analysis across that literature (Scheibehenne, Greifeneder & Todd, 2010)
# found a mean effect near zero.
#
# So the cap is doing *filtering* work, not memory work, and what matters more
# than the number is the query that produced the candidates. It is a named
# constant rather than a literal at each site — one home, changed once when the
# interface has been tried with real users.
#
# It is NOT the join-suggestion cap. That one is three, for a different reason
# (a ranked shortlist of pairs, where a fourth alternative adds a decision rather
# than an option), and lives in `join_suggestions.py`. The two are never
# collapsed into one number.
CHIP_SET_LIMIT = 6

# Piece identifiers. They are the vocabulary the prompt, the page and the
# tests share, so they are spelled once here.
PIECE_GOAL = "goal"
PIECE_SOURCES = "sources"
PIECE_COLUMNS = "columns"
PIECE_JOINS = "joins"
PIECE_OUTPUT_COLUMNS = "output_columns"
PIECE_NAME = "name"
PIECE_STORAGE = "storage"

# How the assistant may raise a pending piece (design §4.0), defined by who acts.
#
# The state says a piece *may* be raised; `surface` says *how*. They are separate
# because `pending` was carrying both meanings: `sources` is pending the moment a
# session exists, and the design also says it is never asked about. Both are true
# of different acts, and this vocabulary is what separates them.
SURFACE_ASK = "ask"        # the user, from a closed set of chips
SURFACE_POINT = "point"    # the user, by ticking in the page's tree
SURFACE_READ = "read"      # the assistant, with a tool — nobody is asked anything
SURFACE_OFFER = "offer"    # the user, accepting or ignoring a computed candidate
SURFACE_INVITE = "invite"  # the user, in their own words

# The pieces a save needs. Joins are conditional on there being two or more
# sources — the manual editor's `aliases > 1 && joinEdges === 0` rule, which
# design §4.4 takes as the definition of required rather than inventing one.
# storage joined this set on 2026-11-06: the concierge must get the answer,
# because a session that completes without it saves with the column default —
# the silent choice this whole change removes. It is pending only while the
# draft holds no answer, so a dataset is asked once.
_REQUIRED = (PIECE_OUTPUT_COLUMNS, PIECE_NAME, PIECE_STORAGE)


@dataclass(frozen=True)
class SchemaState:
    """What is known about one source's columns.

    Three states rather than a list, because "we have not read this table" and
    "this table has no columns" are different answers and a caller that cannot
    tell them apart will ask a question it cannot get an answer to.
    """

    state: str = SCHEMA_NOT_LOOKED_AT
    columns: Tuple[str, ...] = ()

    @classmethod
    def known(cls, columns: Sequence[str]) -> "SchemaState":
        """The columns were read. An empty sequence is legitimate and means
        the table exists but offers nothing to choose."""
        return cls(SCHEMA_KNOWN, tuple(columns))

    @classmethod
    def failed(cls) -> "SchemaState":
        """The read was attempted and did not succeed. Retrying is a caller's
        decision; the scoreboard only reports that the piece cannot be decided."""
        return cls(SCHEMA_FAILED)

    @classmethod
    def not_looked_at(cls) -> "SchemaState":
        """Nothing has read this source yet. This is the state every alias
        starts in, and the one that makes a fresh source pending rather than
        blocked."""
        return cls(SCHEMA_NOT_LOOKED_AT)


@dataclass(frozen=True)
class ValidationSnapshot:
    """The messages `validate_virtual_dataset_definition` returned, verbatim.

    Carrying rendered messages rather than codes is deliberate: the validator
    already translates them into the caller's language and already decides what
    counts as a fault. Re-deriving either here would be the second validator
    §5 forbids.
    """

    errors: Tuple[str, ...] = ()


@dataclass(frozen=True)
class ScoreboardInputs:
    """Everything the computation reads. Nothing is gathered here.

    ``schemas`` is keyed by source alias. An alias with no entry is treated as
    ``not_looked_at`` — the state a source starts in — never as "known and
    empty", because the difference is exactly what the third state exists for.
    """

    draft: Dict[str, Any]
    schemas: Dict[str, SchemaState]
    validation: Optional[ValidationSnapshot] = None
    language: str = "en"


def _key(name: str) -> str:
    """The declared translation key, by its canonical name.

    The declaration is the single source: this returns the key string the two
    renderers resolve, and a mistyped name fails at import rather than shipping
    a key nothing declares.
    """
    return DATASETS[name].key


def _pending(piece: str, surface: str, what: str,
             source: Optional[str] = None, choices: Optional[Sequence[str]] = None) -> Dict[str, Any]:
    """Build one ``pending`` entry.

    ``surface`` is a required positional argument, not a defaulted one, so an
    entry built without it is a ``TypeError`` at construction — the guarantee is
    in the signature rather than in a test that has to remember to look. That is
    what §4.0 asks for: a new piece cannot become askable by silence.
    """
    if surface not in _SURFACES:
        raise ValueError(f"unknown surface {surface!r}; expected one of {sorted(_SURFACES)}")
    entry: Dict[str, Any] = {"piece": piece, "surface": surface, "what": what,
                             "choices": list(choices or ())}
    if source is not None:
        entry["source"] = source
    return entry


_SURFACES = frozenset(
    {SURFACE_ASK, SURFACE_POINT, SURFACE_READ, SURFACE_OFFER, SURFACE_INVITE}
)


def _text(value: Any) -> str:
    """A JSON value as a trimmed string. Anything that is not a string is empty.

    Mirrors Go's ``trimmed``: the two backends must answer the same draft the
    same way, and a number where a name was expected is *absent*, not "5".
    """
    return value.strip() if isinstance(value, str) else ""


def _objects(value: Any) -> List[Dict[str, Any]]:
    """A JSON array of objects, with anything else dropped.

    A missing key is an empty list, which is what an absent piece is. A
    non-object entry is dropped rather than raising: the scoreboard then reports
    the piece as undecided, which is true, instead of failing a whole turn on one
    malformed draft entry. The Go mirror does the same, so both backends answer
    the same input identically.
    """
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, dict)]


def _aliases(draft: Dict[str, Any]) -> List[str]:
    """The sources the draft has, in the order they first appear.

    Declared sources come first, then any alias only a ticked column names.
    That second half is the derivation design §4.6 describes: a source exists
    because a column of it was chosen, so a tick arrives before its source row
    does and the alias still counts.
    """
    seen: set = set()
    aliases: List[str] = []
    for source in _objects(draft.get("sources")):
        alias = _text(source.get("alias"))
        if alias and alias not in seen:
            seen.add(alias)
            aliases.append(alias)
    for column in _objects(draft.get("columns")):
        alias = _text(column.get("source"))
        if alias and alias not in seen:
            seen.add(alias)
            aliases.append(alias)
    return aliases


def _column_state(schema: SchemaState) -> str:
    """One of ``known``, ``empty``, ``failed`` or ``unread``.

    An unrecognised state string is treated as ``unread`` rather than as
    ``known``: the failure mode of the wrong direction is a scoreboard claiming
    columns it has never seen.
    """
    if schema.state == SCHEMA_KNOWN:
        return "known" if schema.columns else "empty"
    if schema.state == SCHEMA_FAILED:
        return "failed"
    return "unread"


def _join_is_complete(join: Dict[str, Any], aliases: List[str]) -> bool:
    """Whether a join names two known sources and a column on each side.

    This is a structural check of the draft, not of the database: it does not
    claim the columns exist, only that the join has been written. Column
    existence is the validator's answer and arrives in the snapshot.
    """
    return (
        bool(_text(join.get("left")))
        and bool(_text(join.get("leftCol")))
        and bool(_text(join.get("right")))
        and bool(_text(join.get("rightCol")))
        and _text(join.get("left")) in aliases
        and _text(join.get("right")) in aliases
    )


def compute_virtual_scoreboard(inp: ScoreboardInputs) -> Dict[str, Any]:
    """Compute the scoreboard for one draft.

    Returns ``{"crystallised", "pending", "blocked", "errors", "complete"}``:

    - ``crystallised`` — the decided pieces, each ``{"piece", "value", "valid"}``
      and, for a source's columns, its ``"source"`` alias.
    - ``pending`` — the undecided pieces, each
      ``{"piece", "what", "choices"}``; ``what`` is a translation key.
    - ``blocked`` — the pieces that cannot be decided yet, each
      ``{"piece", "what", "needs"}``; both are translation keys.
    - ``errors`` — the validation snapshot's messages, unaltered and empty when
      no validation was run.
    - ``complete`` — no required piece is pending or blocked, every crystallised
      piece is valid, and the snapshot reported no errors.
    """
    draft = inp.draft or {}
    schemas = inp.schemas or {}
    aliases = _aliases(draft)

    crystallised: List[Dict[str, Any]] = []
    pending: List[Dict[str, Any]] = []
    blocked: List[Dict[str, Any]] = []

    # --- goal: recorded whenever offered, never asked for, never blocking ---
    goal = _text(draft.get("goal"))
    if goal:
        crystallised.append({"piece": PIECE_GOAL, "value": goal, "valid": True})

    # --- sources: derived from the ticked columns (§4.6), reported not asked ---
    if aliases:
        crystallised.append(
            {"piece": PIECE_SOURCES, "value": list(aliases), "valid": True}
        )
    else:
        pending.append(
            _pending(PIECE_SOURCES, SURFACE_POINT, _key("virtual.scoreboard.sources.what"))
        )

    # --- the columns of each source: one piece per alias ---
    columns_ready: Dict[str, bool] = {}
    for alias in aliases:
        schema = schemas.get(alias) or SchemaState()
        state = _column_state(schema)
        columns_ready[alias] = state == "known"
        if state == "known":
            crystallised.append(
                {
                    "piece": PIECE_COLUMNS,
                    "source": alias,
                    "value": list(schema.columns),
                    "valid": True,
                }
            )
        elif state == "unread":
            pending.append(
                _pending(PIECE_COLUMNS, SURFACE_READ,
                         _key("virtual.scoreboard.columns.what"), source=alias)
            )
        elif state == "failed":
            blocked.append(
                {
                    "piece": PIECE_COLUMNS,
                    "source": alias,
                    "what": _key("virtual.scoreboard.columns.what"),
                    "needs": _key("virtual.scoreboard.columns.needs_failed"),
                }
            )
        else:  # known, and empty
            blocked.append(
                {
                    "piece": PIECE_COLUMNS,
                    "source": alias,
                    "what": _key("virtual.scoreboard.columns.what"),
                    "needs": _key("virtual.scoreboard.columns.needs_empty"),
                }
            )

    # --- joins: absent until there are two sources (design §4.5) ---
    joins = _objects(draft.get("joins"))
    joins_required = len(aliases) >= 2
    if joins_required:
        if joins:
            crystallised.append(
                {
                    "piece": PIECE_JOINS,
                    "value": list(joins),
                    "valid": all(_join_is_complete(j, aliases) for j in joins),
                }
            )
        elif all(columns_ready.values()):
            pending.append(
                _pending(PIECE_JOINS, SURFACE_OFFER, _key("virtual.scoreboard.joins.what"))
            )
        else:
            blocked.append(
                {
                    "piece": PIECE_JOINS,
                    "what": _key("virtual.scoreboard.joins.what"),
                    "needs": _key("virtual.scoreboard.joins.needs"),
                }
            )

    # --- output columns: required, and blocked until one source is readable ---
    outputs = _objects(draft.get("columns"))
    if outputs:
        crystallised.append(
            {
                "piece": PIECE_OUTPUT_COLUMNS,
                "value": list(outputs),
                "valid": all(
                    bool(_text(c.get("column"))) and _text(c.get("source")) in aliases
                    for c in outputs
                ),
            }
        )
    elif any(columns_ready.values()):
        pending.append(
            _pending(PIECE_OUTPUT_COLUMNS, SURFACE_POINT,
                     _key("virtual.scoreboard.output_columns.what"))
        )
    else:
        blocked.append(
            {
                "piece": PIECE_OUTPUT_COLUMNS,
                "what": _key("virtual.scoreboard.output_columns.what"),
                "needs": _key("virtual.scoreboard.output_columns.needs"),
            }
        )

    # --- name: required at save, and the one thing only the user can give ---
    name = _text(draft.get("name"))
    if name:
        crystallised.append({"piece": PIECE_NAME, "value": name, "valid": True})
    else:
        pending.append(
            _pending(PIECE_NAME, SURFACE_INVITE, _key("virtual.scoreboard.name.what"))
        )

    # --- storage: asked once, and required (§4.2, revised 2026-11-06) ---
    #
    # It used to be reported crystallised with the default, on the reasoning that
    # a default settles it. Measured 2026-11-06: the concierge therefore never
    # asked, and a dataset's only chance to be materialised was missed —
    # `materialized` was written false by the column default and never chosen.
    #
    # Pending only while the draft holds no `materialized` key, so it is asked
    # once. `in` rather than a truthiness test: a draft that answered "live" holds
    # `materialized: False`, which is an answer, not an absence.
    if "materialized" in draft:
        crystallised.append(
            {
                "piece": PIECE_STORAGE,
                "value": "materialized" if draft.get("materialized") is True else "live",
                "valid": True,
            }
        )
    else:
        # Choices, so the question arrives as two chips rather than prose. This is
        # the only `ask` piece, and without a closed set `suggest_choices` had
        # nothing to offer — the model could only describe the options.
        pending.append(
            _pending(
                PIECE_STORAGE, SURFACE_ASK, _key("virtual.scoreboard.storage.what"),
                choices=[
                    {"key": "live", "label": _key("virtual.scoreboard.storage.live")},
                    {"key": "materialized", "label": _key("virtual.scoreboard.storage.table")},
                ],
            )
        )

    errors = list(inp.validation.errors) if inp.validation is not None else []

    required = set(_REQUIRED) | ({PIECE_JOINS} if joins_required else set())
    complete = (
        not errors
        and all(piece["valid"] for piece in crystallised)
        and not [p for p in pending if p["piece"] in required]
        and not [b for b in blocked if b["piece"] in required]
    )

    return {
        "crystallised": crystallised,
        "pending": pending,
        "blocked": blocked,
        "errors": errors,
        "complete": complete,
    }


def decided_counts(scoreboard: Dict[str, Any]) -> Dict[str, int]:
    """How many pieces are decided, out of how many exist.

    **Read from the scoreboard's own sections, never tallied again.** The
    progress strip, the session list and the open chat all show this number, and
    the scoreboard is what the assistant is working from — so deriving it here
    means the three surfaces cannot disagree with each other or with the
    assistant. A second tally computed elsewhere would be a second answer.

    A piece is one entry in `crystallised`, `pending` or `blocked`; `errors`
    describes pieces that already exist rather than adding any, so it is not
    counted. `blocked` counts towards the total because a piece the draft needs
    and cannot yet have is still part of the job.
    """
    decided = len(scoreboard.get("crystallised") or [])
    pending = len(scoreboard.get("pending") or [])
    blocked = len(scoreboard.get("blocked") or [])
    return {"decided": decided, "total": decided + pending + blocked}
