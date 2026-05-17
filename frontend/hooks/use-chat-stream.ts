"use client";

import { useState } from "react";

import { getErrorMessage } from "@/lib/utils";
import type { ChatMessage } from "@/lib/types";
import { streamChat } from "@/services/api";

function buildId() {
  return globalThis.crypto?.randomUUID?.() ?? `${Date.now()}-${Math.random()}`;
}

export function useChatStream() {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [isStreaming, setIsStreaming] = useState(false);
  const [lastPrompt, setLastPrompt] = useState("");
  const [lastKbId, setLastKbId] = useState("");
  const [lastSearchQuery, setLastSearchQuery] = useState("");
  const [lastMatchCount, setLastMatchCount] = useState(0);

  async function sendMessage(message: string, kbId: string) {
    const trimmed = message.trim();
    if (!trimmed || !kbId || isStreaming) {
      return;
    }

    const assistantId = buildId();
    setLastPrompt(trimmed);
    setLastKbId(kbId);
    setMessages((current) => [
      ...current,
      { id: buildId(), role: "user", content: trimmed, status: "done" },
      { id: assistantId, role: "assistant", content: "", status: "streaming", sources: [] },
    ]);
    setIsStreaming(true);

    try {
      await streamChat(
        { message: trimmed, kb_id: kbId },
        {
          onMeta(meta) {
            setLastSearchQuery(meta.searchQuery ?? "");
            setLastMatchCount(meta.matches ?? 0);
          },
          onToken(token) {
            setMessages((current) =>
              current.map((item) =>
                item.id === assistantId
                  ? { ...item, content: `${item.content}${token}` }
                  : item,
              ),
            );
          },
          onSources(sources) {
            setMessages((current) =>
              current.map((item) =>
                item.id === assistantId
                  ? { ...item, status: "done", sources }
                  : item,
              ),
            );
          },
          onDone() {
            setMessages((current) =>
              current.map((item) =>
                item.id === assistantId && item.status !== "error"
                  ? { ...item, status: "done" }
                  : item,
              ),
            );
          },
        },
      );
    } catch (error) {
      const messageText = getErrorMessage(error, "Streaming request failed");
      setMessages((current) =>
        current.map((item) =>
          item.id === assistantId
            ? {
                ...item,
                status: "error",
                content:
                  item.content || `Errore durante lo streaming della risposta: ${messageText}`,
              }
            : item,
        ),
      );
    } finally {
      setIsStreaming(false);
    }
  }

  async function retryLast() {
    if (!lastPrompt || !lastKbId || isStreaming) {
      return;
    }
    await sendMessage(lastPrompt, lastKbId);
  }

  function resetConversation() {
    setMessages([]);
    setLastPrompt("");
    setLastKbId("");
    setLastSearchQuery("");
    setLastMatchCount(0);
  }

  return {
    messages,
    isStreaming,
    lastSearchQuery,
    lastMatchCount,
    sendMessage,
    retryLast,
    resetConversation,
  };
}
