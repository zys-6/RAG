# 19 — Project Overview & Knowledge Improvement Recommendations

Last updated: **2026-06-30**

Structured overview of the Document Fragment Platform and focused recommendations for improving the **Knowledge** (知识库) feature — at model, code, and design levels, plus urgent priorities.

**Related docs:** [01-overview.md](./01-overview.md), [11-knowledge-chunking.md](./11-knowledge-chunking.md), [08-known-limitations.md](./08-known-limitations.md), [10-cleanup-recommendations.md](./10-cleanup-recommendations.md)

---

## Project Overview

**Document Fragment Platform** is an enterprise backend for document ingestion, vector search, and RAG Q&A. There is no frontend in this repo; a separate web app calls the HTTP APIs.

### Architecture

```
External LLM / FTP / Jira / enterprise APIs
                    │
    ┌───────────────┼───────────────────────────────┐
    │     document_fragment (one Docker image)       │
    │  ┌──────────┐  ┌───────────┐  ┌──────────┐     │
    │  │ src/api  │  │embedding  │  │ src/rag  │     │
    │  │ :12355   │  │  :12356   │  │  :12357  │     │
    │  │ Parse    │  │ Embed +   │  │ KB / QA  │     │
    │  │ fragment │  │ rerank    │  │ Agents   │     │
    │  └────┬─────┘  └─────┬─────┘  └────┬─────┘     │
    │       └──────────────┴─────────────┘           │
    │              Milvus + SQLite                    │
    └─────────────────────────────────────────────────┘
```

| Layer | Technology |
|-------|------------|
| Framework | FastAPI + Uvicorn |
| Vector DB | Milvus 2.4 (`fragments` collection) |
| Metadata | SQLite (packages, files, agents, dialogues) |
| Embeddings | `text2vec-base-multilingual` (384-dim, 256 token max) |
| Reranker | Transformers sequence classifier |
| Parsing | PyMuPDF, PaddleOCR, layout analysis (PDF/Word/CAJ) |
| LLM | External OpenAI-compatible API (Zhuque / Ollama) |

### Knowledge feature flow

1. **Package** (知识库) → SQLite `Package`
2. **Upload** via FTP URL → Document API parses → layout-based **fragments** → embed → Milvus
3. **Q&A** via `POST /qa/agent/knowledge_agent` → vector search → (intended) outline expansion → LLM stream

**Design choice:** chunks follow **document layout** (headings, paragraphs, tables), not fixed token windows. That preserves structure and citations, but differs from typical RAG (512-token blocks + overlap).

See [11-knowledge-chunking.md](./11-knowledge-chunking.md) for chunking details.

---

## Improvements for Knowledge

### 1. Model level

| Area | Current state | Recommendation |
|------|---------------|----------------|
| **Embedding** | MiniLM-L12-v2 multilingual, 384-dim, **256 token cap** | Upgrade to a stronger Chinese/multilingual model: `bge-m3`, `text2vec-large-chinese`, or `jina-embeddings-v3`. Many enterprise docs exceed 256 tokens per fragment. |
| **Long fragments** | Long paragraphs become **one vector** (up to ~5000 chars) | Add a **second-stage splitter** for fragments >512 tokens (with 10–20% overlap) before embedding. Keep layout metadata (`outline`, `parent_id`, `coordinates`). |
| **Reranker** | Exists at `/rerank` but **not used** in `knowledge_agent_stream` | Wire rerank into the knowledge pipeline after retrieval; take top 30 → rerank → top 5–8 for the prompt. |
| **LLM** | Blocked on `192.168.1.100:7819` in `.env` | Point `API_BASE` / `TOKENIZE_URL` to a reachable endpoint (local Ollama, cloud API). Without this, knowledge Q&A cannot run end-to-end. |
| **Hybrid search** | Vector-only | Add **BM25 / keyword** (Milvus sparse or Elasticsearch) for exact terms, IDs, regulation numbers — common in Chinese enterprise docs. |
| **Query rewriting** | History → `generate_question_by_history` | Add HyDE or multi-query expansion for vague questions. |

See [17-text2vec-embedding-model.md](./17-text2vec-embedding-model.md) for current embedding model details.

---

### 2. Code level

#### Critical retrieval bug — `search_with_same_outline` discards vector search hits

**File:** `src/rag/services/qa.py`

```python
async def search_with_same_outline(
        text: Union[str, List], _filter: str = '',
        with_rerank: bool = True) -> List[Dict]:
    docs = await search(text, filter=_filter, limit=30)
    parent_ids = list(set([item['metadata']['parent_id']
                           for item in docs
                           if item['metadata']['parent_id'] != 'None']))
    if parent_ids:
        docs = query("({}) and type == 'text'".format(
            " or ".join(["parent_id LIKE '%{}%'".format(_parent_id) for _parent_id in parent_ids])
        ))
    return docs
```

When `parent_ids` exist, the top-30 vector results are **replaced** by sibling fragments under those headings. The `with_rerank=True` parameter is never used.

**Fix:** merge vector hits + expanded siblings, dedupe, then rerank.

#### Other code issues

