// components/chat/name-suggestion.tsx
// ============================================================
// A PROPOSED NAME, AND THE FIELD TO CHANGE IT.
//
// The `invite` surface offers one concrete answer — "Bike Sales Trend by Product
// Factor" — and the user may accept it or type their own. Rendering that as a
// single chip made the offer look like a closed set: one button, no way in, and
// the only alternative was to notice the composer at the bottom of the page and
// use that instead. Measured 2026-11-06: the user accepted the suggestion by
// typing "that name is fine", because the chip looked like the whole choice.
//
// So the proposal arrives as an **editable field already holding it**, with one
// button that accepts whatever the field says. Accepting the suggestion is one
// click; replacing it is one edit and one click; and nothing about the offer
// suggests it is final.
//
// Deliberately local state: the text belongs to this row until it is submitted,
// the same way the join editor's rows belong to the page until Apply. A name
// half-typed into a field is not a decision.
// ============================================================

"use client";

import { useState } from "react";
import { Loader2 } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";

export type NameSuggestionProps = {
  /** What the agent proposed. The field starts holding it. */
  suggestion: string;
  /** Called with the accepted text — the proposal, or whatever replaced it. */
  onAccept: (name: string) => void;
  /** Inert while a decision is in flight, never hidden. */
  disabled?: boolean;
  /** Shown while this row's own decision is the one running. */
  busy?: boolean;
  /** Already translated by the caller, like every other chat control here. */
  labels: {
    heading: string;
    accept: string;
    placeholder: string;
  };
};

export function NameSuggestion({ suggestion, onAccept, disabled = false, busy = false, labels }: NameSuggestionProps) {
  const [value, setValue] = useState(suggestion);
  const trimmed = value.trim();

  const submit = () => {
    if (!trimmed || disabled) return;
    onAccept(trimmed);
  };

  return (
    <div className="mt-2 space-y-1.5">
      <p className="text-xs text-muted-foreground">{labels.heading}</p>
      <div className="flex flex-wrap items-center gap-2">
        <Input
          value={value}
          onChange={(event) => setValue(event.target.value)}
          onKeyDown={(event) => {
            if (event.key === "Enter") {
              event.preventDefault();
              submit();
            }
          }}
          placeholder={labels.placeholder}
          disabled={disabled}
          aria-label={labels.heading}
          className="h-7 max-w-sm text-xs"
        />
        <Button
          type="button"
          size="sm"
          className="h-7 text-xs"
          onClick={submit}
          // Disabled only when there is nothing to send or a decision is running —
          // never merely because the field was edited, so the control cannot vanish
          // as a way of telling the user something.
          disabled={disabled || !trimmed}
        >
          {busy && <Loader2 className="size-3.5 animate-spin me-1" />}
          {labels.accept}
        </Button>
      </div>
    </div>
  );
}
