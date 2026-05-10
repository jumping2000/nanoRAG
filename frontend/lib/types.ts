export type SourceCitation = {
  chunk_id: string;
  kb_id: string;
  document_id: string;
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
  document_id: string;
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
};

export type KnowledgeBasePayload = {
  id: string;
  name: string;
};

export type DocumentSummary = {
  document_id: string;
  kb_id: string;
  kb_name: string;
  filename: string;
  chunk_count: number;
  created_at: string;
};
