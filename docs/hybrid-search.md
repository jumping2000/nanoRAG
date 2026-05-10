# Hybrid Search

nanoRAG combines dense retrieval and sparse BM25 retrieval, then merges both rankings with Reciprocal Rank Fusion.

## Dense retrieval

Dense retrieval is responsible for semantic matching.

- provider-agnostic embeddings
- vectors stored in Qdrant
- cosine similarity search

This path is useful for paraphrases and concept-level similarity.

## BM25 sparse retrieval

Sparse retrieval is local and in-process.

- implemented with `rank-bm25`
- tokenization keeps technical terms, acronyms, paths and codes
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
