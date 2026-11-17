// app/admin/setup/internal/translations.ts
// ============================================================
// INTERNAL SETTINGS MODULE TRANSLATIONS
// System diagnostics — read-only indicators, grows over time.
// ============================================================

import type { TranslationKey } from "@/lib/translation-helpers";

export const INTERNAL_SETTINGS = {
    title: { key: "setup.internal.title", fallback: "Internal" },
    description: { key: "setup.internal.description", fallback: "System diagnostics and internal configuration. Read-only status indicators." },
    load_error: { key: "setup.internal.load_error", fallback: "Failed to load system diagnostics" },

    system_status: {
        title: { key: "setup.internal.system_status.title", fallback: "System Status" },
        description: { key: "setup.internal.system_status.description", fallback: "Real-time health indicators for backend services." },
        overall_health: { key: "setup.internal.system_status.overall_health", fallback: "Overall Health" },
        healthy: { key: "setup.internal.system_status.healthy", fallback: "Healthy" },
        unhealthy: { key: "setup.internal.system_status.unhealthy", fallback: "Unhealthy" },
        version: { key: "setup.internal.system_status.version", fallback: "Version" },
        db_pool: { key: "setup.internal.system_status.db_pool", fallback: "Database Pool" },
        db_cluster: { key: "setup.internal.system_status.db_cluster", fallback: "Database Cluster" },
        initialized: { key: "setup.internal.system_status.initialized", fallback: "Initialized" },
        not_initialized: { key: "setup.internal.system_status.not_initialized", fallback: "Not Initialized" },
        shared_memory: { key: "setup.internal.system_status.shared_memory", fallback: "Shared Memory" },
        available: { key: "setup.internal.system_status.available", fallback: "Available" },
        unavailable: { key: "setup.internal.system_status.unavailable", fallback: "Unavailable" },
        not_required: { key: "setup.internal.system_status.not_required", fallback: "Not Required" },
    },

    licence: {
        title: { key: "setup.internal.licence.title", fallback: "Licence & Features" },
        description: { key: "setup.internal.licence.description", fallback: "Current licence tier and enabled features." },
        tier: { key: "setup.internal.licence.tier", fallback: "Licence Tier" },
        issued_to: { key: "setup.internal.licence.issued_to", fallback: "Issued To" },
        expiry: { key: "setup.internal.licence.expiry", fallback: "Expiry" },
        features: { key: "setup.internal.licence.features", fallback: "Enabled Features" },
    },

    future: {
        title: { key: "setup.internal.future.title", fallback: "Coming Soon" },
        description: { key: "setup.internal.future.description", fallback: "Additional diagnostics will be added in future releases." },
        email_transport: { key: "setup.internal.future.email_transport", fallback: "Email transport status" },
        cache_config: { key: "setup.internal.future.cache_config", fallback: "Cache / session configuration" },
        debug_logging: { key: "setup.internal.future.debug_logging", fallback: "Debug / verbose logging toggle" },
        pool_stats: { key: "setup.internal.future.pool_stats", fallback: "Database pool statistics" },
    },
} as const;
