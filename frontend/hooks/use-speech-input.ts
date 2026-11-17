"use client";

import { useEffect, useRef, useState, useCallback } from "react";
import { useTranslate } from "@/lib/translation-helpers";
import { COMMON } from "@/app/common/translations";

interface SpeechInputResult {
    transcript: string;
    interimTranscript: string;
    isListening: boolean;
    speechInputError: string | null;
}

export function useSpeechInput(enabled: boolean): SpeechInputResult {
    const translate = useTranslate();
    const [transcript, setTranscript] = useState("");
    const [interimTranscript, setInterimTranscript] = useState("");
    const [isListening, setIsListening] = useState(false);
    const [speechInputError, setSpeechInputError] = useState<string | null>(null);
    const recognitionRef = useRef<any>(null);
    const enabledRef = useRef(enabled);
    enabledRef.current = enabled;

    const stopRecognition = useCallback(() => {
        if (recognitionRef.current) {
            try { recognitionRef.current.stop(); } catch {}
            recognitionRef.current = null;
        }
        setIsListening(false);
    }, []);

    useEffect(() => {
        if (!enabled) {
            stopRecognition();
            setTranscript("");
            setInterimTranscript("");
            setSpeechInputError(null);
            return;
        }

        if (typeof window === "undefined") return;

        const SpeechRecognitionAPI =
            (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition;

        if (!SpeechRecognitionAPI) {
            setSpeechInputError(translate(COMMON.speech_input_unsupported));
            return;
        }

        setSpeechInputError(null);

        const recognition = new SpeechRecognitionAPI();
        recognition.continuous = true;
        recognition.interimResults = true;
        recognition.lang = navigator.language || "en-US";

        let finalText = "";
        let silenceTimer: ReturnType<typeof setTimeout> | null = null;

        const resetSilenceTimer = () => {
            if (silenceTimer) clearTimeout(silenceTimer);
            silenceTimer = setTimeout(() => {
                if (enabledRef.current) {
                    stopRecognition();
                    setTimeout(() => {
                        if (enabledRef.current) {
                            try { recognition.start(); } catch {}
                        }
                    }, 300);
                }
            }, 3000);
        };

        recognition.onresult = (event: any) => {
            let interim = "";
            for (let i = event.resultIndex; i < event.results.length; i++) {
                const result = event.results[i];
                if (result.isFinal) {
                    finalText += result[0].transcript + " ";
                } else {
                    interim += result[0].transcript;
                }
            }
            setTranscript(finalText.trim());
            setInterimTranscript(interim);
            resetSilenceTimer();
        };

        let intentionalStop = false;

        recognition.onerror = (event: any) => {
            if (event.error === "not-allowed") {
                setSpeechInputError(translate(COMMON.speech_mic_denied));
                intentionalStop = true;
                stopRecognition();
            } else if (event.error === "network") {
                setSpeechInputError(translate(COMMON.speech_network_error));
                intentionalStop = true;
                stopRecognition();
            } else if (event.error !== "no-speech" && event.error !== "aborted") {
                const template = translate(COMMON.speech_recognition_error);
                setSpeechInputError(template.replace("{error}", event.error));
            }
        };

        recognition.onend = () => {
            if (enabledRef.current && !intentionalStop) {
                try { recognition.start(); } catch {}
            }
        };

        try {
            recognition.start();
            recognitionRef.current = recognition;
            setIsListening(true);
            setTranscript("");
            setInterimTranscript("");
        } catch (err: any) {
            const template = translate(COMMON.speech_mic_failed);
            setSpeechInputError(template.replace("{error}", err.message || translate(COMMON.unknown_error) || "Unknown error"));
        }

        return () => {
            stopRecognition();
            if (silenceTimer) clearTimeout(silenceTimer);
        };
    }, [enabled, stopRecognition, translate]);

    return { transcript, interimTranscript, isListening, speechInputError };
}
