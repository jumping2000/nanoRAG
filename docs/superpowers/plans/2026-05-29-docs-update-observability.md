# Docs Update: Query Expansion, Graph Retrieval & Observability — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Update README, hybrid-search, architecture docs to reflect implemented query expansion + graph retrieval; create new observability doc.

**Architecture:** Four markdown files edited. No code changes. Pure documentation update reflecting already-implemented features.

**Tech Stack:** Markdown

---

### Task 1: Update `README.md`

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Edit Overview bullet (line 9)**

Replace single hybrid retrieval bullet with two bullets (hybrid + query expansion).

- [ ] **Step 2: Edit Retrieval flow (lines 38-46)**

Expand from 8 to 10 steps: add optional query expansion (step 3) and optional graph retrieval (step 6), describe RRF as 2-way or 3-way.

- [ ] **Step 3: Add "Graph-augmented retrieval" env section after "Graph-aware reranking" block**

Insert new `### Graph-augmented retrieval` section listing the 4 env vars.

- [ ] **Step 4: Edit Roadmap table (lines 273-276)**

Mark Phase 1 and Phase 2 as `✅ done`.

- [ ] **Step 5: Add `docs/observability.md` to Documentation list**

Add line `- [docs/observability.md](docs/observability.md)` to doc list.

- [ ] **Step 6: Verify README consistency**

Manual check: no stale "planned" references remain for Phases 1-2.

- [ ] **Step 7: Commit**

```bash
git add README.md
git commit -m "docs: update README for query expansion, graph retrieval, and observability"
```

---

### Task 2: Update `docs/hybrid-search.md`

**Files:**
- Modify: `docs/hybrid-search.md`

- [ ] **Step 1: Add "Query expansion from graph entities" section**

Insert after "Dense retrieval" section and before "BM25 sparse retrieval". Describe deterministic entity-label matching, tokenization, neighbor labels, cap.

- [ ] **Step 2: Add "Graph retrieval channel" section**

Insert after "BM25 sparse retrieval" and before "RRF fusion". Describe third channel, scoring, confidence weighting, materialization, fallback lookup.

- [ ] **Step 3: Update "RRF fusion" section**

Change "2-way" to "2-way with dense + sparse, 3-way when graph retrieval is active".

- [ ] **Step 4: Update "Why this approach" section**

Add 2 bullets for optional query expansion and optional graph retrieval.

- [ ] **Step 5: Update "Graph-aware reranking" scope list**

Remove "not query expansion" from the "What it is not" list.

- [ ] **Step 6: Commit**

```bash
git add docs/hybrid-search.md
git commit -m "docs: update hybrid-search for query expansion and graph retrieval"
```

---

### Task 3: Update `docs/architecture.md`

**Files:**
- Modify: `docs/architecture.md`

- [ ] **Step 1: Edit "High-level components" list**

Add 2 entries: "Query expansion" and "Graph retrieval" after the reranking entry.

- [ ] **Step 2: Update "Retrieval flow" Mermaid diagram**

Add `Query Expansion` and `Graph Retrieval` nodes. Show 3-way RRF fusion.

- [ ] **Step 3: Update "Chat flow" Mermaid sequence diagram**

Add `Query Expander` and `Graph Retriever` participants. Show expand → retrieval → rerank flow.

- [ ] **Step 4: Edit "Simplicity boundaries"**

Change "graph-driven query expansion and graph retrieval are planned but not yet implemented" to "implemented and opt-in".

- [ ] **Step 5: Expand "Knowledge Graph → Retrieval integration"**

Replace single paragraph with three bullets: GraphReranker, GraphQueryExpander, GraphRetriever.

- [ ] **Step 6: Commit**

```bash
git add docs/architecture.md
git commit -m "docs: update architecture for query expansion and graph retrieval"
```

---

### Task 4: Create `docs/observability.md`

**Files:**
- Create: `docs/observability.md`

- [ ] **Step 1: Create file with APP_ENV modes section**

Table: production/development/debug comparison (log level, X-Request-ID, trace events, debug in /chat). Plus env setup example.

- [ ] **Step 2: Add JSON structured logging section**

Format example with timestamp, level, logger, message, request_id, event, details. Note httpx/openai silencing.

- [ ] **Step 3: Add Request correlation section**

Describe X-Request-ID generation/inheritance, contextvars propagation, middleware behavior.

- [ ] **Step 4: Add Trace collector section**

Describe debug-mode TraceCollector, `/chat` NDJSON debug event format, event accumulation.

- [ ] **Step 5: Add observe() function section**

Signature explanation, component/action/details parameters.

- [ ] **Step 6: Add Event catalog section**

Tables: HTTP events, API events, Retrieval events, Qdrant events, Graph Store events. Match actual `observe()` calls in source code.

- [ ] **Step 7: Add How to use section**

Local debugging commands (APP_ENV=debug, curl health, /chat debug event). Production guidance (APP_ENV=production, pipe to aggregator).

- [ ] **Step 8: Add Current gaps section**

Table: metrics, distributed tracing, log shipping, sampling, LLM instrumentation, background tasks.

- [ ] **Step 9: Add Future directions section**

5-item numbered list: Prometheus endpoint, OpenTelemetry spans, log shipping config, sampled tracing, provider instrumentation.

- [ ] **Step 10: Verify event catalog against source code**

Run: `grep -r "observe(" backend/ --include="*.py" | grep -v test | grep -v __pycache__` to confirm all events are catalogued.

- [ ] **Step 11: Commit**

```bash
git add docs/observability.md
git commit -m "docs: create observability documentation"
```

---

### Task 5: Final verification

- [ ] **Step 1: Check for stale references**

```bash
grep -rn "planned but not yet" docs/ README.md
```
Expected: no matches.

- [ ] **Step 2: Check cross-references**

All `[docs/observability.md](docs/observability.md)` links resolve to existing file.

- [ ] **Step 3: Commit (if any fixes needed)**

```bash
git add -A docs/ README.md
git commit -m "docs: final verification pass for doc update"
```
