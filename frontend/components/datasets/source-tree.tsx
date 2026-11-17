// components/datasets/source-tree.tsx
// ============================================================
// SOURCE TREE — the data-source panel, as a component.
//
// Moved out of app/datasets/virtual/manual/page.tsx (plan Item 13) so the AI
// virtual-dataset page can mount the same panel rather than imitate it
// (Item 14). A move, not a rewrite: the markup, the two endpoints and the
// loading rules below are the manual page's own.
//
// Three behaviours carried over unchanged:
//
//  1. The tree loads lazily: expanding a connection or a dataset issues a real
//     query against it, and nothing is read until it is expanded.
//  2. The top-level filter narrows only the top level — the connections and the
//     datasets — and never hides a table or a column. Once a source is visible,
//     everything inside it stays reachable.
//  3. Columns read here are published to the caller, not held privately: the
//     caller's join matcher scores against them, so it needs the same lists.
//     `columns` is therefore the caller's cache and this component renders from
//     it, rather than keeping a copy that could disagree with the caller's.
// ============================================================

"use client";

import { useCallback, useEffect, useImperativeHandle, useRef, useState, type Ref } from "react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { apiFetch } from "@/lib/api";
import { useTranslation } from "@/lib/translation-context";
import { useTranslate, getErrorMessageFromData, type TranslationKey } from "@/lib/translation-helpers";
import { COMMON } from "@/app/common/translations";
import { DATASETS } from "@/app/datasets/translations";
import { BROWSE } from "@/app/datasets/browse/translations";
import { SOURCE_TREE, SOURCE_PANEL } from "@/components/datasets/translations";
import { ChevronDown, ChevronRight, Filter, CalendarDays, Hash, PanelRightClose } from "lucide-react";

// ── types ────────────────────────────────────────────────────

export type ColumnInfo = {
  name: string;
  type?: string;
  // Column kinds, from whichever route filled the list. Both routes carry them:
  // the browse route computes them from the driver's own type name, and the
  // dataset-schema route already returned them.
  isNumeric?: boolean;
  isDatetime?: boolean;
};
export type TableInfo = { name: string; type?: string };

export type AvailableConnection = { id?: string; connectionId?: number; name?: string; type?: string };
export type DatasetRow = {
  id: string; name: string; sourceType?: string; sourceOrigin?: string; storageType?: string;
  tableName?: string; isOwn?: boolean; isShared?: boolean; userName?: string | null;
};

// A source the caller has ticked a column from (or one loaded from a definition).
export type PickedSource = {
  alias: string;
  kind: "connection" | "dataset";
  connectionId?: number;
  tableName?: string;
  storageType?: string;
  datasetId?: string;
  label: string;
};

// ── keys and classification ─────────────────────────────────

// The tree's top-level filter. It narrows only the top level — the connections
// and the datasets — and never hides a table or a column: once a source is
// visible, everything inside it stays reachable. Values are the category strings
// `datasetCategory` returns (singular, as sourceType spells them); the labels
// reuse the declarations the /datasets/manage filter already uses.
const SOURCE_FILTERS = [
  { value: "all", label: DATASETS.filter.all },
  { value: "connections", label: BROWSE.connections },
  { value: "virtual", label: DATASETS.filter.virtual },
  { value: "upload", label: DATASETS.filter.uploads },
  { value: "notebook", label: DATASETS.filter.notebooks },
  { value: "postgresql", label: DATASETS.filter.postgresql },
  { value: "mysql", label: DATASETS.filter.mysql },
  { value: "mssql", label: DATASETS.filter.mssql },
  { value: "access", label: DATASETS.filter.access },
];

// Which category a dataset belongs to — the same mapping /datasets/manage uses,
// so a dataset is filed the same way in both places.
const datasetCategory = (ds: DatasetRow): string => {
  const key = ds.sourceOrigin || ds.sourceType || "";
  if (key === "table" || key === "view") return ds.storageType || "postgresql";
  return key;
};

