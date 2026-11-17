// components/chat/join-editor.tsx
// ============================================================
// THE JOIN BLOCK — format A: each join is a row, and each row is a sentence.
//
// The agent writes joins into the draft; this renders them as a block of
// editable rows under the message that produced them. Every field is a
// control, nothing is typed, and the reason sits at the end of the line where a
// reader needs it.
//
// **It is not an offer.** A chip renders while its piece is pending and
// disappears when the piece is settled. This renders *because* the piece is
// settled — the joins are already in the draft. So there is nothing to accept:
// the button re-states the set after an edit, and when nothing was edited it
// says Done and posts nothing. That is the difference between a question and a
// sentence, and it is why this is its own component rather than another
// `Suggestion` kind.
//
// **Adding is chat.** A seventh table is a conversation turn — the agent names
// the pair and the reason, the block grows. Removing is a click: deletion is a
// boolean act and adding is not, so the two do not need to be symmetric, and
// making a user type "don't join stores" to undo a wrong pair is exactly the
// friction this block exists to remove.
//
// The component is dumb: it owns no state. The rows live in the page, because
// the page is what knows the draft and what posts the edit.
// ============================================================

"use client";

import { X } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { JOIN_TYPES, isCompleteJoin, joinSentence, joinsEqual, normaliseJoinType, unattachedAliases } from "@/lib/virtual-joins";
import type { JoinRow } from "@/lib/virtual-joins";

export type JoinEditorTranslations = {
    /** A line above the rows, so the eye knows these are the joins being discussed. */
    heading: string;
    apply: string;
    done: string;
    hint: string;
    coverage: (connected: number, total: number) => string;
    unjoined: (tables: string) => string;
    unsaved: string;
    columnPlaceholder: string;
    typeLabel: string;
    remove: string;
};

export type JoinEditorProps = {
    /** The rows on screen — the page's state, edited here, posted by the page. */
    rows: JoinRow[];
    /** The draft's joins, so the button can tell an edit from a no-op. */
    confirmed: readonly JoinRow[];
    /** The draft's source aliases, in the order the tree holds them. */
    aliases: readonly string[];
    /** Column names per alias, from the scoreboard. Empty means not read yet. */
    columnsByAlias: Record<string, readonly string[]>;
    onRowChange: (index: number, patch: Partial<JoinRow>) => void;
    onRemoveRow: (index: number) => void;
    /** Posted only when the rows differ from the draft. */
    onApply: () => void;
    /** Closes the block without a request — what the button does when unchanged. */
    onDone: () => void;
    disabled?: boolean;
    t: JoinEditorTranslations;
};

/** A column dropdown. An unread schema leaves it empty rather than inventing names. */
function ColumnSelect({
    value,
    columns,
    placeholder,
    onChange,
    disabled,
}: {
    value: string;
    columns: readonly string[];
    placeholder: string;
    onChange: (next: string) => void;
    disabled?: boolean;
}) {
    return (
        <Select value={value} onValueChange={(next) => next && onChange(next)} disabled={disabled}>
            <SelectTrigger className="h-7 w-auto min-w-24 text-xs" aria-label={placeholder}>
                <SelectValue placeholder={placeholder}>{value || placeholder}</SelectValue>
            </SelectTrigger>
            <SelectContent className="min-w-max">
                {columns.map((column) => (
                    <SelectItem key={column} value={column} className="text-xs">
                        {column}
                    </SelectItem>
                ))}
            </SelectContent>
        </Select>
    );
}

/** A source alias dropdown. */
function AliasSelect({
    value,
    aliases,
    onChange,
    disabled,
}: {
    value: string;
    aliases: readonly string[];
    onChange: (next: string) => void;
    disabled?: boolean;
}) {
    return (
        <Select value={value} onValueChange={(next) => next && onChange(next)} disabled={disabled}>
            <SelectTrigger className="h-7 w-auto min-w-20 text-xs font-medium">
                <SelectValue>{value}</SelectValue>
            </SelectTrigger>
            <SelectContent className="min-w-max">
                {aliases.map((alias) => (
                    <SelectItem key={alias} value={alias} className="text-xs">
                        {alias}
                    </SelectItem>
                ))}
            </SelectContent>
        </Select>
    );
}

