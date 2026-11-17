// app/datasets/virtual/manual/page.tsx
// ============================================================
// MANUAL VIRTUAL DATASET EDITOR — prototype
//
// The non-AI editor for virtual datasets. Not linked from anywhere: reach it by
// URL at /datasets/virtual/manual.
//
// It is a UI over the contract that already exists for the AI concierge — the
// same routes, the same shared helpers (save_virtual_dataset_record,
// validate_virtual_dataset_definition, fetch_virtual_join). Nothing here
// re-implements validation or storage; the editor is the other caller.
//
// Design: workbench-documents/workbench-manual-virtual-dataset-editor.html
//
// Three behaviours worth knowing before editing this file:
//
//  1. Output column entries are MERGED, never rebuilt. A saved definition can
//     carry per-column fields nothing reads yet (`alias`, `aggregation`), and a
//     rebuild would silently delete them (docs/code-quirks.md, 2026-09-24). The
//     editor keeps each entry whole and writes only `source` and `column`.
//  2. The tree is not in this file: it is components/datasets/source-tree.tsx,
//     mounted below and driven through a handle. Its markup, its two endpoints
//     and its lazy-loading rules live there.
//  3. Columns read from a saved definition are kept in `preset`, NOT in
//     `columnsByKey` — otherwise expanding that node would find the cache
//     populated and never read the real column list.
// ============================================================

"use client";

import { useState, useEffect, useRef } from "react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Input } from "@/components/ui/input";
import { Switch } from "@/components/ui/switch";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { DataValue } from "@/components/ui/data-value";
import {
  SourceTree,
  connectionKey,
  datasetKey,
  type ColumnInfo,
  type DatasetRow,
  type PickedSource,
  type SourceTreeHandle,
} from "@/components/datasets/source-tree";
import { apiFetch } from "@/lib/api";
import { cn } from "@/lib/utils";
import { useTranslation } from "@/lib/translation-context";
import { useTranslate, getErrorMessageFromData, type TranslationKey } from "@/lib/translation-helpers";
import { COMMON } from "@/app/common/translations";
import { VIRTUAL } from "@/app/datasets/virtual/translations";
import { DATASETS } from "@/app/datasets/translations";
import { MANUAL } from "./translations";
import { ChevronDown, ChevronUp, Loader2, Plus, Users, X } from "lucide-react";

// ── types ────────────────────────────────────────────────────

// One row of the definition's `columns[]`, kept whole so unknown fields survive.
type OutputEntry = { source: string; column: string } & Record<string, unknown>;

type JoinRow = { left: string; leftCol: string; right: string; rightCol: string; type: string };

const JOIN_TYPES = ["INNER", "LEFT", "RIGHT", "FULL"];

// Two join rows describe the same pair when they name the same two aliases,
// whichever way round they were written.
const samePair = (j: { left: string; right: string }, left: string, right: string) =>
  (j.left === left && j.right === right) || (j.left === right && j.right === left);

// Column-name comparison for join suggestions. `base` drops an `_id`/`id` suffix
// and every other character; `stem` also drops a trailing plural `s`. Both feed a
// suggestion a person accepts or ignores, never a decision taken for them.
const base = (n: string) => n.replace(/(_?id)$/i, "").replace(/[^a-z0-9]/gi, "").toLowerCase();
const stem = (n: string) => base(n).replace(/s$/, "");

// What a bare `id` column is compared against: the source's own table name, or a
// dataset's name for a dataset source — NOT the display label. The label carries
// the connection name too ("bike store - sample · customers"), so any comparison
// against it is doomed, and that was why the `<x>_id` → `id` rule could never
// fire for the most common join shape there is.
const sourceNameStem = (s: PickedSource) =>
  stem(s.kind === "dataset" ? s.label : (s.tableName || s.label));

// ── the page ─────────────────────────────────────────────────

