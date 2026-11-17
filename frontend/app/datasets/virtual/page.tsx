"use client";

import { useState, useEffect, useMemo, useRef } from "react";
import { useRouter } from "next/navigation";
import { useTranslation } from "@/lib/translation-context";
import { useTranslate, useTranslateKeyWithParams, getErrorMessageFromData, type TranslationKey } from "@/lib/translation-helpers";
import { apiFetch } from "@/lib/api";
import { ProtectedRoute } from "@/components/protected-route";
import ReturnBanner from "@/components/return-banner";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { toast } from "sonner";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Loader2, Send, ArrowLeft, Link2, Pencil, Copy, PlusCircle, X, PanelRightOpen, CheckCircle } from "lucide-react";
import { useAI } from "@/lib/ai-context";
import AudioToggle from "@/components/audio-toggle";
import AudioSettingsDialog from "@/components/audio-settings-dialog";
import CopyButton from "@/components/copy-button";
import MarkdownContent from "@/components/markdown-content";
import { useSpeechOutput } from "@/hooks/use-speech";
import { useSpeechInput } from "@/hooks/use-speech-input";
import { getCachedSettings, setCachedSettings } from "@/lib/audio-settings";

import { VIRTUAL } from "./translations";
import { MANUAL } from "./manual/translations";
import { DATASETS } from "../translations";
import { COMMON, name_suggestion_accept, name_suggestion_heading } from "@/app/common/translations";
import { AI } from "@/app/ai/translations";
import { SourceTree, connectionKey, datasetKey, type ColumnInfo, type PickedSource } from "@/components/datasets/source-tree";
import { SuggestionChips } from "@/components/chat/suggestion-chips";
import { NameSuggestion } from "@/components/chat/name-suggestion";
import { formatDate, formatTime } from "@/lib/date-format";
import { JoinEditor, JoinList, type JoinEditorTranslations } from "@/components/chat/join-editor";
import { isCompleteJoin, joinsEqual, type JoinRow } from "@/lib/virtual-joins";
import { SOURCE_TREE, SOURCE_PANEL } from "@/components/datasets/translations";

interface ChatSession {
  chatId: string;
  datasetId: string | null;
  stage: string;
  // The scoreboard's decided-piece count (Item 15): the same number the open
  // chat shows, from the same backend function, so the list cannot disagree.
  decided: { decided: number; total: number };
  status: string;
  createdAt: string;
  updatedAt: string;
}

interface Message {
  role: string;
  content: string;
  /** Set when this turn was an act — a chip click — rather than typed text.
   *  Rendered as an act, never as a quoted sentence the user did not write. */
  decision?: DecisionRecord;
  /** The assistant's chips for this turn, when it placed any (Item 22).
   *  A chip is something the agent offered, not a page control: the server
   *  computes the set from the scoreboard and returns it beside the reply, and
   *  the bubble renders it under its own text. */
  suggestion?: Suggestion;
  /** The joins this turn left behind, stored as a snapshot. The newest message
   *  carrying them is the editable block; older ones render read-only. */
  joins?: JoinRow[];
  /** This block's rows have been sent. The editor closes for it and it renders
   *  read-only from then on.
   *
   *  **On the message, not in page state.** It was a page-level
   *  `joinClosed: number | null` until 2026-11-07, holding a message *index* —
   *  and nothing reset it: not `startNewChat`, not `loadChat`, only a reload.
   *  A new conversation restarts the array at 0 and its join reply lands on the
   *  same index a previous conversation had closed, so `i !== joinClosed` was
   *  false and the block rendered read-only — join rows on screen, no Done
   *  button. Measured twice, and cured both times by reloading the page.
   *
   *  A flag cannot be stale against a different array, because it is only ever
   *  read from the message it was set on. */
  joinsConfirmed?: boolean;
}

/** The `suggestion` the chat routes return — `{piece, choices}` from
 *  `suggest_choices`, or `_derive_suggestion`'s field variant. */
/** One selectable chip in a multi-select: the server's own object.
 *
 *  `value` is the draft fragment the confirm writes for it — a source identity
 *  or a column pair — so the page never has to reconstruct what a chip means
 *  from its label. */
interface ChipChoice {
  key: string;
  label: string;
  value: unknown;
  columns?: string[];
}

interface Suggestion {
  piece: string;
  field?: string;
  choices: Array<string | ChipChoice>;
  /** Present and true when the agent offered a set to adjust and confirm. */
  multi?: boolean;
  /** Keys pre-ticked — the agent's proposal. */
  selected?: string[];
  /**
   * Set once the user has confirmed this offer.
   *
   * Without it the row came back after a successful confirm: `multiSelection`
   * is cleared, so the render falls through to `selected` — the agent's
   * original pre-ticked set — and the same chips reappeared as though nothing
   * had been accepted. Measured on 2026-11-05: seven sources, twenty-nine
   * columns and seven cache entries written, and the row still asking.
   */
  applied?: boolean;
}

const isChipChoice = (c: string | ChipChoice): c is ChipChoice =>
  typeof c === "object" && c !== null && "key" in c;

/** One entry as it is stored — the model's conversation, not a display record:
 *  it carries tool results and assistant turns that exist only to hold
 *  tool_calls. */
/** What a chip click did, stored with the turn it produced. */
interface DecisionRecord {
  piece: string;
  /** How many of the thing the act covered — 5 tables, 2 joins, one name. */
  chosen?: number;
  /** The tables accepted, for a `sources` act. */
  tables?: string[];
  /** The pair, for a `joins` act. */
  pair?: string;
  /** The value, for a `name` act. */
  name?: string;
}

interface StoredMessage {
  role: string;
  content?: string;
  tool_calls?: unknown[];
  /** Persisted with the assistant turn: the chips the agent placed that turn. */
  suggestion?: Suggestion;
  /** Present on a user turn that was a click, not typed text. */
  decision?: DecisionRecord;
  /**
   * The joins as this turn left them.
   *
   * A snapshot, not a pointer at the draft: the draft moves on, and a
   * transcript that showed today's joins under yesterday's sentence would be
   * the "message about chips that are no longer visible" defect in another
   * guise. The newest message carrying joins is the editable block; the older
   * ones render their own rows read-only.
   */
  joins?: JoinRow[];
}

// The virtual chat stores the model's conversation, tool results included, and
// every entry is rendered — so the view shows the projection of it: the tool
// traffic and the empty tool-call turns are dropped. This concierge emits no
// [DECISION:…] markers, so there is nothing of that kind to strip here.
function displayMessages(raw: unknown): Message[] {
  const stored = (raw as StoredMessage[] | undefined) || [];
  return stored
    .filter(
      (m) =>
        m.role === "user" ||
        (m.role === "assistant" && (m.content || "").trim() !== ""),
    )
    .map((m) => ({
      role: m.role,
      content: m.content || "",
      suggestion: m.suggestion,
      decision: m.decision,
      joins: m.joins,
    }));
}


/**
 * The assistant turn as the page keeps it.
 *
 * One builder for all four places a reply is appended, because the fields that
 * come with a reply are exactly the ones that used to be dropped: `joins` is
 * what renders the block, and a turn that wrote them must arrive carrying them
 * or the block cannot appear until a reload — which is precisely the defect
 * measured on 2026-11-06 (seven joins in the draft, message 51 stored with
 * them, and nothing on screen).
 */
interface ReplyPayload {
  response?: string;
  suggestion?: Suggestion;
  joins?: JoinRow[];
}

const assistantTurn = (data: ReplyPayload): Message => ({
  role: "assistant",
  content: data.response ?? "",
  suggestion: data.suggestion,
  joins: data.joins && data.joins.length > 0 ? data.joins : undefined,
});


/**
 * The draft, in the shape this page reads.
 *
 * The API sends the draft as the database holds it — `{name, goal, sources,
 * joins, columns}` — while the page reads `draft.virtualSql.sources` and
 * friends. Two `setDraft` call sites normalised that; five did not, so after any
 * send, chip click or chat load every `draft.virtualSql.*` read was `undefined`:
 * the tree showed nothing ticked, the preview card was empty, and the join block
 * compared six rows against an empty confirmed set, decided it was dirty, and
 * offered **Apply** on an untouched block. Clicking it found no edit in progress
 * and answered "Send a message first" — a message about a session that existed.
 *
 * Measured 2026-11-06 on session vdc_6081bdd5b5464ef9: six joins in the draft,
 * six identical joins on the message, and an Apply button that could only fail.
 *
 * One function, used by every writer, so the two shapes cannot drift again.
 */
function toDraftPreview(raw: unknown): DraftPreview | null {
  if (!raw || typeof raw !== "object") return null;
  const source = raw as {
    name?: string | null;
    virtualSql?: DraftPreview["virtualSql"];
    sources?: DraftPreview["virtualSql"]["sources"];
    joins?: DraftPreview["virtualSql"]["joins"];
    columns?: DraftPreview["virtualSql"]["columns"];
  };
  // Tolerant of both shapes: an already-normalised draft passes through
  // unchanged, so a caller cannot double-wrap it.
  if (source.virtualSql) {
    return { name: source.name ?? null, virtualSql: source.virtualSql };
  }
  return {
    name: source.name ?? null,
    virtualSql: {
      sources: source.sources || [],
      joins: source.joins || [],
      columns: source.columns || [],
    },
  };
}

