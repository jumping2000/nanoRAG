"use client";

import {
  ArrowUp,
  BrainCircuit,
  ChevronRight,
  Copy,
  Database,
  FileText,
  FolderKanban,
  GitBranch,
  LibraryBig,
  LoaderCircle,
  Network,
  PanelRight,
  Paperclip,
  Pencil,
  Plus,
  RefreshCcw,
  SearchCode,
  SendHorizonal,
  Trash2,
  Upload,
} from "lucide-react";
import { useDeferredValue, useEffect, useRef, useState } from "react";

import { ChatMarkdown } from "@/components/chat-markdown";
import { KnowledgeGraphPanel } from "@/components/knowledge-graph-panel";
import { ThemeToggle } from "@/components/theme-toggle";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";
import { Textarea } from "@/components/ui/textarea";
import { useChatStream } from "@/hooks/use-chat-stream";
import type { DocumentSummary, KnowledgeBase } from "@/lib/types";
import { cn } from "@/lib/utils";
import {
  createKnowledgeBase,
  deleteKnowledgeBase,
  deleteKnowledgeBaseDocument,
  listKnowledgeBaseDocuments,
  listKnowledgeBases,
  renameKnowledgeBase,
  uploadDocuments,
} from "@/services/api";

export function NanoRagShell() {
  const [knowledgeBases, setKnowledgeBases] = useState<KnowledgeBase[]>([]);
  const [activeKnowledgeBase, setActiveKnowledgeBase] = useState<KnowledgeBase | null>(null);
  const [documents, setDocuments] = useState<DocumentSummary[]>([]);
  const [documentFilter, setDocumentFilter] = useState("");
  const [composerValue, setComposerValue] = useState("");
  const [isLoadingKnowledgeBases, setIsLoadingKnowledgeBases] = useState(true);
  const [isLoadingDocuments, setIsLoadingDocuments] = useState(false);
  const [isUploading, setIsUploading] = useState(false);
  const [uploadProgress, setUploadProgress] = useState(0);
  const [uploadError, setUploadError] = useState("");
  const [kbError, setKbError] = useState("");
  const [sidePanelTab, setSidePanelTab] = useState<"content" | "graph">("content");
  const fileInputRef = useRef<HTMLInputElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const conversationRef = useRef<HTMLDivElement>(null);

  const {
    messages,
    isStreaming,
    lastMatchCount,
    lastSearchQuery,
    resetConversation,
    retryLast,
    sendMessage,
  } = useChatStream();
  const deferredDocumentFilter = useDeferredValue(documentFilter.trim().toLowerCase());
  const filteredDocuments = deferredDocumentFilter
    ? documents.filter((document) => document.filename.toLowerCase().includes(deferredDocumentFilter))
    : documents;

  useEffect(() => {
    void loadKnowledgeBases();
  }, []);

  useEffect(() => {
    const element = textareaRef.current;
    if (!element) {
      return;
    }
    element.style.height = "0px";
    element.style.height = `${Math.min(element.scrollHeight, 220)}px`;
  }, [composerValue]);

  useEffect(() => {
    const container = conversationRef.current;
    if (!container) {
      return;
    }
    container.scrollTop = container.scrollHeight;
  }, [messages]);

  useEffect(() => {
    if (!activeKnowledgeBase) {
      setDocuments([]);
      setDocumentFilter("");
      return;
    }
    setDocumentFilter("");
    resetConversation();
    void loadDocuments(activeKnowledgeBase.id);
  }, [activeKnowledgeBase?.id]);

  async function handleSend() {
    if (!composerValue.trim() || !activeKnowledgeBase) {
      return;
    }

    const message = composerValue;
    setComposerValue("");
    await sendMessage(message, activeKnowledgeBase.id);
  }

  async function handleUpload(fileList: FileList | File[] | null) {
    const files = Array.from(fileList ?? []);
    if (!files.length || !activeKnowledgeBase) {
      return;
    }

    setUploadError("");
    setIsUploading(true);
    setUploadProgress(0);

    try {
      await uploadDocuments(activeKnowledgeBase.id, files, setUploadProgress);
      await Promise.all([loadKnowledgeBases(activeKnowledgeBase.id), loadDocuments(activeKnowledgeBase.id)]);
      setUploadProgress(100);
    } catch (error) {
      setUploadError(error instanceof Error ? error.message : "Upload failed");
    } finally {
      setIsUploading(false);
      window.setTimeout(() => setUploadProgress(0), 500);
    }
  }

  function onDrop(event: React.DragEvent<HTMLDivElement>) {
    event.preventDefault();
    void handleUpload(event.dataTransfer.files);
  }

  async function loadKnowledgeBases(preferredKbId?: string) {
    setKbError("");
    setIsLoadingKnowledgeBases(true);
    try {
      const nextKnowledgeBases = await listKnowledgeBases();
      setKnowledgeBases(nextKnowledgeBases);
      setActiveKnowledgeBase((current) => {
        const nextId = preferredKbId ?? current?.id;
        if (nextId) {
          const matched = nextKnowledgeBases.find((item) => item.id === nextId);
          if (matched) {
            return matched;
          }
        }
        return current && nextKnowledgeBases.some((item) => item.id === current.id) ? current : null;
      });
    } catch (error) {
      setKbError(error instanceof Error ? error.message : "Unable to load knowledge bases");
    } finally {
      setIsLoadingKnowledgeBases(false);
    }
  }

  async function loadDocuments(kbId: string) {
    setIsLoadingDocuments(true);
    try {
      setDocuments(await listKnowledgeBaseDocuments(kbId));
    } catch (error) {
      setUploadError(error instanceof Error ? error.message : "Unable to load documents");
    } finally {
      setIsLoadingDocuments(false);
    }
  }

  async function handleCreateKb() {
    const name = window.prompt("Knowledge Base name");
    if (!name?.trim()) {
      return;
    }

    const id = slugifyKnowledgeBaseId(name);
    try {
      const kb = await createKnowledgeBase({ id, name: name.trim() });
      await loadKnowledgeBases(kb.id);
      setActiveKnowledgeBase(kb);
    } catch (error) {
      setKbError(error instanceof Error ? error.message : "Unable to create knowledge base");
    }
  }

  async function handleRenameKb(kb: KnowledgeBase) {
    const name = window.prompt("Rename Knowledge Base", kb.name);
    if (!name?.trim() || name.trim() === kb.name) {
      return;
    }

    try {
      const updated = await renameKnowledgeBase(kb.id, name.trim());
      await loadKnowledgeBases(updated.id);
      setActiveKnowledgeBase(updated);
    } catch (error) {
      setKbError(error instanceof Error ? error.message : "Unable to rename knowledge base");
    }
  }

  async function handleDeleteKb(kb: KnowledgeBase) {
    const confirmed = window.confirm(`Delete knowledge base \"${kb.name}\"?`);
    if (!confirmed) {
      return;
    }

    try {
      await deleteKnowledgeBase(kb.id);
      const nextActive = activeKnowledgeBase?.id === kb.id ? undefined : activeKnowledgeBase?.id;
      if (activeKnowledgeBase?.id === kb.id) {
        setActiveKnowledgeBase(null);
      }
      await loadKnowledgeBases(nextActive);
    } catch (error) {
      setKbError(error instanceof Error ? error.message : "Unable to delete knowledge base");
    }
  }

  async function handleDeleteDocument(document: DocumentSummary) {
    if (!activeKnowledgeBase) {
      return;
    }
    const confirmed = window.confirm(`Delete document \"${document.filename}\"?`);
    if (!confirmed) {
      return;
    }

    try {
      await deleteKnowledgeBaseDocument(activeKnowledgeBase.id, document.document_id);
      await Promise.all([
        loadDocuments(activeKnowledgeBase.id),
        loadKnowledgeBases(activeKnowledgeBase.id),
      ]);
    } catch (error) {
      setUploadError(error instanceof Error ? error.message : "Unable to delete document");
    }
  }

  if (!activeKnowledgeBase) {
    return (
      <div className="space-y-6">
        <HeroHeader />
        <section className="grid gap-4 xl:grid-cols-[1.2fr_0.8fr]">
          <Card className="overflow-hidden p-6">
            <div className="mb-8 flex items-center justify-between">
              <div>
                <p className="text-sm uppercase tracking-[0.24em] text-foreground/45">Workspaces</p>
                <h1 className="mt-2 text-3xl font-semibold tracking-tight">Knowledge bases pronte per l&rsquo;operatività</h1>
              </div>
              <div className="flex items-center gap-2">
                <Badge className="border-primary/20 bg-primary/10 text-primary">Minimal + Hybrid</Badge>
                <Button type="button" variant="outline" onClick={() => void handleCreateKb()}>
                  <Plus className="size-4" />
                  New KB
                </Button>
              </div>
            </div>
            {kbError ? <p className="mb-4 text-sm text-red-600 dark:text-red-400">{kbError}</p> : null}
            <div className="grid gap-4 md:grid-cols-2">
              {isLoadingKnowledgeBases ? (
                <Card className="p-5 text-sm text-foreground/60">Loading knowledge bases...</Card>
              ) : null}
              {knowledgeBases.map((knowledgeBase) => (
                <button
                  key={knowledgeBase.id}
                  type="button"
                  onClick={() => setActiveKnowledgeBase(knowledgeBase)}
                  className="group rounded-[1.6rem] border border-border/80 bg-background/70 p-5 text-left transition hover:-translate-y-0.5 hover:border-primary/35 hover:shadow-panel"
                >
                  <div className="flex items-center justify-between">
                    <div className="rounded-2xl bg-primary/12 p-3 text-primary">
                      <FolderKanban className="size-5" />
                    </div>
                    <ChevronRight className="size-4 text-foreground/35 transition group-hover:translate-x-1" />
                  </div>
                  <h2 className="mt-5 text-xl font-semibold">{knowledgeBase.name}</h2>
                  <p className="mt-2 text-sm text-foreground/60">Single collection, isolated by metadata filter</p>
                  <div className="mt-6 flex gap-2 text-xs text-foreground/55">
                    <Badge>{knowledgeBase.documents} docs</Badge>
                    <Badge>{knowledgeBase.chunks} chunks</Badge>
                  </div>
                </button>
              ))}
            </div>
            {!isLoadingKnowledgeBases && !knowledgeBases.length ? (
              <div className="mt-6">
                <EmptyPanel
                  title="No knowledge bases yet"
                  caption="Create the first KB to isolate uploads, retrieval, and chat context."
                />
              </div>
            ) : null}
          </Card>
          <Card className="p-6">
            <p className="text-sm uppercase tracking-[0.24em] text-foreground/45">Architecture</p>
            <div className="mt-6 space-y-4 text-sm text-foreground/75">
              <FlowRow icon={<BrainCircuit className="size-4" />} title="Orchestrator Agent" caption="Minimal planning before retrieval" />
              <FlowRow icon={<SearchCode className="size-4" />} title="Hybrid Search" caption="Dense Qdrant + BM25 + RRF" />
              <FlowRow icon={<GitBranch className="size-4" />} title="Knowledge Agent" caption="Reasoning only on retrieved context" />
              <FlowRow icon={<LibraryBig className="size-4" />} title="Scoped Knowledge Bases" caption="Single Qdrant collection with kb_id filtering" />
              <FlowRow icon={<PanelRight className="size-4" />} title="Streaming UI" caption="Realtime markdown answers with source citations" />
            </div>
          </Card>
        </section>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <header className="flex flex-wrap items-center justify-between gap-3 rounded-[1.6rem] border border-border/75 bg-card/88 px-5 py-4 shadow-panel backdrop-blur">
        <div className="space-y-1">
          <div className="flex items-center gap-2 text-sm text-foreground/55">
            <span>nanoRAG</span>
            <ChevronRight className="size-4" />
            <span>Workspace</span>
          </div>
          <div className="flex items-center gap-3">
            <h1 className="text-2xl font-semibold tracking-tight">{activeKnowledgeBase.name}</h1>
            <Badge>{activeKnowledgeBase.documents} files</Badge>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <Button type="button" variant="outline" onClick={() => setActiveKnowledgeBase(null)}>
            <ChevronRight className="size-4 rotate-180" />
            Back to Workspaces
          </Button>
          <ThemeToggle />
        </div>
      </header>

      <section className="grid items-start gap-4 xl:grid-cols-[340px_minmax(0,1fr)_minmax(380px,28vw)]">
        <div className="space-y-4">
        <Card className="p-4">
          <div className="mb-4 flex items-center justify-between">
            <div>
              <p className="text-sm font-medium">Knowledge Bases</p>
              <p className="text-xs text-foreground/55">Scoped retrieval and isolated context</p>
            </div>
            <Button type="button" size="icon" variant="outline" onClick={() => void handleCreateKb()}>
              <Plus className="size-4" />
            </Button>
          </div>

          <div className="space-y-2">
            {knowledgeBases.map((knowledgeBase) => (
              <div
                key={knowledgeBase.id}
                className={cn(
                  "rounded-2xl border p-3 transition",
                  activeKnowledgeBase.id === knowledgeBase.id
                    ? "border-primary/35 bg-primary/10"
                    : "border-border/80 bg-background/60",
                )}
              >
                <button
                  type="button"
                  className="w-full text-left"
                  onClick={() => setActiveKnowledgeBase(knowledgeBase)}
                >
                  <p className="text-sm font-medium">{knowledgeBase.name}</p>
                  <p className="mt-1 text-xs text-foreground/55">
                    {knowledgeBase.documents} docs · {knowledgeBase.chunks} chunks
                  </p>
                </button>
                <div className="mt-3 flex gap-2">
                  <Button type="button" variant="ghost" size="sm" onClick={() => void handleRenameKb(knowledgeBase)}>
                    <Pencil className="size-4" />
                    Rename
                  </Button>
                  <Button type="button" variant="ghost" size="sm" onClick={() => void handleDeleteKb(knowledgeBase)}>
                    <Trash2 className="size-4" />
                    Delete
                  </Button>
                </div>
              </div>
            ))}
          </div>
          {kbError ? <p className="mt-3 text-xs text-red-600 dark:text-red-400">{kbError}</p> : null}
        </Card>

        <Card className="p-4">
          <div className="mb-4 flex items-center justify-between">
            <div>
              <p className="text-sm font-medium">Documents</p>
              <p className="text-xs text-foreground/55">Upload PDF, TXT, MD into the active KB</p>
            </div>
            <Badge>{documents.length}</Badge>
          </div>
          <div
            onDragOver={(event) => event.preventDefault()}
            onDrop={onDrop}
            className="rounded-[1.5rem] border border-dashed border-border/80 bg-background/60 p-5 text-center"
          >
            <div className="mx-auto flex size-12 items-center justify-center rounded-2xl bg-primary/12 text-primary">
              <Upload className="size-5" />
            </div>
            <p className="mt-4 text-sm font-medium">Drop files or browse local sources</p>
            <p className="mt-1 text-xs text-foreground/50">Structural chunking, embeddings, BM25 indexing</p>
            <input
              ref={fileInputRef}
              type="file"
              multiple
              accept=".pdf,.txt,.md"
              className="hidden"
              onChange={(event) => handleUpload(event.target.files)}
            />
            <Button
              type="button"
              variant="outline"
              className="mt-4 w-full"
              onClick={() => fileInputRef.current?.click()}
              disabled={isUploading}
            >
              <Paperclip className="size-4" />
              Upload documents
            </Button>
            {isUploading ? <Progress className="mt-4" value={uploadProgress} /> : null}
            {uploadError ? <p className="mt-3 text-xs text-red-600 dark:text-red-400">{uploadError}</p> : null}
          </div>

          {documents.length ? (
            <div className="mt-5 flex items-center gap-2 rounded-2xl border border-border/80 bg-background/65 px-3 py-2">
              <SearchCode className="size-4 shrink-0 text-foreground/45" />
              <input
                value={documentFilter}
                onChange={(event) => setDocumentFilter(event.target.value)}
                placeholder="Filter documents"
                className="w-full bg-transparent text-sm outline-none placeholder:text-foreground/35"
              />
              <span className="text-xs text-foreground/45">
                {filteredDocuments.length}/{documents.length}
              </span>
            </div>
          ) : null}

          <div className="mt-5 max-h-[28rem] space-y-3 overflow-y-auto pr-1">
            {isLoadingDocuments ? (
              <Card className="p-4 text-sm text-foreground/60">Loading documents...</Card>
            ) : null}
            {documents.length ? (
              filteredDocuments.length ? (
              filteredDocuments.map((document) => (
                <div
                  key={document.document_id}
                  className="rounded-2xl border border-border/80 bg-background/65 p-3"
                >
                  <div className="flex items-start justify-between gap-3">
                    <div className="flex items-start gap-3">
                      <div className="rounded-2xl bg-secondary/70 p-2 text-foreground/70">
                        <FileText className="size-4" />
                      </div>
                      <div>
                        <p className="line-clamp-2 text-sm font-medium">{document.filename}</p>
                        <p className="mt-1 text-xs text-foreground/55">{document.chunk_count} indexed chunks</p>
                      </div>
                    </div>
                    <Button type="button" variant="ghost" size="sm" onClick={() => void handleDeleteDocument(document)}>
                      <Trash2 className="size-4" />
                    </Button>
                  </div>
                </div>
              ))
              ) : (
                <EmptyPanel
                  title="No matching documents"
                  caption="Try a different filename keyword or clear the current filter."
                />
              )
            ) : (
              <EmptyPanel
                title="No uploaded documents"
                caption="Index at least one source to activate grounded retrieval."
              />
            )}
          </div>
        </Card>
        </div>

        <Card className="flex min-h-[72vh] flex-col overflow-hidden">
          <div className="flex items-center justify-between border-b border-border/70 px-5 py-4">
            <div>
              <p className="text-sm font-medium">AI Assistant</p>
              <p className="text-xs text-foreground/55">Grounded answers with streaming markdown</p>
            </div>
            <div className="flex gap-2">
              <Badge>{lastMatchCount} matches</Badge>
              <Badge className="max-w-[180px] truncate">{lastSearchQuery || "query pending"}</Badge>
            </div>
          </div>

          <div ref={conversationRef} className="flex-1 space-y-5 overflow-y-auto px-5 py-5">
            {messages.length ? (
              messages.map((message) => (
                <article
                  key={message.id}
                  className={cn(
                    "flex gap-3",
                    message.role === "user" ? "justify-end" : "justify-start",
                  )}
                >
                  {message.role === "assistant" ? <Avatar label="AI" /> : null}
                  <div
                    className={cn(
                      "max-w-[86%] rounded-[1.6rem] px-4 py-3",
                      message.role === "user"
                        ? "bg-primary text-white"
                        : "border border-border/70 bg-background/75",
                    )}
                  >
                    <div className="flex items-center justify-between gap-3">
                      <p className="text-xs uppercase tracking-[0.22em] opacity-60">
                        {message.role === "user" ? "User" : "Assistant"}
                      </p>
                      {message.role === "assistant" && message.content ? (
                        <button
                          type="button"
                          className="text-foreground/45 transition hover:text-foreground"
                          onClick={() => navigator.clipboard.writeText(message.content)}
                          aria-label="Copy answer"
                        >
                          <Copy className="size-4" />
                        </button>
                      ) : null}
                    </div>
                    <div className="mt-3">
                      {message.role === "assistant" ? (
                        message.content ? (
                          <ChatMarkdown content={message.content} />
                        ) : (
                          <div className="flex items-center gap-2 text-sm text-foreground/55">
                            <LoaderCircle className="size-4 animate-spin" />
                            Streaming response...
                          </div>
                        )
                      ) : (
                        <p className="whitespace-pre-wrap text-sm leading-7">{message.content}</p>
                      )}
                    </div>
                    {message.sources?.length ? (
                      <details className="mt-4 rounded-2xl border border-border/70 bg-card/75 p-3">
                        <summary className="cursor-pointer text-sm font-medium">Sources</summary>
                        <div className="mt-3 space-y-2">
                          {message.sources.map((source) => (
                            <div
                              key={source.chunk_id}
                              className="rounded-2xl border border-border/65 bg-background/70 p-3 text-xs text-foreground/70"
                            >
                              <p className="font-medium text-foreground/85">{source.filename}</p>
                              <p className="mt-1">
                                page {source.page ?? "-"} · section {source.section ?? "-"}
                              </p>
                            </div>
                          ))}
                        </div>
                      </details>
                    ) : null}
                  </div>
                  {message.role === "user" ? <Avatar label="ME" /> : null}
                </article>
              ))
            ) : (
              <EmptyPanel
                title="Ask about your documents"
                caption="Hybrid retrieval will combine semantic vectors and BM25 exact matches before generation."
              />
            )}
          </div>

          <div className="border-t border-border/70 px-5 py-4">
            <div className="rounded-[1.75rem] border border-border/80 bg-background/80 p-3">
              <Textarea
                ref={textareaRef}
                value={composerValue}
                onChange={(event) => setComposerValue(event.target.value)}
                placeholder="Ask a grounded question about your indexed documents..."
                onKeyDown={(event) => {
                  if (event.key === "Enter" && !event.shiftKey) {
                    event.preventDefault();
                    void handleSend();
                  }
                }}
              />
              <div className="mt-3 flex items-center justify-between gap-3">
                <div className="flex items-center gap-2 text-xs text-foreground/50">
                  <Database className="size-4" />
                  RRF fusion · BM25 · Qdrant
                </div>
                <div className="flex items-center gap-2">
                  <Button type="button" variant="outline" onClick={() => retryLast()} disabled={isStreaming}>
                    <RefreshCcw className="size-4" />
                    Retry
                  </Button>
                  <Button type="button" onClick={() => void handleSend()} disabled={isStreaming}>
                    {isStreaming ? <LoaderCircle className="size-4 animate-spin" /> : <SendHorizonal className="size-4" />}
                    Send
                  </Button>
                </div>
              </div>
            </div>
          </div>
        </Card>

        <Card className="p-4">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm font-medium">Workspace panel</p>
              <p className="text-xs text-foreground/55">Content and graph overview</p>
            </div>
            <div className="flex rounded-full border border-border/80 bg-background/70 p-1">
              <button
                type="button"
                className={cn(
                  "rounded-full px-3 py-1.5 text-xs font-medium",
                  sidePanelTab === "content" ? "bg-primary text-white" : "text-foreground/60",
                )}
                onClick={() => setSidePanelTab("content")}
              >
                Content
              </button>
              <button
                type="button"
                className={cn(
                  "rounded-full px-3 py-1.5 text-xs font-medium",
                  sidePanelTab === "graph" ? "bg-primary text-white" : "text-foreground/60",
                )}
                onClick={() => setSidePanelTab("graph")}
              >
                Knowledge Graph
              </button>
            </div>
          </div>

          {sidePanelTab === "content" ? (
            <div className="mt-5 space-y-4">
              <InsightCard
                icon={<SearchCode className="size-4" />}
                title="Retrieval query"
                value={lastSearchQuery || "Waiting for first query"}
              />
              <InsightCard
                icon={<Database className="size-4" />}
                title="Active KB chunks"
                value={String(
                  knowledgeBases.find((item) => item.id === activeKnowledgeBase.id)?.chunks ?? 0,
                )}
              />
              <InsightCard
                icon={<GitBranch className="size-4" />}
                title="Fusion mode"
                value="Dense + BM25 via RRF"
              />
              <InsightCard
                icon={<LibraryBig className="size-4" />}
                title="Storage policy"
                value="Chunks and metadata only. Raw source files are not retained after processing."
              />
            </div>
          ) : (
            <KnowledgeGraphPanel kbId={activeKnowledgeBase.id} />
          )}
        </Card>
      </section>
    </div>
  );
}

function HeroHeader() {
  return (
    <header className="flex flex-wrap items-center justify-between gap-4 rounded-[1.8rem] border border-border/75 bg-card/88 px-6 py-5 shadow-panel backdrop-blur">
      <div>
        <div className="flex items-center gap-2 text-sm text-foreground/55">
          <ArrowUp className="size-4" />
          Agentic RAG platform
        </div>
        <h1 className="mt-3 text-4xl font-semibold tracking-tight">Minimal orchestration, hybrid retrieval, realtime UX.</h1>
      </div>
      <div className="flex items-center gap-2">
        <Badge className="border-primary/20 bg-primary/10 text-primary">FastAPI</Badge>
        <Badge>Next.js</Badge>
        <Badge>Qdrant</Badge>
        <Badge>BM25</Badge>
        <ThemeToggle />
      </div>
    </header>
  );
}

function FlowRow({ icon, title, caption }: { icon: React.ReactNode; title: string; caption: string }) {
  return (
    <div className="flex items-center gap-4 rounded-2xl border border-border/75 bg-background/60 px-4 py-3">
      <div className="rounded-2xl bg-primary/10 p-3 text-primary">{icon}</div>
      <div>
        <p className="text-sm font-medium">{title}</p>
        <p className="text-xs text-foreground/55">{caption}</p>
      </div>
    </div>
  );
}

function EmptyPanel({ title, caption }: { title: string; caption: string }) {
  return (
    <div className="rounded-[1.6rem] border border-dashed border-border/80 bg-background/60 p-8 text-center">
      <p className="text-base font-medium">{title}</p>
      <p className="mt-2 text-sm text-foreground/55">{caption}</p>
    </div>
  );
}

function Avatar({ label }: { label: string }) {
  return (
    <div className="mt-1 flex size-9 shrink-0 items-center justify-center rounded-2xl bg-secondary text-xs font-semibold text-foreground/75">
      {label}
    </div>
  );
}

function InsightCard({ icon, title, value }: { icon: React.ReactNode; title: string; value: string }) {
  return (
    <div className="rounded-[1.4rem] border border-border/75 bg-background/70 p-4">
      <div className="flex items-center gap-2 text-foreground/55">{icon}<span className="text-xs uppercase tracking-[0.2em]">{title}</span></div>
      <p className="mt-3 text-sm font-medium leading-6 text-foreground/85">{value}</p>
    </div>
  );
}

function slugifyKnowledgeBaseId(name: string) {
  return name
    .trim()
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "")
    .slice(0, 48);
}
