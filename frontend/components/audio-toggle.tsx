"use client";

import { useState, useCallback } from "react";
import { Mic, MicOff, Volume2, Volume1, VolumeX, Pause, Play, Square, Settings } from "lucide-react";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { useTranslate } from "@/lib/translation-helpers";
import { COMMON } from "@/app/common/translations";
import { SpeechState } from "@/hooks/use-speech";

interface AudioToggleProps {
    /* Mic — simple on/off toggle */
    micEnabled?: boolean;
    onMicChange?: (enabled: boolean) => void;

    /* Speaker */
    speakerEnabled?: boolean;
    onSpeakerChange?: (enabled: boolean) => void;
    volume?: number;
    onVolumeChange?: (vol: number) => void;
    speakerMuted?: boolean;
    onSpeakerMuteToggle?: () => void;

    /* Playback (speaker only) */
    speechState?: SpeechState;
    onPause?: () => void;
    onResume?: () => void;
    onStop?: () => void;

    /* Settings */
    onSettingsClick?: () => void;
}

/* ------------------------------------------------------------------ */
/*  Volume slider popover shared by mic & speaker                     */
/* ------------------------------------------------------------------ */

function VolumePopover({
    icon,
    open,
    onOpenChange,
    volume,
    onVolumeChange,
    muted,
    onMuteToggle,
    device = "speaker",
    position = "bottom",
    children,
}: {
    icon: React.ReactNode;
    open: boolean;
    onOpenChange: (open: boolean) => void;
    volume: number;
    onVolumeChange: (vol: number) => void;
    muted: boolean;
    onMuteToggle: () => void;
    device?: "speaker" | "mic";
    position?: "top" | "bottom";
    children?: React.ReactNode;
}) {
    const volPercent = Math.round((muted ? 0 : volume) * 100);

    const handleWheel = useCallback((e: React.WheelEvent) => {
        e.preventDefault();
        const delta = e.deltaY > 0 ? -0.05 : 0.05;
        onVolumeChange(Math.max(0, Math.min(1, volume + delta)));
    }, [volume, onVolumeChange]);

    const handleSlider = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
        onVolumeChange(parseInt(e.target.value, 10) / 100);
    }, [onVolumeChange]);

    return (
        <Popover open={open} onOpenChange={onOpenChange}>
            <PopoverTrigger
                className="flex-shrink-0 p-1 rounded hover:bg-muted transition-colors"
                onWheel={handleWheel}
            >
                {icon}
            </PopoverTrigger>
            <PopoverContent
                side={position === "top" ? "top" : "bottom"}
                align="center"
                className="w-auto p-3"
            >
                <div style={{
                    display: "flex",
                    flexDirection: "column",
                    alignItems: "center",
                    gap: "0.5rem",
                }}>
                    {/* Vertical slider */}
                    <div style={{ position: "relative", height: 128, display: "flex", alignItems: "center" }}>
                        <input
                            type="range"
                            min={0}
                            max={100}
                            value={volPercent}
                            onChange={handleSlider}
                            style={{
                                writingMode: "vertical-lr",
                                direction: "rtl",
                                WebkitAppearance: "slider-vertical",
                                width: 20,
                                height: 120,
                                padding: 0,
                                cursor: "pointer",
                            }}
                            title={`${volPercent}%`}
                        />
                    </div>

                    {/* Volume % label */}
                    <span className="text-muted-foreground" style={{ fontSize: "0.7rem" }}>
                        {volPercent}%
                    </span>

                    {/* Mute toggle */}
                    <button
                        type="button"
                        onClick={onMuteToggle}
                        className="flex-shrink-0 p-1 rounded hover:bg-muted transition-colors"
                        title={muted ? "Unmute" : "Mute"}
                    >
                        {device === "mic"
                            ? (muted
                                ? <MicOff className="h-4 w-4 text-red-500" />
                                : <Mic className="h-4 w-4 text-green-600" />)
                            : (muted
                                ? <VolumeX className="h-4 w-4 text-red-500" />
                                : <Volume2 className="h-4 w-4 text-green-600" />)
                        }
                    </button>

                    {/* Extra buttons (playback, settings) */}
                    {children}
                </div>
            </PopoverContent>
        </Popover>
    );
}

/* ------------------------------------------------------------------ */
/*  Main component                                                    */
/* ------------------------------------------------------------------ */

