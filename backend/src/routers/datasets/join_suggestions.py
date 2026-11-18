# src/routers/datasets/join_suggestions.py
# ============================================================
# JOIN SUGGESTIONS — the manual editor's deterministic scorer,
# moved out of the page so both surfaces share it.
# ============================================================
"""Which pairs of sources look joinable, ranked — no model, no I/O.

This is the scorer that lived in the manual editor's render body
(`frontend/app/datasets/virtual/manual/page.tsx`), moved here unchanged in
behaviour so that the manual page, the concierge and the parity harness all
read one implementation. The rules are the page's, deliberately: the ranking
was tuned against real tables and re-deriving it would lose that.

**Pure.** Everything it reads arrives as an argument. It opens no connection
and reads no row — the columns come from the caller's cache, which is the
manual editor's own precedent (it reads a source's columns once, when the
source is picked). A consequence worth stating: a caller that has not read a
source's columns gets no column-matched suggestion for it, only a bare bridge,
which is exactly what the page does today.

**Offered, never applied.** The caller shows these; nothing here writes a
join. A wrong join produces a plausible-looking dataset, which is the worst
outcome for this tool — so the scorer proposes and a person decides.

The ranking, in the order it is applied:

    score 4  a column of one side is plain `id`, and the other side's column
             stems from this side's table name — the `<x>_id` -> `id` shape
    score 3  the two columns are named identically
    score 2  they share a stem (an `_id`/`id` suffix dropped, a plural `s`
             dropped)
    score 0  no column match, but the pair is a *bridge* (see below)

A **bridge** outranks every score. A pair with exactly one side already
attached would connect an orphan to the rest, and that is the one suggestion
that fixes a disconnected graph. When no column match exists for a bridge it is
still offered, with the columns left blank for the person to choose — naming
the pair is the hard part, and the two selects are not.

Ties keep insertion order, which is source order: the sort is stable, as the
page's `Array.prototype.sort` is.
"""

from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Optional, Sequence

from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials

from src.utils.translation import t

from .crud import get_current_language, get_user_id_from_token, security
from .translations import DATASETS

# How many join pairs to offer at once.
#
# Three, and for a different reason from the chip cap. A chip set answers a
# *choice* question and its cap is about scannability — how many options can be
# taken in at once. A join suggestion is a **ranked shortlist of pairs**, each
# carrying two column names and a bridge flag; a fourth alternative does not add
# an option to consider, it adds a decision about which pair to accept. So the
# limit is set by how many pairs a reader will actually weigh, not by how many
# fit on a screen.
#
# It is NOT `CHIP_SET_LIMIT` (six), which lives in `virtual_scoreboard.py`. The
# two numbers are never collapsed into one: different questions, different
# reasoning, and a later change to either should not move the other.
JOIN_SUGGESTION_LIMIT = 3


@dataclass(frozen=True)
class JoinSource:
    """One source, as the caller already knows it.

    ``name`` is the table name for a table source and the dataset's name for a
    dataset source — **never the display label**, which carries the connection
    name too ("bike store - sample · customers") and makes every comparison
    against it fail. That distinction is why the `<x>_id` -> `id` rule could
    never fire for the most common join shape before it was made explicit.
    """

    alias: str
    name: str
    columns: Sequence[str] = ()


@dataclass(frozen=True)
class JoinSuggestion:
    """One offered pair. ``columns_known`` is false for a bare bridge, where
    there is a pair but no column match — the caller renders those with two
    empty selects rather than hiding them."""

    left: str
    left_col: str
    right: str
    right_col: str
    score: int
    bridge: bool
    columns_known: bool
    columns_read: bool
    fills: bool


