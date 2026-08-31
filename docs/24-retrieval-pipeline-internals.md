# 24 — Retrieval Pipeline Internals

Last updated: **2026-07-01**

How knowledge **retrieval** works under the hood — from indexed fragments in Milvus through vector search, sibling expansion, and reranking. Applies to `POST /knowledge_manage/retrieval/search`, `knowledge_agent`, and `scripts/eval_retrieval.py`.

**Related docs:** [22-retrieval-eval.md](./22-retrieval-eval.md) (testing & commands), [11-knowledge-chunking.md](./11-knowledge-chunking.md) (how fragments are created), [17-text2vec-embedding-model.md](./17-text2vec-embedding-model.md), [12-milvus-filter-expressions.md](./12-milvus-filter-expressions.md), [16-milvus-code-locations.md](./16-milvus-code-locations.md)

---

## What this document covers

| Doc | Focus |
|-----|--------|
| **This doc (24)** | Theory & data flow — *why* retrieval behaves as it does |
| [22-retrieval-eval.md](./22-retrieval-eval.md) | *How to test* — golden set, eval script, API commands |
| [11-knowledge-chunking.md](./11-knowledge-chunking.md) | *How chunks are built* at ingest time |

---

## Two phases: index vs query

```
Phase A — INDEXING (upload / parse)          Phase B — RETRIEVAL (every search)
────────────────────────────────────         ────────────────────────────────────
PDF / Word                                   query text
    │                                            │
    ▼                                            ├─► package_id → file MD5 list (SQLite)
Layout parser                                      │
    │                                            ▼
    ▼                                        embed query (same model as index)
Fragments + parent_id / outline                    │
    │                                            ▼
    ▼                                        Milvus vector search (top 30)
POST /embeddings → vector                            │
    │                                            ▼
    ▼                                        sibling expansion (parent_id)
Milvus `fragments`                                   │
    │                                            ▼
SQLite File row (package link)                   merge → cap → rerank → top 8
```

| Phase | When | Output |
|-------|------|--------|
| **Indexing** | Document upload / parse | Vectors + metadata in Milvus; file row in SQLite |
| **Retrieval** | Every search | Ranked text chunks (no re-parse, no new index writes) |

Retrieval **never re-parses** the PDF. It only reads Milvus and calls the Embedding API.

---

## Data model

### Milvus collection `fragments`

Each row = **one layout fragment → one 384-dim vector**.

| Field | Meaning |
|-------|---------|
| `vector` | Embedding from `text2vec-base-multilingual` |
| `page_content` | Full chunk text |
| `document_id` | File MD5 |
| `index` | Reading order within the document (0, 1, 2, …) |
| `outline` | Heading level (0 = body, 1+ = title) |
| `parent_id` | Link to heading tree (see below) |
| `type` | `text`, `title`, `header`, … |
| `coordinates` | PDF bounding box for citations |
| `file_name` | Original filename |

**Indexing code:** `src/api/services/utils.py` → `convert_format()`, `insert_fragments_into_milvus()`.

**Principle:** 1 fragment = 1 vector. Chunks follow **document layout**, not fixed 512-token windows. See [11-knowledge-chunking.md](./11-knowledge-chunking.md).

### SQLite (knowledge library scope)

| Table | Role |
|-------|------|
| `Package` | Knowledge library (`package_id`) |
| `File` | Which file MD5s belong to which package |

Milvus holds **all** indexed documents globally. `package_id` at query time builds a filter: `document_id in [md5, md5, …]`.

