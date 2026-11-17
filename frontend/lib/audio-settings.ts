"use client";

export interface AudioSettings {
    voiceName: string | null;
    speed: number;
    pitch: number;
    volume: number;
    micVolume: number;
    micMuted: boolean;
    speakerMuted: boolean;
}

const SETTINGS_PREFIX = "audio_presets_";

function key(chatType: string): string {
    return SETTINGS_PREFIX + chatType;
}

export function getCachedSettings(chatType: string): AudioSettings {
    const defaults: AudioSettings = { voiceName: null, speed: 1.0, pitch: 1.0, volume: 1.0, micVolume: 1.0, micMuted: false, speakerMuted: false };
    if (typeof window === "undefined") return defaults;
    try {
        const raw = localStorage.getItem(key(chatType));
        if (raw) return { ...defaults, ...JSON.parse(raw) };
    } catch {}
    return defaults;
}

export function setCachedSettings(chatType: string, settings: AudioSettings): void {
    if (typeof window === "undefined") return;
    localStorage.setItem(key(chatType), JSON.stringify(settings));
}

export function clearCachedSettings(chatType: string): void {
    if (typeof window === "undefined") return;
    localStorage.removeItem(key(chatType));
}

export async function loadServerSettings(chatType: string): Promise<AudioSettings | null> {
    try {
        const token = await getAuthToken();
        const res = await fetch(`/api/user/audio-presets/${chatType}`, {
            headers: { Authorization: `Bearer ${token}` },
        });
        if (!res.ok) return null;
        return await res.json();
    } catch {
        return null;
    }
}

export async function saveServerSettings(chatType: string, settings: AudioSettings): Promise<void> {
    try {
        const token = await getAuthToken();
        await fetch(`/api/user/audio-presets/${chatType}`, {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
                Authorization: `Bearer ${token}`,
            },
            body: JSON.stringify(settings),
        });
    } catch {
        // Fire and forget — localStorage already has the value
    }
}

async function getAuthToken(): Promise<string> {
    const res = await fetch("/api/auth/token", { credentials: "include" });
    if (!res.ok) throw new Error("Unauthorized");
    const data = await res.json();
    return data.token;
}