def _base(name: str) -> str:
    """A column name with any ``_id``/``id`` suffix dropped, non-alphanumerics
    stripped and lowercased. ``customer_id`` -> ``customer``.

    ASCII-only, deliberately: the page's rule is ``[^a-z0-9]``, and
    ``str.isalnum()`` would keep a Unicode letter the page drops. The two
    backends must answer the same name the same way.
    """
    text = name
    lowered = text.lower()
    if lowered.endswith("_id"):
        text = text[: -len("_id")]
    elif lowered.endswith("id"):
        text = text[: -len("id")]
    return "".join(
        ch for ch in text if ("a" <= ch.lower() <= "z") or ("0" <= ch <= "9")
    ).lower()


def _stem(name: str) -> str:
    """``_base`` with a trailing plural ``s`` dropped: ``customers`` and
    ``customer_id`` both become ``customer``."""
    text = _base(name)
    return text[:-1] if text.endswith("s") else text


def _complete_join(join: Dict[str, Any]) -> bool:
    """A join that actually connects two sources.

    A row whose columns are still empty connects nothing, so the pair stays
    suggestible — and testing every row instead of this was what used to
    silence the suggestion for exactly the pair that needed it.
    """
    return bool(
        join.get("left")
        and join.get("leftCol")
        and join.get("right")
        and join.get("rightCol")
    )


def _same_pair(join: Dict[str, Any], left: str, right: str) -> bool:
    """A pair is the same pair whichever way round it was written."""
    return (join.get("left") == left and join.get("right") == right) or (
        join.get("left") == right and join.get("right") == left
    )


def unattached_aliases(aliases: Sequence[str], joins: Sequence[Dict[str, Any]]) -> List[str]:
    """The aliases no complete join reaches from the first source.

    The first source is the seed, so a fully disconnected set leaves everything
    after the first unattached — the same rule the page's connectivity check
    uses, which is what makes a bridge the suggestion that reconnects the graph
    rather than merely tidying it.
    """
    if not aliases:
        return []
    edges = [join for join in joins if _complete_join(join)]
    attached = {aliases[0]}
    grew = True
    while grew:
        grew = False
        for join in edges:
            left, right = join.get("left"), join.get("right")
            if left in attached and right not in attached:
                attached.add(right)
                grew = True
            elif right in attached and left not in attached:
                attached.add(left)
                grew = True
    return [alias for alias in aliases if alias not in attached]


def _best_match(left: JoinSource, right: JoinSource) -> Optional[tuple]:
    """The highest-scoring column pair for these two sources, or None.

    Score 4 is checked on both sides: whichever table owns the plain `id`
    column, the other side's `<x>_id` names it.
    """
    left_stem_of_name = _stem(right.name)
    right_stem_of_name = _stem(left.name)
    best: Optional[tuple] = None
    for left_column in left.columns:
        for right_column in right.columns:
            score = 0
            if left_column == right_column:
                score = 3
            left_stem, right_stem = _stem(left_column), _stem(right_column)
            if left_stem and left_stem == right_stem:
                score = max(score, 2)
            if right_column.lower() == "id" and left_stem == left_stem_of_name:
                score = max(score, 4)
            if left_column.lower() == "id" and right_stem == right_stem_of_name:
                score = max(score, 4)
            if score > 0 and (best is None or score > best[0]):
                best = (score, left_column, right_column)
    return best


