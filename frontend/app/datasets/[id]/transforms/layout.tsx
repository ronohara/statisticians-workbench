"use client";

import { formatDate } from "@/lib/date-format";
import { useState, useEffect, useCallback } from "react";
import { useParams, useRouter, useSearchParams, usePathname } from "next/navigation";
import { useTranslation } from "@/lib/translation-context";
import { useTranslate, getErrorMessageFromData } from "@/lib/translation-helpers";
import { apiFetch } from "@/lib/api";
import { ProtectedRoute } from "@/components/protected-route";
import ReturnBanner from "@/components/return-banner";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Loader2, Plus, Search, FlaskConical, X } from "lucide-react";
import { toast } from "sonner";
import { DATASETS } from "../../translations";
import { TRANSFORMS_EDITOR } from "./translations";

interface TransformListItem {
    id: string;
    name: string;
    description: string | null;
    operations: any[];
    userId: string;
    isOwn: boolean;
    createdAt: string;
    updatedAt: string;
}

function TransformsLayoutInner({ children }: { children: React.ReactNode }) {
    const { isLanguageLoaded } = useTranslation();
    const translate = useTranslate();
    const router = useRouter();
    const params = useParams();
    const searchParams = useSearchParams();

    const datasetId = params.id as string;
    const selectedId = (params.transformId as string) || null;
    const returnTo = searchParams.get("returnTo") || null;
    const recipeId = searchParams.get("recipeId") || null;
    const pathname = usePathname();  // Triggers re-fetch on navigation (unlike useParams in layout)

    const [transforms, setTransforms] = useState<TransformListItem[]>([]);
    const [datasetName, setDatasetName] = useState("");
    const [loading, setLoading] = useState(true);
    const [errorMessage, setErrorMessage] = useState<string | null>(null);
    // A failed action — create, connect or disconnect. errorMessage above explains
    // why the list is empty and renders in place of it; this one is reported where
    // there is room to read it, in the right pane above the content.
    const [actionError, setActionError] = useState<string | null>(null);
    const [search, setSearch] = useState("");
    const [creating, setCreating] = useState(false);

    // Recipe-aware mode state
    const [connectedIds, setConnectedIds] = useState<Set<string>>(new Set());
    const [recipeName, setRecipeName] = useState("");
    const [connectingId, setConnectingId] = useState<string | null>(null);

    // Fetch connected transforms when in recipe mode
    useEffect(() => {
        if (!recipeId) return;
        let cancelled = false;
        const fetchConnected = async () => {
            try {
                const res = await apiFetch(`/api/recipes/${recipeId}/transforms`);
                if (!res.ok) return;
                const data = await res.json();
                if (!cancelled) {
                    const ids = new Set<string>((data.transforms || []).map((t: any) => t.id));
                    setConnectedIds(ids);
                }
            } catch {
                // Non-critical
            }
        };
        fetchConnected();

        // Also fetch recipe name
        const fetchRecipeName = async () => {
            try {
                const res = await apiFetch(`/api/recipes/${recipeId}`);
                if (!res.ok) return;
                const data = await res.json();
                if (!cancelled) setRecipeName(data.name || "");
            } catch {
                // Non-critical
            }
        };
        fetchRecipeName();

        return () => { cancelled = true; };
    }, [recipeId]);

    const fetchTransforms = useCallback(async () => {
        setLoading(true);
        setErrorMessage(null);
        // A message about an action on the previous dataset must not follow the
        // user to this one: the list is re-fetched (and the layout kept across a
        // dataset change), so the action error is cleared here too.
        setActionError(null);
        try {
            const [dsRes, tfRes] = await Promise.all([
                apiFetch(`/api/datasets/${datasetId}`),
                apiFetch(`/api/datasets/${datasetId}/transforms`),
            ]);
            if (dsRes.ok) {
                const ds = await dsRes.json();
                setDatasetName(ds.dataset?.name || "");
            }
            if (tfRes.ok) {
                const data = await tfRes.json();
                setTransforms(data.transforms || []);
            } else {
                const ed = await tfRes.json().catch(() => ({}));
                throw new Error(getErrorMessageFromData(translate, ed, DATASETS.transforms_load_error));
            }
        } catch (err: any) {
            setErrorMessage(err.message || translate(DATASETS.transforms_load_error));
        } finally {
            setLoading(false);
        }
    }, [datasetId, translate]);

    // Re-fetch on any navigation (pathname changes reliably; useParams does not inside layouts)
    useEffect(() => { fetchTransforms(); }, [fetchTransforms, pathname]);

    // Connect a transform to the recipe
    const handleConnect = async (e: React.MouseEvent, transformId: string) => {
        e.stopPropagation();
        if (!recipeId) return;

        // Optimistic update
        setConnectedIds((prev) => new Set(prev).add(transformId));
        setConnectingId(transformId);
        setActionError(null);

        try {
            const res = await apiFetch(`/api/recipes/${recipeId}/transforms`, {
                method: "POST",
                body: JSON.stringify({ transformId }),
            });
            if (!res.ok) {
                // Rollback on failure
                setConnectedIds((prev) => {
                    const next = new Set(prev);
                    next.delete(transformId);
                    return next;
                });
                const errData = await res.json().catch(() => ({}));
                const msg = errData.detail || translate(TRANSFORMS_EDITOR.connect_error);
                setActionError(msg);
                toast.error(msg);
            }
        } catch {
            setConnectedIds((prev) => {
                const next = new Set(prev);
                next.delete(transformId);
                return next;
            });
            const msg = translate(TRANSFORMS_EDITOR.connect_error);
            setActionError(msg);
            toast.error(msg);
        } finally {
            setConnectingId(null);
        }
    };

    // Disconnect a transform from the recipe
    const handleDisconnect = async (e: React.MouseEvent, transformId: string) => {
        e.stopPropagation();
        if (!recipeId) return;

        // Optimistic update
        setConnectedIds((prev) => {
            const next = new Set(prev);
            next.delete(transformId);
            return next;
        });
        setActionError(null);

        try {
            const res = await apiFetch(`/api/recipes/${recipeId}/transforms/${transformId}`, {
                method: "DELETE",
            });
            if (!res.ok) {
                // Rollback on failure
                setConnectedIds((prev) => new Set(prev).add(transformId));
                const errData = await res.json().catch(() => ({}));
                const msg = errData.detail || translate(TRANSFORMS_EDITOR.disconnect_error);
                setActionError(msg);
                toast.error(msg);
            }
        } catch {
            setConnectedIds((prev) => new Set(prev).add(transformId));
            const msg = translate(TRANSFORMS_EDITOR.disconnect_error);
            setActionError(msg);
            toast.error(msg);
        }
    };

    const handleCreate = async () => {
        setCreating(true);
        setActionError(null);
        try {
            const res = await apiFetch(`/api/datasets/${datasetId}/transforms`, {
                method: "POST",
                body: JSON.stringify({
                    name: translate(TRANSFORMS_EDITOR.new_transform),
                    operations: [],
                }),
            });
            if (!res.ok) {
                const ed = await res.json().catch(() => ({}));
                throw new Error(getErrorMessageFromData(translate, ed, DATASETS.transforms_create_error));
            }
            const data = await res.json();
            const newId = data.transform_id || data.id;
            await fetchTransforms();
            const params = new URLSearchParams();
            if (returnTo) params.set("returnTo", returnTo);
            if (recipeId) params.set("recipeId", recipeId);
            const qs = params.toString();
            router.push(`/datasets/${datasetId}/transforms/${newId}${qs ? `?${qs}` : ""}`);
        } catch (err: any) {
            const msg = err.message || translate(DATASETS.transforms_create_error);
            setActionError(msg);
            toast.error(msg);
        } finally {
            setCreating(false);
        }
    };

    const filtered = transforms.filter((t) => {
        if (!search.trim()) return true;
        const q = search.toLowerCase();
        return t.name.toLowerCase().includes(q) || (t.description || "").toLowerCase().includes(q);
    });

    if (!isLanguageLoaded) return null;

    const title = datasetName
        ? translate(DATASETS.transforms_for).replace("{name}", datasetName)
        : translate(DATASETS.transforms_title);

    const connectedCount = connectedIds.size;

    return (
        <div className="flex h-full">
            {/* Left pane */}
            <div className="w-[300px] shrink-0 border-e flex flex-col h-full bg-muted/20">
                <div className="px-3 py-2.5 border-b">
                    <h2 className="text-sm font-semibold truncate">
                        {title}
                        {recipeId && recipeName && (
                            <span className="text-muted-foreground font-normal">
                                {" "}&middot;{" "}{translate(TRANSFORMS_EDITOR.for_recipe).replace("{name}", recipeName)}
                            </span>
                        )}
                    </h2>
                    {recipeId && (
                        <p className="text-[11px] text-muted-foreground mt-0.5">
                            {translate(TRANSFORMS_EDITOR.connected_count).replace("{count}", String(connectedCount))}
                        </p>
                    )}
                </div>

                <div className="px-3 py-2 space-y-2 border-b">
                    <div className="relative">
                        <Search className="absolute start-2 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-muted-foreground" />
                        <Input dir="auto"
                            value={search}
                            onChange={(e) => setSearch(e.target.value)}
                            placeholder={translate(TRANSFORMS_EDITOR.search_placeholder)}
                            className="h-8 text-xs ps-7"
                        />
                    </div>
                    <Button
                        size="sm"
                        className="w-full h-7 text-xs"
                        onClick={handleCreate}
                        disabled={creating}
                    >
                        {creating ? (
                            <Loader2 className="h-3.5 w-3.5 animate-spin me-1" />
                        ) : (
                            <Plus className="h-3.5 w-3.5 me-1" />
                        )}
                        {translate(TRANSFORMS_EDITOR.new_transform)}
                    </Button>
                </div>

                <div className="flex-1 overflow-y-auto">
                    {loading ? (
                        <div className="flex items-center justify-center py-10">
                            <Loader2 className="h-5 w-5 animate-spin text-muted-foreground" />
                        </div>
                    ) : errorMessage ? (
                        <p className="text-xs text-destructive px-3 py-3">{errorMessage}</p>
                    ) : filtered.length === 0 ? (
                        <div className="px-3 py-6 text-center">
                            <FlaskConical className="h-6 w-6 mx-auto text-muted-foreground mb-2 opacity-40" />
                            <p className="text-xs text-muted-foreground">
                                {search.trim()
                                    ? translate(TRANSFORMS_EDITOR.no_search_results)
                                    : translate(TRANSFORMS_EDITOR.no_transforms)}
                            </p>
                        </div>
                    ) : (
                        <div className="space-y-px p-1.5">
                            {filtered.map((t) => {
                                const isConnected = connectedIds.has(t.id);
                                const params = new URLSearchParams();
                                if (returnTo) params.set("returnTo", returnTo);
                                if (recipeId) params.set("recipeId", recipeId);
                                const qs = params.toString();
                                return (
                                    <button
                                        key={t.id}
                                        onClick={() =>
                                            router.push(
                                                `/datasets/${datasetId}/transforms/${t.id}${qs ? `?${qs}` : ""}`
                                            )
                                        }
                                        className={`w-full text-start px-3 py-2.5 rounded-md text-sm transition-colors group ${
                                            selectedId === t.id
                                                ? "bg-accent/10 border border-accent/30"
                                                : isConnected && recipeId
                                                ? "bg-accent/10 border border-accent/20"
                                                : "hover:bg-muted border border-transparent"
                                        }`}
                                    >
                                        <div className="flex items-center gap-2">
                                            <FlaskConical className="h-3.5 w-3.5 text-muted-foreground shrink-0" />
                                            <span className="font-medium truncate flex-1">{t.name}</span>
                                            {/* Connect / Disconnect icons */}
                                            {recipeId && (
                                                isConnected ? (
                                                    <button
                                                        type="button"
                                                        onClick={(e) => handleDisconnect(e, t.id)}
                                                        className="shrink-0 p-0.5 rounded hover:bg-destructive/10 text-muted-foreground hover:text-destructive transition-colors"
                                                        title={translate(TRANSFORMS_EDITOR.disconnect_transform)}
                                                    >
                                                        <X className="h-3.5 w-3.5" />
                                                    </button>
                                                ) : (
                                                    <button
                                                        type="button"
                                                        onClick={(e) => handleConnect(e, t.id)}
                                                        disabled={connectingId === t.id}
                                                        className="shrink-0 p-0.5 rounded hover:bg-accent/20 text-muted-foreground hover:text-accent transition-colors"
                                                        title={translate(TRANSFORMS_EDITOR.connect_transform)}
                                                    >
                                                        {connectingId === t.id ? (
                                                            <Loader2 className="h-3.5 w-3.5 animate-spin" />
                                                        ) : (
                                                            <Plus className="h-3.5 w-3.5" />
                                                        )}
                                                    </button>
                                                )
                                            )}
                                        </div>
                                        <div className="flex items-center gap-2 mt-0.5">
                                            <span className="text-[11px] text-muted-foreground">
                                                {translate(TRANSFORMS_EDITOR.operations_count).replace(
                                                    "{count}",
                                                    String(Array.isArray(t.operations) ? t.operations.length : 0)
                                                )}
                                            </span>
                                            <span className="text-[11px] text-muted-foreground">
                                                {formatDate(t.createdAt)}
                                            </span>
                                        </div>
                                    </button>
                                );
                            })}
                        </div>
                    )}
                </div>
            </div>

            <div className="flex-1 min-w-0 overflow-y-auto">
                {/* The page's single return control: the blue banner the datasets
                    pages carry. Both recipe editors link here with a returnTo
                    path; reached from My Data there is none, so the box falls back
                    to that page — and carries no dismiss, because dismissing a way
                    back would leave that entry point a dead end. */}
                <ReturnBanner
                    fallbackHref="/datasets/manage"
                    fallbackText={DATASETS.transforms_back}
                    contextName={recipeName || null}
                    contextLink={TRANSFORMS_EDITOR.back_to_recipe}
                />
                {actionError && (
                    <div className="px-4 pt-4">
                        <p className="text-sm text-destructive bg-destructive/10 rounded px-3 py-2">
                            {actionError}
                        </p>
                    </div>
                )}
                {children}
            </div>
        </div>
    );
}

export default function TransformsLayout({ children }: { children: React.ReactNode }) {
    return (
        <ProtectedRoute>
            <TransformsLayoutInner>{children}</TransformsLayoutInner>
        </ProtectedRoute>
    );
}