See [22-retrieval-eval.md#package-id--search-scope](./22-retrieval-eval.md#package-id--search-scope) for how `package_id` is generated.

---

## `parent_id` and the heading tree

At index time, `add_parent_id_into_fragments()` walks fragments in order and maintains a heading stack:

```python
# src/api/services/utils.py (simplified)
# Body text (outline=0) → parent_id = chain of current heading fragment ids
# Title (outline>0)     → pushes/pops stack by outline level
```

Example structure:

```
[Title] 基于J2EE的电子政务...     outline=1  id=abc
[Text]  关键词:架构,J2EE,...       outline=0  parent_id=abc
[Text]  本论文着重研究了...        outline=0  parent_id=abc
```

**Intent:** If vector search hits one paragraph under a section, retrieval can pull **sibling paragraphs** under the same heading for fuller context.

The function name `search_with_same_outline` is historical — behavior is really **expand by `parent_id`**, not “same outline level”.

---

## Query pipeline (production `mode: pipeline`)

Entry points:

- `POST /knowledge_manage/retrieval/search` → `retrieval_search()` → `search_with_same_outline()`
- `POST /qa/agent/knowledge_agent` → same retrieval, then LLM

**Code:** `src/rag/services/qa.py`

### Step 0 — Scope filter

```python
file_ids = [f.file_id for f in File.get_by(package_id=package_id)]
_filter = "document_id in {}".format(file_ids)
```

Only chunks from files registered in that knowledge library are visible to search.

### Step 1 — Vector search (bi-encoder, semantic)

```python
query_embed = get_vectors([question])[0]   # POST /embeddings
milvus_client.search(collection, data=[query_embed], limit=30, filter=_filter)
```

| Aspect | Detail |
|--------|--------|
| Model | `text2vec-base-multilingual`, 384 dimensions |
| Service | Embedding API port **12356** `/embeddings` |
| Milvus op | **ANN search** — approximate nearest neighbors in vector space |
| Output | Top **30** chunks by similarity |

**Principle:** Question and chunks live in the same vector space. “语义相似” — e.g. a Chinese query can match an English abstract chunk without exact keyword overlap.

**Limits:** Model effective cap ~256 tokens; very long fragments become one weak embedding.

### Step 2 — Sibling expansion (metadata query, no vector)

```python
parent_ids = { hit.parent_id for hit in vector_docs }
sibling_expr = "(parent_id LIKE '%pid%') and type == 'text'"
sibling_docs = milvus_client.query(filter=sibling_expr)   # NOT vector search
docs = merge_documents(vector_docs, sibling_docs)
```

| Operation | Milvus API | Uses embedding? |
|-----------|------------|-----------------|
| `search()` | `.search()` | Yes |
| `query()` | `.query()` | No — boolean filter on metadata only |

**Principle:** Add all **body text** (`type == 'text'`) sharing heading ancestry with any top-30 hit. Results sorted by `index` (document order).

**Fix (2026-07):** Old code **replaced** vector hits with siblings only. Current code **merges** — vector order preserved, siblings add context.

### Step 3 — Cap rerank pool

```python
RERANK_POOL_MAX = 50
pool = cap_for_rerank(docs)   # merged list: vector hits first
```

Large documents can merge to 500+ chunks. The CPU reranker cannot score hundreds of long texts in seconds. The cap keeps the first 50 (mostly vector hits + early siblings).

### Step 4 — Rerank (cross-encoder, precise)

```python
scores = POST /rerank  { query, texts: [chunk1, chunk2, ...] }
# keep scores > 0, sort descending
```

| Stage | Model type | Measures |
|-------|------------|----------|
| Vector search | **Bi-encoder** | Similarity of separate embeddings (fast, broad recall) |
| Rerank | **Cross-encoder** | Relevance of **(query, chunk)** encoded together (slow, precise) |

**Why it matters:** Vector-only put the keywords chunk at rank **16** (short title chunks scored higher). Rerank jointly reads query + chunk → keywords line at rank **1**.

Reranker: transformers sequence classification model in `models/reranker/`, served at `/rerank` on port 12356.

### Step 5 — Top-K

```python
docs = reranked[:top_k]   # default top_k = 8
```

Returned to `retrieval/search` as `data.hits[]`. For `knowledge_agent`, these chunks feed the LLM prompt (trimmed to ~10k chars).

---

## Eval modes vs pipeline steps

| `mode` | Steps run | Use |
|--------|-----------|-----|
| `vector` | Step 1 only | Isolate embedding / Milvus quality |
| `outline` | 1 + 2 | See merge expansion without rerank |
| `pipeline` | 1 + 2 + 3 + 4 + 5 | **Production behavior** |

Script: `scripts/eval_retrieval.py`. Guide: [22-retrieval-eval.md](./22-retrieval-eval.md).

---

## Service diagram

```
Client (Swagger / eval script / frontend)
    │
    ▼
qa_api :12357
    │  retrieval_search / knowledge_agent_stream
    │
    ├──► embedding_api :12356  POST /embeddings  (query → vector)
    ├──► embedding_api :12356  POST /rerank      (query + chunks → scores)
    ├──► Milvus :19530         search() + query()
    └──► SQLite                Package / File → document_id filter
```

Document indexing (separate path):

```
document_fragment_api :12355  →  parse  →  utils.py  →  /embeddings  →  Milvus insert
```

---

## Design principles (summary)

| Principle | In this project |
|-----------|-----------------|
| Layout-first chunks | Paragraphs / titles / tables — not fixed token windows |
| 1 fragment = 1 vector | No overlap at index time |
| Scoped retrieval | `package_id` → SQLite → Milvus `document_id in [...]` |
| Two-stage retrieval | Fast vector recall → slow rerank precision |
| Structure expansion | `parent_id` pulls section siblings when vector hits one paragraph |
| Pool cap | Trade speed vs scoring every sibling on large PDFs |

---

## Known limitations

| Limitation | Effect |
|------------|--------|
| No chunk overlap | Answers on fragment boundaries may miss context |
| Long single-vector fragments | Weak embedding for paragraphs > model token cap |
| Many tiny title chunks | Can dominate raw vector search before rerank |
| `parent_id LIKE` expansion | Can over-fetch siblings on large sections |
| `num_tokens = 0` at index | Context budgeting in LLM path is unreliable |
| Rerank CPU-only in dev | ~15–90s per query when pool is large |

Improvement backlog: [19-knowledge-improvement-recommendations.md](./19-knowledge-improvement-recommendations.md).

---

## Key source files

| Area | Path |
|------|------|
| Retrieval pipeline | `src/rag/services/qa.py` → `search()`, `query()`, `search_with_same_outline()`, `rerank_documents()`, `retrieval_search()` |
| Retrieval test API | `src/rag/controllers/knowledge_mange.py` → `POST /retrieval/search` |
| Indexing + `parent_id` | `src/api/services/utils.py` → `convert_format()`, `add_parent_id_into_fragments()`, `insert_fragments_into_milvus()` |
| Embeddings + rerank | `src/embedding/api.py` |
| Knowledge scope | `src/rag/mappers/knowledge.py` → `Package`, `File` |

---

## One-line mental model

> **Find semantically similar chunks (vector) → add neighboring paragraphs from the same section (`parent_id`) → re-score each (query, chunk) pair with a cross-encoder (rerank) → return the best 8.**

That is the full retrieval path you tested with `POST /knowledge_manage/retrieval/search` — without any LLM.
