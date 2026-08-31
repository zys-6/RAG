# 04 — Functions & API Reference

## Service overview

| Service | Base URL | Swagger |
|---------|----------|---------|
| Document API | http://localhost:12355/api/v1 | http://localhost:12355/docs |
| Embedding API | http://localhost:12356 | http://localhost:12356/docs |
| RAG / QA API | http://localhost:12357 | http://localhost:12357/docs |

---

## 1. Document API — document ingestion

**Purpose:** Parse uploaded files into fragments and index into Milvus.

| Prefix | Endpoint | Description |
|--------|----------|-------------|
| `/pdf` | POST `/sync` | Parse PDF, fragment, embed, store |
| `/word` | POST `/sync` | Parse Word document |
| `/word` | POST `/doc2docx` | Convert .doc to .docx |
| `/ocr` | POST `/sync` | OCR-based document parsing |
| `/caj` | POST `/sync/caj` | CAJ (Chinese academic) format |
| `/zip` | POST `/sync` | Batch zip upload |
| `/zip` | POST `/ftp`, `/upload_ftp` | FTP-related upload |
| `/manage` | GET `/list` | List document library tasks |
| `/manage` | POST `/update` | Update task metadata |
| `/manage` | DELETE `/document_delete` | Delete document |

**Supported formats:** PDF, Word, CAJ, OCR images, ZIP archives.

**Output:** Fragment JSON under `src/api/static/fragment/`; vectors in Milvus collection `fragments`.

---

## 2. Embedding API — vectors & reranking

**Purpose:** Turn text into embeddings; rerank search candidates.

| Endpoint | Method | Body | Response |
|----------|--------|------|----------|
| `/embeddings` | POST | `{"input": "text"}` or list | OpenAI-style embedding vectors |
| `/rerank` | POST | `{"query": "...", "texts": ["...", "..."]}` | `scores`, `softmax_scores` |

**Models:**

- Embeddings: `text2vec-base-multilingual` (CPU by default)
- Reranker: transformers sequence classification model in `models/reranker/`

**Used by:** Document API (indexing), RAG API (search pipeline).

---

## 3. RAG / QA API — knowledge & chat

### 3.1 Knowledge base — `/knowledge_manage`

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/tree` | GET | Knowledge base tree for user |
| `/package/list` | GET | List knowledge packages |
| `/package/get` | GET | Package details |
| `/package/create` | POST | Create knowledge base |
| `/package/update` | POST | Update package |
| `/package/delete` | DELETE | Delete package |
| `/file/list` | GET | Files in a package |
| `/file/upload` | POST | Upload file to knowledge base |
| `/file/update` | POST | Update file metadata |
| `/file/delete` | DELETE | Delete file |
| `/delete` | DELETE | Clear Milvus data for KB |

### 3.2 Agents — `/agent`

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/list` | GET | List all agents |
| `/get` | GET | Agent detail |
| `/create` | POST | Create custom agent |
| `/update` | POST | Update agent |
| `/delete` | DELETE | Delete agent |
| `/stream` | POST | Streaming agent chat (SSE) |

### 3.3 Q&A — `/qa`

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/qa` | POST | General LLM chat with RAG |
| `/ocr-chat` | POST | OCR-focused chat |
| `/ocr-org` | POST | OCR team template |
| `/agent/db_agent` | POST | Database assistant |
| `/agent/knowledge_agent` | POST | Document library assistant |
| `/agent/report_agent` | POST | Annual report assistant |
| `/agent/week_agent` | POST | Weekly report assistant |
| `/agent/template_agent` | POST | Template assistant |
| `/agent/jira_week_agent` | POST | Jira weekly report |
| `/qa_desc` | POST | Database detail lookup |
| `/get_status` | POST | Task status |
| `/report` | POST | Upload report |

Most chat endpoints return **Server-Sent Events (SSE)** streams.

### 3.4 System / config — `/api_manage`, `/user_config_manage`

**API manage:** Dynamic tool/API configuration (fields, data CRUD).

**User config:** Per-user JSON template storage.

---

## Core functional flows

### Flow A — Index a document

```
Client → POST /api/v1/pdf/sync (Document API)
    → parse PDF (document_fragment + layout_analysis)
    → POST /embeddings (Embedding API, internal)
    → insert vectors (Milvus)
    → save fragment JSON + task metadata
```

### Flow B — RAG question answering

```
Client → POST /qa/qa (RAG API)
    → embed question (Embedding API)
    → Milvus similarity search
    → POST /rerank (Embedding API)
    → assemble prompt (prompt_config.yaml)
    → call external LLM (request_llm.py)
    → stream SSE response
    → save Dialogue to SQLite
```

### Flow C — Knowledge base upload

```
Client → POST /knowledge_manage/file/upload
    → triggers Document API processing
    → SQLite File record updated
    → vectors in Milvus linked to package
```

---

## External dependencies for full functionality

| Feature | Requires |
|---------|----------|
| Document parsing | Models in `models/`, Document API up |
| Embeddings / search | Embedding API + Milvus |
| Chat / agents | RAG API + **reachable LLM** |
| Jira weekly report | Jira server in config |
| FTP upload | FTP server in config |

---

## What works without external LLM

- Document upload and parsing
- Embeddings and rerank
- Knowledge base list / agent list (SQLite)
- Milvus vector search (if data indexed)

## What requires external LLM

- `/qa/*` chat endpoints
- Agent streaming
- Report generation agents

See [05-configuration.md](./05-configuration.md) for LLM URL setup.
