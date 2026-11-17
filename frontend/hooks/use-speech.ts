"use client";

import { useEffect, useRef, useState, useCallback } from "react";
import { getCachedSettings, setCachedSettings, AudioSettings } from "@/lib/audio-settings";
import { useTranslate } from "@/lib/translation-helpers";
import { COMMON } from "@/app/common/translations";

export type SpeechState = "idle" | "speaking" | "paused";

export function useSpeechOutput(
    text: string,
    enabled: boolean,
    chatType?: string,
): {
    speechOutputError: string | null;
    speechState: SpeechState;
    pause: () => void;
    resume: () => void;
    stop: () => void;
    volume: number;
    setVolume: (vol: number) => void;
} {
    const translate = useTranslate();
    const spokenRef = useRef<string | null>(null);
    const [speechOutputError, setSpeechOutputError] = useState<string | null>(null);
    const [speechState, setSpeechState] = useState<SpeechState>("idle");
    const [volume, setVolumeState] = useState(1.0);

    // Load volume from cache on mount
    useEffect(() => {
        if (chatType) {
            const settings = getCachedSettings(chatType);
            setVolumeState(settings.volume ?? 1.0);
        }
    }, [chatType]);

    const setVolume = useCallback((vol: number) => {
        const clamped = Math.max(0, Math.min(1, vol));
        setVolumeState(clamped);
        if (chatType) {
            const settings = getCachedSettings(chatType);
            settings.volume = clamped;
            setCachedSettings(chatType, settings);
        }
    }, [chatType]);

    const pause = useCallback(() => {
        if (typeof window !== "undefined" && window.speechSynthesis) {
            window.speechSynthesis.pause();
        }
    }, []);

    const resume = useCallback(() => {
        if (typeof window !== "undefined" && window.speechSynthesis) {
            window.speechSynthesis.resume();
        }
    }, []);

    const stop = useCallback(() => {
        if (typeof window !== "undefined" && window.speechSynthesis) {
            window.speechSynthesis.cancel();
            setSpeechState("idle");
        }
    }, []);

    useEffect(() => {
        if (!enabled) {
            // Stop any ongoing speech when speaker is disabled
            if (typeof window !== "undefined" && window.speechSynthesis) {
                window.speechSynthesis.cancel();
            }
            return;
        }
        if (!text || typeof window === "undefined") return;

        if (typeof window.speechSynthesis === "undefined") {
            setSpeechOutputError(translate(COMMON.speech_output_unsupported));
            return;
        }
        setSpeechOutputError(null);

        if (text === spokenRef.current) return;
        spokenRef.current = text;

        let settings: AudioSettings = { voiceName: null, speed: 1.0, pitch: 1.0, volume: 1.0, micVolume: 1.0, micMuted: false, speakerMuted: false };
        if (chatType) {
            settings = getCachedSettings(chatType);
        }

        const timer = setTimeout(() => {
            const synth = window.speechSynthesis;
            synth.cancel();
            const utterance = new SpeechSynthesisUtterance(text);
            utterance.rate = settings.speed;
            utterance.pitch = settings.pitch;
            utterance.volume = settings.volume ?? 1.0;
            if (settings.voiceName) {
                const voices = synth.getVoices();
                const match = voices.find(v => v.name === settings.voiceName);
                if (match) utterance.voice = match;
            }

            utterance.onstart = () => setSpeechState("speaking");
            utterance.onpause = () => setSpeechState("paused");
            utterance.onresume = () => setSpeechState("speaking");
            utterance.onend = () => setSpeechState("idle");
            utterance.onerror = () => setSpeechState("idle");

            synth.speak(utterance);
        }, 50);

        return () => {
            clearTimeout(timer);
        };
    }, [text, enabled, chatType, translate]);

    return { speechOutputError, speechState, pause, resume, stop, volume, setVolume };
}
