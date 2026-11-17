// components/chat/suggestion-chips.tsx
// ============================================================
// SUGGESTION CHIPS — one closed set of choices, rendered as a row of buttons.
//
// Hoisted out of app/ai/recipe/page.tsx (Item 15 of the virtual-dataset v2 plan)
// so the recipe page and the virtual-dataset page render chips the same way
// instead of each keeping its own copy. What is shared is the ROW, not the
// choice: each caller builds its own items, because what a chip means differs
// between the two surfaces — a recipe chip names an algorithm or a column, a
// virtual-dataset chip names a value from the scoreboard's `ask` set.
//
// Deliberately dumb: no fetching, no label lookup, no disabled logic beyond the
// caller's own. A chip's label is whatever the caller decided it should say,
// which is what keeps the translation declarations at the call site where the
// rule requires them.
// ============================================================

"use client";

import { useState } from "react";
import { Loader2 } from "lucide-react";

import { Button } from "@/components/ui/button";

export type ChipItem = {
  /** Passed back to `onPick`; also the React key, so it must be stable. */
  key: string;
  /** What the chip reads. Already translated by the caller. */
  label: string;
};

export type SuggestionChipsProps = {
  items: ChipItem[];
  onPick: (key: string) => void;
  /** Chips are inert while the surface is busy — never hidden, so the row does not jump. */
  disabled?: boolean;
  /**
   * Show a spinner beside the row.
   *
   * A disabled chip is not the same as a visibly working one: the decision turn
   * validates, saves and — for a materialised dataset — builds a table, which
   * takes seconds. Measured 2026-11-06: the user chose "Saved table", saw nothing
   * change, and pressed the button again; the second click was what confused the
   * conversation. Inert and silent reads as broken.
   */
  busy?: boolean;
  /** Optional heading above the row; omitted, the row stands alone. */
  heading?: string;
  /**
   * The choices the cap left out, and the words that offer them.
   *
   * A count alone made the cap a silent loss of function rather than a display
   * limit: measured 2026-11-11, a reply told the user to click "Linear
   * Regression" — seventh of eight algorithms, cap at six — and no such chip
   * existed. The conversation dead-ended on a choice the row had hidden. So the
   * remainder travels and this row can expand to show it: the cap still bounds
   * what is on screen by default, and nothing becomes unreachable.
   */
  overflowItems?: ChipItem[];
  /** Label for the control that reveals `overflowItems`. Already translated. */
  expandLabel?: string;
  /** Label for the control that hides them again. */
  collapseLabel?: string;
  /**
   * How many choices the row is NOT showing, and the words that say so.
   *
   * The backend caps a chip row at six and sends the count it left out, because a
   * row that silently shows six of eleven says "these are the options" when it
   * means "these are some of them". The label arrives already translated, for the
   * same reason a chip's does: this component is deliberately dumb, and the
   * declaration belongs at the call site where the rule puts it.
   *
   * Rendering it is the whole point — the count travelling without a line on
   * screen leaves the row reading as complete, which is the outcome the cap
   * exists to prevent.
   */
  withheld?: number;
  withheldLabel?: string;
  /**
   * Multi-select mode: the keys currently selected, and clicking toggles.
   *
   * Additive, and that is deliberate. The recipe page renders single-pick chips
   * and passes neither prop, so its behaviour is unchanged — this is one row
   * that can be either, not two components that must be kept in step.
   */
  selectedKeys?: readonly string[];
};

export function SuggestionChips({
  items,
  onPick,
  disabled = false,
  busy = false,
  heading,
  withheld = 0,
  withheldLabel,
  overflowItems,
  expandLabel,
  collapseLabel,
  selectedKeys,
}: SuggestionChipsProps) {
  // Expanded is row-local state: it is a property of what this reader is looking
  // at, not of the conversation, so it must not travel back to the server or be
  // inherited by the next row.
  const [expanded, setExpanded] = useState(false);
  // Nothing pending is not an empty row: an empty pill would suggest a choice
  // exists and failed to load.
  if (items.length === 0) return null;

  return (
    <div className="space-y-1">
      {heading && <p className="text-xs text-muted-foreground">{heading}</p>}
      <div className="flex flex-wrap items-center gap-1.5">
        {(expanded && overflowItems ? [...items, ...overflowItems] : items).map((item) => {
          const isSelected = selectedKeys ? selectedKeys.includes(item.key) : false;
          return (
            <Button
              key={item.key}
              type="button"
              variant={isSelected ? "default" : "outline"}
              size="sm"
              disabled={disabled}
              aria-pressed={selectedKeys ? isSelected : undefined}
              onClick={() => onPick(item.key)}
              className="h-7 rounded-full px-3 text-xs font-normal"
            >
              {item.label}
            </Button>
          );
        })}
        {withheld > 0 && withheldLabel && !(overflowItems && overflowItems.length > 0) && (
          // A plain word when the remainder is not available to render. With the
          // items in hand the same text becomes a control below, because a count
          // a reader cannot act on is what hid a choice in the first place.
          <span className="text-xs text-muted-foreground">{withheldLabel}</span>
        )}
        {overflowItems && overflowItems.length > 0 && withheldLabel && (
          <Button
            type="button"
            variant="ghost"
            size="sm"
            disabled={disabled}
            aria-expanded={expanded}
            onClick={() => setExpanded((v) => !v)}
            className="h-7 rounded-full px-2 text-xs font-normal text-muted-foreground"
          >
            {expanded ? (collapseLabel || withheldLabel) : (expandLabel || withheldLabel)}
          </Button>
        )}
        {busy && <Loader2 className="size-3.5 animate-spin text-muted-foreground" aria-hidden />}
      </div>
    </div>
  );
}
