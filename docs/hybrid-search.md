# Hybrid Search

nanoRAG combines dense retrieval and sparse BM25 retrieval, merges both rankings with Reciprocal Rank Fusion, then applies a small graph-aware reranking pass on chat candidates.

Each query is scoped to the active knowledge base through `kb_id` filtering.

## Dense retrieval

Dense retrieval is responsible for semantic matching.

- provider-agnostic embeddings
- vectors stored in one shared Qdrant collection
- retrieval filtered by payload field `kb_id`
- cosine similarity search

This path is useful for paraphrases and concept-level similarity.

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

## RRF fusion

RRF is intentionally simple.

Formula:

$$
RRF(d) = \sum_{r \in R} \frac{1}{k + rank_r(d)}
$$

Where:

- $d$ is a document chunk
- $R$ is the set of rankings
- $k$ is a damping constant, set to `60`

## Why this approach

- strong retrieval quality without reranking
- predictable CPU usage
- low implementation complexity
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
- not query expansion
- not a replacement for dense or sparse search

Why this first step exists:

- improve relational questions without widening the architecture too much
- reuse graph evidence already produced during ingestion
- keep rollback cheap if graph noise hurts ranking quality
