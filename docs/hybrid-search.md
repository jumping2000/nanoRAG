# nanoRAG — Hybrid Search

nanoRAG combines dense retrieval and sparse BM25 retrieval, merges both rankings with Reciprocal Rank Fusion, then applies a small graph-aware reranking pass on chat candidates.

Each query is scoped to the active knowledge base through `kb_id` filtering.

## Dense retrieval

Dense retrieval is responsible for semantic matching.

- provider-agnostic embeddings
- vectors stored in one shared Qdrant collection
- retrieval filtered by payload field `kb_id`
- cosine similarity search

This path is useful for paraphrases and concept-level similarity.

## Query expansion from graph entities

When `GRAPH_QUERY_EXPANSION_ENABLED` is true, the query is enriched before
dense and sparse retrieval run:

- the query is tokenized into candidate terms
- each term is looked up against entity labels in the SQLite graph store
- matched canonical labels and their neighbor labels are appended to the query
- expansion is capped at `GRAPH_QUERY_EXPANSION_MAX_TERMS` added terms
- deterministic — no LLM calls, no external service dependencies

This is useful when user queries use aliases or partial names that differ
from the canonical entity labels stored in the graph.

## BM25 sparse retrieval

Sparse retrieval is local and in-process.

- implemented with `rank-bm25`
- tokenization keeps technical terms, acronyms, paths and codes
- corpus partitioned in-memory by `kb_id`
- ideal for exact matches and domain jargon

This path is especially useful for:

- acronyms
- service names
- error codes
- package names
- internal identifiers

## Graph retrieval channel

When `GRAPH_RETRIEVAL_ENABLED` is true, a third retrieval channel joins
dense and sparse search:

- entity seeds come from query expansion (or a local lookup if expansion is off)
- the graph store returns chunk candidates ranked by entity and relation mentions
- candidates are scored with the same entity/relation weights as the
  graph reranker: entity mentions × 0.35 + relation mentions × 0.65
- the score is multiplied by the sum of confidence values
- up to `GRAPH_RETRIEVAL_TOP_K` candidates are materialized into
  `RetrievedChunk` objects via the sparse chunk store

Key design choice: when graph retrieval is enabled but query expansion is
disabled, a lightweight local entity lookup still runs to provide seed
entities — so graph retrieval never silently returns zero results.

## RRF fusion

RRF is intentionally simple.

Formula:

$$
RRF(d) = \sum_{r \in R} \frac{1}{k + rank_r(d)}
$$

Where:

- $d$ is a document chunk
- $R$ is the set of rankings (2-way with dense + sparse, 3-way when graph retrieval is active)
- $k$ is a damping constant, set to `60`

## Why this approach

- strong retrieval quality without reranking
- predictable CPU usage
- low implementation complexity
- optional query expansion improves recall for alias-heavy domains without
  changing retrieval logic
- optional graph retrieval gives relation-bearing chunks a direct path into
  the candidate set, complementary to post-hoc reranking
- easy to debug and extend
- future-compatible with global multi-KB search without changing the collection layout

## Graph-aware reranking

The current reranking layer is intentionally minimal and only runs on `POST /chat`.

How it works:

- dense and sparse retrieval still generate the candidate set
- RRF still provides the base order
- the backend loads chunk-scoped graph evidence from the SQLite graph store
- each chunk receives a conservative graph bonus
- relation evidence is weighted more heavily than entity-only evidence
- if graph evidence is missing, the original RRF order is preserved

What it is not:

- not graph-only retrieval
- not multi-hop traversal
- not a replacement for dense or sparse search

Why this first step exists:

- improve relational questions without widening the architecture too much
- reuse graph evidence already produced during ingestion
- keep rollback cheap if graph noise hurts ranking quality
