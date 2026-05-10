import type { SourceCitation, UploadResponse } from "@/lib/types";

const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL?.replace(/\/$/, "") ?? "http://localhost:8000";

export async function streamChat(
  body: { message: string; top_k?: number },
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
  files: File[],
  onProgress?: (progress: number) => void,
): Promise<UploadResponse> {
  return new Promise((resolve, reject) => {
    const formData = new FormData();
    for (const file of files) {
      formData.append("files", file);
    }

    const request = new XMLHttpRequest();
    request.open("POST", `${API_BASE_URL}/upload`);
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
