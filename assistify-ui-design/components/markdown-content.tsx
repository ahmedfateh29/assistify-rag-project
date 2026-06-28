"use client";

import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import type { Components } from "react-markdown";

function isMarkdownTableLine(line: string): boolean {
  return /^\s*\|.+\|\s*$/.test(line.trim());
}

function isPipeTableFootnoteCell(cell: string): boolean {
  const c = cell.trim();
  if (c.length > 55) return true;
  return /\b(may be|can be|on request|established accounts|subject to|see below)\b/i.test(c);
}

function looksLikeTableRowLabel(tail: string): boolean {
  const t = tail.trim();
  if (!t || !/^[A-Z]/.test(t)) return false;
  if (isPipeTableFootnoteCell(t)) return false;
  const words = t.split(/\s+/);
  return words.length >= 1 && words.length <= 8 && t.length <= 60;
}

function looksLikePipeTableDataCell(cell: string): boolean {
  if (/[\$€£]/.test(cell)) return true;
  if (/\b\d+(?:\.\d+)?\s*%/.test(cell)) return true;
  if (/\b\d+\s*-\s*\d+\s+business\s+days?\b/i.test(cell)) return true;
  if (/\b(?:minutes?|hours?|same business day|held\s+\d)\b/i.test(cell)) return true;
  if (/\/\s*day\b/i.test(cell)) return true;
  return false;
}

function splitMergedRowCells(cells: string[]): string[] {
  const out: string[] = [];
  for (const cell of cells) {
    if (isPipeTableFootnoteCell(cell)) {
      out.push(cell);
      continue;
    }
    const feeRow = cell.match(/^(\$[\d,]+(?:\.\d+)?(?:\s+[a-z]{2,15}){0,2})\s+([A-Z][A-Za-z].*)$/);
    if (feeRow && looksLikeTableRowLabel(feeRow[2])) {
      out.push(feeRow[1].trim(), feeRow[2].trim());
      continue;
    }
    const free = cell.match(/^(Free|\$[\d,]+(?:\.\d+)?(?:\s*\/\s*day)?)\s+([A-Z][A-Za-z].*)$/);
    if (free && looksLikeTableRowLabel(free[2])) {
      out.push(free[1].trim(), free[2].trim());
      continue;
    }
    const pct = cell.match(/^(.+?%\s*(?:\([^)]+\))?)\s+([A-Z][A-Za-z][A-Za-z0-9\s\-().'/]+)$/);
    if (pct && looksLikeTableRowLabel(pct[2])) {
      out.push(pct[1].trim(), pct[2].trim());
      continue;
    }
    out.push(cell);
  }
  return out;
}

/** Normalize common LLM markdown quirks so lists and headings render correctly. */
function tryParsePipeTable(line: string): string | null {
  let parts = line.split("|").map((p) => p.trim()).filter((p) => p.length > 0);
  let footnote = "";
  if (parts.length > 0) {
    const last = parts[parts.length - 1] ?? "";
    const fn = last.match(/^(Free)\s+(Limits\b.+)$/i);
    if (fn && isPipeTableFootnoteCell(fn[2])) {
      parts[parts.length - 1] = fn[1].trim();
      footnote = fn[2].trim();
    } else if (isPipeTableFootnoteCell(last)) {
      footnote = parts.pop() ?? "";
    }
  }
  parts = splitMergedRowCells(parts);
  if (parts.length < 6) return null;

  const splitMergedHeader = (cells: string[], colCount: number): string[] => {
    if (colCount <= 0 || cells.length <= colCount) return cells;
    const idx = colCount - 1;
    const cell = cells[idx] ?? "";
    const m = cell.match(/^(fee|limit|notes|term|amount)\s+(.+)$/i);
    if (!m || m[2].trim().length < 2) return cells;
    const next = [...cells];
    next[idx] = m[1].toLowerCase() === "fee" ? "Fee" : m[1];
    next.splice(colCount, 0, m[2].trim());
    return next;
  };

  const looksLikeHeader = (cells: string[]): boolean => {
    if (cells.some((cell) => looksLikePipeTableDataCell(cell))) return false;
    let labelish = 0;
    for (const cell of cells) {
      if (/[\$€£]|\d/.test(cell)) continue;
      if (/\b(type|timing|limit|fee|product|amount|term|notes|balance|rate)\b/i.test(cell)) labelish += 1;
      else if (cell.split(/\s+/).length <= 4) labelish += 1;
    }
    return labelish >= Math.max(2, Math.ceil(cells.length / 2));
  };

  for (const cols of [4, 3, 5, 6, 2]) {
    const trial = splitMergedHeader(parts, cols);
    if (trial.length < cols * 2) continue;
    const header = trial.slice(0, cols);
    const body = trial.slice(cols);
    if (body.length % cols !== 0) continue;
    if (!looksLikeHeader(header)) continue;
    const rows = [header];
    for (let i = 0; i < body.length; i += cols) {
      rows.push(body.slice(i, i + cols));
    }
    if (rows.length < 2) continue;
    const lastRow = rows[rows.length - 1];
    if (lastRow && isPipeTableFootnoteCell(lastRow[lastRow.length - 1] ?? "")) {
      footnote = footnote || (lastRow.pop() ?? "");
      if (lastRow.every((cell) => !cell.trim())) rows.pop();
    }
    const md = [
      `| ${rows[0].join(" | ")} |`,
      `| ${Array(cols).fill("---").join(" | ")} |`,
      ...rows.slice(1).map((row) => `| ${row.join(" | ")} |`),
    ];
    return footnote ? `${md.join("\n")}\n\n${footnote}` : md.join("\n");
  }
  return null;
}

function formatPipeDelimitedTables(text: string): string {
  const trimmed = text.trim();
  if ((trimmed.match(/\|/g) ?? []).length < 3) return text;

  const lines = text.split("\n");
  const out: string[] = [];
  for (const line of lines) {
    if (isMarkdownTableLine(line)) {
      out.push(line);
      continue;
    }
    const converted = tryParsePipeTable(line.trim());
    out.push(converted ?? line);
  }
  let merged = out.join("\n").trim();
  if ((merged.match(/\|/g) ?? []).length >= 6 && !merged.includes("\n|")) {
    const single = tryParsePipeTable(merged);
    if (single) merged = single;
  }
  return merged;
}

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

  // Horizontal rules written as "---" without newlines — never touch markdown table rows
  text = text
    .split("\n")
    .map((line) => {
      if (isMarkdownTableLine(line)) return line;
      return line.replace(/([^\n|])\s*---\s*/g, "$1\n\n---\n\n");
    })
    .join("\n");

  // Collapse 3+ blank lines
  text = text.replace(/\n{3,}/g, "\n\n");

  text = formatPipeDelimitedTables(text);

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
