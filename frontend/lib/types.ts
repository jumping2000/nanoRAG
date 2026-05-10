export type SourceCitation = {
  chunk_id: string;
  filename: string;
  page?: number | null;
  section?: string | null;
  score: number;
};

export type ChatMessage = {
  id: string;
  role: "user" | "assistant";
  content: string;
  status?: "streaming" | "done" | "error";
  sources?: SourceCitation[];
};

export type UploadSummary = {
  filename: string;
  ingested_chunks: number;
};

export type UploadResponse = {
  uploaded: UploadSummary[];
};

export type KnowledgeBase = {
  id: string;
  name: string;
  documents: number;
  chunks: number;
  updatedLabel: string;
};