// A source key names one table or one dataset, and is what the tree toggles on.
export const connectionKey = (connectionId: number, tableName: string) => `c${connectionId}:${tableName}`;
export const datasetKey = (datasetId: string) => `d${datasetId}`;
const connectionNodeKey = (connectionId: number) => `conn:${connectionId}`;

// ── the component ───────────────────────────────────────────

export type SourceTreeProps = {
  /** The caller's column cache — this component renders from it and publishes into it. */
  columns: Record<string, ColumnInfo[]>;
  /** Columns a saved definition names, shown until the real list has been read. */
  presetColumns: Record<string, ColumnInfo[]>;
  /** Which columns are in the caller's output: `${sourceKey}::${column}` → true. */
  ticked: Record<string, boolean>;
  /** A column was ticked or unticked. `make` builds the source entry for a key not yet picked. */
  onToggleColumn: (key: string, column: string, make: (alias: string) => PickedSource) => void;
  /** A column list was read. The caller keeps it so its join matcher can score against it. */
  onColumnsRead: (key: string, columns: ColumnInfo[]) => void;
  /** The dataset list was read or re-read, for a caller that also lists datasets itself. */
  onDatasetsLoaded: (datasets: DatasetRow[]) => void;
  /**
   * A read failed, or a new one started. The caller owns the banner; the tree only
   * reports — and reports `null` when a read begins, so an error from a previous
   * read does not outlive it. Without that, a failure on one connection stayed on
   * screen while another connection expanded normally beneath it.
   */
  onError: (message: string | null) => void;
  /**
   * Whether a column can be ticked. Default true — the manual editor's tree.
   * False on the AI page, where a tick would have to write the draft and no
   * endpoint applies one; a checkbox that recorded nothing would be worse than
   * no checkbox, because it would look like it had decided something.
   */
  selectable?: boolean;
  /**
   * Fill the height it is given instead of capping the list at 32rem — what a
   * docked panel wants, and what the manual editor's half-width card does not.
   */
  docked?: boolean;
  /** Given, the panel renders a collapse control in its own header (design §9.4). */
  onCollapse?: () => void;
};

export type SourceTreeHandle = {
  /** Open the nodes a definition's sources sit on, read what they hang from, reveal the first. */
  openSources: (sources: PickedSource[]) => void;
  /** Read a source's columns, unless they are already read or being read. */
  loadColumns: (key: string) => void;
  /** Re-read the dataset list — after a save, so a new dataset appears in the tree. */
  refreshDatasets: () => void;
};

