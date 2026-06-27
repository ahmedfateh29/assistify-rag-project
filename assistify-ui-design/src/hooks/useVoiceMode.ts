"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { computeEnergy, convertToPCM16, pcm16ToFloat32, resample } from "@/src/lib/audioUtils";
import type { WsControlAction } from "@/src/hooks/useChatWebSocket";
import type { AppLanguage } from "@/src/lib/types";

export type VoiceState =
  | "idle"
  | "listening"
  | "processing"
  | "transcribing"
  | "speaking"
  | "interrupted"
  | "error";

export type VoiceWsApi = {
  connected: boolean;
  sendBinary: (buf: ArrayBuffer) => void;
  sendControl: (action: WsControlAction, extra?: Record<string, unknown>) => void;
};

const STT_PENDING_WATCHDOG_MS = 3000;
const WS_PREBUFFER_SECS = 0.3;
const TTS_SAMPLE_RATE = 24000;
const CAPTURE_SAMPLE_RATE = 16000;

type UseVoiceModeOptions = {
  language: AppLanguage;
  wsApiRef: React.MutableRefObject<VoiceWsApi>;
  ttsEnabled?: boolean;
  onUserTranscript?: (text: string) => void;
  onAssistantText?: (text: string) => void;
};

function statusLabel(state: VoiceState, language: AppLanguage, errorMsg?: string): string {
  const ar = language === "ar";
  if (errorMsg) return errorMsg;
  switch (state) {
    case "idle":
      return ar ? "جاهز — تحدث عندما تريد" : "Ready — speak when you want";
    case "listening":
      return ar ? "الاستماع..." : "Listening...";
    case "processing":
      return ar ? "جاري معالجة الصوت..." : "Processing speech...";
    case "transcribing":
      return ar ? "جاري التفكير..." : "Thinking...";
    case "speaking":
      return ar ? "يتحدث..." : "Speaking...";
    case "interrupted":
      return ar ? "تمت المقاطعة..." : "Interrupted...";
    case "error":
      return ar ? "خطأ" : "Error";
    default:
      return "";
  }
}

