"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import type { AppLanguage } from "@/src/lib/types";

export type WsControlAction =
  | "set_language"
  | "set_conversation_id"
  | "stop_recording"
  | "clear_audio_buffer"
  | "interrupt";

type ChatWsOptions = {
  language: AppLanguage;
  conversationId: string | null;
  ttsEnabled?: boolean;
  enabled?: boolean;
  onAssistantComplete?: (text: string) => void;
  onUserTranscript?: (text: string) => void;
  onInboundMessage?: (message: Record<string, unknown>) => void;
  onBinaryMessage?: (chunk: ArrayBuffer) => void;
};

const MAX_RECONNECT_DELAY_MS = 5000;

export function useChatWebSocket({
  language,
  conversationId,
  ttsEnabled = true,
  enabled = true,
  onAssistantComplete,
  onUserTranscript,
  onInboundMessage,
  onBinaryMessage,
}: ChatWsOptions) {
  const wsRef = useRef<WebSocket | null>(null);
  const [connected, setConnected] = useState(false);
  const [thinking, setThinking] = useState(false);
  const [streamingText, setStreamingText] = useState("");
  const [kbMessage, setKbMessage] = useState<string | null>(null);

  const languageRef = useRef(language);
  const conversationIdRef = useRef(conversationId);
  const ttsEnabledRef = useRef(ttsEnabled);
  const onAssistantCompleteRef = useRef(onAssistantComplete);
  const onUserTranscriptRef = useRef(onUserTranscript);
  const onInboundMessageRef = useRef(onInboundMessage);
  const onBinaryMessageRef = useRef(onBinaryMessage);

  useEffect(() => {
    languageRef.current = language;
    conversationIdRef.current = conversationId;
    ttsEnabledRef.current = ttsEnabled;
    onAssistantCompleteRef.current = onAssistantComplete;
    onUserTranscriptRef.current = onUserTranscript;
    onInboundMessageRef.current = onInboundMessage;
    onBinaryMessageRef.current = onBinaryMessage;
  });

  const closedByUnmountRef = useRef(false);
  const reconnectAttemptsRef = useRef(0);
  const reconnectTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const connect = useCallback(() => {
    if (typeof window === "undefined") return;
    const proto = window.location.protocol === "https:" ? "wss" : "ws";
    const ws = new WebSocket(`${proto}://${window.location.host}/ws`);
    ws.binaryType = "arraybuffer";
    wsRef.current = ws;

    ws.onopen = () => {
      reconnectAttemptsRef.current = 0;
      setConnected(true);
      ws.send(JSON.stringify({ type: "control", action: "set_language", language: languageRef.current }));
      if (conversationIdRef.current) {
        ws.send(
          JSON.stringify({
            type: "control",
            action: "set_conversation_id",
            conversation_id: conversationIdRef.current,
          }),
        );
      }
    };

    ws.onmessage = (event) => {
      if (event.data instanceof ArrayBuffer) {
        onBinaryMessageRef.current?.(event.data);
        return;
      }
      try {
        const msg = JSON.parse(event.data as string) as Record<string, unknown>;
        onInboundMessageRef.current?.(msg);
        const type = String(msg.type ?? "");
        if (type === "thinking") setThinking(true);
        if (type === "transcript" && msg.final) {
          onUserTranscriptRef.current?.(String(msg.text ?? ""));
          setThinking(true);
        }
        if (type === "aiResponseChunk" && msg.text) {
          setStreamingText((prev) => prev + String(msg.text));
        }
        if (type === "aiResponseDone") {
          setThinking(false);
          const full = String(msg.fullText ?? "");
          setStreamingText("");
          if (full) onAssistantCompleteRef.current?.(full);
        }
        if (type === "kb_updated" && msg.message) setKbMessage(String(msg.message));
      } catch {
        // ignore malformed frames
      }
    };

    ws.onclose = () => {
      setConnected(false);
      if (closedByUnmountRef.current) return;
      reconnectAttemptsRef.current += 1;
      const delay = Math.min(1000 * reconnectAttemptsRef.current, MAX_RECONNECT_DELAY_MS);
      reconnectTimerRef.current = setTimeout(connect, delay);
    };
  }, []);

  useEffect(() => {
    if (!enabled) {
      closedByUnmountRef.current = true;
      if (reconnectTimerRef.current) clearTimeout(reconnectTimerRef.current);
      wsRef.current?.close();
      setConnected(false);
      return;
    }
    closedByUnmountRef.current = false;
    connect();
    return () => {
      closedByUnmountRef.current = true;
      if (reconnectTimerRef.current) clearTimeout(reconnectTimerRef.current);
      wsRef.current?.close();
    };
  }, [connect, enabled]);

  useEffect(() => {
    const ws = wsRef.current;
    if (!ws || ws.readyState !== WebSocket.OPEN) return;
    ws.send(JSON.stringify({ type: "control", action: "set_language", language }));
    ws.send(JSON.stringify({ type: "control", action: "set_conversation_id", conversation_id: conversationId }));
  }, [language, conversationId]);

  const sendText = useCallback((text: string) => {
    const ws = wsRef.current;
    if (!ws || ws.readyState !== WebSocket.OPEN) return;
    ws.send(
      JSON.stringify({
        text,
        language: languageRef.current,
        conversation_id: conversationIdRef.current,
        tts_enabled: ttsEnabledRef.current,
      }),
    );
    setThinking(true);
    setStreamingText("");
  }, []);

  const sendBinary = useCallback((buf: ArrayBuffer) => {
    const ws = wsRef.current;
    if (!ws || ws.readyState !== WebSocket.OPEN) return;
    ws.send(buf);
  }, []);

  const sendControl = useCallback((action: WsControlAction, extra: Record<string, unknown> = {}) => {
    const ws = wsRef.current;
    if (!ws || ws.readyState !== WebSocket.OPEN) return;
    ws.send(JSON.stringify({ type: "control", action, ...extra }));
  }, []);

  return {
    connected,
    thinking,
    streamingText,
    kbMessage,
    sendText,
    sendBinary,
    sendControl,
    dismissKb: () => setKbMessage(null),
  };
}
