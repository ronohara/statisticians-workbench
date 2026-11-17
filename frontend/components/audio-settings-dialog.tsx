"use client";

import { useState, useEffect, useMemo } from "react";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import {
    Dialog,
    DialogContent,
    DialogHeader,
    DialogTitle,
} from "@/components/ui/dialog";
import {
    getCachedSettings,
    setCachedSettings,
    clearCachedSettings,
    loadServerSettings,
    saveServerSettings,
    AudioSettings,
} from "@/lib/audio-settings";
import { useTranslate } from "@/lib/translation-helpers";
import { COMPONENTS } from "@/components/translations";

interface AudioSettingsDialogProps {
    open: boolean;
    onClose: () => void;
    chatType: string;
}

export default function AudioSettingsDialog({ open, onClose, chatType }: AudioSettingsDialogProps) {
    const translate = useTranslate();
    const [voiceName, setVoiceName] = useState<string>("");
    const [speed, setSpeed] = useState(1.0);
    const [pitch, setPitch] = useState(1.0);
    const [voices, setVoices] = useState<SpeechSynthesisVoice[]>([]);

    // Load voices on mount
    useEffect(() => {
        if (typeof window === "undefined") return;
        const synth = window.speechSynthesis;
        const loadVoices = () => setVoices(synth.getVoices());
        loadVoices();
        synth.onvoiceschanged = loadVoices;
        return () => { synth.onvoiceschanged = null; };
    }, []);

    // Load settings when dialog opens or chatType changes
    useEffect(() => {
        if (!open) return;

        // 1. Load from localStorage instantly
        const cached = getCachedSettings(chatType);
        setVoiceName(cached.voiceName || "");
        setSpeed(cached.speed);
        setPitch(cached.pitch);

        // 2. Sync from server in background
        loadServerSettings(chatType).then(server => {
            if (server) {
                setVoiceName(server.voiceName || "");
                setSpeed(server.speed);
                setPitch(server.pitch);
                setCachedSettings(chatType, server);
            }
        });
    }, [open, chatType]);

    const handleClose = () => {
        // Preserve existing volume/mute settings from cache
        const existing = getCachedSettings(chatType);
        const settings: AudioSettings = {
            ...existing,
            voiceName: voiceName || null,
            speed,
            pitch,
        };
        setCachedSettings(chatType, settings);
        saveServerSettings(chatType, settings); // fire and forget
        onClose();
    };

    const handleReset = () => {
        clearCachedSettings(chatType);
        setVoiceName("");
        setSpeed(1.0);
        setPitch(1.0);
    };

    // Filter voices: prefer current language + English
    const filteredVoices = useMemo(() => {
        if (voices.length === 0) return [];
        const lang = navigator.language?.slice(0, 2) || "en";
        const preferred = voices.filter(v => v.lang.startsWith(lang));
        return preferred.length > 0 ? preferred : voices.filter(v => v.lang.startsWith("en"));
    }, [voices]);

    const getVoiceLabel = (v: SpeechSynthesisVoice) =>
        `${v.name} (${v.lang})${v.default ? " — default" : ""}`;

    return (
        <Dialog open={open} onOpenChange={(o) => { if (!o) handleClose(); }}>
            <DialogContent className="sm:max-w-md">
                <DialogHeader>
                    <DialogTitle>{translate(COMPONENTS.audio_settings_dialog.title)}</DialogTitle>
                </DialogHeader>
                <div className="space-y-4 pt-2">
                    {/* Voice selection */}
                    <div className="space-y-2">
                        <Label>{translate(COMPONENTS.audio_settings_dialog.voice)}</Label>
                        <select
                            className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
                            value={voiceName}
                            onChange={(e) => {
                                setVoiceName(e.target.value);
                                const existing2 = getCachedSettings(chatType);
                                const settings: AudioSettings = { ...existing2, voiceName: e.target.value || null, speed, pitch };
                                setCachedSettings(chatType, settings);
                            }}
                        >
                            <option value="">{translate(COMPONENTS.audio_settings_dialog.system_default)}</option>
                            {filteredVoices.map((v) => (
                                <option key={v.name} value={v.name}>
                                    {getVoiceLabel(v)}
                                </option>
                            ))}
                        </select>
                    </div>

                    {/* Speed */}
                    <div className="space-y-2">
                        <Label>{translate(COMPONENTS.audio_settings_dialog.speed_label).replace("{0}", speed.toFixed(1))}</Label>
                        <input
                            type="range"
                            className="w-full"
                            value={speed}
                            min={0.5}
                            max={2.0}
                            step={0.1}
                            onChange={(e) => {
                                const val = parseFloat(e.target.value);
                                setSpeed(val);
                                setCachedSettings(chatType, { ...getCachedSettings(chatType), voiceName: voiceName || null, speed: val, pitch });
                            }}
                        />
                    </div>

                    {/* Pitch */}
                    <div className="space-y-2">
                        <Label>{translate(COMPONENTS.audio_settings_dialog.pitch_label).replace("{0}", pitch.toFixed(1))}</Label>
                        <input
                            type="range"
                            className="w-full"
                            value={pitch}
                            min={0.5}
                            max={2.0}
                            step={0.1}
                            onChange={(e) => {
                                const val = parseFloat(e.target.value);
                                setPitch(val);
                                setCachedSettings(chatType, { ...getCachedSettings(chatType), voiceName: voiceName || null, speed, pitch: val });
                            }}
                        />
                    </div>

                    <div className="flex justify-between pt-2">
                        <Button variant="outline" onClick={handleReset}>
                            {translate(COMPONENTS.audio_settings_dialog.reset_to_defaults)}
                        </Button>
                        <Button onClick={handleClose}>{translate(COMPONENTS.audio_settings_dialog.close)}</Button>
                    </div>
                </div>
            </DialogContent>
        </Dialog>
    );
}