export function useVoiceMode({
  language,
  wsApiRef,
  ttsEnabled = true,
  onUserTranscript,
  onAssistantText,
}: UseVoiceModeOptions) {
  const [isOpen, setIsOpen] = useState(false);
  const [state, setState] = useState<VoiceState>("idle");
  const [statusText, setStatusText] = useState("");
  const [userText, setUserText] = useState("");
  const [assistantText, setAssistantText] = useState("");
  const [showRetry, setShowRetry] = useState(false);

  const isOpenRef = useRef(false);
  const stateRef = useRef<VoiceState>("idle");
  const isRecordingRef = useRef(false);
  const pauseSendRef = useRef(false);
  const ttsEnabledRef = useRef(ttsEnabled);
  const onUserTranscriptRef = useRef(onUserTranscript);
  const onAssistantTextRef = useRef(onAssistantText);

  const audioContextRef = useRef<AudioContext | null>(null);
  const mediaStreamRef = useRef<MediaStream | null>(null);
  const analyserRef = useRef<AnalyserNode | null>(null);
  const capturePollRef = useRef<ReturnType<typeof setInterval> | number | null>(null);
  const captureBufferRef = useRef<Float32Array | null>(null);

  const ttsCtxRef = useRef<AudioContext | null>(null);
  const ttsGainRef = useRef<GainNode | null>(null);
  const ttsSourcesRef = useRef<AudioBufferSourceNode[]>([]);
  const wsAudioStateRef = useRef<"idle" | "buffering" | "playing">("idle");
  const wsScheduledTimeRef = useRef(0);
  const wsPendingChunksRef = useRef<Float32Array[]>([]);
  const wsPendingDurationRef = useRef(0);

  const sttWatchdogRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const assistantBufferRef = useRef("");
  const startListeningRef = useRef<() => Promise<void>>(async () => {});

  useEffect(() => {
    ttsEnabledRef.current = ttsEnabled;
    onUserTranscriptRef.current = onUserTranscript;
    onAssistantTextRef.current = onAssistantText;
  });

  const setVoiceState = useCallback(
    (next: VoiceState, err?: string) => {
      stateRef.current = next;
      setState(next);
      setStatusText(statusLabel(next, language, err));
    },
    [language],
  );

  const getTtsContext = useCallback(() => {
    if (!ttsCtxRef.current || ttsCtxRef.current.state === "closed") {
      ttsCtxRef.current = new (window.AudioContext || (window as unknown as { webkitAudioContext: typeof AudioContext }).webkitAudioContext)({
        sampleRate: TTS_SAMPLE_RATE,
      });
      ttsGainRef.current = ttsCtxRef.current.createGain();
      ttsGainRef.current.connect(ttsCtxRef.current.destination);
    }
    if (ttsCtxRef.current.state === "suspended") void ttsCtxRef.current.resume();
    return ttsCtxRef.current;
  }, []);

  const stopTtsPlayback = useCallback(() => {
    for (const src of ttsSourcesRef.current) {
      try {
        src.stop();
        src.disconnect();
      } catch {
        /* ignore */
      }
    }
    ttsSourcesRef.current = [];
    wsAudioStateRef.current = "idle";
    wsPendingChunksRef.current = [];
    wsPendingDurationRef.current = 0;
    if (typeof window !== "undefined" && window.speechSynthesis) {
      window.speechSynthesis.cancel();
    }
  }, []);

  const scheduleAudioChunk = useCallback(
    (float32: Float32Array) => {
      const ctx = getTtsContext();
      const gain = ttsGainRef.current;
      if (!gain) return;
      const audioBuffer = ctx.createBuffer(1, float32.length, TTS_SAMPLE_RATE);
      audioBuffer.getChannelData(0).set(float32);
      const source = ctx.createBufferSource();
      source.buffer = audioBuffer;
      source.connect(gain);
      if (wsScheduledTimeRef.current < ctx.currentTime) {
        wsScheduledTimeRef.current = ctx.currentTime + 0.02;
      }
      source.start(wsScheduledTimeRef.current);
      ttsSourcesRef.current.push(source);
      wsScheduledTimeRef.current += audioBuffer.duration;
    },
    [getTtsContext],
  );

  const scheduleAllPending = useCallback(() => {
    while (wsPendingChunksRef.current.length > 0) {
      const chunk = wsPendingChunksRef.current.shift();
      if (chunk) scheduleAudioChunk(chunk);
    }
  }, [scheduleAudioChunk]);

  const handleTtsAudioStart = useCallback(() => {
    if (!ttsEnabledRef.current) return;
    const ctx = getTtsContext();
    if (wsAudioStateRef.current === "idle") {
      wsAudioStateRef.current = "buffering";
      wsPendingChunksRef.current = [];
      wsPendingDurationRef.current = 0;
      wsScheduledTimeRef.current = ctx.currentTime + 0.05;
    }
    setVoiceState("speaking");
    pauseSendRef.current = true;
  }, [getTtsContext, setVoiceState]);

  const handleWsAudioChunk = useCallback(
    (arrayBuffer: ArrayBuffer) => {
      if (!ttsEnabledRef.current || wsAudioStateRef.current === "idle") return;
      const float32 = pcm16ToFloat32(arrayBuffer);
      if (wsAudioStateRef.current === "buffering") {
        wsPendingChunksRef.current.push(float32);
        wsPendingDurationRef.current += float32.length / TTS_SAMPLE_RATE;
        if (wsPendingDurationRef.current >= WS_PREBUFFER_SECS) {
          wsAudioStateRef.current = "playing";
          scheduleAllPending();
        }
      } else if (wsAudioStateRef.current === "playing") {
        scheduleAudioChunk(float32);
      }
    },
    [scheduleAllPending, scheduleAudioChunk],
  );

  const clearSttWatchdog = useCallback(() => {
    if (sttWatchdogRef.current) {
      clearTimeout(sttWatchdogRef.current);
      sttWatchdogRef.current = null;
    }
  }, []);

  const armSttWatchdog = useCallback(() => {
    clearSttWatchdog();
    sttWatchdogRef.current = setTimeout(() => {
      sttWatchdogRef.current = null;
      if (!isOpenRef.current || stateRef.current !== "processing") return;
      const msg = language === "ar" ? "لم أسمعك بوضوح — حاول مرة أخرى" : "Didn't catch that — try again";
      setVoiceState("error", msg);
      setShowRetry(true);
    }, STT_PENDING_WATCHDOG_MS);
  }, [clearSttWatchdog, language, setVoiceState]);

  const releaseCapture = useCallback(() => {
    isRecordingRef.current = false;
    pauseSendRef.current = false;
    if (capturePollRef.current) {
      clearInterval(capturePollRef.current);
      capturePollRef.current = null;
    }
    if (analyserRef.current) {
      analyserRef.current.disconnect();
      analyserRef.current = null;
    }
    captureBufferRef.current = null;
    if (audioContextRef.current) {
      void audioContextRef.current.close();
      audioContextRef.current = null;
    }
    if (mediaStreamRef.current) {
      mediaStreamRef.current.getTracks().forEach((t) => t.stop());
      mediaStreamRef.current = null;
    }
  }, []);

  const resumeListening = useCallback(() => {
    assistantBufferRef.current = "";
    setAssistantText("");
    setUserText("");
    setShowRetry(false);
    stopTtsPlayback();
    if (isOpenRef.current) {
      void startListeningRef.current();
    } else {
      setVoiceState("idle");
    }
  }, [setVoiceState, stopTtsPlayback]);

  const completeVoiceTurn = useCallback(() => {
    clearSttWatchdog();
    const ctx = getTtsContext();
    const remaining = Math.max(0, wsScheduledTimeRef.current - ctx.currentTime);
    const afterPlayback = () => {
      wsAudioStateRef.current = "idle";
      pauseSendRef.current = false;
      if (isOpenRef.current) {
        setTimeout(() => {
          if (isOpenRef.current) void startListeningRef.current();
        }, 400);
      } else {
        setVoiceState("idle");
      }
    };
    if (remaining > 0.1 && wsAudioStateRef.current === "playing") {
      setTimeout(afterPlayback, remaining * 1000 + 200);
    } else {
      afterPlayback();
    }
  }, [clearSttWatchdog, getTtsContext, setVoiceState]);

  const stopListening = useCallback(
    (discard = false) => {
      if (!isRecordingRef.current) return;
      releaseCapture();
      wsApiRef.current.sendControl(discard ? "clear_audio_buffer" : "stop_recording");
      if (!discard) {
        setVoiceState("processing");
        armSttWatchdog();
      }
    },
    [armSttWatchdog, releaseCapture, setVoiceState, wsApiRef],
  );

  const bargeIn = useCallback(() => {
    stopTtsPlayback();
    wsApiRef.current.sendControl("interrupt");
    wsApiRef.current.sendControl("clear_audio_buffer");
    setVoiceState("interrupted");
    pauseSendRef.current = false;
    setTimeout(() => {
      if (isOpenRef.current) void startListeningRef.current();
    }, 300);
  }, [setVoiceState, stopTtsPlayback, wsApiRef]);

  const startListening = useCallback(async () => {
    if (!navigator.mediaDevices?.getUserMedia) {
      setVoiceState("error", "Voice not supported in this browser.");
      setShowRetry(true);
      return;
    }
    if (!wsApiRef.current.connected) {
      setVoiceState("error", "Not connected to server.");
      setShowRetry(true);
      return;
    }
    try {
      wsApiRef.current.sendControl("set_language", { language });
      const ctx = new (window.AudioContext || (window as unknown as { webkitAudioContext: typeof AudioContext }).webkitAudioContext)();
      if (ctx.state === "suspended") await ctx.resume();
      const stream = await navigator.mediaDevices.getUserMedia({
        audio: { echoCancellation: true, noiseSuppression: true, autoGainControl: true },
      });
      const source = ctx.createMediaStreamSource(stream);
      const analyser = ctx.createAnalyser();
      analyser.fftSize = 4096;
      source.connect(analyser);
      const buffer = new Float32Array(analyser.fftSize);
      captureBufferRef.current = buffer;
      capturePollRef.current = window.setInterval(() => {
        if (!isRecordingRef.current) return;
        analyser.getFloatTimeDomainData(buffer);
        if (pauseSendRef.current) {
          if (computeEnergy(buffer) > 0.09) bargeIn();
          return;
        }
        const resampled = resample(buffer, ctx.sampleRate, CAPTURE_SAMPLE_RATE);
        if (resampled && wsApiRef.current.connected) {
          wsApiRef.current.sendBinary(convertToPCM16(resampled));
        }
      }, 50);
      audioContextRef.current = ctx;
      mediaStreamRef.current = stream;
      analyserRef.current = analyser;
      isRecordingRef.current = true;
      pauseSendRef.current = false;
      setVoiceState("listening");
    } catch (err) {
      setVoiceState("error", err instanceof Error ? err.message : "Mic access denied");
      setShowRetry(true);
    }
  }, [bargeIn, language, setVoiceState, wsApiRef]);

  startListeningRef.current = startListening;

  const speakBrowserFallback = useCallback(
    (text: string) => {
      if (!window.speechSynthesis) {
        completeVoiceTurn();
        return;
      }
      const utter = new SpeechSynthesisUtterance(text);
      utter.lang = language === "ar" ? "ar-SA" : "en-US";
      utter.onend = () => completeVoiceTurn();
      utter.onerror = () => completeVoiceTurn();
      window.speechSynthesis.speak(utter);
      setVoiceState("speaking");
    },
    [completeVoiceTurn, language, setVoiceState],
  );

  const handleInboundMessage = useCallback(
    (msg: Record<string, unknown>) => {
      if (!isOpenRef.current) return;
      const type = String(msg.type ?? "");

      if (type === "transcript") {
        clearSttWatchdog();
        const text = String(msg.text ?? "").trim();
        if (msg.final && text) {
          setUserText(text);
          onUserTranscriptRef.current?.(text);
          setVoiceState("transcribing");
        }
      } else if (type === "thinking") {
        setVoiceState("transcribing");
      } else if (type === "aiResponseChunk" && msg.text) {
        assistantBufferRef.current += String(msg.text);
        setAssistantText(assistantBufferRef.current);
        onAssistantTextRef.current?.(assistantBufferRef.current);
        setVoiceState("transcribing");
        if (isRecordingRef.current) stopListening(true);
      } else if (type === "aiResponseDone") {
        const full = String(msg.fullText ?? assistantBufferRef.current ?? "");
        assistantBufferRef.current = full;
        setAssistantText(full);
        onAssistantTextRef.current?.(full);
        if (!msg.server_tts_pending && !ttsEnabledRef.current) {
          completeVoiceTurn();
        }
      } else if (type === "ttsAudioStart") {
        handleTtsAudioStart();
      } else if (type === "ttsAudioEnd") {
        if (wsAudioStateRef.current === "buffering" && wsPendingChunksRef.current.length > 0) {
          wsAudioStateRef.current = "playing";
          scheduleAllPending();
        }
        completeVoiceTurn();
      } else if (type === "ttsFallback") {
        const fb = String(msg.text ?? assistantBufferRef.current ?? "").trim();
        if (fb) speakBrowserFallback(fb);
        else completeVoiceTurn();
      } else if (type === "stt_failed") {
        clearSttWatchdog();
        setVoiceState("error", String(msg.message ?? "Speech recognition failed"));
        setShowRetry(true);
      } else if (type === "system_busy") {
        setVoiceState("error", String(msg.message ?? "System busy, try again"));
        setShowRetry(true);
      } else if (type === "error") {
        setVoiceState("error", String(msg.message ?? "Voice error"));
        setShowRetry(true);
      }
    },
    [
      clearSttWatchdog,
      completeVoiceTurn,
      handleTtsAudioStart,
      scheduleAllPending,
      setVoiceState,
      speakBrowserFallback,
      stopListening,
    ],
  );

  const handleBinaryMessage = useCallback(
    (chunk: ArrayBuffer) => {
      if (!isOpenRef.current) return;
      handleWsAudioChunk(chunk);
    },
    [handleWsAudioChunk],
  );

  const openVoiceMode = useCallback(() => {
    isOpenRef.current = true;
    setIsOpen(true);
    setShowRetry(false);
    assistantBufferRef.current = "";
    setUserText("");
    setAssistantText("");
    void startListening();
  }, [startListening]);

  const closeVoiceMode = useCallback(() => {
    isOpenRef.current = false;
    setIsOpen(false);
    clearSttWatchdog();
    stopListening(true);
    releaseCapture();
    stopTtsPlayback();
    setVoiceState("idle");
    setShowRetry(false);
  }, [clearSttWatchdog, releaseCapture, setVoiceState, stopListening, stopTtsPlayback]);

  useEffect(() => {
    if (!isOpen) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") closeVoiceMode();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [closeVoiceMode, isOpen]);

  useEffect(() => () => {
    releaseCapture();
    stopTtsPlayback();
    clearSttWatchdog();
  }, [clearSttWatchdog, releaseCapture, stopTtsPlayback]);

  return {
    isOpen,
    state,
    statusText,
    userText,
    assistantText,
    showRetry,
    openVoiceMode,
    closeVoiceMode,
    stopListening: () => stopListening(false),
    retry: resumeListening,
    handleInboundMessage,
    handleBinaryMessage,
  };
}