def compute_join_suggestions(
    sources: Sequence[JoinSource],
    joins: Iterable[Dict[str, Any]] = (),
    limit: int = JOIN_SUGGESTION_LIMIT,
) -> List[JoinSuggestion]:
    """The ranked pairs to offer, capped at ``limit``.

    ``limit`` is a parameter rather than a constant read inside, so a test can
    prove both backends honour it rather than a literal baked into each.
    """
    joins = list(joins)
    aliases = [source.alias for source in sources]
    orphans = set(unattached_aliases(aliases, joins))

    items: List[tuple] = []
    for i in range(len(sources)):
        for j in range(i + 1, len(sources)):
            left, right = sources[i], sources[j]
            if any(_complete_join(join) and _same_pair(join, left.alias, right.alias) for join in joins):
                continue
            pair_row_exists = any(_same_pair(join, left.alias, right.alias) for join in joins)

            is_bridge = (left.alias in orphans) != (right.alias in orphans)
            columns_read = bool(left.columns) and bool(right.columns)
            best = _best_match(left, right)

            if best is not None and best[0] >= 2:
                items.append(
                    JoinSuggestion(
                        left=left.alias,
                        left_col=best[1],
                        right=right.alias,
                        right_col=best[2],
                        score=best[0],
                        bridge=is_bridge,
                        columns_known=True,
                        columns_read=columns_read,
                        fills=pair_row_exists,
                    )
                )
            elif is_bridge and not pair_row_exists:
                # A bare bridge is worth offering only when no row names the
                # pair yet; accepting it would otherwise have nothing to fill.
                items.append(
                    JoinSuggestion(
                        left=left.alias,
                        left_col="",
                        right=right.alias,
                        right_col="",
                        score=0,
                        bridge=True,
                        columns_known=False,
                        columns_read=columns_read,
                        fills=False,
                    )
                )

    # Bridge first, then score. The sort is stable, so equal pairs keep source
    # order — the same order the page produced.
    items.sort(key=lambda item: (not item.bridge, -item.score))
    return items[:limit]


# ── the route ────────────────────────────────────────────────

# Its own router with the same prefix as `virtual.py`'s, so the endpoint sits
# beside the others at `/api/datasets/virtual/...` while the scorer stays a
# self-contained module. No database pool: nothing here reads a row.
router = APIRouter(prefix="/virtual", tags=["virtual-datasets"])


def _parse_sources(raw: Any) -> List[JoinSource]:
    """Build the scorer's inputs, or raise on a body the caller got wrong.

    Refused rather than repaired: a source with no alias or no name cannot be
    scored, and guessing which table was meant would produce a suggestion for a
    table the caller never chose.
    """
    if not isinstance(raw, list):
        raise ValueError("sources must be a list")
    sources: List[JoinSource] = []
    for entry in raw:
        if not isinstance(entry, dict):
            raise ValueError("each source must be an object")
        alias = entry.get("alias")
        name = entry.get("name")
        if not isinstance(alias, str) or not alias:
            raise ValueError("each source needs an alias")
        if not isinstance(name, str) or not name:
            raise ValueError("each source needs a name")
        columns = entry.get("columns") or []
        if not isinstance(columns, list) or not all(isinstance(c, str) for c in columns):
            raise ValueError("columns must be a list of strings")
        sources.append(JoinSource(alias=alias, name=name, columns=tuple(columns)))
    return sources


@router.post("/join-suggestions")
async def join_suggestions(
    body: dict,
    credentials: HTTPAuthorizationCredentials = Depends(security),
    language: str = Depends(get_current_language),
):
    """Offer ranked join pairs for the sources in the body.

    Computes over what the caller supplies and reads nothing: the columns are
    the caller's cache, which is the manual editor's own precedent. It answers
    suggestions, never a join — nothing is applied here.
    """
    # Authenticated like every other /virtual route. The pool is None on purpose:
    # this route touches no table, and passing one would suggest it does.
    await get_user_id_from_token(credentials)

    try:
        sources = _parse_sources(body.get("sources"))
    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=await t(None, language, DATASETS["virtual.join_suggestions.invalid_sources"], error=str(exc)),
        )

    joins = body.get("joins") or []
    if not isinstance(joins, list):
        raise HTTPException(
            status_code=400,
            detail=await t(None, language, DATASETS["virtual.join_suggestions.invalid_sources"], error="joins must be a list"),
        )

    suggestions = compute_join_suggestions(sources, [j for j in joins if isinstance(j, dict)])
    return {
        "suggestions": [
            {
                "left": s.left,
                "leftCol": s.left_col,
                "right": s.right,
                "rightCol": s.right_col,
                "score": s.score,
                "bridge": s.bridge,
                "columnsKnown": s.columns_known,
                "columnsRead": s.columns_read,
                "fills": s.fills,
            }
            for s in suggestions
        ],
        "limit": JOIN_SUGGESTION_LIMIT,
    }
