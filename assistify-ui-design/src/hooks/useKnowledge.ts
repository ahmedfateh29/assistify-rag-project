"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { apiClient, secureFetch } from "@/src/lib/apiClient";
import {
  type KbPipelineStatus,
  isPipelineBusy,
} from "@/src/types/kbPipeline";

export interface KnowledgeFile {
  /** Canonical on-disk name used for API calls (may include upload prefix). */
  filename: string;
  /** Human-friendly label for the UI. */
  displayName: string;
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

const STORED_PREFIX_RE = /^[0-9a-f]{8}_(.+)$/i;

function stripStoredPrefix(name: string): string {
  const match = STORED_PREFIX_RE.exec(name);
  return match ? match[1] : name;
}

function normalizeFile(entry: RawKnowledgeFile): KnowledgeFile {
  const stored =
    entry.stored_name ||
    entry.filename ||
    entry.name ||
    "";
  const display =
    entry.display_name ||
    (stored ? stripStoredPrefix(stored) : "") ||
    stored;
  return {
    filename: stored,
    displayName: display,
    size: entry.size,
    uploaded_at: entry.modified ? new Date(entry.modified * 1000).toISOString() : undefined,
    indexed_chunks: entry.indexed_chunks,
  };
}

const POLL_INTERVAL_MS = 1000;

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
    collection_chunks: typeof data.collection_chunks === "number" ? data.collection_chunks : undefined,
    stage_timings: data.stage_timings as Record<string, number> | undefined,
    updated_at: typeof data.updated_at === "number" ? data.updated_at : undefined,
    proxy_degraded: data.proxy_degraded === true,
  };
}

function logKbStatusReceived(status: KbPipelineStatus): void {
  console.info("[KB_STATUS_RECEIVED]", {
    updated_at: status.updated_at,
    state: status.state,
    stage: status.stage,
  });
}

function logKbStatusIgnoredStale(existingUpdatedAt: number, incomingUpdatedAt: number | undefined): void {
  console.info("[KB_STATUS_IGNORED_STALE]", {
    existing_updated_at: existingUpdatedAt,
    incoming_updated_at: incomingUpdatedAt,
  });
}

