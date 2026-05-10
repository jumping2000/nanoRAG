# Frontend

The frontend is a Next.js App Router application with a client-heavy shell optimized for document QA.

## UX model

The SPA has two levels:

- dashboard: knowledge base overview
- workspace: KB sidebar plus the existing three operational columns

## Workspace layout

- Sidebar: knowledge base selection and KB CRUD.
- Left column: upload area and indexed document list for the active KB.
- Center column: ChatGPT-style assistant, streaming output and citations scoped to the active KB.
- Right column: retrieval insights and a future-ready graph panel.

## Key components

- `components/nanorag-shell.tsx`: main UI shell.
- `hooks/use-chat-stream.ts`: KB-scoped streaming state management.
- `services/api.ts`: KB CRUD, document CRUD, upload and chat transport.
- `components/chat-markdown.tsx`: Markdown rendering and syntax highlighting.
- `components/ui/*`: shadcn-style primitives.

## Knowledge base interactions

The shell now supports:

- create KB
- rename KB
- delete KB
- select active KB
- list documents for the active KB
- delete documents from the active KB
- upload and chat scoped to the active KB

## Streaming strategy

The backend returns `application/x-ndjson`.
The frontend parses events incrementally and updates the last assistant message token by token.

Supported event types:

- `meta`
- `token`
- `sources`
- `done`

On KB switch, the chat state is reset so responses cannot mix context from different knowledge bases.

## Markdown rendering

- `react-markdown`
- `remark-gfm`
- `react-syntax-highlighter`

This keeps rendering lightweight without introducing complex editor/runtime dependencies.
