"use client";

import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import type { Components } from "react-markdown";

/** Normalize common LLM markdown quirks so lists and headings render correctly. */
export function normalizeMarkdown(content: string): string {
  let text = content.replace(/\r\n/g, "\n").trim();
  if (!text) return text;

  // Strip raw document-header separator lines (===, ---, ~~~) from RAG chunks
  text = text.replace(/^[=\-_~|]{4,}\s*$/gm, "");

  // Strip document title + underline pattern: "Title Text\n========"
  text = text.replace(/^.{3,80}\n[=\-_~]{4,}\s*$/gm, "");

  // Strip inline separator runs that survived (e.g. "text ===== more text")
  text = text.replace(/\s*[=_~]{4,}\s*/g, " ");

  // "**: - item" or "**:\n- item" — ensure list items start on their own line
  text = text.replace(/\*\*:\s*-\s+/g, "**:\n\n- ");

  // Multiple inline bullets on one line: "…sentence. - Next bullet"
  text = text.replace(/([.!?])\s+-\s+(?=\*\*|[A-Z])/g, "$1\n\n- ");

  // Section headers stuck to bullets: "Report**: - The"
  text = text.replace(/(\*\*[^*\n]+?\*\*:)\s+-\s+/g, "$1\n\n- ");

  // Horizontal rules written as "---" without newlines
  text = text.replace(/([^\n])\s*---\s*/g, "$1\n\n---\n\n");

  // Collapse 3+ blank lines
  text = text.replace(/\n{3,}/g, "\n\n");

  return text.trim();
}

type MarkdownContentProps = {
  content: string;
  variant?: "assistant" | "user";
  isStreaming?: boolean;
};

const assistantComponents: Components = {
  h1: ({ children }) => (
    <h1 className="mb-3 mt-4 border-b border-white/10 pb-2 text-lg font-semibold tracking-tight text-white first:mt-0">
      {children}
    </h1>
  ),
  h2: ({ children }) => (
    <h2 className="mb-2.5 mt-4 text-base font-semibold text-white first:mt-0">{children}</h2>
  ),
  h3: ({ children }) => (
    <h3 className="mb-2 mt-3 text-sm font-semibold text-[#10a37f] first:mt-0">{children}</h3>
  ),
  p: ({ children }) => <p className="mb-3 leading-relaxed text-[#e8e8f0] last:mb-0">{children}</p>,
  strong: ({ children }) => <strong className="font-semibold text-white">{children}</strong>,
  em: ({ children }) => <em className="italic text-[#d4d4dc]">{children}</em>,
  ul: ({ children }) => (
    <ul className="mb-3 ml-1 list-none space-y-2 pl-0 last:mb-0 [&>li]:relative [&>li]:pl-5 [&>li]:before:absolute [&>li]:before:left-0 [&>li]:before:top-[0.55em] [&>li]:before:h-1.5 [&>li]:before:w-1.5 [&>li]:before:rounded-full [&>li]:before:bg-[#10a37f] [&>li]:before:content-['']">
      {children}
    </ul>
  ),
  ol: ({ children }) => (
    <ol className="mb-3 list-decimal space-y-2 pl-5 marker:text-[#10a37f] last:mb-0">{children}</ol>
  ),
  li: ({ children }) => <li className="leading-relaxed text-[#e8e8f0]">{children}</li>,
  blockquote: ({ children }) => (
    <blockquote className="my-3 border-l-2 border-[#10a37f]/60 bg-white/[0.03] py-1 pl-4 italic text-[#c8c8d4]">
      {children}
    </blockquote>
  ),
  code: ({ className, children }) => {
    const isBlock = Boolean(className);
    if (isBlock) {
      return (
        <code className={`block overflow-x-auto rounded-lg bg-[#171717] px-3 py-2 font-mono text-xs text-[#a5f3d0] ${className ?? ""}`}>
          {children}
        </code>
      );
    }
    return (
      <code className="rounded bg-[#171717] px-1.5 py-0.5 font-mono text-xs text-[#a5f3d0]">{children}</code>
    );
  },
  pre: ({ children }) => (
    <pre className="my-3 overflow-x-auto rounded-xl border border-[#404040] bg-[#171717] p-3 last:mb-0">
      {children}
    </pre>
  ),
  a: ({ href, children }) => (
    <a
      href={href}
      target="_blank"
      rel="noopener noreferrer"
      className="font-medium text-[#10a37f] underline decoration-[#10a37f]/40 underline-offset-2 transition-colors hover:text-[#14c997] hover:decoration-[#14c997]"
    >
      {children}
    </a>
  ),
  hr: () => <hr className="my-4 border-0 border-t border-white/10" />,
  table: ({ children }) => (
    <div className="my-3 overflow-x-auto rounded-lg border border-[#404040]">
      <table className="w-full min-w-[280px] text-left text-sm">{children}</table>
    </div>
  ),
  thead: ({ children }) => <thead className="bg-[#1a1a1a] text-xs uppercase tracking-wide text-[#9ca3af]">{children}</thead>,
  th: ({ children }) => <th className="px-3 py-2 font-medium">{children}</th>,
  td: ({ children }) => <td className="border-t border-[#333] px-3 py-2 text-[#e8e8f0]">{children}</td>,
};

const userComponents: Components = {
  ...assistantComponents,
  p: ({ children }) => <p className="mb-2 leading-relaxed last:mb-0">{children}</p>,
  strong: ({ children }) => <strong className="font-semibold">{children}</strong>,
  ul: ({ children }) => (
    <ul className="mb-2 ml-1 list-none space-y-1 pl-0 last:mb-0 [&>li]:relative [&>li]:pl-4 [&>li]:before:absolute [&>li]:before:left-0 [&>li]:before:top-[0.6em] [&>li]:before:h-1 [&>li]:before:w-1 [&>li]:before:rounded-full [&>li]:before:bg-white/80 [&>li]:before:content-['']">
      {children}
    </ul>
  ),
};

export function MarkdownContent({ content, variant = "assistant", isStreaming }: MarkdownContentProps) {
  const normalized = normalizeMarkdown(content);
  const components = variant === "user" ? userComponents : assistantComponents;

  return (
    <div className="markdown-body text-sm">
      <ReactMarkdown remarkPlugins={[remarkGfm]} components={components}>
        {normalized}
      </ReactMarkdown>
      {isStreaming && (
        <span
          className="ml-0.5 inline-block h-[1.1em] w-[2px] animate-pulse rounded-full bg-[#10a37f] align-text-bottom"
          aria-hidden
        />
      )}
    </div>
  );
}
