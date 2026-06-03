import type {
  DocumentSummary,
  GraphNodeDetail,
  GraphSnapshot,
  KnowledgeBase,
  KnowledgeBasePayload,
  SourceCitation,
  UploadResponse,
} from "@/lib/types";

const explicitApiBaseUrl = process.env.NEXT_PUBLIC_API_BASE_URL?.replace(/\/$/, "");

function resolveApiBaseUrl() {
  if (explicitApiBaseUrl) {
    return explicitApiBaseUrl;
  }
  if (typeof window !== "undefined" && window.location.port !== "3000") {
    return window.location.origin;
  }
  return "http://localhost:8000";
}

const API_BASE_URL = resolveApiBaseUrl();

export async function streamChat(
  body: { message: string; kb_id: string; top_k?: number },
  handlers: {
    onMeta?: (meta: { searchQuery?: string; matches?: number }) => void;
    onToken?: (token: string) => void;
    onSources?: (sources: SourceCitation[]) => void;
    onDone?: () => void;
  },
) {
  const response = await fetch(`${API_BASE_URL}/chat`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(body),
  });

  if (!response.ok || !response.body) {
    throw new Error(`Chat request failed with status ${response.status}`);
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { done, value } = await reader.read();
    if (done) {
      break;
    }

    buffer += decoder.decode(value, { stream: true });
    const lines = buffer.split("\n");
    buffer = lines.pop() ?? "";

    for (const line of lines) {
      const trimmed = line.trim();
      if (!trimmed) {
        continue;
      }
      const event = JSON.parse(trimmed) as {
        type: string;
        content?: string;
        searchQuery?: string;
        matches?: number;
        sources?: SourceCitation[];
      };

      if (event.type === "meta") {
        handlers.onMeta?.({
          searchQuery: event.searchQuery,
          matches: event.matches,
        });
      }
      if (event.type === "token" && event.content) {
        handlers.onToken?.(event.content);
      }
      if (event.type === "sources") {
        handlers.onSources?.(event.sources ?? []);
      }
      if (event.type === "done") {
        handlers.onDone?.();
      }
    }
  }
}

export function uploadDocuments(
  kbId: string,
  files: File[],
  onProgress?: (progress: number) => void,
): Promise<UploadResponse> {
  return new Promise((resolve, reject) => {
    const formData = new FormData();
    for (const file of files) {
      formData.append("files", file);
    }

    const request = new XMLHttpRequest();
  request.open("POST", `${API_BASE_URL}/kb/${encodeURIComponent(kbId)}/upload`);
    request.responseType = "json";

    request.upload.onprogress = (event) => {
      if (event.lengthComputable) {
        onProgress?.(Math.round((event.loaded / event.total) * 100));
      }
    };

    request.onload = () => {
      if (request.status >= 200 && request.status < 300) {
        resolve(request.response as UploadResponse);
        return;
      }

      reject(new Error(`Upload failed with status ${request.status}`));
    };

    request.onerror = () => reject(new Error("Upload failed"));
    request.send(formData);
  });
}

export async function listKnowledgeBases(): Promise<KnowledgeBase[]> {
  const response = await fetch(`${API_BASE_URL}/kb`, { cache: "no-store" });
  if (!response.ok) {
    throw new Error(`KB list request failed with status ${response.status}`);
  }
  return (await response.json()) as KnowledgeBase[];
}

export async function createKnowledgeBase(payload: KnowledgeBasePayload): Promise<KnowledgeBase> {
  const response = await fetch(`${API_BASE_URL}/kb`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(payload),
  });
  if (!response.ok) {
    throw new Error(`KB creation failed with status ${response.status}`);
  }
  return (await response.json()) as KnowledgeBase;
}

export async function renameKnowledgeBase(kbId: string, name: string): Promise<KnowledgeBase> {
  const response = await fetch(`${API_BASE_URL}/kb/${encodeURIComponent(kbId)}`, {
    method: "PATCH",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ name }),
  });
  if (!response.ok) {
    throw new Error(`KB rename failed with status ${response.status}`);
  }
  return (await response.json()) as KnowledgeBase;
}

export async function deleteKnowledgeBase(kbId: string): Promise<void> {
  const response = await fetch(`${API_BASE_URL}/kb/${encodeURIComponent(kbId)}`, {
    method: "DELETE",
  });
  if (!response.ok) {
    throw new Error(`KB delete failed with status ${response.status}`);
  }
}

export async function listKnowledgeBaseDocuments(kbId: string): Promise<DocumentSummary[]> {
  const response = await fetch(`${API_BASE_URL}/kb/${encodeURIComponent(kbId)}/documents`, {
    cache: "no-store",
  });
  if (!response.ok) {
    throw new Error(`Document list failed with status ${response.status}`);
  }
  return (await response.json()) as DocumentSummary[];
}

export async function deleteKnowledgeBaseDocument(
  kbId: string,
  documentId: string,
): Promise<void> {
  const response = await fetch(
    `${API_BASE_URL}/kb/${encodeURIComponent(kbId)}/documents/${encodeURIComponent(documentId)}`,
    {
      method: "DELETE",
    },
  );
  if (!response.ok) {
    throw new Error(`Document delete failed with status ${response.status}`);
  }
}

export async function getKnowledgeGraph(
  kbId: string,
  options?: { limit?: number; minWeight?: number },
): Promise<GraphSnapshot> {
  const params = new URLSearchParams();
  if (options?.limit) {
    params.set("limit", String(options.limit));
  }
  if (options?.minWeight) {
    params.set("min_weight", String(options.minWeight));
  }

  const response = await fetch(
    `${API_BASE_URL}/kb/${encodeURIComponent(kbId)}/graph?${params.toString()}`,
    { cache: "no-store" },
  );
  if (!response.ok) {
    throw new Error(`Graph request failed with status ${response.status}`);
  }
  return (await response.json()) as GraphSnapshot;
}

export async function getKnowledgeGraphNodeDetail(
  kbId: string,
  entityId: string,
  options?: { evidenceLimit?: number },
): Promise<GraphNodeDetail> {
  const params = new URLSearchParams();
  if (options?.evidenceLimit) {
    params.set("evidence_limit", String(options.evidenceLimit));
  }

  const query = params.toString();
  const response = await fetch(
    `${API_BASE_URL}/kb/${encodeURIComponent(kbId)}/graph/node/${encodeURIComponent(entityId)}${query ? `?${query}` : ""}`,
    { cache: "no-store" },
  );
  if (!response.ok) {
    throw new Error(`Graph node detail request failed with status ${response.status}`);
  }
  return (await response.json()) as GraphNodeDetail;
}