export default function AudioToggle({
    micEnabled: micProp,
    onMicChange,
    speakerEnabled: speakerProp,
    onSpeakerChange,
    volume: volProp,
    onVolumeChange,
    speakerMuted: spkMutedProp,
    onSpeakerMuteToggle,
    speechState,
    onPause,
    onResume,
    onStop,
    onSettingsClick,
}: AudioToggleProps) {
    const translate = useTranslate();

    // Internal state when no props provided
    const [internalMic, setInternalMic] = useState(false);
    const [internalSpeaker, setInternalSpeaker] = useState(false);
    const [speakerOpen, setSpeakerOpen] = useState(false);

    const isMicOn = micProp ?? internalMic;
    const isSpeakerOn = speakerProp ?? internalSpeaker;
    const speakerVolume = volProp ?? 1.0;
    const speakerMuted = spkMutedProp ?? false;
    const isSpeaking = speechState === "speaking";
    const isPaused = speechState === "paused";

    const toggleMic = useCallback(() => {
        const next = !isMicOn;
        onMicChange?.(next);
        setInternalMic(next);
    }, [isMicOn, onMicChange]);

    const toggleSpeaker = useCallback(() => {
        const next = !isSpeakerOn;
        onSpeakerChange?.(next);
        setInternalSpeaker(next);
    }, [isSpeakerOn, onSpeakerChange]);

    const speakerOff = !isSpeakerOn || speakerMuted || speakerVolume === 0;
    const SpeakerIcon = speakerOff ? VolumeX : Volume2;
    const speakerColor = speakerOff ? "#dc2626" : "#16a34a";

    const MicIcon = isMicOn ? Mic : MicOff;
    const micColor = isMicOn ? "#16a34a" : "#dc2626";

    return (
        <>
            {/* ---- Microphone — simple on/off toggle ---- */}
            <button
                type="button"
                onClick={toggleMic}
                className="flex-shrink-0 p-1 rounded hover:bg-muted transition-colors"
                title={translate(isMicOn ? COMMON.microphone_on : COMMON.microphone_off)}
            >
                <MicIcon className="h-4 w-4" style={{ color: micColor }} />
            </button>

            {/* ---- Speaker ---- */}
            <VolumePopover
                open={speakerOpen}
                onOpenChange={setSpeakerOpen}
                volume={speakerVolume}
                onVolumeChange={(v) => {
                    onVolumeChange?.(v);
                    if (!isSpeakerOn && v > 0) {
                        onSpeakerChange?.(true);
                        setInternalSpeaker(true);
                    }
                }}
                muted={speakerMuted}
                onMuteToggle={() => onSpeakerMuteToggle?.()}
                position="top"
                icon={
                    <SpeakerIcon className="h-4 w-4" style={{
                        color: speakerColor,
                        animation: isSpeaking ? "pulse 1.5s ease-in-out infinite" : undefined,
                    }} />
                }
            >
                {/* Playback controls */}
                {(isSpeaking || isPaused) && (
                    <div style={{ display: "flex", gap: "0.3rem" }}>
                        {isPaused ? (
                            <button
                                type="button"
                                onClick={onResume}
                                className="flex-shrink-0 p-1 rounded hover:bg-muted transition-colors"
                                title={translate(COMMON.audio_resume)}
                            >
                                <Play className="h-4 w-4 text-green-600" />
                            </button>
                        ) : (
                            <button
                                type="button"
                                onClick={onPause}
                                className="flex-shrink-0 p-1 rounded hover:bg-muted transition-colors"
                                title={translate(COMMON.audio_pause)}
                            >
                                <Pause className="h-4 w-4 text-amber-600" />
                            </button>
                        )}
                        <button
                            type="button"
                            onClick={onStop}
                            className="flex-shrink-0 p-1 rounded hover:bg-muted transition-colors"
                            title={translate(COMMON.audio_stop)}
                        >
                            <Square className="h-4 w-4 text-red-500" />
                        </button>
                    </div>
                )}

                {/* Settings gear */}
                <button
                    type="button"
                    onClick={() => {
                        setSpeakerOpen(false);
                        onSettingsClick?.();
                    }}
                    className="flex-shrink-0 p-1 rounded hover:bg-muted transition-colors"
                    title={translate(COMMON.audio_settings)}
                >
                    <Settings className="h-3.5 w-3.5 text-muted-foreground" />
                </button>
            </VolumePopover>
        </>
    );
}
