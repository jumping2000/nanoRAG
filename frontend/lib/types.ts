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

export type GraphEvidence = {
  chunk_id: string;
  document_id: string;
  filename: string;
  page?: number | null;
  section?: string | null;
  snippet: string;
  confidence: number;
};

export type GraphNode = {
  id: string;
  label: string;
  entity_type: string;
  mentions: number;
};

export type GraphEdge = {
  id: string;
  source: string;
  target: string;
  predicate: string;
  weight: number;
  evidence: GraphEvidence[];
};

export type GraphNodeRelation = {
  edge_id: string;
  predicate: string;
  direction: "incoming" | "outgoing";
  counterpart: GraphNode;
  weight: number;
  evidence: GraphEvidence[];
};

export type GraphNodeDocument = {
  document_id: string;
  filename: string;
  mention_count: number;
};

export type GraphStats = {
  nodes: number;
  edges: number;
  mentions: number;
};

export type GraphSnapshot = {
  kb_id: string;
  nodes: GraphNode[];
  edges: GraphEdge[];
  stats: GraphStats;
};

export type GraphNodeDetail = {
  node: GraphNode;
  relations: GraphNodeRelation[];
  documents: GraphNodeDocument[];
  stats: Record<string, number>;
};
