"use client";

import { Mic, Send } from "lucide-react";
import { useCallback, useEffect, useRef, useState } from "react";
import { useChatWebSocket } from "@/src/hooks/useChatWebSocket";
import { useVoiceMode, type VoiceWsApi } from "@/src/hooks/useVoiceMode";
import type { UiMessage } from "@/src/hooks/useConversations";
import type { AppLanguage } from "@/src/lib/types";
import { ChatMessage } from "./chat-message";
import { Header } from "./header";
import { KBBanner } from "./kb-banner";
import { ThinkingIndicator } from "./thinking-indicator";
import { VoiceOverlay } from "./voice-overlay";

interface ChatAreaProps {
  onMenuClick: () => void;
  messages: UiMessage[];
  activeConversationId: string | null;
  appendMessage: (role: "user" | "assistant", text: string, persist?: boolean) => Promise<void>;
  exitUrl: string;
  wsEnabled?: boolean;
}

export function ChatArea({
  onMenuClick,
  messages,
  activeConversationId,
  appendMessage,
  exitUrl,
  wsEnabled = true,
}: ChatAreaProps) {
  const [inputValue, setInputValue] = useState("");
  const [language, setLanguage] = useState<AppLanguage>("en");
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const voiceOpenRef = useRef(false);
  const wsApiRef = useRef<VoiceWsApi>({
    connected: false,
    sendBinary: () => {},
    sendControl: () => {},
  });

  const appendUser = useCallback(
    (text: string) => {
      appendMessage("user", text, true).catch(() => {});
    },
    [appendMessage],
  );

  const appendAssistant = useCallback(
    (text: string) => {
      appendMessage("assistant", text, true).catch(() => {});
    },
    [appendMessage],
  );

  const voiceMode = useVoiceMode({
    language,
    wsApiRef,
    ttsEnabled: true,
    onUserTranscript: appendUser,
    onAssistantText: () => {},
  });

  const onInboundCombined = useCallback(
    (msg: Record<string, unknown>) => {
      voiceMode.handleInboundMessage(msg);
    },
    [voiceMode],
  );

  const onBinaryCombined = useCallback(
    (chunk: ArrayBuffer) => {
      voiceMode.handleBinaryMessage(chunk);
    },
    [voiceMode],
  );

  const chatWs = useChatWebSocket({
    language,
    conversationId: activeConversationId,
    ttsEnabled: true,
    enabled: wsEnabled,
    onAssistantComplete: appendAssistant,
    onUserTranscript: (text) => {
      if (!voiceOpenRef.current) appendUser(text);
    },
    onInboundMessage: onInboundCombined,
    onBinaryMessage: onBinaryCombined,
  });

  useEffect(() => {
    wsApiRef.current = {
      connected: chatWs.connected,
      sendBinary: chatWs.sendBinary,
      sendControl: chatWs.sendControl,
    };
  }, [chatWs.connected, chatWs.sendBinary, chatWs.sendControl]);

  useEffect(() => {
    voiceOpenRef.current = voiceMode.isOpen;
  }, [voiceMode.isOpen]);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, chatWs.streamingText, voiceMode.assistantText]);

  const handleSend = async () => {
    const text = inputValue.trim();
    if (!text) return;
    setInputValue("");
    await appendMessage("user", text, true);
    chatWs.sendText(text);
  };

  return (
    <div className="relative flex flex-1 flex-col bg-[#232323]">
      <Header exitUrl={exitUrl} language={language} onLanguageChange={setLanguage} onMenuClick={onMenuClick} />
      {chatWs.kbMessage && <KBBanner message={chatWs.kbMessage} onDismiss={chatWs.dismissKb} />}
      <div className="flex-1 space-y-4 overflow-y-auto p-4 md:p-6">
        {messages.map((m) => (
          <ChatMessage key={m.id} message={m} />
        ))}
        {chatWs.streamingText && !voiceMode.isOpen && (
          <ChatMessage
            message={{ id: "stream", type: "assistant", content: chatWs.streamingText, language }}
          />
        )}
        {chatWs.thinking && !voiceMode.isOpen && <ThinkingIndicator />}
        <div ref={messagesEndRef} />
      </div>
      <div className="border-t border-[#333333] bg-[#232323] p-4 md:p-6">
        <div className="mx-auto max-w-4xl">
          <div className="flex items-end gap-3 rounded-lg border border-[#333333] bg-[#2b2b2b] p-3">
            <input
              className="flex-1 bg-transparent text-sm text-[#fafaff] outline-none placeholder:text-[#9ca3af]"
              value={inputValue}
              onChange={(e) => setInputValue(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && handleSend()}
              placeholder="Type your message..."
            />
            <div className="flex gap-2">
              <button
                type="button"
                className={`rounded p-2 transition-colors ${
                  voiceMode.isOpen
                    ? "bg-[#6c63ff]/20 text-[#6c63ff]"
                    : "text-[#6c63ff] hover:bg-[#333333]"
                }`}
                onClick={() => (voiceMode.isOpen ? voiceMode.closeVoiceMode() : voiceMode.openVoiceMode())}
                aria-label={voiceMode.isOpen ? "Close voice mode" : "Open voice mode"}
              >
                <Mic size={20} />
              </button>
              <button
                type="button"
                className="rounded bg-[#10a37f] p-2 text-white transition-colors hover:bg-[#0d8a6b]"
                onClick={handleSend}
                aria-label="Send message"
              >
                <Send size={20} />
              </button>
            </div>
          </div>
        </div>
      </div>

      <VoiceOverlay
        isOpen={voiceMode.isOpen}
        state={voiceMode.state}
        statusText={voiceMode.statusText}
        userText={voiceMode.userText}
        assistantText={voiceMode.assistantText}
        showRetry={voiceMode.showRetry}
        onClose={voiceMode.closeVoiceMode}
        onStop={voiceMode.stopListening}
        onRetry={voiceMode.retry}
      />
    </div>
  );
}
