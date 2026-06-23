"use client";

import { useState } from "react";
import {
  Download,
  Edit2,
  Eye,
  FileText,
  Loader2,
  RefreshCw,
  Trash2,
  Upload,
} from "lucide-react";
import { useKnowledge } from "@/src/hooks/useKnowledge";
import { useProfile } from "@/src/hooks/useProfile";
import { Card } from "@/src/components/ui/Card";
import { Modal } from "@/src/components/ui/Modal";
import { PageHeader } from "@/src/components/ui/PageHeader";
import { SearchInput } from "@/src/components/ui/SearchInput";
import { StatCard } from "@/src/components/ui/StatCard";
import { KbPipelineStatusPanel } from "@/src/features/knowledge/KbPipelineStatusPanel";
import { pipelineStateLabel } from "@/src/types/kbPipeline";

function formatBytes(bytes?: number) {
  if (!bytes) return "—";
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

export function KnowledgePageContent({
  title = "Knowledge Base",
  readOnly = false,
}: {
  title?: string;
  readOnly?: boolean;
}) {
  const {
    files,
    pipelineStatus,
    isPipelineBusy,
    loading,
    upload,
    reindexAll,
    reindexFile,
    clearCache,
    remove,
    getFileContent,
    getPdfData,
    updateFileContent,
    downloadUrl,
  } = useKnowledge();
  const { profile } = useProfile();

  const businessLabel =
    profile?.tenant_name || (profile?.tenant_id ? `Business #${profile.tenant_id}` : "");

  const [searchTerm, setSearchTerm] = useState("");
  const [uploading, setUploading] = useState(false);
  const [reindexing, setReindexing] = useState(false);
  const [previewOpen, setPreviewOpen] = useState(false);
  const [previewTitle, setPreviewTitle] = useState("");
  const [previewContent, setPreviewContent] = useState("");
  const [previewPdf, setPreviewPdf] = useState<string | null>(null);
  const [editOpen, setEditOpen] = useState(false);
  const [editFilename, setEditFilename] = useState("");
  const [editContent, setEditContent] = useState("");
  const [saving, setSaving] = useState(false);

  const filtered = files.filter((f) =>
    f.filename.toLowerCase().includes(searchTerm.toLowerCase()),
  );

  const actionsDisabled = isPipelineBusy || uploading || reindexing;
  const statusLabel = pipelineStateLabel(pipelineStatus?.state);

  const handleUpload = async (file: File) => {
    setUploading(true);
    try {
      await upload(file);
    } finally {
      setUploading(false);
    }
  };

  const handleReindexAll = async () => {
    setReindexing(true);
    try {
      await reindexAll();
    } finally {
      setReindexing(false);
    }
  };

  const openPreview = async (filename: string) => {
    setPreviewTitle(filename);
    setPreviewPdf(null);
    setPreviewContent("");
    setPreviewOpen(true);
    if (filename.toLowerCase().endsWith(".pdf")) {
      const data = await getPdfData(filename);
      const b64 = data.data ?? data.base64 ?? "";
      setPreviewPdf(b64 ? `data:application/pdf;base64,${b64}` : null);
    } else {
      const content = await getFileContent(filename);
      setPreviewContent(content);
    }
  };

  const openEdit = async (filename: string) => {
    const content = await getFileContent(filename);
    setEditFilename(filename);
    setEditContent(content);
    setEditOpen(true);
  };

  const saveEdit = async () => {
    setSaving(true);
    try {
      await updateFileContent(editFilename, editContent);
      setEditOpen(false);
    } finally {
      setSaving(false);
    }
  };

  return (
    <div>
      <PageHeader
        title={title}
        subtitle={
          businessLabel
            ? `Managing knowledge base for ${businessLabel}`
            : "Upload and manage knowledge base documents"
        }
      />

      <div className="mb-8 grid gap-4 md:grid-cols-3">
        <StatCard icon={<FileText className="h-6 w-6" />} label="Documents" value={String(files.length)} colorClass="text-[#10a37f]" />
        <StatCard
          icon={<Upload className="h-6 w-6" />}
          label="KB Status"
          value={statusLabel}
          colorClass={
            pipelineStatus?.state === "failed"
              ? "text-red-400"
              : isPipelineBusy
                ? "text-[#f6c33c]"
                : "text-[#2563eb]"
          }
        />
        <StatCard
          icon={<FileText className="h-6 w-6" />}
          label="Indexed Chunks"
          value={String(files.reduce((sum, f) => sum + (f.indexed_chunks ?? 0), 0))}
          colorClass="text-[#f6c33c]"
        />
      </div>

      <KbPipelineStatusPanel status={pipelineStatus} />

      {!readOnly && (
        <Card className="mb-8 border-dashed p-8 text-center">
          <Upload className="mx-auto mb-4 h-10 w-10 text-[#10a37f]" />
          <p className="mb-4 text-[#9ca3af]">Upload PDF or TXT documents for the knowledge base</p>
          <label
            className={`inline-flex items-center gap-2 rounded-lg bg-[#10a37f] px-6 py-2 text-sm font-medium text-white hover:bg-[#0d8a68] ${
              actionsDisabled ? "pointer-events-none opacity-50" : "cursor-pointer"
            }`}
          >
            {uploading ? <Loader2 className="h-4 w-4 animate-spin" /> : <Upload className="h-4 w-4" />}
            Choose file
            <input
              type="file"
              accept=".pdf,.txt"
              className="hidden"
              disabled={actionsDisabled}
              onChange={(e) => e.target.files?.[0] && handleUpload(e.target.files[0]).catch(() => {})}
            />
          </label>
          <button
            type="button"
            disabled={actionsDisabled}
            className="ml-3 inline-flex items-center gap-2 rounded-lg border border-[#444] px-4 py-2 text-sm text-[#9ca3af] hover:text-[#fafaff] disabled:cursor-not-allowed disabled:opacity-50"
            onClick={() => handleReindexAll().catch(() => {})}
          >
            {reindexing ? <Loader2 className="h-4 w-4 animate-spin" /> : <RefreshCw className="h-4 w-4" />}
            Reindex all
          </button>
          <button
            type="button"
            disabled={actionsDisabled}
            className="ml-3 inline-flex items-center gap-2 rounded-lg border border-[#444] px-4 py-2 text-sm text-[#9ca3af] hover:text-[#fafaff] disabled:cursor-not-allowed disabled:opacity-50"
            onClick={() => clearCache().catch(() => {})}
          >
            Clear cache
          </button>
        </Card>
      )}

      <div className="mb-4">
        <SearchInput value={searchTerm} onChange={setSearchTerm} placeholder="Search documents..." />
      </div>

      {loading ? (
        <p className="text-[#9ca3af]">Loading documents...</p>
      ) : (
        <div className="space-y-3">
          {filtered.map((f) => (
            <Card key={f.filename} className="flex flex-col gap-3 p-4 md:flex-row md:items-center md:justify-between">
              <div className="flex items-center gap-3">
                <FileText className="h-5 w-5 text-[#10a37f]" />
                <div>
                  <span className="font-medium text-[#fafaff]">{f.filename}</span>
                  <p className="text-xs text-[#9ca3af]">
                    {formatBytes(f.size)}
                    {typeof f.indexed_chunks === "number" ? ` · ${f.indexed_chunks} chunks` : ""}
                  </p>
                </div>
              </div>
              <div className="flex flex-wrap gap-2">
                <button
                  type="button"
                  onClick={() => openPreview(f.filename).catch(() => {})}
                  className="flex items-center gap-1 rounded-lg bg-[#333333] px-3 py-1.5 text-xs text-[#fafaff] hover:bg-[#444444]"
                >
                  <Eye className="h-3 w-3" /> Preview
                </button>
                <a
                  href={downloadUrl(f.filename)}
                  className="flex items-center gap-1 rounded-lg bg-[#333333] px-3 py-1.5 text-xs text-[#fafaff] hover:bg-[#444444]"
                >
                  <Download className="h-3 w-3" /> Download
                </a>
                {!readOnly && (
                  <>
                    {f.filename.toLowerCase().endsWith(".txt") && (
                      <button
                        type="button"
                        onClick={() => openEdit(f.filename).catch(() => {})}
                        className="flex items-center gap-1 rounded-lg bg-[#2563eb] px-3 py-1.5 text-xs text-white"
                      >
                        <Edit2 className="h-3 w-3" /> Edit
                      </button>
                    )}
                    <button
                      type="button"
                      disabled={actionsDisabled}
                      onClick={() => reindexFile(f.filename).catch(() => {})}
                      className="flex items-center gap-1 rounded-lg bg-[#333333] px-3 py-1.5 text-xs text-[#fafaff] disabled:opacity-50"
                    >
                      <RefreshCw className="h-3 w-3" /> Reindex
                    </button>
                    <button
                      type="button"
                      onClick={() => remove(f.filename).catch(() => {})}
                      disabled={actionsDisabled}
                      className="rounded-lg p-2 text-[#9ca3af] hover:text-red-400 disabled:opacity-50"
                      aria-label="Delete document"
                    >
                      <Trash2 className="h-4 w-4" />
                    </button>
                  </>
                )}
              </div>
            </Card>
          ))}
          {filtered.length === 0 && (
            <p className="py-8 text-center text-[#9ca3af]">No documents found</p>
          )}
        </div>
      )}

      <Modal open={previewOpen} onClose={() => setPreviewOpen(false)} title={`Preview: ${previewTitle}`}>
        {previewPdf ? (
          <iframe src={previewPdf} className="h-96 w-full rounded-lg border border-[#333]" title="PDF preview" />
        ) : (
          <pre className="max-h-96 overflow-auto whitespace-pre-wrap rounded-lg bg-[#232323] p-4 text-sm text-[#fafaff]">
            {previewContent || "No preview available"}
          </pre>
        )}
      </Modal>

      <Modal
        open={editOpen}
        onClose={() => setEditOpen(false)}
        title={`Edit: ${editFilename}`}
        footer={
          <>
            <button type="button" onClick={() => setEditOpen(false)} className="flex-1 rounded-lg bg-[#333333] px-4 py-2 text-[#fafaff]">
              Cancel
            </button>
            <button
              type="button"
              onClick={saveEdit}
              disabled={saving}
              className="flex flex-1 items-center justify-center gap-2 rounded-lg bg-[#10a37f] px-4 py-2 text-white disabled:opacity-50"
            >
              {saving ? <Loader2 className="h-4 w-4 animate-spin" /> : null}
              Save
            </button>
          </>
        }
      >
        <textarea
          className="h-64 w-full rounded-lg border border-[#333333] bg-[#232323] px-4 py-2 font-mono text-sm text-[#fafaff]"
          value={editContent}
          onChange={(e) => setEditContent(e.target.value)}
        />
      </Modal>
    </div>
  );
}