export function useKnowledge() {
  const [files, setFiles] = useState<KnowledgeFile[]>([]);
  const [pipelineStatus, setPipelineStatus] = useState<KbPipelineStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const refreshRef = useRef<(() => Promise<void>) | null>(null);
  /** Highest backend updated_at applied to the UI — stale polls cannot regress past this. */
  const appliedUpdatedAtRef = useRef<number | undefined>(undefined);
  /** True while a kb_status HTTP request started by the poll loop is in flight. */
  const pollInFlightRef = useRef(false);
  /** Set when READY is observed so late poll completions are ignored. */
  const pollingStoppedRef = useRef(false);

  const applyKbStatus = useCallback((status: KbPipelineStatus): boolean => {
    logKbStatusReceived(status);

    const incomingUpdatedAt = status.updated_at;
    const existingUpdatedAt = appliedUpdatedAtRef.current;
    const incomingReady = status.state === "ready";

    // READY always wins — even if the proxy flagged the response as degraded.
    // The backend is authoritative for completion; a proxy_degraded flag on a
    // READY response must not prevent the UI from advancing to the ready state.
    if (incomingReady) {
      if (incomingUpdatedAt !== undefined) {
        appliedUpdatedAtRef.current = incomingUpdatedAt;
      }
      setPipelineStatus(status);
      return true;
    }

    // Non-READY proxy_degraded responses are non-authoritative — keep polling
    // without regressing the UI to an earlier state.
    if (status.proxy_degraded) {
      console.info("[KB_STATUS_IGNORED_DEGRADED]", { message: status.message });
      return false;
    }

    // Only apply monotonic guard when both sides have timestamps.
    if (
      existingUpdatedAt !== undefined
      && incomingUpdatedAt !== undefined
      && incomingUpdatedAt < existingUpdatedAt
    ) {
      logKbStatusIgnoredStale(existingUpdatedAt, incomingUpdatedAt);
      return false;
    }

    if (incomingUpdatedAt !== undefined) {
      appliedUpdatedAtRef.current = incomingUpdatedAt;
    }

    setPipelineStatus(status);
    return true;
  }, []);

  const stopKbPolling = useCallback(() => {
    if (pollRef.current) {
      clearInterval(pollRef.current);
      pollRef.current = null;
    }
  }, []);

  const fetchKbStatus = useCallback(async (): Promise<KbPipelineStatus> => {
    const data = await apiClient.get<Record<string, unknown>>("/api/knowledge/kb_status");
    const status = parseKbStatus(data);
    applyKbStatus(status);
    return status;
  }, [applyKbStatus]);

  const refreshFiles = useCallback(async () => {
    const list = await apiClient.get<RawKnowledgeFile[] | { files?: RawKnowledgeFile[] }>(
      "/api/knowledge/files",
    );
    setFiles(parseFileList(list));
  }, []);

  const refresh = useCallback(async () => {
    setLoading(true);
    try {
      const [list, kb] = await Promise.all([
        apiClient.get<RawKnowledgeFile[] | { files?: RawKnowledgeFile[] }>("/api/knowledge/files"),
        apiClient.get<Record<string, unknown>>("/api/knowledge/kb_status"),
      ]);
      setFiles(parseFileList(list));
      applyKbStatus(parseKbStatus(kb));
    } finally {
      setLoading(false);
    }
  }, [applyKbStatus]);

  refreshRef.current = refresh;

  const handlePipelineReady = useCallback(async () => {
    pollingStoppedRef.current = true;
    stopKbPolling();
    await refreshRef.current?.();
  }, [stopKbPolling]);

  const startKbPolling = useCallback(() => {
    stopKbPolling();
    pollingStoppedRef.current = false;

    const poll = async () => {
      if (pollingStoppedRef.current || pollInFlightRef.current) {
        return;
      }

      pollInFlightRef.current = true;
      try {
        const data = await apiClient.get<Record<string, unknown>>("/api/knowledge/kb_status");
        if (pollingStoppedRef.current) {
          return;
        }

        const status = parseKbStatus(data);
        const applied = applyKbStatus(status);
        if (!applied) {
          return;
        }

        if (!isPipelineBusy(status.state)) {
          await handlePipelineReady();
        }
      } catch {
        // keep polling on transient errors
      } finally {
        pollInFlightRef.current = false;
      }
    };

    void poll();
    pollRef.current = setInterval(() => {
      void poll();
    }, POLL_INTERVAL_MS);
  }, [applyKbStatus, handlePipelineReady, stopKbPolling]);

  const upload = useCallback(
    async (file: File) => {
      startKbPolling();
      const form = new FormData();
      form.append("file", file);
      const res = await secureFetch("/proxy/upload_rag", { method: "POST", body: form });
      if (!res.ok) {
        stopKbPolling();
        pollingStoppedRef.current = false;
        throw new Error("Upload failed");
      }
      // File is saved on disk before background indexing finishes.
      await refreshFiles();
      const status = await fetchKbStatus();
      if (!isPipelineBusy(status.state)) {
        await handlePipelineReady();
      }
    },
    [startKbPolling, stopKbPolling, fetchKbStatus, refreshFiles, handlePipelineReady],
  );

  const reindexAll = useCallback(async () => {
    startKbPolling();
    try {
      await apiClient.post("/api/knowledge/reindex-all", {});
    } catch (err) {
      stopKbPolling();
      pollingStoppedRef.current = false;
      throw err;
    }
    pollingStoppedRef.current = true;
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
        pollingStoppedRef.current = false;
        throw err;
      }
      pollingStoppedRef.current = true;
      stopKbPolling();
      await refresh();
    },
    [startKbPolling, stopKbPolling, refresh],
  );

  const clearCache = useCallback(async () => {
    const data = await apiClient.post<{ message?: string }>("/api/knowledge/clear-cache", {});
    return (
      data?.message ?? "Cache cleared — next chat will use fresh knowledge base data."
    );
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
    return apiClient.get<{ bytes_b64?: string; data?: string; base64?: string }>(
      `/api/knowledge/files/${encodeURIComponent(filename)}/pdf-data`,
    );
  }, []);

  const previewUrl = useCallback((filename: string) => {
    return `/api/knowledge/files/${encodeURIComponent(filename)}/preview`;
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
    let cancelled = false;

    const bootstrap = async () => {
      try {
        await refresh();
        if (cancelled) return;
        const status = await fetchKbStatus();
        if (cancelled) return;
        if (isPipelineBusy(status.state)) {
          startKbPolling();
        }
      } catch {
        if (!cancelled) {
          // Self-heal: start polling even when initial refresh fails.
          startKbPolling();
        }
      }
    };

    void bootstrap();
    return () => {
      cancelled = true;
      stopKbPolling();
    };
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
    previewUrl,
    updateFileContent,
    downloadUrl,
  };
}