interface VirtualDataset {
  id: string;
  name: string;
  description: string | null;
  sourceType: string;
  status: string;
  datasetGroup: string;
  isOwn: boolean;
  createdAt: string;
}

/** The scoreboard's pending entry — the shape `compute_virtual_scoreboard` emits. */
interface PendingPiece {
  piece: string;
  surface: "ask" | "point" | "read" | "offer" | "invite";
  /** The declared key's name. Kept for the chip key, never rendered. */
  what: string;
  /**
   * The sentence, already resolved through `t()` by the server — its English
   * fallback when the key has no row in the Translation table yet. The page
   * renders this and never builds a key of its own: a key crossing the wire has
   * no declaration here to fall back to.
   */
  whatText?: string;
  choices?: string[];
  source?: string;
}

interface Scoreboard {
  pending?: PendingPiece[];
  crystallised?: { piece: string; value?: unknown }[];
  blocked?: { piece: string }[];
  errors?: unknown[];
}

interface DraftPreview {
  name: string | null;
  virtualSql: {
    sources?: { alias?: string; tableName?: string; connectionId?: number; datasetId?: string; storageType?: string }[];
    /** `reason` is optional: the agent may state only the pair, and the row then
     *  renders without one rather than with an invented justification. */
    joins?: { left?: string; leftCol?: string; right?: string; rightCol?: string; type?: string; reason?: string }[];
    columns?: { source?: string; column?: string }[];
  };
  validation?: { valid?: boolean; errors?: string[] } | null;
}

interface AvailableConnection {
  id: string;
  connectionId: number;
  name: string;
  provider: string;
  isOwn: boolean;
}

interface AIModel {
  modelCode: string;
  modelName: string;
}

// A stable no-op for the panel's callbacks this page does not act on. A fresh
// arrow each render would re-run the tree's effects on every parent update.
const noop = () => {};

// Piece labels for the progress strip (Item 22). Every one names a declaration
// that already exists — the preview card's own labels — because a second key
// carrying the same English would be a duplicate fallback the linter reports.
// Nothing here repeats a key or an English string.
//
// Four pieces have a label; two do not, and it is deliberate. `columns` is
// omitted because its question already names the table it is asking about
// ("What is inside 'brands'?"), so a prefix would repeat it. Storage and goal
// are absent because neither can ever be the first pending piece: storage is
// satisfied by its default, and goal never blocks. A label for any of them
// would render nowhere — the orphan this item exists to prevent.
const PIECE_LABELS: Record<string, TranslationKey | undefined> = {
  sources: VIRTUAL.preview_sources,
  joins: VIRTUAL.preview_joins,
  output_columns: VIRTUAL.preview_columns,
  name: VIRTUAL.preview_name,
};

// Chip headings, keyed by the piece the chips answer. A heading is only shown
// for a piece with one; the rest render the row alone rather than inventing a
// caption.
const CHIP_HEADINGS: Record<string, TranslationKey | undefined> = {
  sources: VIRTUAL.heading_choose_table,
  columns: VIRTUAL.heading_choose_columns,
  joins: VIRTUAL.heading_match_columns,
  storage: VIRTUAL.heading_materialised,
};

// The tree's node key for a draft source — the same two builders the tree uses,
// so a ticked column and the row it belongs to cannot disagree about identity.
const keyOfSource = (src: { connectionId?: number; tableName?: string; datasetId?: string }) =>
  src.datasetId ? datasetKey(src.datasetId) : connectionKey(Number(src.connectionId), String(src.tableName));