export function JoinEditor({
    rows,
    confirmed,
    aliases,
    columnsByAlias,
    onRowChange,
    onRemoveRow,
    onApply,
    onDone,
    disabled = false,
    t,
}: JoinEditorProps) {
    // Nothing to edit is not an empty row: an empty block would look like a
    // join that failed to load.
    if (rows.length === 0) return null;

    const changed = !joinsEqual(rows, confirmed);
    const unjoined = unattachedAliases(aliases, rows);
    const complete = rows.filter(isCompleteJoin).length;

    return (
        <div className="mt-2 space-y-1.5">
            {/* The block announces itself. Without this the rows read as part of
                the model's prose, and a reply that has moved on to asking for a
                name reads as if the joins were not there at all. */}
            <p className="text-xs">
                <span className="font-medium">{t.heading}</span>
                <span className="text-muted-foreground"> — {t.hint}</span>
            </p>
            <div className="space-y-1" dir="ltr">
                {rows.map((row, index) => {
                    const incomplete = !isCompleteJoin(row);
                    return (
                        <div
                            key={`${row.left}\u0000${row.right}\u0000${index}`}
                            className={`flex flex-wrap items-center gap-1 rounded-md border px-1.5 py-1 ${
                                incomplete ? "border-amber-300 bg-amber-50/40 dark:bg-amber-950/20" : "border-border"
                            }`}
                        >
                            <AliasSelect
                                value={row.left}
                                aliases={aliases}
                                onChange={(left) => onRowChange(index, { left })}
                                disabled={disabled}
                            />
                            <ColumnSelect
                                value={row.leftCol}
                                columns={columnsByAlias[row.left] ?? []}
                                placeholder={t.columnPlaceholder}
                                onChange={(leftCol) => onRowChange(index, { leftCol })}
                                disabled={disabled}
                            />
                            <span className="px-0.5 text-xs text-muted-foreground">=</span>
                            <ColumnSelect
                                value={row.rightCol}
                                columns={columnsByAlias[row.right] ?? []}
                                placeholder={t.columnPlaceholder}
                                onChange={(rightCol) => onRowChange(index, { rightCol })}
                                disabled={disabled}
                            />
                            <AliasSelect
                                value={row.right}
                                aliases={aliases}
                                onChange={(right) => onRowChange(index, { right })}
                                disabled={disabled}
                            />
                            <Select
                                value={normaliseJoinType(row.type)}
                                onValueChange={(next) => next && onRowChange(index, { type: next })}
                                disabled={disabled}
                            >
                                <SelectTrigger className="h-7 w-auto min-w-16 text-xs" aria-label={t.typeLabel}>
                                    <SelectValue>{normaliseJoinType(row.type)}</SelectValue>
                                </SelectTrigger>
                                <SelectContent className="min-w-max">
                                    {JOIN_TYPES.map((type) => (
                                        <SelectItem key={type} value={type} className="text-xs">
                                            {type}
                                        </SelectItem>
                                    ))}
                                </SelectContent>
                            </Select>
                            {row.reason && (
                                // The reason is what makes the row reviewable: a plausible
                                // `customer_id = order_id` is only spot-able when the line says
                                // what it was for. Quiet, so it does not compete with the joins.
                                <span className="min-w-0 truncate text-xs text-muted-foreground">
                                    &mdash; {row.reason}
                                </span>
                            )}
                            <Button
                                type="button"
                                variant="ghost"
                                size="sm"
                                className="ms-auto h-6 w-6 shrink-0 p-0"
                                disabled={disabled}
                                aria-label={t.remove}
                                title={t.remove}
                                onClick={() => onRemoveRow(index)}
                            >
                                <X className="size-3.5" />
                            </Button>
                        </div>
                    );
                })}
            </div>

            {/* The coverage line is the useful half of the graph view, at the cost of
                one sentence: a source with no edge will not appear in the result. */}
            <p className="text-xs text-muted-foreground">
                {unjoined.length > 0
                    ? t.unjoined(unjoined.join(", "))
                    : t.coverage(complete, aliases.length)}
            </p>

            <div className="flex items-center gap-2">
                <Button
                    type="button"
                    size="sm"
                    className="h-7 text-xs"
                    // Never disabled for being unchanged: the control stays the same and
                    // only its label moves, so the block does not appear to lose a button
                    // when the edit is undone.
                    disabled={disabled || (changed && rows.some((row) => !isCompleteJoin(row)))}
                    onClick={changed ? onApply : onDone}
                >
                    {changed ? t.apply : t.done}
                </Button>
                {/* Only a warning here — the hint is in the heading above, and
                    saying it twice would push the rows apart for nothing. */}
                {changed && <span className="text-xs text-amber-700">{t.unsaved}</span>}
            </div>
        </div>
    );
}

/**
 * A settled join set, read-only.
 *
 * Every message that wrote joins keeps its own rows, and only the newest is
 * editable. Older blocks render through this so a reopened transcript shows
 * what was decided when — rather than a sentence referring to a control that is
 * no longer there, which reads as a broken page.
 */
export function JoinList({ rows }: { rows: readonly JoinRow[] }) {
    if (rows.length === 0) return null;
    return (
        <ul className="mt-2 space-y-0.5 text-xs text-muted-foreground" dir="ltr">
            {rows.map((row, index) => (
                <li key={`${row.left}\u0000${row.right}\u0000${index}`} className="truncate">
                    {joinSentence(row)}
                    {row.reason ? ` — ${row.reason}` : ""}
                </li>
            ))}
        </ul>
    );
}
