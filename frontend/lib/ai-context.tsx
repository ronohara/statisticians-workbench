"use client";

import React, { createContext, useContext, useState, useEffect } from "react";
import { useSession } from "next-auth/react";
import { apiFetch } from "@/lib/api";

export type AIProvider = string;

export interface AIConnection {
  id: string;
  connectionId: number;
  userId: string;
  name: string;
  provider: AIProvider;
  apiKey: string | null;
  endpoint: string | null;
  aiConnectionGroup: string;
  isShared: boolean;
  // The two connection timeouts (plan workbench-AI-timeout-policy-plan.html, Item 3).
  // Optional and nullable: absent means the backend did not send the field, null means
  // the connection inherits the workbench default, and a number is its own value.
  // Three states, and collapsing any two of them is how an inherited value comes to
  // look like a configured one.
  connectTimeoutSeconds?: number | null;
  probeTimeoutSeconds?: number | null;
  createdAt: string;
  updatedAt: string;
}

interface AIContextType {
  connections: AIConnection[];
  defaultConnectionId: string | null;
  defaultConnection: AIConnection | null;
  loading: boolean;
  setDefaultConnectionId: (id: string | null) => void;
  addConnection: (connection: Omit<AIConnection, "id" | "connectionId" | "userId" | "isShared" | "createdAt" | "updatedAt">) => Promise<void>;
  updateConnection: (id: string, updates: Partial<Omit<AIConnection, "id" | "connectionId" | "userId" | "isShared" | "createdAt" | "updatedAt">>) => Promise<void>;
  deleteConnection: (id: string) => Promise<void>;
  refreshConnections: () => Promise<void>;
}

const AIContext = createContext<AIContextType | undefined>(undefined);

export function AIProvider({ children }: { children: React.ReactNode }) {
  const { data: session, status } = useSession();
  const [connections, setConnections] = useState<AIConnection[]>([]);
  const [defaultConnectionId, setDefaultConnectionId] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  const fetchConnections = async () => {
    if (status !== "authenticated" || !session?.user?.id) {
      setConnections([]);
      setDefaultConnectionId(null);
      setLoading(false);
      return;
    }

    try {
      setLoading(true);
      const res = await apiFetch("/api/user/ai-connections");
      if (!res.ok) throw new Error("Failed to fetch AI connections");
      const data = await res.json();
      const connectionsWithGroup = (data.connections || []).map((conn: any) => ({
        ...conn,
        aiConnectionGroup: conn.aiConnectionGroup || "00",
      }));
      setConnections(connectionsWithGroup);
    } catch (error) {
      console.error("Error fetching AI connections:", error);
      setConnections([]);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    const loadDefault = async () => {
      if (status !== "authenticated" || !session?.user?.id) {
        setDefaultConnectionId(null);
        return;
      }
      try {
        const res = await apiFetch("/api/user-settings");
        if (res.ok) {
          const data = await res.json();
          // Settings are now top-level properties, not nested in a settings object
          if (data.defaultAIConnectionId) {
            setDefaultConnectionId(data.defaultAIConnectionId);
          }
        }
      } catch (error) {
        console.error("Failed to load default AI connection from settings:", error);
      }
    };
    loadDefault();
  }, [session, status]);

  useEffect(() => {
    if (status === "authenticated") {
      fetchConnections();
    } else if (status === "unauthenticated") {
      setConnections([]);
      setDefaultConnectionId(null);
      setLoading(false);
    }
  }, [session?.user?.id, status]);

  const persistDefault = async (id: string | null) => {
    if (status !== "authenticated") return;
    try {
      await apiFetch("/api/user-settings", {
        method: "POST",
        body: JSON.stringify({ defaultAIConnectionId: id }),
      });
    } catch (error) {
      console.error("Failed to save default AI connection:", error);
    }
  };

  const handleSetDefaultConnectionId = (id: string | null) => {
    setDefaultConnectionId(id);
    persistDefault(id);
  };

  const refreshConnections = async () => {
    await fetchConnections();
  };

  const addConnection = async (connection: Omit<AIConnection, "id" | "connectionId" | "userId" | "isShared" | "createdAt" | "updatedAt">) => {
    const res = await apiFetch("/api/user/ai-connections", {
      method: "POST",
      body: JSON.stringify(connection),
    });
    if (!res.ok) {
      const error = await res.json();
      throw new Error(error.error || "Failed to add AI connection");
    }
    await refreshConnections();
  };

  const updateConnection = async (id: string, updates: Partial<Omit<AIConnection, "id" | "connectionId" | "userId" | "isShared" | "createdAt" | "updatedAt">>) => {
    const res = await apiFetch("/api/user/ai-connections", {
      method: "PATCH",
      body: JSON.stringify({ id, ...updates }),
    });
    if (!res.ok) {
      const error = await res.json();
      throw new Error(error.error || "Failed to update AI connection");
    }
    await refreshConnections();
  };

  const deleteConnection = async (id: string) => {
    const res = await apiFetch(`/api/user/ai-connections?id=${id}`, {
      method: "DELETE",
    });
    if (!res.ok) {
      const error = await res.json();
      throw new Error(error.error || "Failed to delete AI connection");
    }
    if (defaultConnectionId === id) {
      handleSetDefaultConnectionId(null);
    }
    await refreshConnections();
  };

  const defaultConnection = connections.find(c => c.id === defaultConnectionId) || null;

  return (
    <AIContext.Provider
      value={{
        connections,
        defaultConnectionId,
        defaultConnection,
        loading,
        setDefaultConnectionId: handleSetDefaultConnectionId,
        addConnection,
        updateConnection,
        deleteConnection,
        refreshConnections,
      }}
    >
      {children}
    </AIContext.Provider>
  );
}

export function useAI() {
  const context = useContext(AIContext);
  if (!context) throw new Error("useAI must be used within AIProvider");
  return context;
}