"use client";

import { useState, useRef, useEffect } from "react";
import { useTranslate } from "@/lib/translation-helpers";
import { Button } from "@/components/ui/button";
import { PlusCircle, MessageSquare, X, FileText, Pencil } from "lucide-react";
import { AI } from "../../translations";
import { CHAT } from "@/app/chat/translations";

interface AISession {
    sessionId: string;
    stage: string;
    displayName?: string | null;
    isManualRecipe?: boolean;
    recipeName?: string;
    status?: string;
}

interface SessionsSidebarProps {
    sessions: AISession[];
    activeSessionId: string | null;
    onSelect: (sessionId: string, isManual?: boolean) => void;
    onCreateNew: () => void;
    onDelete: (sessionId: string) => void;
    onRename: (sessionId: string, newName: string) => void;
}

const STAGE_LABELS: Record<string, any> = {
    greeting: AI.ai_recipe_stage_greeting,
    goal: AI.ai_recipe_stage_goal,
    technique: AI.ai_recipe_stage_technique,
    columns: AI.ai_recipe_stage_columns,
    transforms: AI.ai_recipe_stage_transforms,
    visualisation: AI.ai_recipe_stage_visualisation,
    review: AI.ai_recipe_stage_review,
    complete: AI.ai_recipe_stage_complete,
};

function stageLabel(stage: string, translate: (key: any) => string): string {
    const key = STAGE_LABELS[stage];
    return key ? translate(key) : stage;
}

