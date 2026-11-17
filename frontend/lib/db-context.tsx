"use client";

import React, { createContext, useContext, useState, useEffect } from "react";
import { useSession } from "next-auth/react";
import { apiFetch } from "@/lib/api";

export type DatabaseType = "postgresql" | "mysql" | "mssql" | "access";

export interface DatabaseConnection {
  id: string;
  connectionId: number;
  isOwn: boolean;
  canCreateDatabase: boolean;
  canCreateTables: boolean;
  name: string;
  type: DatabaseType;
  host: string;
  port: number;
  database: string;
  username: string;
  password: string;
  dbConnectionGroup: string;
  isShared: boolean;
  createdAt: string;
  updatedAt: string;
  /** The probe's stored result. Null before the connection has ever been probed. */
  probeState?: string | null;
  /** Why it failed, when `probeState` is not `reachable`. */
  probeDetail?: string | null;
  /** When the last probe ran — success or failure. */
  probedAt?: string | null;
  /** When it last succeeded. Untouched by a failure, so it can be far older. */
  probeSuccessAt?: string | null;
}

interface DBContextType {
  connections: DatabaseConnection[];
  defaultConnectionId: string | null;
  defaultConnection: DatabaseConnection | null;
  loading: boolean;
  setDefaultConnectionId: (id: string | null) => void;
  addConnection: (connection: Omit<DatabaseConnection, "id" | "connectionId" | "isOwn" | "canCreateDatabase" | "canCreateTables" | "createdAt" | "updatedAt">) => Promise<void>;
  updateConnection: (id: string, updates: Partial<Omit<DatabaseConnection, "id" | "connectionId" | "isOwn" | "canCreateDatabase" | "canCreateTables" | "createdAt" | "updatedAt">>) => Promise<void>;
  deleteConnection: (id: string) => Promise<void>;
  refreshConnections: () => Promise<void>;
}

const DBContext = createContext<DBContextType | undefined>(undefined);

export function DBProvider({ children }: { children: React.ReactNode }) {
  const [connections, setConnections] = useState<DatabaseConnection[]>([]);
  const [defaultConnectionId, setDefaultConnectionId] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const { status } = useSession();

  const fetchConnections = async () => {
    try {
      const res = await apiFetch("/api/user/database-connections");
      if (!res.ok) {
        throw new Error(
          `Failed to fetch connections (HTTP ${res.status}, redirected: ${res.redirected}, url: ${res.url})`
        );
      }
      const contentType = res.headers.get("content-type") || "";
      if (!contentType.includes("application/json")) {
        throw new Error(
          `Expected JSON from /api/user/database-connections but got "${
            contentType || "no content-type"
          }" (redirected: ${res.redirected}, url: ${res.url})`
        );
      }
      const data = await res.json();
      const connectionsWithGroup = (data.connections || []).map((conn: any) => ({
        ...conn,
        dbConnectionGroup: conn.dbConnectionGroup || "00",
      }));
      setConnections(connectionsWithGroup);
    } catch (error) {
      console.error("Error fetching connections:", error);
      setConnections([]);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    const saved = localStorage.getItem("default_db_connection_id");
    if (saved) setDefaultConnectionId(saved);
  }, []);

  useEffect(() => {
    if (defaultConnectionId) {
      localStorage.setItem("default_db_connection_id", defaultConnectionId);
    } else {
      localStorage.removeItem("default_db_connection_id");
    }
  }, [defaultConnectionId]);

  useEffect(() => {
    if (status === "authenticated") {
      fetchConnections();
    } else if (status === "unauthenticated") {
      setConnections([]);
      setLoading(false);
    }
  }, [status]);

  const refreshConnections = async () => {
    setLoading(true);
    await fetchConnections();
  };

  const addConnection = async (connection: Omit<DatabaseConnection, "id" | "connectionId" | "isOwn" | "canCreateDatabase" | "canCreateTables" | "createdAt" | "updatedAt">) => {
    const res = await apiFetch("/api/user/database-connections", {
      method: "POST",
      body: JSON.stringify(connection),
    });
    if (!res.ok) {
      const error = await res.json();
      throw new Error(error.message || error.error || "Failed to add connection");
    }
    const data = await res.json();
    await refreshConnections();
    return data;
  };

  const updateConnection = async (id: string, updates: Partial<Omit<DatabaseConnection, "id" | "connectionId" | "isOwn" | "canCreateDatabase" | "canCreateTables" | "createdAt" | "updatedAt">>) => {
    const res = await apiFetch("/api/user/database-connections", {
      method: "PATCH",
      body: JSON.stringify({ id, ...updates }),
    });
    if (!res.ok) {
      const error = await res.json();
      throw new Error(error.message || error.error || "Failed to update connection");
    }
    await refreshConnections();
  };

  const deleteConnection = async (id: string) => {
    const res = await apiFetch(`/api/user/database-connections?id=${id}`, {
      method: "DELETE",
    });
    if (!res.ok) {
      const error = await res.json();
      throw new Error(error.message || error.error || "Failed to delete connection");
    }
    if (defaultConnectionId === id) {
      setDefaultConnectionId(null);
    }
    await refreshConnections();
  };

  const defaultConnection = connections.find(c => c.id === defaultConnectionId) || null;

  return (
    <DBContext.Provider
      value={{
        connections,
        defaultConnectionId,
        defaultConnection,
        loading,
        setDefaultConnectionId,
        addConnection,
        updateConnection,
        deleteConnection,
        refreshConnections,
      }}
    >
      {children}
    </DBContext.Provider>
  );
}

export function useDB() {
  const context = useContext(DBContext);
  if (!context) throw new Error("useDB must be used within DBProvider");
  return context;
}