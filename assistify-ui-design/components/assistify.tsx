"use client";

import { useEffect, useState } from "react";
import { ChatArea } from "./chat-area";
import { Sidebar } from "./sidebar";
import { useConversations } from "@/src/hooks/useConversations";
import { useInactivityLogout } from "@/src/hooks/useInactivityLogout";
import { useProfile } from "@/src/hooks/useProfile";

export function Assistify() {
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const { profile, exitUrl } = useProfile();
  const {
    conversations,
    activeConversationId,
    messages,
    initialize,
    loadConversation,
    createConversation,
    renameConversation,
    deleteConversation,
    clearAllConversations,
    appendMessage,
  } = useConversations();

  useInactivityLogout({ timeoutMs: 30 * 60 * 1000, enabled: Boolean(profile) });

  useEffect(() => {
    if (!profile) return;
    initialize().catch(() => {});
  }, [initialize, profile]);

  const handleRenameConversation = async (id: string, title: string) => {
    const nextTitle = title.trim();
    if (!nextTitle) return;
    await renameConversation(id, nextTitle.slice(0, 80));
  };

  if (!profile) return null;

  return (
    <div className="flex h-screen bg-[#232323]">
      {sidebarOpen && (
        <div className="fixed inset-0 z-40 bg-black/50 lg:hidden" onClick={() => setSidebarOpen(false)} />
      )}
      <div
        className={`fixed inset-y-0 left-0 z-50 transition-transform duration-300 lg:static lg:translate-x-0 ${
          sidebarOpen ? "translate-x-0" : "-translate-x-full"
        }`}
      >
        <Sidebar
          conversations={conversations}
          activeConversationId={activeConversationId}
          onNewChat={async () => {
            await createConversation();
            setSidebarOpen(false);
          }}
          onSelectConversation={async (id) => {
            await loadConversation(id);
            setSidebarOpen(false);
          }}
          onRenameConversation={handleRenameConversation}
          onDeleteConversation={deleteConversation}
          onClearAll={clearAllConversations}
        />
      </div>
      <ChatArea
        messages={messages}
        activeConversationId={activeConversationId}
        appendMessage={appendMessage}
        exitUrl={exitUrl}
        wsEnabled={Boolean(profile)}
        onMenuClick={() => setSidebarOpen(!sidebarOpen)}
      />
    </div>
  );
}