export function SourceTree({
  ref,
  columns,
  presetColumns,
  ticked,
  onToggleColumn,
  onColumnsRead,
  onDatasetsLoaded,
  onError,
  selectable = true,
  docked = false,
  onCollapse,
}: SourceTreeProps & { ref?: Ref<SourceTreeHandle> }) {
  const { isLanguageLoaded } = useTranslation();
  const translate = useTranslate();

  const [connections, setConnections] = useState<AvailableConnection[]>([]);
  const [datasets, setDatasets] = useState<DatasetRow[]>([]);
  const [treeLoading, setTreeLoading] = useState(true);
  const [sourceFilter, setSourceFilter] = useState("all");
  const [expanded, setExpanded] = useState<Record<string, boolean>>({});
  const [tablesByConnection, setTablesByConnection] = useState<Record<number, TableInfo[]>>({});
  const [loadingKey, setLoadingKey] = useState<Record<string, boolean>>({});
  // The tree holds every connection and every dataset the account has, so the row
  // a definition's source sits on can be open and still below the visible part of
  // the box; revealKey is the row to bring into view once a definition is loaded.
  //
  // A ref rather than state, because the reveal is a one-shot: clearing state from
  // inside the effect that reads it is a cascading render (eslint
  // react-hooks/set-state-in-effect, which the page carried twice before the move).
  // The expanded map is what re-renders the tree, and it changes on every call.
  const revealKey = useRef<string | null>(null);
  const treeRef = useRef<HTMLDivElement | null>(null);

  // ── the two lists the tree is built from ────────────────────

  const refreshDatasets = useCallback(async () => {
    const res = await apiFetch("/api/datasets");
    if (res.ok) {
      const rows: DatasetRow[] = (await res.json()).datasets || [];
      setDatasets(rows);
      onDatasetsLoaded(rows);
    }
  }, [onDatasetsLoaded]);

  useEffect(() => {
    if (!isLanguageLoaded) return;
    let cancelled = false;
    (async () => {
      try {
        const [connRes, dsRes] = await Promise.all([
          apiFetch("/api/user/database-connections/available"),
          apiFetch("/api/datasets"),
        ]);
        if (cancelled) return;
        if (connRes.ok) setConnections((await connRes.json()).connections || []);
        if (dsRes.ok) {
          const rows: DatasetRow[] = (await dsRes.json()).datasets || [];
          setDatasets(rows);
          onDatasetsLoaded(rows);
        }
      } catch {
        if (!cancelled) onError(translate(SOURCE_TREE.no_sources));
      } finally {
        if (!cancelled) setTreeLoading(false);
      }
    })();
    return () => { cancelled = true; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isLanguageLoaded]);

  // ── lazy loading ────────────────────────────────────────────

  // Report the server's own sentence when it sent one, and the translated
  // fallback only when it did not. The 500 body carries a `detail` naming the
  // cause — `password authentication failed for user "localadmin"`, or a host
  // that does not resolve — and replacing it with "The tables could not be read"
  // is what made two unrelated faults look like one, and neither look fixable.
  const reportFailure = async (res: Response | null, fallback: TranslationKey) => {
    if (!res) {
      onError(translate(fallback));
      return;
    }
    let data: unknown = null;
    try { data = await res.json(); } catch { /* not JSON — keep the fallback */ }
    onError(getErrorMessageFromData(translate, data, fallback));
  };

  const loadTables = async (connectionId: number) => {
    if (tablesByConnection[connectionId] || loadingKey[connectionNodeKey(connectionId)]) return;
    onError(null);
    setLoadingKey((s) => ({ ...s, [connectionNodeKey(connectionId)]: true }));
    let res: Response | null = null;
    try {
      res = await apiFetch(`/api/datasets/browse/${connectionId}`);
      if (!res.ok) {
        await reportFailure(res, SOURCE_TREE.tables_error);
        return;
      }
      const data = await res.json();
      setTablesByConnection((s) => ({ ...s, [connectionId]: data.tables || [] }));
    } catch {
      await reportFailure(res, SOURCE_TREE.tables_error);
    } finally {
      setLoadingKey((s) => ({ ...s, [connectionNodeKey(connectionId)]: false }));
    }
  };

  const loadColumns = async (key: string) => {
    if (columns[key] || loadingKey[key]) return;
    onError(null);
    setLoadingKey((s) => ({ ...s, [key]: true }));
    let res: Response | null = null;
    try {
      const path = key.startsWith("c")
        ? (() => {
            const rest = key.slice(1);
            const cut = rest.indexOf(":");
            return `/api/datasets/browse/${rest.slice(0, cut)}/${encodeURIComponent(rest.slice(cut + 1))}/columns`;
          })()
        : `/api/datasets/${key.slice(1)}/schema`;
      res = await apiFetch(path);
      if (!res.ok) {
        await reportFailure(res, SOURCE_TREE.columns_error);
        return;
      }
      const data = await res.json();
      const cols: ColumnInfo[] = (data.columns || []).map(
        (c: { name: string; type?: string; dtype?: string; is_numeric?: boolean; is_datetime?: boolean }) => ({
          name: c.name,
          // A column's SQL type is `type` on the browse route and `dtype` on the
          // dataset-schema route (docs/code-quirks.md, 2026-09-24).
          type: c.type ?? c.dtype,
          // Both kinds come from the server, which knows the driver's own type
          // name. Deriving them here from the display string would be a second
          // home for the classification.
          isNumeric: c.is_numeric === true,
          isDatetime: c.is_datetime === true,
        }),
      );
      onColumnsRead(key, cols);
    } catch {
      await reportFailure(res, SOURCE_TREE.columns_error);
    } finally {
      setLoadingKey((s) => ({ ...s, [key]: false }));
    }
  };

  const columnsFor = (key: string): ColumnInfo[] => columns[key] || presetColumns[key] || [];

  const toggleExpand = (key: string) => {
    const opening = !expanded[key];
    setExpanded((s) => ({ ...s, [key]: opening }));
    if (!opening) return;
    if (key.startsWith("conn:")) void loadTables(Number(key.slice(5)));
    else void loadColumns(key);
  };

  // ── opening a saved definition ──────────────────────────────

  // Every source the definition names is opened, so a definition that has just
  // been loaded shows what it reads from instead of leaving it buried in the
  // tree. The node's columns come from presetColumns until the tree reads the
  // table, so the ticked ones are visible immediately.
  //
  // A source read through a connection hangs from that connection's row, and
  // that row draws only the tables it has read — so the connection is opened
  // and its table list read too, or the picked row would have nothing to sit
  // under.
  const openSources = (sources: PickedSource[]) => {
    // The reveal can only find a row the tree is rendering, and the filter is the
    // user's to set — so it goes back to All when a definition is opened, or a
    // definition opened while the filter hid its source's row would scroll to
    // nothing at all.
    setSourceFilter("all");
    const opened: Record<string, boolean> = {};
    const readConnections = new Set<number>();
    // The row the first source sits on, to be brought into view by the effect
    // below. For a source behind a connection that is the connection's own row:
    // it is the part of the branch that is on screen, with the table under it.
    let reveal: string | null = null;
    for (const source of sources) {
      const key = source.datasetId
        ? datasetKey(source.datasetId)
        : connectionKey(Number(source.connectionId), String(source.tableName));
      opened[key] = true;
      if (source.datasetId) {
        if (reveal === null) reveal = key;
        continue;
      }
      const connectionId = Number(source.connectionId);
      opened[connectionNodeKey(connectionId)] = true;
      if (reveal === null) reveal = connectionNodeKey(connectionId);
      // One read per connection: the table list belongs to the connection, and
      // several sources habitually name tables of the same one. loadTables'
      // own guard cannot see a state update made in this same tick.
      if (!readConnections.has(connectionId)) {
        readConnections.add(connectionId);
        void loadTables(connectionId);
      }
    }
    setExpanded(opened);
    revealKey.current = reveal;
  };

  // Bring the row that revealKey names into view, once the tree has re-rendered
  // with the definition's sources open. The box is scrolled by hand rather than
  // with scrollIntoView, which would drag the page itself to the row as well.
  // Runs on the expanded map — the render the reveal depends on — and clears the
  // ref so a later expand does not scroll again.
  useEffect(() => {
    const wanted = revealKey.current;
    if (!wanted) return;
    revealKey.current = null;
    const container = treeRef.current;
    const target = container
      ? Array.from(container.querySelectorAll<HTMLElement>("[data-node-key]"))
          .find((el) => el.dataset.nodeKey === wanted)
      : undefined;
    if (container && target) {
      container.scrollTop += target.getBoundingClientRect().top - container.getBoundingClientRect().top;
    }
  }, [expanded]);

  useImperativeHandle(ref, () => ({ openSources, loadColumns, refreshDatasets }));

  // ── render helpers ──────────────────────────────────────────

  const nodeHeader = (key: string, label: string, sub?: string) => (
    <button
      type="button"
      onClick={() => toggleExpand(key)}
      className="flex w-full items-center gap-1.5 text-sm text-start hover:text-foreground"
    >
      {expanded[key] ? <ChevronDown className="size-3.5 shrink-0" /> : <ChevronRight className="size-3.5 shrink-0" />}
      <span className="truncate">{label}</span>
      {sub && <span className="text-xs text-muted-foreground ms-auto shrink-0">{sub}</span>}
    </button>
  );

  const renderColumns = (key: string, make: (alias: string) => PickedSource) => {
    if (loadingKey[key]) {
      return <p className="text-xs text-muted-foreground px-2 py-1">{translate(SOURCE_TREE.loading_columns)}</p>;
    }
    const cols = columnsFor(key);
    if (cols.length === 0) return null;
    const all = cols.every((c) => ticked[`${key}::${c.name}`]);
    const some = cols.some((c) => ticked[`${key}::${c.name}`]);
    const selectAll = (target: boolean) => {
      for (const c of cols) {
        if (Boolean(ticked[`${key}::${c.name}`]) !== target) onToggleColumn(key, c.name, make);
      }
    };
    // The kind glyph sits beside the name and does nothing but say what the
    // column is (design §9.4.3): a datetime column stays selectable for someone
    // who wants it as a text value, so this annotates and never filters.
    const kindGlyph = (c: ColumnInfo) => {
      if (c.isDatetime) {
        return <CalendarDays className="size-3 shrink-0 text-muted-foreground" aria-hidden="true" />;
      }
      if (c.isNumeric) {
        return <Hash className="size-3 shrink-0 text-muted-foreground" aria-hidden="true" />;
      }
      return null;
    };
    return (
      <div className="ps-6 py-1 space-y-1">
        {selectable && (
          <div className="flex items-center gap-2 pb-1">
            <Checkbox checked={all} indeterminate={!all && some} onCheckedChange={() => selectAll(!all)} />
            <button
              type="button"
              className="text-xs text-muted-foreground hover:text-foreground underline"
              onClick={() => selectAll(!all)}
            >
              {all ? translate(SOURCE_TREE.select_none) : translate(SOURCE_TREE.select_all)}
            </button>
          </div>
        )}
        {cols.map((c) =>
          selectable ? (
            <label key={c.name} className="flex items-center gap-2 text-sm cursor-pointer">
              <Checkbox
                checked={Boolean(ticked[`${key}::${c.name}`])}
                onCheckedChange={() => onToggleColumn(key, c.name, make)}
              />
              {kindGlyph(c)}
              <span className="truncate">{c.name}</span>
              {c.type && <span className="text-xs text-muted-foreground ms-auto shrink-0">{c.type}</span>}
            </label>
          ) : (
            <div key={c.name} className="flex items-center gap-2 text-sm">
              {kindGlyph(c)}
              <span className="truncate">{c.name}</span>
              {c.type && <span className="text-xs text-muted-foreground ms-auto shrink-0">{c.type}</span>}
            </div>
          ),
        )}
      </div>
    );
  };

  // ── render ──────────────────────────────────────────────────

  // The filter, applied to the top level only.
  const visibleConnections = sourceFilter === "all" || sourceFilter === "connections" ? connections : [];
  const visibleDatasets = sourceFilter === "all"
    ? datasets
    : datasets.filter((d) => datasetCategory(d) === sourceFilter);
  const nothingAtAll = connections.length === 0 && datasets.length === 0;
  const nothingVisible = !nothingAtAll && visibleConnections.length === 0 && visibleDatasets.length === 0;

  return (
    <Card className={docked ? "h-full flex flex-col min-h-0" : undefined}>
      {/* Docked, the heading takes the panel's full width and the controls sit on the
          line below it. In a 280-380px column a row puts the title beside a 160px
          filter and a 32px button, which squeezes "Where the data comes from" into a
          narrow column and wraps it. The manual editor's card is half of a wide
          two-column page, where the row is right and stays. */}
      <CardHeader
        className={
          docked
            ? "flex flex-col items-stretch gap-2 space-y-0"
            : "flex flex-row items-start justify-between space-y-0 gap-3"
        }
      >
        <div className="space-y-1 min-w-0">
          <CardTitle className="text-base">{translate(SOURCE_TREE.sources_title)}</CardTitle>
          <CardDescription>{translate(SOURCE_TREE.sources_hint)}</CardDescription>
        </div>
        <div className="flex items-center gap-2 shrink-0">
          <Filter className="h-4 w-4 text-muted-foreground" />
          <Select value={sourceFilter} onValueChange={(v) => v && setSourceFilter(v)}>
            <SelectTrigger className="w-40">
              <SelectValue>
                {(value: string) => {
                  const chosen = SOURCE_FILTERS.find((f) => f.value === value);
                  return chosen ? translate(chosen.label) : translate(DATASETS.filter.all);
                }}
              </SelectValue>
            </SelectTrigger>
            <SelectContent alignItemWithTrigger={false}>
              {SOURCE_FILTERS.map((f) => (
                <SelectItem key={f.value} value={f.value}>{translate(f.label)}</SelectItem>
              ))}
            </SelectContent>
          </Select>
          {onCollapse && (
            <Button
              variant="ghost"
              size="icon"
              className="h-8 w-8 shrink-0"
              onClick={onCollapse}
              aria-label={translate(SOURCE_PANEL.collapse)}
            >
              <PanelRightClose className="h-4 w-4" />
            </Button>
          )}
        </div>
      </CardHeader>
      <CardContent
        ref={treeRef}
        className={docked ? "space-y-3 flex-1 min-h-0 overflow-y-auto" : "space-y-3 max-h-[32rem] overflow-y-auto"}
      >
        {treeLoading && <p className="text-sm text-muted-foreground">{translate(COMMON.loading)}</p>}
        {!treeLoading && nothingAtAll && (
          <p className="text-sm text-muted-foreground">{translate(SOURCE_TREE.no_sources)}</p>
        )}
        {!treeLoading && nothingVisible && (
          <p className="text-sm text-muted-foreground">{translate(SOURCE_TREE.no_match)}</p>
        )}

        {visibleConnections.map((conn) => {
          const connId = Number(conn.connectionId ?? conn.id);
          const nodeKey = connectionNodeKey(connId);
          return (
            <div key={nodeKey} data-node-key={nodeKey} className="border-b border-border pb-2 last:border-0">
              {nodeHeader(nodeKey, conn.name || String(connId), conn.type)}
              {expanded[nodeKey] && loadingKey[nodeKey] && (
                <p className="text-xs text-muted-foreground ps-4 py-1">{translate(COMMON.loading)}</p>
              )}
              {expanded[nodeKey] && (tablesByConnection[connId] || []).map((t) => {
                const key = connectionKey(connId, t.name);
                return (
                  <div key={key} className="ps-4 mt-1">
                    {nodeHeader(key, t.name)}
                    {expanded[key] && renderColumns(key, (alias) => ({
                      alias, kind: "connection", connectionId: connId, tableName: t.name,
                      storageType: conn.type, label: `${conn.name || connId} · ${t.name}`,
                    }))}
                  </div>
                );
              })}
            </div>
          );
        })}

        {visibleDatasets.map((ds) => {
          const key = datasetKey(ds.id);
          return (
            <div key={key} data-node-key={key} className="border-b border-border pb-2 last:border-0">
              {nodeHeader(key, ds.name, ds.sourceType)}
              {expanded[key] && renderColumns(key, (alias) => ({
                alias, kind: "dataset", datasetId: ds.id, storageType: ds.storageType,
                tableName: ds.tableName, label: ds.name,
              }))}
            </div>
          );
        })}
      </CardContent>
    </Card>
  );
}
