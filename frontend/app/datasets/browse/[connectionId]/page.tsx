"use client";

import { useState, useEffect } from "react";
import { useParams, useRouter } from "next/navigation";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { ProtectedRoute } from "@/components/protected-route";
import { Table2, ArrowLeft, Loader2, Database } from "lucide-react";
import { useTranslate } from "@/lib/translation-helpers";
import { apiFetch } from "@/lib/api";
import { BROWSE } from "../translations";

interface TableInfo {
  name: string;
  type: string;
}

interface ColumnInfo {
  name: string;
  type: string;
  nullable: boolean;
}

function BrowseContent() {
  const params = useParams();
  const router = useRouter();
  const translate = useTranslate();
  const connectionId = params.connectionId as string;

  const [tables, setTables] = useState<TableInfo[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedTable, setSelectedTable] = useState<string | null>(null);
  const [columns, setColumns] = useState<ColumnInfo[]>([]);
  const [loadingCols, setLoadingCols] = useState(false);
  const [previewRows, setPreviewRows] = useState<any[] | null>(null);
  const [previewCols, setPreviewCols] = useState<string[]>([]);
  const [loadingPreview, setLoadingPreview] = useState(false);

  const apiBase = `/api/datasets/browse/${connectionId}`;

  useEffect(() => {
    (async () => {
      try {
        const r = await apiFetch(apiBase);
        if (!r.ok) {
          let msg = translate(BROWSE.load_tables_error);
          try {
            const errData = await r.json();
            if (errData.detail) msg = typeof errData.detail === "string" ? errData.detail : JSON.stringify(errData.detail);
          } catch { /* use default */ }
          throw new Error(msg);
        }
        const data = await r.json();
        setTables(data.tables || []);
      } catch (e: any) {
        setError(e.message);
      } finally {
        setLoading(false);
      }
    })();
  }, [apiBase]);

  const loadColumns = async (tableName: string) => {
    setSelectedTable(tableName);
    setColumns([]);
    setPreviewRows(null);
    setLoadingCols(true);
    try {
      const r = await apiFetch(`${apiBase}/${tableName}/columns`);
      const data = await r.json();
      setColumns(data.columns || []);
    } catch {
      setError(translate(BROWSE.load_columns_error));
    } finally {
      setLoadingCols(false);
    }
  };

  const loadPreview = async (tableName: string) => {
    setLoadingPreview(true);
    try {
      const r = await apiFetch(`${apiBase}/${tableName}/preview?limit=100`);
      const data = await r.json();
      setPreviewCols(data.columns || []);
      setPreviewRows(data.rows || []);
    } catch {
      setError(translate(BROWSE.load_preview_error));
    } finally {
      setLoadingPreview(false);
    }
  };

  if (loading) {
    return (
      <div className="flex justify-center py-20">
        <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
      </div>
    );
  }

  if (error) {
    return (
      <div className="max-w-2xl mx-auto py-12">
        <Card className="border-red-200">
          <CardContent className="py-8 text-center">
            <p className="text-red-600">{error}</p>
            <Button variant="outline" className="mt-4" onClick={() => router.back()}>
              <ArrowLeft className="h-4 w-4 me-2" />
              {translate(BROWSE.back)}
            </Button>
          </CardContent>
        </Card>
      </div>
    );
  }

  return (
    <div className="max-w-5xl mx-auto py-8 px-4 space-y-6">
      <div className="flex items-center gap-4">
        <Button variant="outline" size="sm" onClick={() => router.push("/settings/database")}>
          <ArrowLeft className="h-4 w-4 me-2" />
          {translate(BROWSE.connections)}
        </Button>
        <h1 className="text-xl font-bold">{translate(BROWSE.browse_tables)}</h1>
        <span className="text-sm text-muted-foreground">{translate(BROWSE.tables_count).replace("{count}", String(tables.length))}</span>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Table list */}
        <Card className="lg:col-span-1">
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium flex items-center gap-2">
              <Database className="h-4 w-4" />
              {translate(BROWSE.tables)}
            </CardTitle>
          </CardHeader>
          <CardContent className="p-0">
            <div className="divide-y max-h-[70vh] overflow-y-auto">
              {tables.map(t => (
                <button
                  key={t.name}
                  onClick={() => loadColumns(t.name)}
                  className={`w-full text-start px-4 py-2.5 text-sm hover:bg-accent transition-colors flex items-center gap-2 ${
                    selectedTable === t.name ? "bg-accent font-medium" : ""
                  }`}
                >
                  <Table2 className="h-3.5 w-3.5 text-muted-foreground shrink-0" />
                  {t.name}
                </button>
              ))}
            </div>
          </CardContent>
        </Card>

        {/* Column details + Preview */}
        <div className="lg:col-span-2 space-y-4">
          {!selectedTable && (
            <Card>
              <CardContent className="py-12 text-center text-muted-foreground">
                {translate(BROWSE.select_table_hint)}
              </CardContent>
            </Card>
          )}

          {selectedTable && (
            <>
              {/* Columns */}
              <Card>
                <CardHeader className="pb-2">
                  <CardTitle className="text-sm font-medium">
                    {translate(BROWSE.columns_title).replace("{table}", selectedTable)}
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  {loadingCols ? (
                    <Loader2 className="h-4 w-4 animate-spin" />
                  ) : (
                    <table className="w-full text-sm">
                      <thead>
                        <tr className="border-b text-start">
                          <th className="py-1.5 pe-4 font-medium text-muted-foreground">{translate(BROWSE.column)}</th>
                          <th className="py-1.5 pe-4 font-medium text-muted-foreground">{translate(BROWSE.type)}</th>
                          <th className="py-1.5 font-medium text-muted-foreground">{translate(BROWSE.nullable)}</th>
                        </tr>
                      </thead>
                      <tbody>
                        {columns.map(c => (
                          <tr key={c.name} className="border-b last:border-0">
                            <td className="py-1.5 pe-4 font-mono text-xs">{c.name}</td>
                            <td className="py-1.5 pe-4 text-xs text-muted-foreground">{c.type}</td>
                            <td className="py-1.5 text-xs text-muted-foreground">
                              {c.nullable ? "YES" : "NO"}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  )}
                </CardContent>
              </Card>

              {/* Preview */}
              <Card>
                <CardHeader className="pb-2">
                  <div className="flex items-center justify-between">
                    <CardTitle className="text-sm font-medium">{translate(BROWSE.preview)}</CardTitle>
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => loadPreview(selectedTable)}
                      disabled={loadingPreview}
                    >
                      {loadingPreview && <Loader2 className="h-3 w-3 me-1 animate-spin" />}
                      {translate(BROWSE.load_preview)}
                    </Button>
                  </div>
                </CardHeader>
                <CardContent>
                  {!previewRows && !loadingPreview && (
                    <p className="text-sm text-muted-foreground">
                      {translate(BROWSE.preview_hint)}
                    </p>
                  )}
                  {previewRows && (
                    <div className="overflow-x-auto max-h-96">
                      <table className="w-full text-xs">
                        <thead>
                          <tr className="border-b bg-muted/50">
                            {previewCols.map(c => (
                              <th key={c} className="py-1.5 px-2 text-start font-mono font-medium whitespace-nowrap">
                                {c}
                              </th>
                            ))}
                          </tr>
                        </thead>
                        <tbody>
                          {previewRows.map((row, i) => (
                            <tr key={i} className="border-b last:border-0 hover:bg-muted/30">
                              {row.map((val: string, j: number) => (
                                <td key={j} className="py-1 px-2 whitespace-nowrap max-w-[200px] truncate">
                                  {val}
                                </td>
                              ))}
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  )}
                </CardContent>
              </Card>
            </>
          )}
        </div>
      </div>
    </div>
  );
}

export default function BrowsePage() {
  return (
    <ProtectedRoute>
      <BrowseContent />
    </ProtectedRoute>
  );
}
