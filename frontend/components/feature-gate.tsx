"use client";

/**
 * Golden Screwdriver — FeatureGate component.
 *
 * FeatureProvider wraps the app and fetches GET /api/features on mount.
 * useFeature(key) returns true if the named feature is enabled.
 * FeatureGate conditionally renders children when the feature is enabled.
 *
 * While the features API is loading, FeatureGate renders nothing to
 * prevent a flash of gated content before the licence check completes.
 */

import {
    createContext,
    useContext,
    useEffect,
    useState,
    type ReactNode,
} from "react";

// ── Types ──────────────────────────────────────────────────────────

interface FeatureContextValue {
    features: Set<string>;
    loaded: boolean;
}

// ── Context ────────────────────────────────────────────────────────

const FeatureContext = createContext<FeatureContextValue>({
    features: new Set(),
    loaded: false,
});

// ── Provider ───────────────────────────────────────────────────────

export function FeatureProvider({ children }: { children: ReactNode }) {
    const [features, setFeatures] = useState<Set<string>>(new Set());
    const [loaded, setLoaded] = useState(false);

    useEffect(() => {
        let cancelled = false;

        fetch("/api/features")
            .then((r) => {
                if (!r.ok) throw new Error(`HTTP ${r.status}`);
                return r.json();
            })
            .then((data: { features?: string[] }) => {
                if (!cancelled) {
                    setFeatures(new Set(data.features ?? []));
                    setLoaded(true);
                }
            })
            .catch(() => {
                // On failure, assume open-source mode (no features)
                if (!cancelled) {
                    setFeatures(new Set());
                    setLoaded(true);
                }
            });

        return () => {
            cancelled = true;
        };
    }, []);

    return (
        <FeatureContext.Provider value={{ features, loaded }}>
            {children}
        </FeatureContext.Provider>
    );
}

// ── Hook ───────────────────────────────────────────────────────────

export function useFeature(feature: string): boolean {
    const { features } = useContext(FeatureContext);
    return features.has(feature);
}

export function useFeaturesLoaded(): boolean {
    const { loaded } = useContext(FeatureContext);
    return loaded;
}

// ── Gate ───────────────────────────────────────────────────────────

interface FeatureGateProps {
    feature: string;
    children: ReactNode;
    fallback?: ReactNode;
}

export function FeatureGate({
    feature,
    children,
    fallback = null,
}: FeatureGateProps) {
    const { loaded } = useContext(FeatureContext);
    const enabled = useFeature(feature);

    // While loading, render nothing to prevent flash of gated content
    if (!loaded) return null;

    if (enabled) return <>{children}</>;
    return <>{fallback}</>;
}
