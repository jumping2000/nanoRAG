# Frontend

The frontend is a Next.js App Router application with a client-heavy shell optimized for document QA.

## UX model

The SPA has two levels:

- dashboard: knowledge base overview
- workspace: three-column operational view

## Workspace layout

- Left column: upload area and indexed document list.
- Center column: ChatGPT-style assistant, streaming output and citations.
- Right column: retrieval insights and a future-ready graph panel.

## Key components

- `components/nanorag-shell.tsx`: main UI shell.
- `hooks/use-chat-stream.ts`: streaming state management.
- `services/api.ts`: upload and chat transport.
- `components/chat-markdown.tsx`: Markdown rendering and syntax highlighting.
- `components/ui/*`: shadcn-style primitives.

## Streaming strategy

The backend returns `application/x-ndjson`.
The frontend parses events incrementally and updates the last assistant message token by token.

Supported event types:

- `meta`
- `token`
- `sources`
- `done`

## Markdown rendering

- `react-markdown`
- `remark-gfm`
- `react-syntax-highlighter`

This keeps rendering lightweight without introducing complex editor/runtime dependencies.