export default function ManualVirtualDatasetPage() {
  const { isLanguageLoaded } = useTranslation();
  const translate = useTranslate();

  // tree
  // The tree owns its own state; the page keeps the two lists it needs for its
  // other panels — the dataset list behind the open selector, and the column
  // cache the join matcher scores against. The tree publishes both.
  const tree = useRef<SourceTreeHandle | null>(null);
  const [datasets, setDatasets] = useState<DatasetRow[]>([]);
  const [columnsByKey, setColumnsByKey] = useState<Record<string, ColumnInfo[]>>({});
  const [presetColumns, setPresetColumns] = useState<Record<string, ColumnInfo[]>>({});

  // the definition being built
  const [picked, setPicked] = useState<Record<string, PickedSource>>({});  // source key → source
  const [ticked, setTicked] = useState<Record<string, boolean>>({});       // `${key}::${column}` → true
  const [output, setOutput] = useState<OutputEntry[]>([]);
  const [joins, setJoins] = useState<JoinRow[]>([]);
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [materialized, setMaterialized] = useState(false);
  const [editingId, setEditingId] = useState<string | null>(null);

  // feedback
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  /**
   * A materialisation the save could not complete, and the dataset it belongs to.
   *
   * Persistent and inline, per the project's error rule: the save itself succeeded,
   * so this is not a save failure — it is an operational problem the user fixes and
   * then retries, and it has to stay on screen until they do.
   */
  const [materializeFailure, setMaterializeFailure] = useState<{ id: string; message: string } | null>(null);
  // A save the validator refused renders BESIDE the buttons, not at the top of
  // this page: the buttons are at the bottom of a long form, so a banner at the
  // top is off-screen at the moment it matters. The page-top banner keeps the
  // load and read failures, which happen while the reader is up there.
  const [actionError, setActionError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [validationErrors, setValidationErrors] = useState<string[]>([]);
  const [preview, setPreview] = useState<{ columns: string[]; rows: string[][] } | null>(null);
  const [busy, setBusy] = useState<string | null>(null);

  const aliases = Object.values(picked).map((s) => s.alias);
  const keyForAlias = (alias: string) => Object.keys(picked).find((k) => picked[k].alias === alias) || "";
  const sourceLabel = (alias: string) => picked[keyForAlias(alias)]?.label || alias;

  // ── reading sources ────────────────────────────────────────

  // Read the columns of every source the definition uses, once each. A source
  // opened from a saved definition carries only the columns that definition
  // names — the output list — so without this the matcher scores against a
  // handful of names and can find nothing to suggest.
  const pickedKeyList = Object.keys(picked).join(",");
  useEffect(() => {
    for (const key of pickedKeyList.split(",")) {
      if (key) tree.current?.loadColumns(key);
    }
  }, [pickedKeyList]);

  const columnsFor = (key: string): ColumnInfo[] => columnsByKey[key] || presetColumns[key] || [];

  // ── ticking a column ────────────────────────────────────────

  const toggleColumn = (key: string, column: string, make: (alias: string) => PickedSource) => {
    const tickKey = `${key}::${column}`;
    if (ticked[tickKey]) {
      const alias = picked[key]?.alias;
      setTicked((s) => { const next = { ...s }; delete next[tickKey]; return next; });
      setOutput((entries) => entries.filter((e) => !(alias && e.source === alias && e.column === column)));
      return;
    }
    let alias = picked[key]?.alias;
    if (!alias) {
      // An alias must be unique among the sources already in the definition.
      const used = new Set(Object.values(picked).map((s) => s.alias));
      let n = Object.keys(picked).length + 1;
      alias = `s${n}`;
      while (used.has(alias)) { n += 1; alias = `s${n}`; }
      setPicked((s) => ({ ...s, [key]: make(alias as string) }));
    }
    setTicked((s) => ({ ...s, [tickKey]: true }));
    setOutput((entries) => (
      entries.some((e) => e.source === alias && e.column === column)
        ? entries
        // Merge, never rebuild: an entry loaded from a definition keeps every
        // field it arrived with; only the two the editor owns are written.
        : [...entries, { source: alias, column }]
    ));
  };

  // ── aliases, ordering, joins ────────────────────────────────

  const renameAlias = (key: string, next: string) => {
    const current = picked[key]?.alias;
    if (!current || !next || next === current) return;
    if (aliases.includes(next)) { setValidationErrors([translate(MANUAL.alias_taken)]); return; }
    setValidationErrors([]);
    setPicked((s) => ({ ...s, [key]: { ...s[key], alias: next } }));
    setOutput((entries) => entries.map((e) => (e.source === current ? { ...e, source: next } : e)));
    setJoins((rows) => rows.map((j) => ({
      ...j,
      left: j.left === current ? next : j.left,
      right: j.right === current ? next : j.right,
    })));
  };

  const moveColumn = (index: number, delta: number) => {
    setOutput((entries) => {
      const target = index + delta;
      if (target < 0 || target >= entries.length) return entries;
      const next = [...entries];
      [next[index], next[target]] = [next[target], next[index]];
      return next;
    });
  };

  const removeOutput = (index: number) => {
    const entry = output[index];
    const key = keyForAlias(entry.source);
    setOutput((entries) => entries.filter((_, i) => i !== index));
    if (key && ticked[`${key}::${entry.column}`]) {
      setTicked((s) => { const next = { ...s }; delete next[`${key}::${entry.column}`]; return next; });
    }
  };

  const addJoin = (join?: Partial<JoinRow>) => {
    const left = join?.left ?? aliases[0] ?? "";
    setJoins((rows) => [...rows, {
      left,
      leftCol: join?.leftCol ?? "",
      right: join?.right ?? aliases.find((a) => a !== left) ?? "",
      rightCol: join?.rightCol ?? "",
      type: join?.type ?? "INNER",
    }]);
  };

  const updateJoin = (index: number, patch: Partial<JoinRow>) =>
    setJoins((rows) => rows.map((j, i) => (i === index ? { ...j, ...patch } : j)));

  // Accepting a suggestion fills the row that already names this pair — usually
  // an unfinished bridge — rather than adding a second row for the same two
  // sources. A duplicate would leave the empty one still blocking the save and
  // still hiding the remedy.
  const applyJoinSuggestion = (s: { left: string; leftCol: string; right: string; rightCol: string }) => {
    const idx = joins.findIndex((j) => samePair(j, s.left, s.right) && (!j.leftCol || !j.rightCol));
    if (idx < 0) { addJoin(s); return; }
    if (!s.leftCol || !s.rightCol) return; // nothing to fill with
    const flipped = joins[idx].left !== s.left;
    setJoins((rows) => rows.map((r, i) => (i === idx
      ? { ...r, leftCol: flipped ? s.rightCol : s.leftCol, rightCol: flipped ? s.leftCol : s.rightCol }
      : r)));
  };

  // The join graph must connect every source, and the builder attaches from the
  // FIRST source outwards (build_postgres_join_sql seeds its FROM with
  // sources[0] and follows join edges). This mirrors that fixpoint exactly, so
  // the editor can report a disconnected graph before the server does — and it
  // names the same aliases the server's error would name.
  const joinEdges = joins.filter((j) => j.left && j.right && j.leftCol && j.rightCol);

  const unattachedAliases = (): string[] => {
    if (aliases.length === 0) return [];
    const attached = new Set<string>([aliases[0]]);
    let grew = true;
    while (grew) {
      grew = false;
      for (const j of joinEdges) {
        if (attached.has(j.left) && !attached.has(j.right)) { attached.add(j.right); grew = true; }
        else if (attached.has(j.right) && !attached.has(j.left)) { attached.add(j.left); grew = true; }
      }
    }
    return aliases.filter((a) => !attached.has(a));
  };

  // An alias on its own is hard to place; the label is what the tree showed.
  const describeAliases = (list: string[]) =>
    list.map((a) => (sourceLabel(a) && sourceLabel(a) !== a ? `${a} (${sourceLabel(a)})` : a)).join(", ");

  // Deterministic join suggestions — no AI, no model call. Ranked over the
  // columns already read: a `<x>_id` → `id` match first, then an identical name.
  //
  // A BRIDGE ranks above everything else: a pair with exactly one side already
  // attached would connect an orphan to the rest, which is the one suggestion
  // that fixes a disconnected graph. When no column match exists for a bridge it
  // is still offered — the pair, with the columns left to choose — because
  // naming the pair is the hard part and the two selects are not.
  //
  // Offered to accept, never applied silently: a wrong join produces a
  // plausible-looking dataset, which is the worst outcome for this tool.
  const suggestions = (() => {
    const keys = Object.keys(picked);
    const orphans = new Set(unattachedAliases());
    const items: {
      score: number; bridge: boolean; columnsKnown: boolean; columnsRead: boolean; fills: boolean;
      left: string; leftCol: string; right: string; rightCol: string;
    }[] = [];
    for (let i = 0; i < keys.length; i += 1) {
      for (let j = i + 1; j < keys.length; j += 1) {
        const a = picked[keys[i]], b = picked[keys[j]];
        // Only a join that actually connects the two counts as "already joined" —
        // the same completeness rule the connectivity check and the SQL builder
        // use. A row whose columns are still empty connects nothing, so the pair
        // stays suggestible. Testing every row here is what used to silence the
        // suggestion for exactly the pair that needed it.
        if (joinEdges.some((x) => samePair(x, a.alias, b.alias))) continue;
        const pairRowExists = joins.some((x) => samePair(x, a.alias, b.alias));
        const bridge = orphans.has(a.alias) !== orphans.has(b.alias);
        let best: { score: number; leftCol: string; rightCol: string } | null = null;
        // Whether both sides have column lists to score at all — the difference
        // between "nothing matched" and "nothing was read", which the bare bridge
        // has to say out loud or it reads as a dead end.
        const columnsRead = columnsFor(keys[i]).length > 0 && columnsFor(keys[j]).length > 0;
        for (const ca of columnsFor(keys[i])) {
          for (const cb of columnsFor(keys[j])) {
            let score = 0;
            if (ca.name === cb.name) score = 3;
            if (stem(ca.name).length > 0 && stem(ca.name) === stem(cb.name)) score = Math.max(score, 2);
            if (/^id$/i.test(cb.name) && stem(ca.name) === sourceNameStem(b)) score = Math.max(score, 4);
            if (/^id$/i.test(ca.name) && stem(cb.name) === sourceNameStem(a)) score = Math.max(score, 4);
            if (score > 0 && (!best || score > best.score)) best = { score, leftCol: ca.name, rightCol: cb.name };
          }
        }
        if (best && best.score >= 2) {
          items.push({ score: best.score, bridge, columnsKnown: true, columnsRead, fills: pairRowExists,
            left: a.alias, leftCol: best.leftCol, right: b.alias, rightCol: best.rightCol });
        } else if (bridge && !pairRowExists) {
          // A bare bridge is worth offering only when no row names the pair yet;
          // otherwise accepting it would have nothing to fill.
          items.push({ score: 0, bridge: true, columnsKnown: false, columnsRead, fills: false,
            left: a.alias, leftCol: "", right: b.alias, rightCol: "" });
        }
      }
    }
    items.sort((x, y) => (Number(y.bridge) - Number(x.bridge)) || (y.score - x.score));
    return items.slice(0, 3);
  })();

  // ── building the definition ─────────────────────────────────

  const buildDefinition = () => ({
    sources: Object.values(picked).map((s) =>
      s.kind === "dataset"
        ? { alias: s.alias, datasetId: s.datasetId, storageType: s.storageType, tableName: s.tableName }
        : { alias: s.alias, connectionId: s.connectionId, tableName: s.tableName, storageType: s.storageType },
    ),
    joins: joins.filter((j) => j.left && j.right && j.leftCol && j.rightCol),
    columns: output,
  });

  const readError = async (res: Response, fallback: TranslationKey) => {
    let data: unknown = {};
    try { const text = await res.text(); if (text) data = JSON.parse(text); } catch { /* keep {} */ }
    return getErrorMessageFromData(translate, data, fallback);
  };

  // What is wrong before anything is sent. Reported on click, never used to
  // disable a control.
  const structuralProblem = (): string | null => {
    if (output.length === 0) return translate(MANUAL.need_columns);
    if (joins.some((j) => !j.left || !j.right || !j.leftCol || !j.rightCol)) return translate(MANUAL.incomplete_join);
    if (aliases.length > 1 && joinEdges.length === 0) return translate(MANUAL.need_join);
    const unattached = unattachedAliases();
    if (unattached.length > 0) {
      return translate(MANUAL.unattached_sources).replace("{sources}", describeAliases(unattached));
    }
    return null;
  };

  // ── the three actions ───────────────────────────────────────

  const handleValidate = async () => {
    setBusy("validate"); setActionError(null); setNotice(null); setValidationErrors([]);
    const problem = structuralProblem();
    if (problem) { setValidationErrors([problem]); setBusy(null); return; }
    try {
      const res = await apiFetch("/api/datasets/virtual/validate", {
        method: "POST",
        body: JSON.stringify({ virtualSql: buildDefinition() }),
      });
      if (!res.ok) throw new Error(await readError(res, MANUAL.preview_error));
      const data = await res.json();
      if (data.valid) setNotice(translate(MANUAL.validate_ok));
      else setValidationErrors(data.errors || []);
    } catch (e: unknown) {
      setActionError(e instanceof Error ? e.message : translate(MANUAL.preview_error));
    } finally { setBusy(null); }
  };

  const handleTestJoin = async () => {
    setBusy("preview"); setErrorMessage(null); setNotice(null); setPreview(null); setValidationErrors([]);
    const problem = structuralProblem();
    if (problem) { setValidationErrors([problem]); setBusy(null); return; }
    try {
      const res = await apiFetch("/api/datasets/virtual/preview", {
        method: "POST",
        body: JSON.stringify({ virtualSql: buildDefinition() }),
      });
      if (!res.ok) throw new Error(await readError(res, MANUAL.preview_error));
      const data = await res.json();
      setPreview({ columns: data.columns || [], rows: data.rows || [] });
      setNotice(
        (data.row_count ?? 0) === 0
          ? translate(MANUAL.preview_empty)
          : translate(MANUAL.preview_rows).replace("{count}", String(data.row_count ?? 0)),
      );
    } catch (e: unknown) {
      setActionError(e instanceof Error ? e.message : translate(MANUAL.preview_error));
    } finally { setBusy(null); }
  };

  const handleSave = async () => {
    setBusy("save"); setActionError(null); setNotice(null); setValidationErrors([]);
    if (!name.trim()) { setActionError(translate(MANUAL.need_name)); setBusy(null); return; }
    const problem = structuralProblem();
    if (problem) { setValidationErrors([problem]); setBusy(null); return; }
    try {
      const body: Record<string, unknown> = {
        name: name.trim(),
        description: description.trim() || null,
        virtualSql: buildDefinition(),
        materialized,
      };
      if (editingId) body.id = editingId;
      const res = await apiFetch("/api/datasets/virtual/save", {
        method: "POST",
        body: JSON.stringify(body),
      });
      if (!res.ok) throw new Error(await readError(res, MANUAL.save_error));
      const data = await res.json();
      const savedId = data.id ?? editingId;
      setEditingId(savedId);
      setNotice(translate(MANUAL.save_success));
      // Save-and-report: the definition is written, and the build is reported
      // separately. A failure here is not a save failure, so it does not replace
      // the notice — it sits beside it until the user retries.
      setMaterializeFailure(
        data.materializeError && savedId
          ? { id: savedId, message: String(data.materializeError) }
          : null,
      );
      void tree.current?.refreshDatasets();
    } catch (e: unknown) {
      setActionError(e instanceof Error ? e.message : translate(MANUAL.save_error));
    } finally { setBusy(null); }
  };

  /**
   * Retry the build for the dataset just saved.
   *
   * Its own request, carrying no definition: the definition is already stored, and
   * re-submitting it to retry is how a stale client overwrites a newer dataset.
   */
  const retryMaterialise = async () => {
    if (!materializeFailure) return;
    setBusy("retry");
    try {
      const res = await apiFetch(`/api/datasets/${materializeFailure.id}/materialize`, { method: "POST" });
      if (!res.ok) throw new Error(await readError(res, MANUAL.save_error));
      const data = await res.json();
      if (data.materializeError) {
        setMaterializeFailure({ id: materializeFailure.id, message: String(data.materializeError) });
      } else {
        setMaterializeFailure(null);
        setNotice(translate(MANUAL.materialize_done));
      }
      void tree.current?.refreshDatasets();
    } catch (e: unknown) {
      setMaterializeFailure({
        id: materializeFailure.id,
        message: e instanceof Error ? e.message : translate(MANUAL.save_error),
      });
    } finally { setBusy(null); }
  };

  // ── opening an existing dataset ─────────────────────────────

  const hydrate = (definition: Record<string, unknown>) => {
    const sources = (definition.sources as PickedSource[] | undefined) || [];
    const columns = (definition.columns as OutputEntry[] | undefined) || [];
    const nextPicked: Record<string, PickedSource> = {};
    const nextTicked: Record<string, boolean> = {};
    const nextPreset: Record<string, ColumnInfo[]> = {};

    const keyOf = (s: PickedSource) =>
      s.datasetId ? datasetKey(s.datasetId) : connectionKey(Number(s.connectionId), String(s.tableName));

    for (const s of sources) {
      const key = keyOf(s);
      nextPicked[key] = {
        ...s,
        kind: s.datasetId ? "dataset" : "connection",
        label: s.datasetId
          ? (datasets.find((d) => d.id === s.datasetId)?.name || s.datasetId)
          : String(s.tableName),
      };
      // The definition names columns for this source — enough to populate a join
      // control before the tree has read the table. Kept apart from
      // columnsByKey so expanding the node still reads the real column list.
      const named = columns.filter((c) => c.source === s.alias).map((c) => ({ name: c.column }));
      if (named.length) nextPreset[key] = named;
    }
    for (const c of columns) {
      const s = sources.find((x) => x.alias === c.source);
      if (s) nextTicked[`${keyOf(s)}::${c.column}`] = true;
    }

    setPicked(nextPicked);
    setTicked(nextTicked);
    setPresetColumns(nextPreset);
    setOutput(columns);
    setJoins((definition.joins as JoinRow[] | undefined) || []);
    // Every source the definition names is opened in the tree, so a definition
    // that has just been loaded shows what it reads from instead of leaving it
    // buried.
    tree.current?.openSources(sources);
  };

  const openExisting = async (datasetId: string) => {
    setErrorMessage(null); setNotice(null); setValidationErrors([]); setPreview(null);
    try {
      const res = await apiFetch(`/api/datasets/virtual/definition/${datasetId}`);
      if (!res.ok) throw new Error(await readError(res, MANUAL.load_error));
      const data = await res.json();
      setEditingId(data.id);
      setName(data.name || "");
      setDescription(data.description || "");
      setMaterialized(Boolean(data.materialized));
      hydrate(data.virtualSql || {});
      // The notice states what saving will do — and the backend has just said what that
      // is: canEdit is the same rule the save enforces (the owner, or an administrator
      // when the dataset is shared to the group they belong to). Deriving it from isOwn
      // here would tell an administrator that a shared definition is read-only while the
      // save would accept it. The save control stays enabled either way: this states what
      // the backend will do, it does not suppress the action.
      setNotice(translate(data.canEdit === false ? MANUAL.loaded_note_shared : MANUAL.loaded_note));
    } catch (e: unknown) {
      setErrorMessage(e instanceof Error ? e.message : translate(MANUAL.load_error));
    }
  };

  const resetAll = () => {
    setEditingId(null); setName(""); setDescription(""); setMaterialized(false);
    setPicked({}); setTicked({}); setOutput([]); setJoins([]); setPresetColumns({});
    setPreview(null); setNotice(null); setErrorMessage(null); setActionError(null); setValidationErrors([]);
  };

  // ── render helpers ──────────────────────────────────────────

  // `unfinished` marks the box itself, not only its row: a row cannot be read at
  // a glance without knowing which of its two columns is the missing one.
  const columnSelect = (key: string, value: string, onChange: (v: string) => void, placeholder: string, unfinished = false) => {
    const warn = unfinished ? "border-amber-400" : undefined;
    const cols = columnsFor(key);
    if (cols.length === 0) {
      return <Input dir="ltr" value={value} onChange={(e) => onChange(e.target.value)} placeholder={placeholder} className={cn("h-8", warn)} />;
    }
    return (
      <Select value={value} onValueChange={(v) => v && onChange(v)}>
        <SelectTrigger className={cn("w-full", warn)}><SelectValue placeholder={placeholder} /></SelectTrigger>
        <SelectContent>
          {cols.map((c) => <SelectItem key={c.name} value={c.name}>{c.name}</SelectItem>)}
        </SelectContent>
      </Select>
    );
  };

  // ── render ──────────────────────────────────────────────────

  if (!isLanguageLoaded) {
    return <div className="max-w-6xl mx-auto py-8 px-6">{translate(COMMON.loading)}</div>;
  }

  const virtualDatasets = datasets.filter((d) => d.sourceType === "virtual");
  // The opened definition's own row, for the sharing chips below: the list response
  // already carries isShared / isOwn / userName, so the page states who shared it
  // rather than re-deriving anything.
  const openedRow = editingId ? datasets.find((d) => d.id === editingId) : undefined;
  const pickedKeys = Object.keys(picked);

  return (
    <div className="max-w-6xl mx-auto space-y-6 p-6">
      <div>
        <h1 className="text-3xl font-bold">{translate(MANUAL.title)}</h1>
        <p className="text-sm text-muted-foreground mt-1">{translate(MANUAL.intro)}</p>
      </div>

      {materializeFailure && (
        <div className="rounded-md border border-amber-300 bg-amber-50 px-3 py-2 dark:border-amber-800 dark:bg-amber-950/40">
          <p className="text-sm text-amber-900 dark:text-amber-200">
            {translate(MANUAL.materialize_failed)} <span className="font-mono text-xs">{materializeFailure.message}</span>
          </p>
          <Button
            variant="outline"
            size="sm"
            className="mt-2 h-7"
            onClick={retryMaterialise}
            disabled={busy === "retry"}
          >
            {busy === "retry" ? <Loader2 className="size-3.5 animate-spin me-1" /> : null}
            {translate(MANUAL.materialize_retry)}
          </Button>
        </div>
      )}

      {errorMessage && (
        <div className="p-3 bg-red-50 border border-red-200 rounded-md text-red-800 text-sm flex items-start justify-between gap-3">
          <span>{errorMessage}</span>
          <button type="button" onClick={() => setErrorMessage(null)} className="text-red-600 hover:text-red-800">&times;</button>
        </div>
      )}
      {notice && (
        <div className="p-3 bg-green-50 border border-green-200 rounded-md text-green-800 text-sm flex items-start justify-between gap-3">
          <span>{notice}</span>
          <button type="button" onClick={() => setNotice(null)} className="text-green-600 hover:text-green-800">&times;</button>
        </div>
      )}
      {/* The sharing of the open definition, stated where the page says it is open: the
          list response carries isShared / isOwn / userName, so nothing is re-derived.
          A row of its own rather than inside the dismissible notice, so it stays. */}
      {openedRow && (openedRow.isShared === true || (!openedRow.isOwn && openedRow.userName)) && (
        <div className="flex items-center gap-2">
          {openedRow.isShared === true && (
            <span className="text-xs bg-green-100 text-green-800 px-1.5 py-0.5 rounded flex items-center gap-1">
              <Users className="h-3 w-3" />
              {translate(DATASETS.shared_badge)}
            </span>
          )}
          {!openedRow.isOwn && openedRow.userName && (
            <span className="text-xs text-muted-foreground">
              {translate(DATASETS.by_label)} {openedRow.userName}
            </span>
          )}
        </div>
      )}
      <Card>
        <CardContent className="py-4 flex flex-col sm:flex-row sm:items-end gap-3">
          <div className="flex-1 space-y-2">
            <Label>{translate(MANUAL.open_label)}</Label>
            {virtualDatasets.length === 0 ? (
              <p className="text-sm text-muted-foreground">{translate(MANUAL.open_none)}</p>
            ) : (
              <Select value={editingId ?? ""} onValueChange={(v) => v && openExisting(v)}>
                <SelectTrigger className="w-full">
                  <SelectValue placeholder={translate(MANUAL.open_label)}>
                    {(value: string) => virtualDatasets.find((d) => d.id === value)?.name ?? value}
                  </SelectValue>
                </SelectTrigger>
                <SelectContent>
                  {virtualDatasets.map((d) => (
                    <SelectItem key={d.id} value={d.id}>
                      {d.name}
                      {d.isShared === true && (
                        <span className="text-xs bg-green-100 text-green-800 px-1.5 py-0.5 rounded flex items-center gap-1">
                          <Users className="h-3 w-3" />
                          {translate(DATASETS.shared_badge)}
                        </span>
                      )}
                      {!d.isOwn && d.userName && (
                        <span className="text-xs text-muted-foreground">
                          {translate(DATASETS.by_label)} {d.userName}
                        </span>
                      )}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            )}
          </div>
          <Button variant="outline" onClick={resetAll}>{translate(MANUAL.new_dataset)}</Button>
        </CardContent>
      </Card>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* the tree */}
        <SourceTree
          ref={tree}
          columns={columnsByKey}
          presetColumns={presetColumns}
          ticked={ticked}
          onToggleColumn={toggleColumn}
          onColumnsRead={(key, cols) => setColumnsByKey((s) => ({ ...s, [key]: cols }))}
          onDatasetsLoaded={setDatasets}
          onError={setErrorMessage}
        />

        {/* joins, output, preview */}
        <div className="space-y-6">
          <Card>
            <CardHeader>
              <CardTitle className="text-base">{translate(MANUAL.joins_title)}</CardTitle>
              <CardDescription>{translate(MANUAL.joins_hint)}</CardDescription>
            </CardHeader>
            <CardContent className="space-y-3">
              {unattachedAliases().length > 0 && (
                <p className="text-xs text-amber-700">
                  {translate(MANUAL.unattached_sources).replace("{sources}", describeAliases(unattachedAliases()))}
                </p>
              )}
              {joins.some((j) => !j.left || !j.right || !j.leftCol || !j.rightCol) && (
                <p className="text-xs text-amber-700">{translate(MANUAL.incomplete_join)}</p>
              )}
              {joins.map((j, i) => {
                const unfinished = !j.left || !j.right || !j.leftCol || !j.rightCol;
                return (
                <div
                  key={i}
                  className={cn(
                    "space-y-2 rounded-md border p-2",
                    unfinished ? "border-amber-300 bg-amber-50/40" : "border-border",
                  )}
                >
                  <div className="grid grid-cols-2 gap-2">
                    <Select value={j.left} onValueChange={(v) => v && updateJoin(i, { left: v })}>
                      <SelectTrigger className="w-full"><SelectValue>{sourceLabel(j.left)}</SelectValue></SelectTrigger>
                      <SelectContent>
                        {aliases.map((a) => <SelectItem key={a} value={a}>{sourceLabel(a)}</SelectItem>)}
                      </SelectContent>
                    </Select>
                    {columnSelect(keyForAlias(j.left), j.leftCol, (v) => updateJoin(i, { leftCol: v }), translate(MANUAL.column_placeholder), !j.leftCol)}
                    <Select value={j.right} onValueChange={(v) => v && updateJoin(i, { right: v })}>
                      <SelectTrigger className="w-full"><SelectValue>{sourceLabel(j.right)}</SelectValue></SelectTrigger>
                      <SelectContent>
                        {aliases.map((a) => <SelectItem key={a} value={a}>{sourceLabel(a)}</SelectItem>)}
                      </SelectContent>
                    </Select>
                    {columnSelect(keyForAlias(j.right), j.rightCol, (v) => updateJoin(i, { rightCol: v }), translate(MANUAL.column_placeholder), !j.rightCol)}
                    <Select value={j.type} onValueChange={(v) => v && updateJoin(i, { type: v })}>
                      <SelectTrigger className="w-full"><SelectValue>{j.type}</SelectValue></SelectTrigger>
                      <SelectContent>
                        {JOIN_TYPES.map((t) => <SelectItem key={t} value={t}>{t}</SelectItem>)}
                      </SelectContent>
                    </Select>
                    <Button variant="outline" size="sm" onClick={() => setJoins((rows) => rows.filter((_, x) => x !== i))}>
                      <X className="size-3.5 me-1" />{translate(MANUAL.remove_join)}
                    </Button>
                  </div>
                </div>
                );
              })}

              {suggestions.map((s, i) => (
                <div key={i} className="flex items-center gap-2 text-sm">
                  <span className="text-xs px-2 py-0.5 rounded-full bg-muted text-muted-foreground shrink-0">
                    {translate(s.bridge ? MANUAL.bridge : MANUAL.suggested)}
                  </span>
                  <span dir="ltr" className="truncate font-mono text-xs">
                    {s.columnsKnown
                      ? `${s.left}.${s.leftCol} = ${s.right}.${s.rightCol}`
                      : `${s.left} ⋈ ${s.right}`}
                  </span>
                  {!s.columnsKnown && (
                    <span className="text-xs text-muted-foreground truncate">
                      {s.columnsRead ? translate(MANUAL.bridge_choose_columns) : translate(MANUAL.bridge_no_columns)}
                    </span>
                  )}
                  <Button variant="outline" size="sm" className="ms-auto shrink-0" onClick={() => applyJoinSuggestion(s)}>
                    {s.fills ? translate(MANUAL.complete_join) : translate(MANUAL.add_join)}
                  </Button>
                </div>
              ))}

              <Button variant="outline" size="sm" onClick={() => addJoin()}>
                <Plus className="size-3.5 me-1" />{translate(MANUAL.add_join)}
              </Button>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle className="text-base">{translate(MANUAL.output_title)}</CardTitle>
              <CardDescription>{translate(MANUAL.output_hint)}</CardDescription>
            </CardHeader>
            <CardContent className="space-y-2">
              {output.length === 0 && <p className="text-sm text-muted-foreground">{translate(MANUAL.need_columns)}</p>}
              {output.map((entry, i) => (
                <div key={`${entry.source}.${entry.column}.${i}`} className="flex items-center gap-2 text-sm">
                  <span className="font-mono text-xs truncate" dir="ltr">{`${entry.source}.${entry.column}`}</span>
                  {"aggregation" in entry && (
                    <span className="text-xs text-muted-foreground shrink-0" dir="ltr">{String(entry.aggregation)}</span>
                  )}
                  <span className="ms-auto flex items-center gap-1 shrink-0">
                    <Button variant="outline" size="sm" aria-label={translate(MANUAL.move_up)} onClick={() => moveColumn(i, -1)}>
                      <ChevronUp className="size-3.5" />
                    </Button>
                    <Button variant="outline" size="sm" aria-label={translate(MANUAL.move_down)} onClick={() => moveColumn(i, 1)}>
                      <ChevronDown className="size-3.5" />
                    </Button>
                    <Button variant="outline" size="sm" aria-label={translate(MANUAL.remove)} onClick={() => removeOutput(i)}>
                      <X className="size-3.5" />
                    </Button>
                  </span>
                </div>
              ))}
              {output.some((e) => "aggregation" in e) && (
                <p className="text-xs text-muted-foreground">{translate(MANUAL.aggregation_note)}</p>
              )}
            </CardContent>
          </Card>

          <Card>
            <CardHeader><CardTitle className="text-base">{translate(VIRTUAL.preview_title)}</CardTitle></CardHeader>
            <CardContent className="space-y-3">
              {preview && preview.columns.length > 0 && (
                <div className="overflow-x-auto max-h-64">
                  <table className="w-full text-xs">
                    <thead>
                      <tr>{preview.columns.map((c) => (
                        <th key={c} className="text-start px-2 py-1 border-b border-border" dir="ltr">{c}</th>
                      ))}</tr>
                    </thead>
                    <tbody>
                      {preview.rows.map((r, i) => (
                        <tr key={i}>{r.map((cell, x) => (
                          <td key={x} className="px-2 py-1 border-b border-border" dir="ltr"><DataValue value={String(cell ?? "—")} /></td>
                        ))}</tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
              <p className="text-xs text-muted-foreground">{translate(MANUAL.test_pulls_every_source)}</p>
            </CardContent>
          </Card>
        </div>
      </div>

      {/* name, description, aliases, actions */}
      <Card>
        <CardContent className="py-4 space-y-4">
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div className="space-y-2">
              <Label>{translate(MANUAL.name_label)}</Label>
              <Input value={name} onChange={(e) => setName(e.target.value)} className="h-8" />
            </div>
            <div className="space-y-2">
              <Label>{translate(MANUAL.description_label)}</Label>
              <Input value={description} onChange={(e) => setDescription(e.target.value)} className="h-8" />
            </div>
          </div>

          <div className="flex items-center gap-3">
            <Switch checked={materialized} onCheckedChange={setMaterialized} />
            <div>
              <Label>{translate(MANUAL.materialized_label)}</Label>
              <p className="text-xs text-muted-foreground">{translate(MANUAL.materialized_hint)}</p>
            </div>
          </div>

          {pickedKeys.length > 0 && (
            <div className="space-y-2">
              {pickedKeys.map((key) => (
                <div key={key} className="flex items-center gap-2 text-sm">
                  <span className="text-muted-foreground truncate">{picked[key].label}</span>
                  <Input
                    dir="ltr"
                    value={picked[key].alias}
                    onChange={(e) => renameAlias(key, e.target.value)}
                    className="h-7 w-24 ms-auto"
                    aria-label={translate(MANUAL.alias_label)}
                  />
                </div>
              ))}
            </div>
          )}

          {/* The refusal, beside the button that caused it — a banner at the top of
              this page is scrolled away by the time the reader presses Save. */}
          {actionError && (
            <div className="p-3 bg-red-50 border border-red-200 rounded-md text-red-800 text-sm flex items-start justify-between gap-3">
              <span>{actionError}</span>
              <button type="button" onClick={() => setActionError(null)} className="text-red-600 hover:text-red-800">&times;</button>
            </div>
          )}
          {validationErrors.length > 0 && (
            <div className="p-3 bg-amber-50 border border-amber-200 rounded-md text-amber-800 text-sm">
              <p className="font-medium">{translate(MANUAL.validate_errors)}</p>
              <ul className="list-disc ms-5 mt-1">
                {validationErrors.map((e, i) => <li key={i}>{e}</li>)}
              </ul>
            </div>
          )}

          <div className="flex flex-wrap gap-3">
            <Button variant="outline" onClick={handleValidate}>
              {busy === "validate" ? translate(COMMON.loading) : translate(MANUAL.validate)}
            </Button>
            <Button variant="outline" onClick={handleTestJoin}>
              {busy === "preview" ? translate(COMMON.loading) : translate(MANUAL.test_join)}
            </Button>
            <Button onClick={handleSave}>
              {busy === "save" ? translate(COMMON.saving) : (editingId ? translate(MANUAL.update_dataset) : translate(COMMON.save))}
            </Button>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
