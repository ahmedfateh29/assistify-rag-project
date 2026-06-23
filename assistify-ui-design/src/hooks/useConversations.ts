"use client";

import { useCallback, useState } from "react";
import { apiClient } from "@/src/lib/apiClient";
import type { ConversationDetail, ConversationMessage, ConversationSummary } from "@/src/lib/types";

export interface UiMessage {
  id: string;
  type: "user" | "assistant";
  content: string;
  language: "en" | "ar";
}

export function useConversations() {
  const [conversations, setConversations] = useState<ConversationSummary[]>([]);
  const [activeConversationId, setActiveConversationId] = useState<string | null>(null);
  const [messages, setMessages] = useState<UiMessage[]>([]);
  const [isLoading, setIsLoading] = useState(false);

  const mapMessage = useCallback((msg: ConversationMessage): UiMessage => {
    const language: "en" | "ar" = /[\u0600-\u06FF]/.test(msg.text) ? "ar" : "en";
    return { id: `${Date.now()}-${Math.random()}`, type: msg.role, content: msg.text, language };
  }, []);

  const refreshConversations = useCallback(async () => {
    const data = await apiClient.get<{ conversations: ConversationSummary[] }>("/conversations");
    setConversations(data.conversations ?? []);
    return data.conversations ?? [];
  }, []);

  const initialize = useCallback(async () => {
    setIsLoading(true);
    try {
      await refreshConversations();
    } finally {
      setIsLoading(false);
    }
  }, [refreshConversations]);

  const loadConversation = useCallback(
    async (id: string) => {
      const data = await apiClient.get<ConversationDetail>(`/conversations/${id}`);
      setActiveConversationId(id);
      setMessages((data.messages ?? []).map(mapMessage));
    },
    [mapMessage],
  );

  const createConversation = useCallback(async () => {
    const data = await apiClient.post<ConversationDetail>("/conversations");
    await refreshConversations();
    setActiveConversationId(data.id);
    setMessages((data.messages ?? []).map(mapMessage));
    return data;
  }, [mapMessage, refreshConversations]);

  const renameConversation = useCallback(
    async (id: string, title: string) => {
      await apiClient.patch(`/conversations/${id}`, { title });
      await refreshConversations();
    },
    [refreshConversations],
  );

  const deleteConversation = useCallback(
    async (id: string) => {
      await apiClient.delete(`/conversations/${id}`);
      if (activeConversationId === id) {
        setActiveConversationId(null);
        setMessages([]);
      }
      await refreshConversations();
    },
    [activeConversationId, refreshConversations],
  );

  const clearAllConversations = useCallback(async () => {
    await apiClient.delete("/conversations");
    setActiveConversationId(null);
    setMessages([]);
    await refreshConversations();
  }, [refreshConversations]);

  const appendMessage = useCallback(
    async (role: "user" | "assistant", text: string, persist = true) => {
      setMessages((prev) => [...prev, mapMessage({ role, text })]);
      if (persist && activeConversationId) {
        await apiClient.post(`/conversations/${activeConversationId}/message`, { role, text });
        await refreshConversations();
      }
    },
    [activeConversationId, mapMessage, refreshConversations],
  );

  return {
    conversations,
    activeConversationId,
    messages,
    isLoading,
    initialize,
    loadConversation,
    createConversation,
    renameConversation,
    deleteConversation,
    clearAllConversations,
    appendMessage,
  };
}
