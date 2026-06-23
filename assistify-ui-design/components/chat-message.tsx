import type { UiMessage } from "@/src/hooks/useConversations";

export function ChatMessage({ message }: { message: UiMessage }) {
  const isUser = message.type === "user";
  return (
    <div className={`mb-4 flex ${isUser ? "justify-end" : "justify-start"}`}>
      <div
        className={`max-w-[80%] rounded-2xl px-4 py-3 text-sm ${
          isUser ? "bg-[#10a37f] text-white" : "bg-[#2b2b2b] text-[#fafaff]"
        }`}
      >
        {message.content}
      </div>
    </div>
  );
}