export default function SessionsSidebar({
    sessions,
    activeSessionId,
    onSelect,
    onCreateNew,
    onDelete,
    onRename,
}: SessionsSidebarProps) {
    const translate = useTranslate();
    const [editingId, setEditingId] = useState<string | null>(null);
    const [editValue, setEditValue] = useState("");
    const editInputRef = useRef<HTMLInputElement>(null);

    // Auto-focus the edit input when it appears
    useEffect(() => {
        if (editingId) editInputRef.current?.focus();
    }, [editingId]);

    const startEdit = (sessionId: string, currentLabel: string) => {
        setEditingId(sessionId);
        setEditValue(currentLabel);
    };

    const commitEdit = () => {
        if (editingId && editValue.trim()) {
            onRename(editingId, editValue.trim());
        }
        setEditingId(null);
        setEditValue("");
    };

    const cancelEdit = () => {
        setEditingId(null);
        setEditValue("");
    };

    return (
        <div className="border-r border-border bg-card" style={{
            overflow: "auto",
            display: "flex",
            flexDirection: "column",
        }}>
            <div className="border-b border-border" style={{ padding: "1rem" }}>
                <Button onClick={onCreateNew} size="sm" style={{ width: "100%" }}>
                    <PlusCircle style={{ width: 16, height: 16, marginRight: 6 }} />
                    {translate(AI.ai_recipe_new_session)}
                </Button>
            </div>
            <div style={{ flex: 1, overflow: "auto", padding: "0.5rem" }}>
                {sessions.length === 0 && (
                    <p className="text-muted-foreground" style={{
                        padding: "1rem",
                        fontSize: "0.85rem",
                        textAlign: "center",
                    }}>
                        {translate(AI.ai_recipe_no_sessions)}
                    </p>
                )}
                {sessions.map((s) => {
                    const isActive = s.sessionId === activeSessionId;
                    const isManual = s.isManualRecipe === true;
                    const isEditing = editingId === s.sessionId;
                    const label = isManual
                        ? (s.recipeName || translate(AI.ai_recipe_manual_label))
                        : (s.displayName || stageLabel(s.stage, translate));
                    return (
                        <div
                            key={s.sessionId}
                            className={isActive ? "bg-muted" : ""}
                            style={{
                                display: "flex",
                                alignItems: "center",
                                borderRadius: "6px",
                                marginBottom: "2px",
                            }}
                        >
                            <button
                                onClick={() => {
                                    if (!isEditing) onSelect(s.sessionId, s.isManualRecipe);
                                }}
                                className={isActive ? "text-primary" : "text-foreground"}
                                style={{
                                    flex: 1,
                                    textAlign: "left",
                                    padding: "0.6rem 0.5rem 0.6rem 0.75rem",
                                    border: "none",
                                    cursor: isEditing ? "default" : "pointer",
                                    fontSize: "0.85rem",
                                    background: "transparent",
                                }}
                            >
                                {isManual ? (
                                    <FileText style={{
                                        width: 14, height: 14, display: "inline",
                                        marginRight: 6, verticalAlign: "middle",
                                        opacity: 0.6,
                                    }} />
                                ) : (
                                    <MessageSquare style={{
                                        width: 14, height: 14, display: "inline",
                                        marginRight: 6, verticalAlign: "middle",
                                    }} />
                                )}
                                {isEditing ? (
                                    <input dir="auto"
                                        ref={editInputRef}
                                        value={editValue}
                                        onChange={(e) => setEditValue(e.target.value)}
                                        onKeyDown={(e) => {
                                            if (e.key === "Enter") { e.preventDefault(); commitEdit(); }
                                            if (e.key === "Escape") { e.preventDefault(); cancelEdit(); }
                                        }}
                                        onBlur={commitEdit}
                                        onClick={(e) => e.stopPropagation()}
                                        style={{
                                            verticalAlign: "middle",
                                            fontSize: "0.85rem",
                                            padding: "0.15rem 0.3rem",
                                            border: "1px solid hsl(var(--primary))",
                                            borderRadius: "3px",
                                            background: "#fff",
                                            color: "#1e293b",
                                            width: "140px",
                                            maxWidth: "100%",
                                        }}
                                    />
                                ) : (
                                    <span style={{ verticalAlign: "middle" }}>{label}</span>
                                )}
                                {isManual && !isEditing && (
                                    <span style={{
                                        fontSize: "0.65rem",
                                        marginLeft: "0.35rem",
                                        padding: "0.05rem 0.3rem",
                                        borderRadius: "3px",
                                        fontWeight: 600,
                                        textTransform: "uppercase",
                                        verticalAlign: "middle",
                                        background: s.status === "complete" ? "#dcfce7" : "#fef3c7",
                                        color: s.status === "complete" ? "#16a34a" : "#b45309",
                                    }}>
                                        {s.status === "complete"
                                            ? translate(AI.ai_recipe_status_ready)
                                            : translate(AI.ai_recipe_status_draft)}
                                    </span>
                                )}
                            </button>
                            {!isManual && !isEditing && (
                                <button
                                    onClick={(e) => {
                                        e.stopPropagation();
                                        startEdit(s.sessionId, label);
                                    }}
                                    title={translate(CHAT.rename)}
                                    style={{
                                        border: "none",
                                        background: "transparent",
                                        cursor: "pointer",
                                        padding: "0.6rem 0.2rem",
                                        color: "hsl(var(--muted-foreground))",
                                        borderRadius: "4px",
                                        opacity: 0.35,
                                        transition: "opacity 0.15s",
                                    }}
                                    onMouseEnter={(e) => { (e.currentTarget as HTMLElement).style.opacity = "0.8"; }}
                                    onMouseLeave={(e) => { (e.currentTarget as HTMLElement).style.opacity = "0.35"; }}
                                >
                                    <Pencil style={{ width: 12, height: 12 }} />
                                </button>
                            )}
                            {!isManual && (
                                <button
                                    onClick={(e) => {
                                        e.stopPropagation();
                                        onDelete(s.sessionId);
                                    }}
                                    title={translate(AI.ai_recipe_delete_session)}
                                    style={{
                                        border: "none",
                                        background: "transparent",
                                        cursor: "pointer",
                                        padding: "0.6rem 0.5rem",
                                        color: "hsl(var(--muted-foreground))",
                                        borderRadius: "4px",
                                        opacity: 0.5,
                                        transition: "opacity 0.15s",
                                    }}
                                    onMouseEnter={(e) => { (e.currentTarget as HTMLElement).style.opacity = "1"; }}
                                    onMouseLeave={(e) => { (e.currentTarget as HTMLElement).style.opacity = "0.5"; }}
                                >
                                    <X style={{ width: 14, height: 14 }} />
                                </button>
                            )}
                        </div>
                    );
                })}
            </div>
        </div>
    );
}