| Issue | Location | Fix |
|-------|----------|-----|
| Delete file leaves orphan vectors | `src/rag/services/knowledge.py` → `delete_file()` | Delete Milvus rows where `document_id == file_id` |
| Token count is character length | `src/rag/services/qa.py` → `get_num_tokens()` — `TOKENIZE_URL` unreachable | Restore real tokenization or use `tiktoken` |
| `eval()` on LLM JSON | `get_user_intent()` | Use `json.loads()` with validation |
| Monolithic `qa.py` (~2700 lines) | Mixed agents, reports, Jira, knowledge | Split into `knowledge_qa.py`, `db_agent.py`, etc. |
| Backup/dead code | `qa_bak.py`, `request_llm_bak.py`, … | Remove (see [10-cleanup-recommendations.md](./10-cleanup-recommendations.md)) |
| FTP-only upload | `upload_file()` → `requests_upload_file(ftp_url=...)` | Add direct multipart upload for dev/modern deployments |
| Secrets in repo | `.env`, `app_config_pro.yaml` (FTP password, JWT) | Move to env vars / secret store; rotate exposed tokens |
| No tests | — | Add retrieval golden-set tests (question → expected doc_ids) |

---

### 3. Design level

#### Strengths to keep

- Layout-aware parsing with `outline`, `parent_id`, page coordinates — strong for citations in structured Chinese documents.
- Three-service split (parse / embed / RAG) scales independently.
- Package scoping (`document_id in [package file_ids]`) gives multi-tenant knowledge bases.

#### Design gaps

| Gap | Impact | Direction |
|-----|--------|-----------|
| No chunk overlap | Answers spanning two fragments miss context | Hybrid: layout chunks + token sub-chunks for long blocks |
| No re-indexing API | Strategy changes require re-upload | Add `/knowledge_manage/file/reindex` |
| No auth | `user_id` from client only | API keys or JWT at gateway |
| Dual config (`.env` + YAML) | Easy misconfiguration (e.g. `MILVUS_URI` vs `MILVUS_URL`) | Single source of truth; env overrides YAML |
| Milvus not in compose | Manual startup step | Add Milvus + Attu to `docker-compose.yaml` |
| Celery/Redis referenced but not deployed | Async ingest unavailable | Add Redis + worker, or document sync-only path |
| Tiny title chunks dominate search | Median fragment ~50 chars | Filter or down-weight `outline > 0`-only hits at retrieval |
| `num_tokens = 0` at index time | Context budgeting unreliable | Compute and store at ingest |

#### Suggested target retrieval pipeline

```
Question
  → (optional) query rewrite
  → vector search top-30 (package filter)
  → expand siblings via parent_id (merge, don't replace)
  → rerank top-30 → top-8
  → filter noise (titles-only, abstract)
  → token-budget trim
  → LLM + citations
```

---

## What to improve urgently (priority order)

### P0 — Unblocks everything

1. **Configure a reachable LLM** — All `/qa/*` and `knowledge_agent` are blocked when `API_BASE` points to an unreachable host. Update `.env` and `app_config_pro.yaml`; restart `qa_api`. See [08-known-limitations.md](./08-known-limitations.md).
2. **Fix `search_with_same_outline`** — Current behavior likely hurts retrieval quality more than embedding model choice. Merge + rerank instead of replace.

### P1 — Knowledge quality & data integrity

3. **Enable rerank in knowledge Q&A** — Infrastructure exists at Embedding API `/rerank`; wire it into `knowledge_agent_stream`.
4. **Delete Milvus vectors when deleting files** — Orphan vectors waste space and can leak cross-package context if filters fail.
5. **Handle long fragments** — Split blocks >512 tokens before embedding (embedding model max is 256 tokens anyway).

### P2 — Operability

6. **Direct file upload** — FTP dependency blocks easy testing and new deployments.
7. **Unify configuration** — One config path; remove hardcoded LAN IPs for your environment. See [18-configuration-files-summary.md](./18-configuration-files-summary.md).
8. **Add Milvus to compose** — Reduce manual ops friction. See [07-docker.md](./07-docker.md).
9. **Rotate secrets** — JWT, FTP credentials, and API keys are in plain config files.

### P3 — Maintainability

10. **Split `qa.py`** and remove `*_bak*` files (~13 GB cleanup from temp/rogue files is separate but recommended). See [10-cleanup-recommendations.md](./10-cleanup-recommendations.md).

---

## Summary

This is a **layout-first RAG platform** tuned for Chinese enterprise documents (PDF/Word/CAJ), with good citation metadata but a retrieval pipeline that diverges from modern RAG practice (no overlap, rerank unused, possible bug in outline expansion).

The highest-leverage fixes are:

1. Connect a working LLM
2. Fix retrieval merge/rerank logic
3. Split long fragments for embedding
4. Clean up Milvus on delete

Model upgrades (e.g. bge-m3) matter, but fixing retrieval logic will likely show faster gains than swapping embeddings alone.

---

## Quick reference — key files

| Area | Path |
|------|------|
| Knowledge CRUD | `src/rag/controllers/knowledge_mange.py`, `src/rag/services/knowledge.py` |
| Knowledge Q&A | `src/rag/services/qa.py` → `knowledge_agent_stream()` |
| Retrieval | `src/rag/services/qa.py` → `search()`, `search_with_same_outline()`, `rerank_documents()` |
| Parse + index | `src/api/services/utils.py`, `src/document_fragment/document/pdf_document.py` |
| Embeddings | `src/embedding/api.py` |
| Config | `.env`, `src/rag/configs/app_config_pro.yaml` |
