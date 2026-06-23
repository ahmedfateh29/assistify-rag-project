"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { apiClient, secureFetch } from "@/src/lib/apiClient";
import {
  type KbPipelineStatus,
  isPipelineBusy,
} from "@/src/types/kbPipeline";

export interface KnowledgeFile {
  filename: string;
  size?: number;
  uploaded_at?: string;
  indexed_chunks?: number;
}

interface RawKnowledgeFile {
  filename?: string;
  name?: string;
  stored_name?: string;
  display_name?: string;
  size?: number;
  modified?: number;
  indexed_chunks?: number;
}

const POLL_INTERVAL_MS = 1000;

function normalizeFile(entry: RawKnowledgeFile): KnowledgeFile {
  const filename =
    entry.filename ||
    entry.display_name ||
    entry.name ||
    entry.stored_name ||
    "";
  return {
    filename,
    size: entry.size,
    uploaded_at: entry.modified ? new Date(entry.modified * 1000).toISOString() : undefined,
    indexed_chunks: entry.indexed_chunks,
  };
}

function parseFileList(data: RawKnowledgeFile[] | { files?: RawKnowledgeFile[] }): KnowledgeFile[] {
  const raw = Array.isArray(data) ? data : data.files ?? [];
  return raw.map(normalizeFile).filter((f) => f.filename);
}

function parseKbStatus(data: Record<string, unknown>): KbPipelineStatus {
  const state = String(data.state ?? "ready").toLowerCase() as KbPipelineStatus["state"];
  return {
    state: ["uploading", "processing", "ready", "failed"].includes(state)
      ? state
      : "ready",
    stage: data.stage as KbPipelineStatus["stage"],
    message: data.message as string | undefined,
    filename: data.filename as string | null | undefined,
    percent: typeof data.percent === "number" ? data.percent : undefined,
    indexed_chunks: typeof data.indexed_chunks === "number" ? data.indexed_chunks : undefined,
    total_chunks: typeof data.total_chunks === "number" ? data.total_chunks : undefined,
    stage_timings: data.stage_timings as Record<string, number> | undefined,
    updated_at: typeof data.updated_at === "number" ? data.updated_at : undefined,
  };
}

export function useKnowledge() {
  const [files, setFiles] = useState<KnowledgeFile[]>([]);
  const [pipelineStatus, setPipelineStatus] = useState<KbPipelineStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const refreshRef = useRef<(() => Promise<void>) | null>(null);

  const stopKbPolling = useCallback(() => {
    if (pollRef.current) {
      clearInterval(pollRef.current);
      pollRef.current = null;
    }
  }, []);

  const fetchKbStatus = useCallback(async (): Promise<KbPipelineStatus> => {
    const data = await apiClient.get<Record<string, unknown>>("/api/knowledge/kb_status");
    const status = parseKbStatus(data);
    setPipelineStatus(status);
    return status;
  }, []);

  const refresh = useCallback(async () => {
    setLoading(true);
    try {
      const [list, kb] = await Promise.all([
        apiClient.get<RawKnowledgeFile[] | { files?: RawKnowledgeFile[] }>("/api/knowledge/files"),
        apiClient.get<Record<string, unknown>>("/api/knowledge/kb_status"),
      ]);
      setFiles(parseFileList(list));
      setPipelineStatus(parseKbStatus(kb));
    } finally {
      setLoading(false);
    }
  }, []);

  refreshRef.current = refresh;

  const startKbPolling = useCallback(() => {
    stopKbPolling();
    const poll = async () => {
      try {
        const status = await fetchKbStatus();
        if (!isPipelineBusy(status.state)) {
          stopKbPolling();
          await refreshRef.current?.();
        }
      } catch {
        // keep polling on transient errors
      }
    };
    void poll();
    pollRef.current = setInterval(() => {
      void poll();
    }, POLL_INTERVAL_MS);
  }, [fetchKbStatus, stopKbPolling]);

  const upload = useCallback(
    async (file: File) => {
      startKbPolling();
      const form = new FormData();
      form.append("file", file);
      const res = await secureFetch("/proxy/upload_rag", { method: "POST", body: form });
      if (!res.ok) {
        stopKbPolling();
        throw new Error("Upload failed");
      }
      await fetchKbStatus();
    },
    [startKbPolling, stopKbPolling, fetchKbStatus],
  );

  const reindexAll = useCallback(async () => {
    startKbPolling();
    try {
      await apiClient.post("/api/knowledge/reindex-all", {});
    } catch (err) {
      stopKbPolling();
      throw err;
    }
    stopKbPolling();
    await refresh();
  }, [startKbPolling, stopKbPolling, refresh]);

  const reindexFile = useCallback(
    async (filename: string) => {
      startKbPolling();
      try {
        await apiClient.post(`/api/knowledge/reindex-file?filename=${encodeURIComponent(filename)}`, {});
      } catch (err) {
        stopKbPolling();
        throw err;
      }
      stopKbPolling();
      await refresh();
    },
    [startKbPolling, stopKbPolling, refresh],
  );

  const clearCache = useCallback(async () => {
    await apiClient.post("/api/knowledge/clear-cache", {});
  }, []);

  const remove = useCallback(
    async (filename: string) => {
      await apiClient.delete(`/api/knowledge/files/${encodeURIComponent(filename)}`);
      await refresh();
    },
    [refresh],
  );

  const getFileContent = useCallback(async (filename: string) => {
    const data = await apiClient.get<{ content?: string } | string>(
      `/api/knowledge/files/${encodeURIComponent(filename)}`,
    );
    if (typeof data === "string") return data;
    return data.content ?? "";
  }, []);

  const getPdfData = useCallback(async (filename: string) => {
    return apiClient.get<{ data?: string; base64?: string }>(
      `/api/knowledge/files/${encodeURIComponent(filename)}/pdf-data`,
    );
  }, []);

  const updateFileContent = useCallback(
    async (filename: string, content: string) => {
      await apiClient.put(`/api/knowledge/files/${encodeURIComponent(filename)}`, { content });
      await refresh();
    },
    [refresh],
  );

  const downloadUrl = useCallback((filename: string) => {
    return `/api/knowledge/files/${encodeURIComponent(filename)}/download`;
  }, []);

  useEffect(() => {
    refresh()
      .then(() => fetchKbStatus())
      .then((status) => {
        if (isPipelineBusy(status.state)) startKbPolling();
      })
      .catch(() => {});
    return () => stopKbPolling();
  }, [refresh, fetchKbStatus, startKbPolling, stopKbPolling]);

  const isPipelineBusyState = isPipelineBusy(pipelineStatus?.state);

  return {
    files,
    pipelineStatus,
    isPipelineBusy: isPipelineBusyState,
    loading,
    refresh,
    upload,
    reindexAll,
    reindexFile,
    clearCache,
    remove,
    getFileContent,
    getPdfData,
    updateFileContent,
    downloadUrl,
  };
}
