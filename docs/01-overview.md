# 01 — Project Overview

## What is this project?

A **backend platform** for:

1. **Ingesting documents** (PDF, Word, CAJ, OCR, ZIP)
2. **Splitting them into fragments** (text blocks, tables, structure)
3. **Vectorizing fragments** for semantic search
4. **Powering RAG Q&A**, knowledge bases, and custom **Agents** via external LLM APIs

There is **no frontend** in this repository. A separate web application calls these HTTP APIs.

## Target users / context

Built as an **internal enterprise tool** (Chinese document workflows, CAJ format, Jira/FTP integrations). Config files contain private-network IP addresses and service tokens from the original deployment environment.

## Architecture (globe view)

```
                    ┌─────────────────────────────────┐
                    │  External: LLM, FTP, Jira, …    │
                    └───────────────┬─────────────────┘
                                    │
    ┌───────────────────────────────┼───────────────────────────────┐
    │              document_fragment (one repo, one Docker image)    │
    │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐          │
    │  │  src/api    │  │src/embedding│  │  src/rag    │          │
    │  │  :12355     │  │  :12356     │  │  :12357     │          │
    │  │  Parse docs │  │  Vectors    │  │  Chat / KB  │          │
    │  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘          │
    │         └────────┬────────┴────────┬────────┘                 │
    │                  ▼                 ▼                          │
    │           Milvus (vectors)    SQLite (metadata)                │
    └─────────────────────────────────────────────────────────────────┘
```

## Three services, one codebase

| Logical service | Code folder | Container port | Entry module |
|-----------------|-------------|----------------|--------------|
| Document API | `src/api/` | 12355 | `api.main:app` |
| Embedding API | `src/embedding/` | 12356 | `embedding.api:app` |
| RAG / QA API | `src/rag/` | 12357 | `rag.api:app` |

All three use the **same Docker image** (`document_fragment:mupdf-3`) but start different Uvicorn processes.

## Technology stack

| Layer | Technology |
|-------|------------|
| Web framework | FastAPI + Uvicorn |
| Vector DB | Milvus 2.4 |
| Metadata DB | SQLite (embedded file) |
| Embeddings | text2vec-base-multilingual |
| Reranker | transformers (sequence classification) |
| Document parsing | pymupdf, PaddleOCR, custom layout_analysis |
| LLM | External OpenAI-compatible API |
| Runtime | Docker (Linux), Python 3.8 in image |

## End-to-end data flow

```
Upload document
    → Document API parses → fragments
    → Embedding API → vectors
    → Milvus stores vectors; static JSON + SQLite store metadata

User asks question
    → RAG API embeds query
    → Milvus similarity search
    → Rerank
    → Build prompt → External LLM
    → Stream answer (SSE)
```

## What this project is NOT

- Not a self-contained LLM (model is external)
- Not a turnkey product (requires tar images, config, Milvus)
- Not a monolith UI (API-only)
- Not fully portable without updating `app_config_pro.yaml` IPs

## Naming confusion (read this first)

| Name | Meaning |
|------|---------|
| `document_fragment/` (folder) | Entire project root |
| `src/document_fragment/` | Shared **parsing library** (not the server) |
| `document_fragment:mupdf-3` | Docker **image** tag |
| `document_fragment_api` | Docker Compose **service** name for Document API |

## Related folders outside main app

| Path | Status |
|------|--------|
| `setup/voice/` | Incomplete Whisper/voice stub (not in compose) |
| `setup/Dockerfile` | Small overlay only; base image comes from tar |

See [03-structure.md](./03-structure.md) for folder details.