function VirtualDatasetsContent() {
  const { isLanguageLoaded } = useTranslation();
  const translate = useTranslate();
  const tx = useTranslateKeyWithParams();
  const router = useRouter();
  const { defaultConnectionId } = useAI();

  // AI connection state
  const [aiConnections, setAIConnections] = useState<AvailableConnection[]>([]);
  const [selectedAIConnectionId, setSelectedAIConnectionId] = useState<string | null>(null);
  const [models, setModels] = useState<AIModel[]>([]);
  const [selectedModelCode, setSelectedModelCode] = useState<string | null>(null);
  const [loadingAIConnections, setLoadingAIConnections] = useState(true);

  // Chat state
  const [chatId, setChatId] = useState<string | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [sending, setSending] = useState(false);
  /**
   * The message whose chip row is waiting on a decision, so that row can show a
   * spinner.
   *
   * `sending` alone disables the chips and shows the thinking bubble at the
   * bottom of the transcript — but a decision turn validates, saves and, for a
   * materialised dataset, builds a table. A row that is inert and silent reads as
   * broken, and measured 2026-11-06 the user pressed the button again because
   * nothing had visibly happened.
   */
  const [pendingChipAt, setPendingChipAt] = useState<number | null>(null);
  // The Verbose switch was removed from the UI on 2026-10-11: it was never changed, and being
  // fixed on is the behaviour the chat has always run with. The value stays as a constant so the
  // request the client sends is unchanged - the backend reads it and appends its VERBOSE /
  // HELPFUL MODE block to the system prompt (virtual_chat.py).
  const verbose = true;
  // Decided / total pieces, from the scoreboard. Null until a session loads.
  const [decided, setDecided] = useState<{ decided: number; total: number } | null>(null);
  // The scoreboard as the server last computed it. Only the pending entries are
  // read here — the strip's bar takes `decided`/`total`, the chips take the
  // `ask` entries — and it is kept whole so a future reader does not have to
  // re-fetch it to see what else the turn reported.
  const [scoreboard, setScoreboard] = useState<Scoreboard | null>(null);
  const [draft, setDraft] = useState<DraftPreview | null>(null);

  // Audio state
  const [speakerEnabled, setSpeakerEnabled] = useState(false);
  const [micEnabled, setMicEnabled] = useState(false);
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [speakerMuted, setSpeakerMuted] = useState(false);

  // Audio output: speak the last non-user message
  const lastAssistantContent = messages.slice().reverse().find(m => m.role !== "user")?.content ?? "";
  const { speechOutputError, speechState, pause, resume, stop, volume, setVolume } =
      useSpeechOutput(lastAssistantContent, speakerEnabled, "virtual");
  const { isListening, transcript, speechInputError } = useSpeechInput(micEnabled);

  // Sidebar state
  const [virtualDatasets, setVirtualDatasets] = useState<VirtualDataset[]>([]);
  const [loadingDatasets, setLoadingDatasets] = useState(true);
  const [chats, setChats] = useState<ChatSession[]>([]);

  // Ticking a column decides the `point` piece (design §4.6): the column joins the
  // output list and its source comes into being, in one server write. So the tree
  // is given the draft's own columns as its ticked set, and a click posts to
  // /chat/{id}/columns. The panel is not the owner of that state — the draft is —
  // which is why these are derived here rather than held in the component.
  const draftSources = draft?.virtualSql?.sources ?? [];
  const draftColumns = draft?.virtualSql?.columns ?? [];
  const ticked = useMemo(() => {
    const map: Record<string, boolean> = {};
    for (const src of draftSources) {
      if (!src.alias) continue;
      const key = keyOfSource(src);
      for (const c of draftColumns) {
        if (c.source === src.alias && c.column) map[`${key}::${c.column}`] = true;
      }
    }
    return map;
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [draft]);

  // Columns the draft names for a source, shown until the tree has read the real
  // list — the same rule the manual editor follows with `preset`.
  const presetColumns = useMemo(() => {
    const map: Record<string, ColumnInfo[]> = {};
    for (const src of draftSources) {
      if (!src.alias) continue;
      const key = keyOfSource(src);
      const named = draftColumns
        .filter((c) => c.source === src.alias && c.column)
        .map((c) => ({ name: String(c.column) }));
      if (named.length) map[key] = named;
    }
    return map;
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [draft]);

  // The scoreboard as the server holds it. Read after a tick because a tick can
  // decide the `sources` piece and leave the join one pending — the chips come
  // from that same list, so a stale copy would offer a choice already taken.
  const refreshScoreboard = async () => {
    if (!chatId) return;
    try {
      const res = await apiFetch(`/api/datasets/virtual/chat/${chatId}`);
      if (!res.ok) return;
      const data = await res.json();
      if (data.scoreboard) setScoreboard(data.scoreboard);
      if (data.decided) setDecided(data.decided);
      if (data.contextData?.draft) {
        const merged = data.contextData.draft;
        setDraft((prev) => ({
          name: prev?.name ?? merged.name ?? null,
          virtualSql: {
            sources: merged.sources || [],
            joins: merged.joins || [],
            columns: merged.columns || [],
          },
        }));
      }
    } catch {
      // Not silent: the chips are read from this, so a failure leaves them
      // showing a set the user may already have decided — Item 17 names "a chip
      // set that could not be loaded" as needing a persistent message.
      setChatError(translate(VIRTUAL.chip_load_error));
    }
  };

  // A chip is only ever a member of a closed set the server named — the `ask`
  // surface. `point` pieces (sources, output columns) and `offer` pieces (joins)
  // are answered elsewhere: a tick in the tree, or accepting a suggested pair.
  // A chip row for one of those would be an empty row, which is the visible form
  // of the bug this filter prevents.
  // What the scoreboard says is still missing, in the scoreboard's own words.
  // This is where design §11 puts it — "the one-line 'what is missing' text for
  // the progress strip, where a label alone is not enough" — and it is the reason
  // the nine `virtual.scoreboard.*.what` keys exist at all. Before this the strip
  // showed a count and a bar with nothing saying WHAT remained.
  //
  // The first pending piece, because the page asks one thing at a time; a piece
  // whose text names a source ("What is inside 's2'?") is resolved against the
  // draft so the reader sees the table, not the alias.
  const pendingQuestion: string | null = useMemo(() => {
    for (const entry of scoreboard?.pending ?? []) {
      // `whatText` is the server's rendering of the declared key, with {source}
      // already filled from the draft. Before this the page built its own key
      // object with an empty fallback, so an untranslated key rendered as
      // nothing at all — and an absent line is indistinguishable from "nothing
      // is pending".
      if (entry.whatText) return entry.whatText;
    }
    return null;
  }, [scoreboard]);

  // The piece that sentence belongs to (Item 22), from the same pass, so the
  // strip can name it: "Joins — Which tables should be joined?". Kept separate
  // from `pendingQuestion` rather than returned as a pair, so the sentence's
  // existing consumers are untouched.
  const pendingPiece: string | null = useMemo(() => {
    for (const entry of scoreboard?.pending ?? []) {
      if (entry.whatText) return entry.piece;
    }
    return null;
  }, [scoreboard]);

  // A chip names a member of a closed set the server computed — the agent's own
  // suggestion for this turn, never a page-level row. Before Item 22 this page
  // built one from `scoreboard.pending` filtered on `surface === "ask"`, and
  // that filter could never match: the only `ask` piece in the design is
  // storage, and storage is satisfied by its default and never pending. So the
  // row was always empty, a suggestion the server computed was discarded by the
  // send handler, and no chip has ever rendered on this page.
  //
  // `piece::value` is the chip's key; the decision route splits it back apart,
  // because it is the only place that knows the appliers.
  /** True when the scoreboard already reports this piece as settled.
   *
   *  This is what makes a stored offer safe to reload. The suggestion is now
   *  persisted with its message, so reopening a chat finds it — and an offer the
   *  user has since accepted must not come back asking again. The scoreboard is
   *  the authority on that, not the message: it is computed from the draft as it
   *  stands, so it is right after a reload, after a chip, and after a turn that
   *  decided the piece by another route.
   *
   *  `crystallised` is the settled set; `sources`, `columns` and the rest each
   *  appear there once decided.
   */
  const pieceIsDecided = (piece: string): boolean =>
    (scoreboard?.crystallised ?? []).some((entry) => entry.piece === piece);

  /**
   * One line describing what a chip click did.
   *
   * The transcript stores the act, not a sentence in the user's voice. This is
   * the rendering: it says what happened, and it never quotes.
   */
  const actSummary = (
    act: DecisionRecord,
    tr: (key: TranslationKey, params?: Record<string, unknown>) => string,
  ): string => {
    if (act.piece === "sources" || act.piece === "columns") {
      const count = act.chosen ?? 0;
      const tables = (act.tables ?? []).join(", ");
      return tables && count > 1
        ? tr(VIRTUAL.act_sources_short, { count, tables })
        : tr(VIRTUAL.act_sources, { count });
    }
    if (act.piece === "joins" && act.pair) {
      return tr(VIRTUAL.act_join, { pair: act.pair });
    }
    // A set has no single pair to name. The count is what a reader wants from the
    // act anyway: six joins is the fact, and which six are on the rows below.
    if (act.piece === "joins") {
      return tr(VIRTUAL.act_joins, { count: act.chosen ?? 0 });
    }
    if (act.piece === "name" && act.name) {
      return tr(VIRTUAL.act_named, { name: act.name });
    }
    return tr(VIRTUAL.act_applied, { piece: act.piece });
  };

  const suggestionFor = (msg: Message): Suggestion | null => {
    if (msg.role !== "assistant" || !msg.suggestion) return null;
    if (msg.suggestion.choices.length === 0) return null;
    // A consumed offer, or one whose piece the draft has since settled.
    if (msg.suggestion.applied) return null;
    if (pieceIsDecided(msg.suggestion.piece)) return null;
    return msg.suggestion;
  };

  /** The piece's own name, so the question arrives with what it is asking
   *  about. A label for a piece with none returns undefined and the chip row
   *  stands alone rather than guessing. */
  const pieceLabel = (piece: string): string | null => {
    const decl = PIECE_LABELS[piece];
    return decl ? translate(decl) : null;
  };

  // The chip's value is the half after `piece::`; the server splits it back apart
  // in the decision route, which is the only place that knows the appliers.
  /**
   * The AI connection the user has selected, in the wire's shape.
   *
   * Every request that can start a turn needs it — the send, a chip, and a
   * confirm. `pickChip` and `confirmMultiChoice` did not send it, so the
   * decision endpoint took its early "no connection" path: the draft was
   * written and the reply was never produced. The page ignored `respondError`
   * too, so a click looked like it had done nothing.
   */
  const currentAIConnectionId = (): number | null =>
    selectedAIConnectionId
      ? aiConnections.find((c) => c.id === selectedAIConnectionId)?.connectionId ?? null
      : null;

  const pickChip = async (key: string, messageIndex: number) => {
    if (!chatId) {
      setPanelError(translate(VIRTUAL.panel_tick_no_session));
      return;
    }
    const cut = key.indexOf("::");
    const piece = key.slice(0, cut);
    const value = key.slice(cut + 2);
    setPanelError(null);
    // A chip click runs a whole model turn, so it needs the same busy state the
    // send and the multi-select confirm use. Without it the row stayed clickable
    // and a second click fired a second decision — measured 2026-11-06.
    setSending(true);
    setPendingChipAt(messageIndex);
    try {
      const res = await apiFetch(`/api/datasets/virtual/chat/${chatId}/decision`, {
        method: "POST",
        body: JSON.stringify({ piece, value, connectionId: currentAIConnectionId() }),
      });
      if (!res.ok) {
        let data: unknown = null;
        try { data = await res.json(); } catch { /* keep the fallback */ }
        setPanelError(getErrorMessageFromData(translate, data, VIRTUAL.chip_error));
        return;
      }
      const data = await res.json();
      if (data.draft) setDraft(toDraftPreview(data.draft));
      if (data.scoreboard) setScoreboard(data.scoreboard);
      if (data.decided) setDecided(data.decided);
      // A click that saved a dataset must refresh the list on the left.
      //
      // `refreshSidebar` was called from the message path only, and the dataset
      // is saved by the STORAGE click — a decision — so the pane kept showing the
      // datasets from before the save until the page was reloaded. Measured
      // 2026-11-07, session vdc_24c28d832d3945be: the reply named
      // `vd_b569fc8dbd114a19` and the list did not contain it.
      //
      // The server sets `datasetId` on the decision response for exactly this
      // (see `link_saved_dataset`), so the client has the signal it needs.
      if (data.datasetId) refreshSidebar();
      // A reply is appended when it carries ANYTHING to show — text or joins.
      //
      // `if (data.response)` alone dropped a decision turn that wrote joins and
      // then produced no prose: the joins were in the draft, persisted, and
      // invisible on screen because no message carried them and the block only
      // renders under a message that has them. `assistantTurn` already copies
      // both fields, so the guard is the only thing that was wrong here.
      if (data.response || (data.joins?.length ?? 0) > 0) {
        setMessages((prev) => [...prev, assistantTurn(data)]);
      }
      // The decision was recorded but the turn could not run. Saying so is not
      // optional: the draft changed, so silence reads as "applied and answered".
      if (data.respondError) setPanelError(data.respondError);
    } catch {
      setPanelError(translate(VIRTUAL.chip_error));
    } finally {
      setSending(false);
      setPendingChipAt(null);
    }
  };

  // A multi-select the agent offered: `selected` holds chip keys. It lives on the
  // page rather than in the message, because unticking is a decision about what
  // will be sent, not about what the assistant said.
  const [multiSelection, setMultiSelection] = useState<{
    messageIndex: number;
    piece: string;
    selected: string[];
  } | null>(null);

  const toggleMultiChoice = (
    messageIndex: number,
    piece: string,
    choices: ChipChoice[],
    key: string,
  ) => {
    const current = multiSelection?.messageIndex === messageIndex
      ? multiSelection.selected
      : choices.map((c) => c.key);
    const next = current.includes(key)
      ? current.filter((k) => k !== key)
      : [...current, key];
    setMultiSelection({ messageIndex, piece, selected: next });
  };

  // One confirm, one request, one atomic write on the server. The values are the
  // chips' own `value` fragments, so the page never reconstructs what a chip
  // means from its label.
  const confirmMultiChoice = async (
    messageIndex: number,
    piece: string,
    choices: ChipChoice[],
  ) => {
    if (!chatId) {
      setPanelError(translate(VIRTUAL.panel_tick_no_session));
      return;
    }
    const selected = multiSelection?.messageIndex === messageIndex
      ? multiSelection.selected
      : choices.map((c) => c.key);
    const value = choices
      .filter((c) => selected.includes(c.key))
      .map((c) => ({ ...(c.value as Record<string, unknown>), columns: c.columns ?? [] }));
    if (value.length === 0) {
      setPanelError(translate(VIRTUAL.selection_hint));
      return;
    }
    setPanelError(null);
    setSending(true);
    setPendingChipAt(messageIndex);
    try {
      const res = await apiFetch(`/api/datasets/virtual/chat/${chatId}/decision`, {
        method: "POST",
        body: JSON.stringify({ piece, value, connectionId: currentAIConnectionId() }),
      });
      if (!res.ok) {
        let data: unknown = null;
        try { data = await res.json(); } catch { /* keep the fallback */ }
        setPanelError(getErrorMessageFromData(translate, data, VIRTUAL.chip_error));
        return;
      }
      const data = await res.json();
      if (data.draft) setDraft(toDraftPreview(data.draft));
      if (data.scoreboard) setScoreboard(data.scoreboard);
      if (data.decided) setDecided(data.decided);
      // See the note on the first call site — a click that saved a dataset must
      // refresh the pane.
      if (data.datasetId) refreshSidebar();
      // Text or joins — see the note on the first call site. A multi-select
      // confirm that wrote joins must render them even with an empty reply.
      if (data.response || (data.joins?.length ?? 0) > 0) {
        setMessages((prev) => [...prev, assistantTurn(data)]);
      }
      // The offer has been used: mark it, so the row does not re-present itself
      // with the agent's original selection. The decision endpoint may append a
      // NEW message with its own suggestion — that one is a fresh offer from the
      // turn it just ran, and it renders normally because only this index is
      // marked.
      setMessages((prev) =>
        prev.map((m, idx) =>
          idx === messageIndex && m.suggestion
            ? { ...m, suggestion: { ...m.suggestion, applied: true } }
            : m,
        ),
      );
      setMultiSelection(null);
      if (data.respondError) setPanelError(data.respondError);
    } catch {
      setPanelError(translate(VIRTUAL.chip_error));
    } finally {
      setSending(false);
      setPendingChipAt(null);
    }
  };

  // ── the join block (format A) ──────────────────────────────
  //
  // The joins are in the draft, so this is an editor over what the agent wrote
  // rather than an offer. The rows live here because the page is what knows the
  // draft and what posts the edit; the block itself owns no state.
  //
  // `joinEdit` is the message whose block is being edited, and `joinRows` the
  // rows on screen. Keying by message index rather than by "the newest block"
  // means a reload, or a turn arriving mid-edit, cannot move the edit to a
  // different block under the user's hands.
  const [joinEdit, setJoinEdit] = useState<{ messageIndex: number; rows: JoinRow[] } | null>(null);

  /** The joins the draft holds, which is what an unchanged block is unchanged from. */
  const confirmedJoins = useMemo<JoinRow[]>(() => {
    const raw = draft?.virtualSql?.joins ?? [];
    return raw.map((join) => ({
      left: join.left ?? "",
      leftCol: join.leftCol ?? "",
      right: join.right ?? "",
      rightCol: join.rightCol ?? "",
      type: join.type ?? "inner",
      ...(join.reason ? { reason: join.reason } : {}),
    }));
  }, [draft]);

  /** The draft's source aliases, in the order the draft holds them. */
  const draftAliases = useMemo<string[]>(() => {
    const raw = draft?.virtualSql?.sources ?? [];
    return raw.map((source) => source.alias ?? "").filter(Boolean);
  }, [draft]);

  /** Column names per alias, from the scoreboard's crystallised `columns` pieces.
   *  The same source the tree and the scoreboard use — no second schema read. */
  const columnsByAlias = useMemo(() => {
    const byAlias: Record<string, string[]> = {};
    for (const entry of scoreboard?.crystallised ?? []) {
      if (entry.piece !== "columns") continue;
      const source = (entry as { source?: string }).source;
      const value = (entry as { value?: unknown }).value;
      if (source && Array.isArray(value)) {
        byAlias[source] = value.filter((name): name is string => typeof name === "string");
      }
    }
    return byAlias;
  }, [scoreboard]);

  /** The newest assistant message carrying joins is the editable one. */
  const liveJoinIndex = useMemo(() => {
    for (let index = messages.length - 1; index >= 0; index -= 1) {
      const message = messages[index];
      if (message.role === "assistant" && (message.joins?.length ?? 0) > 0) return index;
    }
    return -1;
  }, [messages]);

  /**
   * Edit one row. The first edit seeds the state from the message's own rows, so
   * there is no "begin editing" step to forget and no effect to keep in sync —
   * the block is editable the moment it renders.
   */
  const patchJoinRow = (messageIndex: number, base: JoinRow[], index: number, patch: Partial<JoinRow>) => {
    setJoinEdit((prev) => {
      const rows = prev?.messageIndex === messageIndex ? prev.rows : base.map((row) => ({ ...row }));
      return {
        messageIndex,
        rows: rows.map((row, i) => (i === index ? { ...row, ...patch } : row)),
      };
    });
  };

  const removeJoinRow = (messageIndex: number, base: JoinRow[], index: number) => {
    setJoinEdit((prev) => {
      const rows = prev?.messageIndex === messageIndex ? prev.rows : base.map((row) => ({ ...row }));
      return { messageIndex, rows: rows.filter((_, i) => i !== index) };
    });
  };

  /**
   * Re-state the join set. ONE writer, two labels.
   *
   * The whole set is sent, not a patch: the editor holds every row, so what it
   * posts is what the user decided on. The server replaces the joins and tells
   * the follow-up turn what changed — which row moved column, which type moved,
   * and above all which row went, because a removal is a decision and a turn that
   * is not told may simply put it back.
   *
   * **`Done` uses the same path as `Apply`.** It used to close the block locally
   * and send nothing, which was invisible: the rows went from dropdowns to plain
   * text and the conversation said nothing at all. Measured 2026-11-06 — the user
   * pressed Done and saw no response, while the next piece (`name`) was still
   * open. A silent close is not useful: the block was the turn's answer surface,
   * so finishing with it has to produce a turn. The label still says what the
   * click means — nothing changed, and the agent now knows that too, because the
   * decision note says "the joins were confirmed unchanged".
   */
  const submitJoinEdit = async (messageIndex: number, rows: JoinRow[]) => {
    if (!chatId) {
      setPanelError(translate(VIRTUAL.panel_tick_no_session));
      return;
    }
    const value = rows.filter(isCompleteJoin);
    if (value.length === 0) {
      setPanelError(translate(VIRTUAL.joins_unsaved));
      return;
    }
    setPanelError(null);
    setSending(true);
    try {
      const res = await apiFetch(`/api/datasets/virtual/chat/${chatId}/decision`, {
        method: "POST",
        body: JSON.stringify({ piece: "joins", value, connectionId: currentAIConnectionId() }),
      });
      if (!res.ok) {
        let data: unknown = null;
        try { data = await res.json(); } catch { /* keep the fallback */ }
        setPanelError(getErrorMessageFromData(translate, data, VIRTUAL.chip_error));
        return;
      }
      const data = await res.json();
      if (data.draft) setDraft(toDraftPreview(data.draft));
      if (data.scoreboard) setScoreboard(data.scoreboard);
      if (data.decided) setDecided(data.decided);
      if (data.datasetId) refreshSidebar();
      // The block that made this decision keeps the rows that were written, so
      // the closed list is what the user actually decided rather than the set the
      // agent first proposed. The reply carries no block of its own: a block
      // belongs to the turn that proposed the joins, not to the one confirming
      // them, and appending one here is what made Done offer Done again.
      //
      // `joinsConfirmed` replaces the old page-level `joinClosed` index. The flag
      // travels with the message, so it cannot point at a different conversation
      // — the defect it repairs, documented on `Message.joinsConfirmed`.
      setMessages((prev) =>
        prev.map((m, idx) =>
          idx === messageIndex ? { ...m, joins: value, joinsConfirmed: true } : m,
        ),
      );
      if (data.response || (data.joins?.length ?? 0) > 0) {
        setMessages((prev) => [...prev, assistantTurn(data)]);
      }
      setJoinEdit(null);
      if (data.respondError) setPanelError(data.respondError);
    } catch {
      setPanelError(translate(VIRTUAL.chip_error));
    } finally {
      setSending(false);
    }
  };

  /** Apply: the rows differ from the draft. */
  const applyJoinEdit = () => {
    if (!joinEdit) return;
    void submitJoinEdit(joinEdit.messageIndex, joinEdit.rows);
  };

  /** Done: the rows match the draft. Same request — the turn has to happen. */
  const doneJoinEdit = (messageIndex: number, rows: JoinRow[]) => {
    void submitJoinEdit(messageIndex, rows);
  };

  // One click, one write. `make` builds the source identity from the node the tree
  // rendered; its alias argument is a placeholder, because the server mints the
  // alias — it is the only party that can, against the draft as it stands.
  const toggleColumn = async (key: string, column: string, make: (alias: string) => PickedSource) => {
    if (!chatId) {
      setPanelError(translate(VIRTUAL.panel_tick_no_session));
      return;
    }
    const src = make("");
    const action = ticked[`${key}::${column}`] ? "untick" : "tick";
    setPanelError(null);
    try {
      const res = await apiFetch(`/api/datasets/virtual/chat/${chatId}/columns`, {
        method: "POST",
        body: JSON.stringify({
          action,
          column,
          connectionId: src.connectionId,
          tableName: src.tableName,
          datasetId: src.datasetId,
          storageType: src.storageType,
        }),
      });
      if (!res.ok) {
        let data: unknown = null;
        try { data = await res.json(); } catch { /* keep the fallback */ }
        setPanelError(getErrorMessageFromData(translate, data, VIRTUAL.panel_tick_error));
        return;
      }
      const data = await res.json();
      const merged = data.draft || {};
      setDraft((prev) => ({
        name: prev?.name ?? merged.name ?? null,
        virtualSql: {
          sources: merged.sources || [],
          joins: merged.joins || [],
          columns: merged.columns || [],
        },
      }));
      if (data.decided) setDecided(data.decided);
      // The tick route returns the count but not the scoreboard, so the chips are
      // re-read from the session rather than guessed: a tick can decide the
      // `source` piece and leave the join one pending.
      void refreshScoreboard();
    } catch {
      setPanelError(translate(VIRTUAL.panel_tick_error));
    }
  };

  // Docked source panel (design §9.4). The fold belongs to THIS session — the
  // user's decision of 2026-11-03, "foldable = this session" — so it is stored in
  // contextData.panelCollapsed through PATCH /chat/{id}/panel and read back with
  // the session. A fresh session opens shown, which is this default.
  const [panelCollapsed, setPanelCollapsed] = useState(false);
  const [panelError, setPanelError] = useState<string | null>(null);
  // Failures render where they happened, not as a toast that disappears before
  // it is read (AGENTS.md, persistent errors). The panel has its own slot below
  // the input; these two cover the sidebar's dataset and chat actions, and the
  // chat column's own loads.
  const [sidebarError, setSidebarError] = useState<string | null>(null);
  const [chatError, setChatError] = useState<string | null>(null);
  const [treeColumns, setTreeColumns] = useState<Record<string, ColumnInfo[]>>({});

  const inputRef = useRef<HTMLInputElement>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  useEffect(() => { scrollToBottom(); }, [messages]);

  // Refocus the chat input once a send completes and the input is re-enabled.
  // (The input is `disabled` while `sending`, so a synchronous focus in the
  // finally block fires too early to take effect.)
  useEffect(() => {
    if (!sending) {
      inputRef.current?.focus();
    }
  }, [sending]);

  const getConnectionLabel = (conn: AvailableConnection) => {
    if (!conn) return "";
    const name = conn.name || conn.provider || String(conn.connectionId);
    return conn.isOwn ? `${name} (${conn.provider})` : `* ${name} (${conn.provider})`;
  };

  const fetchAIConnections = async () => {
    setLoadingAIConnections(true);
    try {
      const res = await apiFetch("/api/user/ai-connections/available");
      if (res.ok) {
        const data = await res.json();
        const conns = data.connections || [];
        setAIConnections(conns);
        if (conns.length > 0) {
          setSelectedAIConnectionId(conns[0].id);
        }
      }
    } catch (err) {
      console.error("Error fetching AI connections:", err);
    } finally {
      setLoadingAIConnections(false);
    }
  };

  const fetchModels = async (connectionId: string) => {
    try {
      const res = await apiFetch(`/api/user/ai-connections/${connectionId}/models?enabled=true`);
      if (res.ok) {
        const data = await res.json();
        const mods = data.models || [];
        setModels(mods);
        if (mods.length > 0) {
          setSelectedModelCode(mods[0].modelCode);
        }
      }
    } catch (err) {
      console.error("Error fetching models:", err);
    }
  };

  // Fetch virtual datasets and existing chats on load
  const refreshSidebar = async () => {
    try {
      const [dsRes, chatRes] = await Promise.all([
        apiFetch("/api/datasets"),
        apiFetch("/api/datasets/virtual/chat"),
      ]);
      if (dsRes.ok) {
        const data = await dsRes.json();
        const virtual = (data.datasets || []).filter(
          (ds: any) => ds.sourceType === "virtual"
        );
        setVirtualDatasets(virtual);
      }
      if (chatRes.ok) {
        const data = await chatRes.json();
        setChats(data.chats || []);
      }
    } catch (err) {
      console.error("Error refreshing sidebar:", err);
    }
  };

  useEffect(() => {
    const init = async () => {
      await refreshSidebar();
      setLoadingDatasets(false);
      fetchAIConnections();
    };
    init();
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    if (selectedAIConnectionId) {
      fetchModels(selectedAIConnectionId);
    }
  }, [selectedAIConnectionId]);

  useEffect(() => {
    if (defaultConnectionId && aiConnections.length > 0) {
      const defaultConn = aiConnections.find(c => c.id === defaultConnectionId);
      if (defaultConn) {
        setSelectedAIConnectionId(defaultConnectionId);
      }
    }
  }, [defaultConnectionId, aiConnections]);

  // Start new chat
  const startNewChat = async () => {
    setMessages([]);
    setChatId(null);
    setDecided(null);
    setInput("");
    setDraft(null);
    inputRef.current?.focus();
  };

  // One place that turns a failed response into the sentence to show: the
  // server's own `detail` when it sent one, the translated fallback when it did
  // not. A non-ok response is a failure — before this, `if (res.ok)` meant a 404
  // from a delete reported nothing at all, which is worse than a toast.
  const failureText = async (res: Response, fallback: TranslationKey) => {
    let data: unknown = null;
    try { data = await res.json(); } catch { /* not JSON — keep the fallback */ }
    return getErrorMessageFromData(translate, data, fallback);
  };

  // Edit existing dataset
  const editDataset = async (ds: VirtualDataset) => {
    setSidebarError(null);
    try {
      const res = await apiFetch("/api/datasets/virtual/chat", {
        method: "POST",
        body: JSON.stringify({ datasetId: ds.id, message: "Edit this virtual dataset" }),
      });
      if (!res.ok) {
        setSidebarError(await failureText(res, VIRTUAL.error));
        return;
      }
      const data = await res.json();
      void loadChat(data.chatId);
    } catch {
      setSidebarError(translate(VIRTUAL.error));
    }
  };

  // Clone dataset
  const cloneDataset = async (ds: VirtualDataset) => {
    setSidebarError(null);
    try {
      const res = await apiFetch("/api/datasets/virtual/chat", {
        method: "POST",
        body: JSON.stringify({ datasetId: ds.id, message: "Clone this virtual dataset", clone: true }),
      });
      if (!res.ok) {
        setSidebarError(await failureText(res, VIRTUAL.error));
        return;
      }
      const data = await res.json();
      void loadChat(data.chatId);
    } catch {
      setSidebarError(translate(VIRTUAL.error));
    }
  };

  // Delete dataset
  const deleteDataset = async (e: React.MouseEvent, ds: VirtualDataset) => {
    e.stopPropagation();
    setSidebarError(null);
    try {
      const res = await apiFetch(`/api/datasets/${ds.id}`, {
        method: "DELETE",
      });
      if (!res.ok) {
        setSidebarError(await failureText(res, VIRTUAL.error));
        return;
      }
      setVirtualDatasets((prev) => prev.filter((d) => d.id !== ds.id));
      toast.success(translate(VIRTUAL.deleted));
    } catch {
      setSidebarError(translate(VIRTUAL.error));
    }
  };

  // Delete chat session
  const deleteChat = async (e: React.MouseEvent, chatIdToDelete: string) => {
    e.stopPropagation();
    setSidebarError(null);
    try {
      const res = await apiFetch(`/api/datasets/virtual/chat/${chatIdToDelete}`, {
        method: "DELETE",
      });
      if (!res.ok) {
        setSidebarError(await failureText(res, VIRTUAL.error));
        return;
      }
      setChats((prev) => prev.filter((c) => c.chatId !== chatIdToDelete));
      if (chatId === chatIdToDelete) {
        startNewChat();
      }
    } catch {
      setSidebarError(translate(VIRTUAL.error));
    }
  };

  // Load existing chat
  const loadChat = async (id: string) => {
    setChatError(null);
    try {
      const res = await apiFetch(`/api/datasets/virtual/chat/${id}`);
      // A session that cannot be loaded used to leave the previous conversation
      // on screen with no word about it — the worst of both, since the reader
      // would answer the wrong dataset.
      if (!res.ok) {
        setChatError(await failureText(res, VIRTUAL.error));
        return;
      }
      {
        const data = await res.json();
        setChatId(data.chatId);
        setMessages(displayMessages(data.messages));
        setDecided(data.decided || null);
        setDraft(toDraftPreview(data.contextData?.draft));
        setScoreboard(data.scoreboard || null);
        // The fold travels with the session, so a panel folded in an earlier
        // visit to this chat comes back folded (design §9.4).
        setPanelCollapsed(data.contextData?.panelCollapsed === true);
      }
    } catch {
      setChatError(translate(VIRTUAL.error));
    }
  };

  // Persist the panel's fold for this session. Best-effort in the sense that the
  // page stays usable if it fails, never in the sense that the failure is hidden:
  // panelError renders inline beside the panel and stays until dismissed.
  const persistPanel = async (collapsed: boolean, forChatId: string | null) => {
    if (!forChatId) return;  // no session yet — sent when the first message creates one
    setPanelError(null);
    try {
      const res = await apiFetch(`/api/datasets/virtual/chat/${forChatId}/panel`, {
        method: "PATCH",
        body: JSON.stringify({ collapsed }),
      });
      if (!res.ok) throw new Error(String(res.status));
    } catch {
      setPanelError(translate(VIRTUAL.panel_fold_error));
    }
  };

  const togglePanel = () => {
    const next = !panelCollapsed;
    setPanelCollapsed(next);
    void persistPanel(next, chatId);
  };

  // Send message
  const sendMessage = async () => {
    if (!input.trim() || sending) return;
    const msg = input.trim();
    setInput("");
    setSending(true);
    // A chat that does not exist yet cannot have stored the fold, so if one is
    // created by this message the current fold is written to it — otherwise a
    // panel folded before the first message would reopen on reload.
    const wasNewChat = !chatId;

    // Optimistic user message
    setMessages((prev) => [...prev, { role: "user", content: msg }]);

    try {
      const res = await apiFetch("/api/datasets/virtual/chat", {
        method: "POST",
        body: JSON.stringify({ 
          chatId, 
          message: msg, 
          verbose,
          connectionId: currentAIConnectionId(),
          model: selectedModelCode,
        }),
      });

      if (res.ok) {
        const data = await res.json();
        setChatId(data.chatId);
        if (wasNewChat && data.chatId && panelCollapsed) void persistPanel(panelCollapsed, data.chatId);
        if (data.draft) setDraft(toDraftPreview(data.draft));
        if (data.decided) setDecided(data.decided);
        if (data.scoreboard) setScoreboard(data.scoreboard);
        setMessages((prev) => [...prev, assistantTurn(data)]);
        if (data.datasetId) refreshSidebar();
      } else {
        let errorMsg = translate(VIRTUAL.error);
        try {
          const errData = await res.json();
          if (errData.detail) errorMsg = errData.detail;
        } catch {}
        setMessages((prev) => [...prev, { role: "assistant", content: errorMsg }]);
      }
    } catch (err) {
      setMessages((prev) => [...prev, { role: "assistant", content: `${translate(VIRTUAL.error)}` }]);
    } finally {
      setSending(false);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  };


  if (!isLanguageLoaded) {
    return (
      <div className="flex items-center justify-center h-64">
        <Loader2 className="animate-spin h-8 w-8" />
      </div>
    );
  }

  const columnCount = draft?.virtualSql?.columns?.length ?? 0;

  // The join block's words. Built here rather than inside the component because
  // the declarations belong to this module — a component that resolved its own
  // keys would be a second place a key could be named, which is the drift the
  // translation rules exist to stop.
  const joinEditorT: JoinEditorTranslations = {
    // Reused from the preview card's own label rather than minted: "Joins" is the
    // same word for the same thing, and a second key with an identical fallback
    // is the duplicate the linter forbids.
    heading: translate(VIRTUAL.preview_joins),
    apply: translate(VIRTUAL.joins_apply),
    // Reused, not re-declared: the recipe concierge's "Done" is the same word for
    // the same act, and a second key with an identical fallback is the duplicate
    // the linter forbids.
    done: translate(AI.ai_recipe_done),
    hint: translate(VIRTUAL.joins_hint),
    coverage: (connected, total) => tx(VIRTUAL.joins_coverage, { connected, total }),
    unjoined: (tables) => tx(VIRTUAL.joins_unjoined, { tables }),
    unsaved: translate(VIRTUAL.joins_unsaved),
    columnPlaceholder: translate(DATASETS.schema.column_name),
    typeLabel: translate(VIRTUAL.join_type_label),
    // The manual editor is the peer of this one and has said "Remove this join"
    // since it was built; the AI editor says the same words, so it names the same
    // declaration rather than minting a twin.
    remove: translate(MANUAL.remove_join),
  };

  return (
    <div className={`virtual-chat-layout${panelCollapsed ? " is-panel-collapsed" : ""}`}>
      {/* The recipe page's arrangement, followed here so the chat owns the screen: a fixed-height
          grid with page scroll removed, the sidebar in one column, and the chat in the other with
          the title and controls as its own header rather than in a card above it. */}
      <style>{`
        .virtual-chat-layout {
          display: grid;
          grid-template-columns: 260px 1fr clamp(280px, 24vw, 380px);
          grid-template-rows: auto 1fr;
          height: calc(100vh - 64px);
          overflow: hidden;
        }
        /* The fold is one arrangement, not a breakpoint: the panel narrows to a
           tab that keeps its heading and the column count visible (design §9.4). */
        .virtual-chat-layout.is-panel-collapsed {
          grid-template-columns: 260px 1fr 44px;
        }
        .virtual-chat-layout > .virtual-chat-banner { grid-column: 1 / -1; }
        .virtual-chat-layout > .virtual-sessions-panel {
          grid-row: 2;
          overflow: auto;
          background: var(--card);
          border-right: 1px solid var(--border);
          padding: 0.75rem;
        }
        .virtual-chat-layout > .virtual-chat-panel {
          grid-row: 2;
          display: flex;
          flex-direction: column;
          min-width: 0;
          overflow: hidden;
        }
        .virtual-chat-layout > .virtual-sources-panel {
          grid-row: 2;
          display: flex;
          flex-direction: column;
          min-height: 0;
          overflow: hidden;
          background: var(--card);
          border-left: 1px solid var(--border);
          padding: 0.75rem;
        }
        .virtual-chat-layout.is-panel-collapsed > .virtual-sources-panel {
          padding: 0.5rem 0.25rem;
        }
        @media (max-width: 1279px) {
          .virtual-chat-layout { grid-template-columns: 1fr clamp(280px, 24vw, 380px); }
          .virtual-chat-layout.is-panel-collapsed { grid-template-columns: 1fr 44px; }
          .virtual-chat-layout > .virtual-sessions-panel { display: none; }
        }
      `}</style>

      <div className="virtual-chat-banner">
        <ReturnBanner />
      </div>

        {/* Sidebar */}
        <div className="virtual-sessions-panel space-y-4">

          {sidebarError && (
            <div className="p-2 bg-red-50 border border-red-200 rounded-md text-red-800 text-xs flex items-start justify-between gap-2">
              <span>{sidebarError}</span>
              <button type="button" onClick={() => setSidebarError(null)} className="text-red-600 hover:text-red-800">&times;</button>
            </div>
          )}

          {/* Existing virtual datasets */}
          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm">{translate(VIRTUAL.existing_title)}</CardTitle>
            </CardHeader>
            <CardContent>
              {loadingDatasets ? (
                <Loader2 className="animate-spin h-4 w-4" />
              ) : virtualDatasets.length === 0 ? (
                <p className="text-xs text-muted-foreground">{translate(VIRTUAL.existing_none)}</p>
              ) : (
                <div className="space-y-1">
                  {virtualDatasets.map((ds) => (
                    <div key={ds.id} className="p-2 rounded-md hover:bg-muted/50 text-xs">
                      <div className="font-medium truncate">{ds.name}</div>
                      <div className="text-muted-foreground">
                        <span className={`inline-block px-1 py-0.5 rounded text-[10px] ${
                          ds.status === "ready" ? "bg-green-100 text-green-800" : "bg-yellow-100 text-yellow-800"
                        }`}>
                          {ds.status === "ready" ? translate(VIRTUAL.ready_badge) : translate(VIRTUAL.draft_badge)}
                        </span>
                      </div>
                      <div className="flex gap-1 mt-1">
                        {ds.isOwn && (
                          <Button variant="ghost" size="sm" className="h-6 text-[10px] px-1"
                                  onClick={() => editDataset(ds)}>
                            <Pencil className="h-3 w-3 me-0.5" />
                            {translate(VIRTUAL.edit)}
                          </Button>
                        )}
                        <Button variant="ghost" size="sm" className="h-6 text-[10px] px-1"
                                onClick={() => cloneDataset(ds)}>
                          <Copy className="h-3 w-3 me-0.5" />
                          {translate(VIRTUAL.clone)}
                        </Button>
                        <Button variant="ghost" size="sm" className="h-6 text-[10px] px-1 text-destructive"
                                onClick={(e) => deleteDataset(e, ds)}>
                          <X className="h-3 w-3 me-0.5" />
                        </Button>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </CardContent>
          </Card>

          {/* Recent chats */}
          {chats.length > 0 && (
            <Card>
              <CardHeader className="pb-2">
                <CardTitle className="text-sm">{translate(VIRTUAL.recent_chats)}</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="space-y-1">
                  {chats.slice(0, 5).map((c) => (
                    <div key={c.chatId} className="text-xs p-1.5 rounded hover:bg-muted/50 cursor-pointer truncate flex items-center justify-between gap-1"
                         onClick={() => loadChat(c.chatId)}>
                      <span className="truncate">
                        <span className="text-muted-foreground/60 me-1">
                          {(() => {
                            const d = new Date(c.updatedAt);
                            const now = new Date();
                            const isToday = d.toDateString() === now.toDateString();
                            if (isToday) {
                              // Time alone, because the date is obvious for today.
                              return formatTime(c.updatedAt);
                            }
                            return formatDate(c.updatedAt);
                          })()}
                        </span>
                        {c.decided ? tx(VIRTUAL.progress_decided, c.decided) : ""}
                      </span>
                      {c.chatId !== chatId && (
                        <button
                          className="flex-shrink-0 text-muted-foreground hover:text-destructive p-0.5 rounded hover:bg-destructive/10"
                          onClick={(e) => deleteChat(e, c.chatId)}
                          title={translate(COMMON.delete_chat)}
                        >
                          <X className="h-3 w-3" />
                        </button>
                      )}
                    </div>
                  ))}
                  {chats.length > 5 && (
                    <div className="text-xs text-center text-muted-foreground/50 py-0.5">
                      ——— {translate(VIRTUAL.more)} ———
                    </div>
                  )}
                </div>
              </CardContent>
            </Card>
          )}
        </div>

        {/* Chat panel */}
        <div className="virtual-chat-panel">

          {chatError && (
            <div className="p-2 bg-red-50 border border-red-200 rounded-md text-red-800 text-xs flex items-start justify-between gap-2 m-3 mb-0">
              <span>{chatError}</span>
              <button type="button" onClick={() => setChatError(null)} className="text-red-600 hover:text-red-800">&times;</button>
            </div>
          )}
          {/* Chat header: the title and the controls, so nothing sits above the messages */}
          <div className="border-b border-border bg-card px-3 py-2 flex flex-wrap items-center gap-2">
            <Button variant="ghost" size="icon" className="h-8 w-8" onClick={() => router.push("/datasets/manage")}>
              <ArrowLeft className="h-4 w-4" />
            </Button>
            <span className="font-semibold text-sm flex items-center gap-1.5 me-1">
              <Link2 className="h-4 w-4" />
              {translate(VIRTUAL.title)}
            </span>
            <Select
              value={selectedAIConnectionId || ""}
              onValueChange={(val) => setSelectedAIConnectionId(val || null)}
              disabled={loadingAIConnections}
            >
              <SelectTrigger className="h-8 w-[180px] text-xs">
                <SelectValue placeholder={translate(AI.select_ai_connection_placeholder)}>
                  {selectedAIConnectionId !== null
                    ? getConnectionLabel(aiConnections.find(c => c.id === selectedAIConnectionId)!)
                    : ""}
                </SelectValue>
              </SelectTrigger>
              <SelectContent>
                {aiConnections.map((conn) => (
                  <SelectItem key={conn.id} value={conn.id}>
                    {getConnectionLabel(conn)}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            <Select
              value={selectedModelCode || ""}
              onValueChange={(val) => setSelectedModelCode(val || null)}
              disabled={!selectedAIConnectionId || models.length === 0}
            >
              <SelectTrigger className="h-8 w-[160px] text-xs">
                <SelectValue placeholder={translate(AI.select_model_placeholder)}>
                  {selectedModelCode !== null
                    ? (models.find(m => m.modelCode === selectedModelCode)?.modelName || selectedModelCode)
                    : ""}
                </SelectValue>
              </SelectTrigger>
              <SelectContent>
                {models.map((m) => (
                  <SelectItem key={m.modelCode} value={m.modelCode}>
                    {m.modelName || m.modelCode}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            {/* The strip: the count, and a bar that reads the same two numbers.
                The bar is not decoration — "3 of 6" is a figure a reader has to
                compute with, and the remaining distance is what the strip is for.
                Its width comes from decided/total, so it cannot drift from the
                text beside it. */}
            <span className="ms-auto flex items-center gap-2 whitespace-nowrap">
              {decided && decided.total > 0 && (
                <span
                  className="h-1.5 w-16 overflow-hidden rounded-full bg-muted"
                  role="progressbar"
                  aria-valuemin={0}
                  aria-valuemax={decided.total}
                  aria-valuenow={decided.decided}
                  aria-label={tx(VIRTUAL.progress_decided, decided)}
                >
                  <span
                    className="block h-full rounded-full bg-primary transition-[width]"
                    style={{ width: `${Math.round((decided.decided / decided.total) * 100)}%` }}
                  />
                </span>
              )}
              <span className="text-xs text-muted-foreground">
                {decided ? tx(VIRTUAL.progress_decided, decided) : ""}
              </span>
            </span>
            {/* What is still missing, in the scoreboard's words (design §11),
                prefixed by the piece it belongs to (Item 22). Without the label
                a sentence like "Which tables should be joined?" arrives with
                nothing saying which part of the definition it is asking about;
                the label comes from PIECE_LABELS and is absent for a piece that
                has none, so the sentence still stands alone rather than
                guessing. Truncated rather than wrapped: it sits in the header
                row, and the full sentence is available from the assistant. */}
            {pendingQuestion && (
              <span
                className="hidden max-w-[22rem] truncate text-xs text-muted-foreground/80 lg:inline"
                title={pendingPiece ? `${pieceLabel(pendingPiece) ?? ""} — ${pendingQuestion}` : pendingQuestion}
              >
                {pendingPiece && pieceLabel(pendingPiece) ? `${pieceLabel(pendingPiece)} — ` : ""}
                {pendingQuestion}
              </span>
            )}
            <Button
              variant="outline"
              size="sm"
              onClick={startNewChat}
            >
              <PlusCircle className="h-4 w-4 me-1" />
              {translate(AI.new_session)}
            </Button>
          </div>

          {!loadingAIConnections && aiConnections.length === 0 && (
            <p className="mx-3 mt-2 text-sm text-amber-600 bg-amber-50 border border-amber-200 rounded-md px-3 py-2">
              {translate(AI.no_ai_connections)}
            </p>
          )}

          {/*
            The read-only dataset preview used to sit here: name, sources, joins and
            output columns, mirroring the draft. It was removed on 2026-11-06 —
            the block of joins under each message already shows the joins, and the
            scoreboard reports every other piece as the conversation resolves it.
            A second, static copy of the same state competed with the conversation
            rather than supporting it: it duplicated what the agent had just said,
            could not be edited, and gave a reader two places to look for one
            answer.
          */}

          {/* Messages - the chat owns whatever height is left */}
          <div className="flex-1 min-h-0 overflow-y-auto p-4 space-y-3">
              {messages.length === 0 && (
                <div className="flex items-center justify-center h-full text-muted-foreground text-sm">
                  <p className="whitespace-pre-line max-w-md text-center">{translate(VIRTUAL.welcome)}</p>
                </div>
              )}
              {messages.map((msg, i) => (
                <div key={i} className={`flex ${msg.role === "user" ? "justify-end" : "justify-start"}`}>
                  <div className="flex items-end gap-1">
                    {msg.decision ? (
                      // An act, not speech. The chip was clicked; nothing was
                      // typed. Rendered as a quiet line on the left of the
                      // user's column rather than a bubble in their voice — a
                      // bubble would quote them saying something they never said.
                      <div className="max-w-[75%] rounded-lg border border-dashed border-border px-3 py-1.5 text-xs text-muted-foreground">
                        {actSummary(msg.decision, translate)}
                      </div>
                    ) : (
                    <div className={`max-w-[75%] rounded-lg px-3 py-2 text-sm ${
                      msg.role === "user"
                        ? "bg-primary text-primary-foreground"
                        : "bg-muted"
                    }`}>
                      <div className="text-sm flex-1"><MarkdownContent>{msg.content}</MarkdownContent></div>
                      {/* The assistant's own chips, under its own text (Item 22).
                          A heading names the piece the choices answer; a piece
                          with no heading renders the row alone. */}
                      {(() => {
                        const offered = msg.role === "assistant" ? msg.suggestion : null;
                        if (!offered || offered.choices.length === 0) return null;

                        const sg = suggestionFor(msg);
                        if (!sg) {
                          // The offer was used — by the confirm, or by a turn that decided
                          // the piece some other way. A marker takes the chips' place
                          // rather than leaving nothing: the message text above still says
                          // "confirm that selection", and a sentence asking for something
                          // with no control under it reads as a broken page. One line keeps
                          // the transcript truthful about what was asked and what happened.
                          // A green badge, not a muted line: this is the one
                          // signal in the transcript that the user's click
                          // landed, and `text-muted-foreground` read as a caption
                          // rather than as a confirmation. The pattern is the
                          // house one for a success state — `bg-green-100
                          // text-green-800` with a check icon — matching
                          // `components/test-state-badge.tsx` and the manual
                          // editor's completed marker, so it is the same green
                          // the rest of the product uses for "done".
                          return (
                            <span className="mt-2 inline-flex items-center gap-1 rounded px-1.5 py-0.5 text-xs font-medium bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-300">
                              <CheckCircle className="h-3 w-3" />
                              {translate(VIRTUAL.suggestion_applied)}
                            </span>
                          );
                        }
                        const heading = CHIP_HEADINGS[sg.piece];

                        // A multi-select the agent offered: the set arrives
                        // pre-ticked, the user adjusts, and one confirm writes it
                        // all in a single act. The single-pick row is unchanged
                        // for every other piece.
                        if (sg.multi) {
                          const choices = sg.choices.filter(isChipChoice);
                          const selected = multiSelection?.messageIndex === i
                            ? multiSelection.selected
                            : (sg.selected ?? choices.map((c) => c.key));
                          return (
                            <div className="mt-2 space-y-1.5">
                              <SuggestionChips
                                items={choices.map((c) => ({ key: c.key, label: c.label }))}
                                onPick={(key) => toggleMultiChoice(i, sg.piece, choices, key)}
                                disabled={sending}
                                busy={pendingChipAt === i}
                                heading={heading ? translate(heading) : undefined}
                                selectedKeys={selected}
                              />
                              <div className="flex items-center gap-2">
                                <Button
                                  type="button"
                                  size="sm"
                                  disabled={sending || selected.length === 0}
                                  onClick={() => confirmMultiChoice(i, sg.piece, choices)}
                                  className="h-7 text-xs"
                                >
                                  {translate(VIRTUAL.confirm_selection)}
                                </Button>
                                <span className="text-xs text-muted-foreground">
                                  {translate(VIRTUAL.selection_hint)}
                                </span>
                              </div>
                            </div>
                          );
                        }

                        // A proposed NAME is an invitation, not a closed set: the
                        // offer arrives as an editable field holding it, so
                        // accepting is one click and replacing it is one edit.
                        // As a bare chip it looked like the only option, and the
                        // user typed "that name is fine" instead — measured
                        // 2026-11-06.
                        if (sg.piece === "name") {
                          const proposed = sg.choices
                            .map((c) => (isChipChoice(c) ? c.label : c))
                            .filter((label): label is string => typeof label === "string" && label.length > 0);
                          if (proposed.length > 0) {
                            return (
                              <NameSuggestion
                                suggestion={proposed[0]}
                                onAccept={(name) => pickChip(`name::${name}`, i)}
                                disabled={sending}
                                busy={pendingChipAt === i}
                                labels={{
                                  heading: translate(name_suggestion_heading),
                                  accept: translate(name_suggestion_accept),
                                  placeholder: translate(MANUAL.name_label),
                                }}
                              />
                            );
                          }
                        }

                        return (
                          <div className="mt-2">
                            <SuggestionChips
                              items={sg.choices.map((c) => ({
                                key: `${sg.piece}::${isChipChoice(c) ? c.key : c}`,
                                label: isChipChoice(c) ? c.label : c,
                              }))}
                              onPick={(key) => pickChip(key, i)}
                              disabled={sending}
                              busy={pendingChipAt === i}
                              heading={heading ? translate(heading) : undefined}
                            />
                          </div>
                        );
                      })()}
                      {/* Format A — the joins as editable rows, under the message that
                          wrote them. The newest block that has not been confirmed is
                          the editor; every other one renders its own rows read-only,
                          so a reopened transcript still shows what was decided when
                          rather than a sentence referring to a control that is gone.

                          `!msg.joinsConfirmed` and not an index comparison: the
                          block closes itself by setting that flag on this message
                          (see `submitJoinEdit`), so no page-level state can point at
                          the wrong conversation. */}
                      {msg.role === "assistant" && (msg.joins?.length ?? 0) > 0 && (
                        i === liveJoinIndex && !msg.joinsConfirmed ? (
                          <JoinEditor
                            rows={joinEdit?.messageIndex === i ? joinEdit.rows : (msg.joins ?? [])}
                            confirmed={confirmedJoins}
                            aliases={draftAliases}
                            columnsByAlias={columnsByAlias}
                            onRowChange={(index, patch) => patchJoinRow(i, msg.joins ?? [], index, patch)}
                            onRemoveRow={(index) => removeJoinRow(i, msg.joins ?? [], index)}
                            onApply={applyJoinEdit}
                            onDone={() => doneJoinEdit(i, msg.joins ?? [])}
                            disabled={sending}
                            t={joinEditorT}
                          />
                        ) : (
                          <JoinList rows={msg.joins ?? []} />
                        )
                      )}
                    </div>
                    )}
                    {!msg.decision && <CopyButton text={msg.content} />}
                  </div>
                </div>
              ))}
              {sending && (
                <div className="flex justify-start">
                  <div className="bg-muted rounded-lg px-3 py-2 flex items-center gap-2 text-progress">
                    <Loader2 className="animate-spin h-4 w-4" />
                    {translate(AI.thinking)}
                  </div>
                </div>
              )}
              <div ref={messagesEndRef} />
            </div>

            {/* Nothing sits here: chips belong to the assistant's message, not
                to the page. Item 15's page-level row was always empty — its
                filter required `surface === "ask"`, and the only `ask` piece
                in the design (storage) is satisfied by its default and never
                pending — so it was removed in Item 22 and the chips moved
                under the bubble that placed them. */}

            {/* Input */}
            <div className="p-3 border-t flex gap-2">
              <AudioToggle
                micEnabled={micEnabled} onMicChange={setMicEnabled}
                speakerEnabled={speakerEnabled} onSpeakerChange={setSpeakerEnabled}
                volume={volume} onVolumeChange={setVolume}
                speakerMuted={speakerMuted}
                onSpeakerMuteToggle={() => { const next = !speakerMuted; setSpeakerMuted(next); setSpeakerEnabled(!next); const s = getCachedSettings("virtual"); s.speakerMuted = next; setCachedSettings("virtual", s); }}
                speechState={speechState} onPause={pause} onResume={resume} onStop={stop}
                onSettingsClick={() => setSettingsOpen(true)}
              />
              <Input dir="ltr"
                ref={inputRef}
                autoFocus
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={handleKeyDown}
                placeholder={translate(VIRTUAL.placeholder)}
                disabled={sending}
                className="flex-1"
              />
              <Button onClick={sendMessage} disabled={!input.trim() || sending} size="icon">
                <Send className="h-4 w-4" />
              </Button>
            </div>

            {/* The persistent error, in one fixed place: directly below the text entry
                and inside the chat column. It used to render inside the docked panel,
                which meant folding the panel hid the message telling the user the fold
                had not been saved. Staying in the chat column also keeps it visible when
                the panel is folded. It is not a toast: it stays until dismissed. */}
            {panelError && (
              <div className="mx-3 mb-3 p-2 bg-red-50 border border-red-200 rounded-md text-red-800 text-xs flex items-start justify-between gap-2">
                <span>{panelError}</span>
                <button type="button" onClick={() => setPanelError(null)} className="text-red-600 hover:text-red-800">&times;</button>
              </div>
            )}
          <AudioSettingsDialog open={settingsOpen} onClose={() => setSettingsOpen(false)} chatType="virtual" />
        </div>

        {/* The source panel, docked right: the manual editor's own tree, showing what
            the assistant is talking about rather than describing it (design §9.4).
            Read-only here — see the note on `selectable` in the component: a tick on
            this page would have to write the draft, and no endpoint applies one yet. */}
        <div className="virtual-sources-panel">
          {panelCollapsed ? (
            <div className="flex h-full min-h-0 flex-col items-center gap-2">
              <Button
                variant="ghost"
                size="icon"
                className="h-7 w-7 shrink-0"
                onClick={togglePanel}
                aria-label={translate(SOURCE_PANEL.expand)}
              >
                <PanelRightOpen className="h-4 w-4" />
              </Button>
              <span className="[writing-mode:vertical-rl] min-h-0 truncate text-xs text-muted-foreground">
                {translate(SOURCE_TREE.sources_title)}
              </span>
              <span className="shrink-0 text-[10px] tabular-nums text-muted-foreground">
                {tx(VIRTUAL.panel_columns, { count: columnCount })}
              </span>
            </div>
          ) : (
            <SourceTree
              columns={treeColumns}
              presetColumns={presetColumns}
              ticked={ticked}
              onToggleColumn={toggleColumn}
              onColumnsRead={(key, cols) => setTreeColumns((s) => ({ ...s, [key]: cols }))}
              onDatasetsLoaded={noop}
              onError={setPanelError}
              docked
              onCollapse={togglePanel}
            />
          )}
        </div>
    </div>
  );
}

export default function VirtualDatasetsPage() {
  return (
    <ProtectedRoute>
      <VirtualDatasetsContent />
    </ProtectedRoute>
  );
}
