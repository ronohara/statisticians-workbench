// lib/virtual-joins.ts
// ============================================================
// JOIN ROWS — the shape a virtual dataset's joins have, and the two questions
// the chat asks about a set of them: is this pair already here, and which
// sources are still on their own.
//
// Extracted because the join block in the chat needs both, and the manual
// editor at `/datasets/virtual/manual` has had its own copies since it was
// built. Two implementations of "are these the same pair" is how the two
// surfaces would drift apart on the one rule they must share: a pair written
// `a = b` is the same join as `b = a`.
//
// Deliberately no fetching, no React, no translations. This is arithmetic over
// a plain array, so it can be reasoned about — and tested — on its own.
// ============================================================

/**
 * One join, as the draft stores it.
 *
 * `type` is written lower-case by the agent's tool (`set_join` defaults to
 * `inner`) and upper-case by the manual editor's picker (`INNER`). The SQL
 * builder upper-cases whatever it is given, so the two spellings are
 * equivalent on the wire; they are kept as typed here so a round-trip through
 * the editor does not silently rewrite the draft's own vocabulary.
 *
 * `reason` is why the pair was chosen, and it is optional: the model may state
 * only the pair. Absent means the row renders without a reason, never with an
 * invented one.
 */
export type JoinRow = {
    left: string;
    leftCol: string;
    right: string;
    rightCol: string;
    type: string;
    reason?: string;
};

/** The four join types the SQL builder understands. */
export const JOIN_TYPES = ["INNER", "LEFT", "RIGHT", "FULL"] as const;

/** A join with all five parts present, so it can be sent or executed. */
export const isCompleteJoin = (join: JoinRow): boolean =>
    Boolean(join.left && join.right && join.leftCol && join.rightCol);

/**
 * True when two rows describe the same join, whichever way round it was written.
 *
 * The pair is the identity: a row whose type moved from INNER to LEFT is the
 * same join changed, not one join removed and another added. That is what makes
 * an edit readable as a diff rather than as a wholesale replacement.
 */
export const samePair = (row: { left: string; right: string }, left: string, right: string): boolean =>
    (row.left === left && row.right === right) || (row.left === right && row.right === left);

/** A row's join type in one casing, for comparing two spellings of the same type. */
export const normaliseJoinType = (type: string | undefined): string =>
    (type || "inner").toUpperCase();

/**
 * True when two join sets are the same, row for row and field for field.
 *
 * Used for one decision only: whether the block's rows still match the draft.
 * If they do, the button says Done and posts nothing — a confirm that changes
 * nothing should not cost a model turn.
 *
 * Order is not part of the comparison. A user who reorders rows has not changed
 * the dataset, and treating that as a change would make the button lie.
 */
export const joinsEqual = (a: readonly JoinRow[], b: readonly JoinRow[]): boolean => {
    if (a.length !== b.length) return false;

    const key = (join: JoinRow): string => {
        const pair = [join.left, join.right].sort().join("\u0000");
        return `${pair}\u0001${join.leftCol}\u0001${join.rightCol}\u0001${normaliseJoinType(join.type)}`;
    };

    const left = a.map(key).sort();
    const right = b.map(key).sort();
    return left.every((entry, index) => entry === right[index]);
};

/**
 * The aliases no complete join reaches.
 *
 * The join graph must connect every source; the builder attaches from the first
 * source outwards, so a source with no edge is one that will not appear in the
 * result at all. That is worth saying plainly under the rows — "not joined:
 * staffs" is the sentence that explains why the result is short of a table.
 *
 * A half-written row does not count as an edge: a pair chosen without columns
 * relates nothing yet.
 */
export const unattachedAliases = (aliases: readonly string[], joins: readonly JoinRow[]): string[] => {
    const attached = new Set<string>();
    for (const join of joins) {
        if (isCompleteJoin(join)) {
            attached.add(join.left);
            attached.add(join.right);
        }
    }
    return aliases.filter((alias) => !attached.has(alias));
};

/**
 * A join read as a sentence: `orders.order_id = order_items.order_id, inner`.
 *
 * The reason is deliberately not appended here. It is rendered on the same line
 * but as its own quiet element, and folding it into the text would make it
 * indistinguishable from the join itself when the line wraps.
 */
export const joinSentence = (join: JoinRow): string =>
    `${join.left}.${join.leftCol} = ${join.right}.${join.rightCol}, ${(join.type || "inner").toLowerCase()}`;
