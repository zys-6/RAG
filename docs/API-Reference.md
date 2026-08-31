# Document Fragment Platform — API Reference

Enterprise document processing and RAG backend. All services expose Swagger at `/docs`.

> **Note:** Cursor cannot open `.docx` in the editor. Use this `.md` file in Cursor, or open
> `API-Reference.docx` with Microsoft Word from File Explorer.

## Swagger / OpenAPI

| Service | Port | Swagger UI | OpenAPI JSON |
|---------|------|------------|--------------|
| Document API | 12355 | http://localhost:12355/docs | http://localhost:12355/openapi.json |
| Embedding API | 12356 | http://localhost:12356/docs | http://localhost:12356/openapi.json |
| RAG / QA API | 12357 | http://localhost:12357/docs | http://localhost:12357/openapi.json |

## How to use Swagger

1. Run `docker compose up -d` from the `document_fragment` project root
2. Open a Swagger URL above in your browser
3. Expand an endpoint → **Try it out** → **Execute**

## Response formats

| Service | Response shape |
|---------|----------------|
| Document API | `{ "data", "detail", "status_code" }` |
| RAG (most routes) | `{ "data", "detail", "status_code" }` |
| RAG `/api_manage/*` and `/unit_aliases/*` | `{ "status", "detail", "data" }` |
| QA streaming | `text/event-stream` (SSE) |
| Embedding API | OpenAI-style JSON / `{ scores, softmax_scores }` |

## Runtime parity notes

This file is intentionally aligned to the current runtime, not to an idealized API surface.

Known mismatches and quirks preserved as of August 31, 2026:

- `/user_config_manage/*` is documented below because the controller exists, but those routes are not mounted by `src/rag/api.py`.
- `/qa/ocr-team`, `/qa/agent/request_agent`, `/qa/agent/mermaid_agent`, `/qa/agent/contract_agent`, and `/unit_aliases/*` are mounted at runtime and should stay documented here even though they were missing from earlier snapshots.

Resolved in Stage 2 on August 31, 2026:

- `src/rag/api.py` no longer includes `qa_router` twice. The duplicate registration was removed after Stage 1 route/OpenAPI coverage was added.

---

## Document API (port 12355)

**Swagger:** http://localhost:12355/docs

FastAPI root_path=/api/v1 (for proxy/OpenAPI). Routes are mounted at paths below.

### Word — /word

| Method | Path | Parameters | Description |
|--------|------|------------|-------------|
| POST | `/word/sync` | multipart: file; body: package_id, user_id | Upload Word/doc, convert & index in background |
| POST | `/word/doc2docx` | multipart: file | Convert .doc to .docx; returns file download |

### PDF — /pdf

| Method | Path | Parameters | Description |
|--------|------|------------|-------------|
| POST | `/pdf/sync` | multipart: file; Form: max_threads (opt); body: package_id, user_id | Upload PDF, parse & index in background |

### OCR — /ocr

| Method | Path | Parameters | Description |
|--------|------|------------|-------------|
| POST | `/ocr/sync` | multipart: file | Upload for OCR; returns file_id (MD5) |

### CAJ — /caj

| Method | Path | Parameters | Description |
|--------|------|------------|-------------|
| POST | `/caj/sync/caj` | multipart: file; body: package_id, user_id | Upload CAJ, process in background |

### ZIP — /zip

| Method | Path | Parameters | Description |
|--------|------|------------|-------------|
| POST | `/zip/sync` | multipart: file; body: package_id, user_id | Upload ZIP, extract & process |
| POST | `/zip/ftp` | query: ftp_url | Fetch ZIP from FTP (background) |
| POST | `/zip/upload_ftp` | query: ftp_url, package_id, user_id | FTP ZIP to knowledge base |

### Document manage — /manage

| Method | Path | Parameters | Description |
|--------|------|------------|-------------|
| GET | `/manage/list` | query: page_no (1), page_size (10), sort_field, sort_type (desc) | List document libraries |
| POST | `/manage/update` | body: task_id, kwargs (dict) | Update library metadata |
| POST | `/manage/file_info` | body: { "ids": ["file-a", "file-b"] } | Get file rows from `File` table by `id` |
| DELETE | `/manage/document_delete` | body: md5 (optional) | Delete library by MD5 |

---

## Embedding API (port 12356)

**Swagger:** http://localhost:12356/docs

Vector embedding and reranking service.

### Embeddings

| Method | Path | Parameters | Description |
|--------|------|------------|-------------|
| POST | `/embeddings` | body: { "input": string | string[] | int[][] } | Text to embedding vectors (OpenAI-compatible) |
| POST | `/rerank` | body: query (str), texts (List[str]) | Rerank texts; returns scores & softmax_scores |

---

## RAG / QA API (port 12357)

**Swagger:** http://localhost:12357/docs

Knowledge base, agents, Q&A, and API config management.

### Agent — /agent

| Method | Path | Parameters | Description |
|--------|------|------------|-------------|
| GET | `/agent/list` | — | List all agents |
| GET | `/agent/get` | query: agent_id | Get agent details |
| POST | `/agent/create` | body: name, agent_prompt, description, icon; opt: agent_type, agent_example, agent_temperature | Create agent |
| DELETE | `/agent/delete` | body: agent_id | Delete agent |
| POST | `/agent/update` | body: agent_id, agent_attr, agent_value | Update agent attribute |
| POST | `/agent/stream` | body: agent_id, query; thing_pattern (default false) | Agent chat (SSE stream) |

### Q&A — /qa

| Method | Path | Parameters | Description |
|--------|------|------------|-------------|
| POST | `/qa/qa` | body: task_id, query, history, thing_pattern, user_id | General LLM chat (SSE) |
| POST | `/qa/ocr-chat` | body: task_id, query, history, thing_pattern, user_id, file | OCR document chat (SSE) |
| POST | `/qa/ocr-org` | same as ocr-chat | OCR team template chat (SSE) |
| POST | `/qa/agent/db_agent` | body: task_id, query, history, thing_pattern, user_id | Database assistant (SSE) |
| POST | `/qa/agent/knowledge_agent` | body: package_id, task_id, query, history, thing_pattern, user_id | Knowledge-base agent (SSE) |
| POST | `/qa/agent/knowledge_file_agent` | body: ids, task_id, query, history, thing_pattern, user_id | Knowledge-base agent scoped by File table ids (SSE) |
| POST | `/qa/agent/report_agent` | body: task_id, query, thing_pattern, user_id | Annual report agent (SSE) |
| POST | `/qa/agent/week_agent` | body: task_id, query, thing_pattern, user_id | Weekly report agent (SSE) |
| POST | `/qa/agent/template_agent` | body: task_id, query, thing_pattern, user_id, config_id | Template agent (SSE) |
| POST | `/qa/agent/jira_week_agent` | body: task_id, query, thing_pattern, user_id | Jira weekly report agent (SSE) |
| POST | `/qa/ocr-team` | body: team_id, file, creator_guid | OCR team template parse; JSON response |
| POST | `/qa/agent/request_agent` | body: task_id, query, thing_pattern, user_id | Requirement assistant; custom success envelope |
| POST | `/qa/agent/mermaid_agent` | body: task_id, query, thing_pattern, user_id | Mermaid diagram agent (SSE) |
| POST | `/qa/agent/contract_agent` | body: task_id, query, thing_pattern, user_id | Contract assistant; JSON response |
| POST | `/qa/qa_desc` | body: sql_query (dict), page (1), page_size (15) | SQL query table data |
| POST | `/qa/get_status` | body: task_id | Get QA task status |
| POST | `/qa/report` | body: query | Generate report file (binary download) |

### Knowledge base — /knowledge_manage

| Method | Path | Parameters | Description |
|--------|------|------------|-------------|
| GET | `/knowledge_manage/tree` | query: user_id (opt), group_id (opt) | Knowledge base tree |
| GET | `/knowledge_manage/package/list` | query: user_id (opt), group_id (opt) | List packages |
| GET | `/knowledge_manage/package/get` | query: knowledge_id | Package details |
| GET | `/knowledge_manage/package/recommend` | query: knowledge_id | Recommended questions |
| POST | `/knowledge_manage/package/create` | body: package_name, description, user_id, group_id (opt) | Create package |
| POST | `/knowledge_manage/package/update` | body: package_id, package_name, description | Update package |
| DELETE | `/knowledge_manage/package/delete` | body: package_id | Delete package |
| GET | `/knowledge_manage/file/list` | query: package_id (opt) | List files in package |
| POST | `/knowledge_manage/file/create` | body: id, file_id, file_name, file_size, file_path, file_type, package_id, user_id | Register file (internal) |
| POST | `/knowledge_manage/file/upload` | body: package_id, ftp_url, user_id | Upload via FTP URL |
| POST | `/knowledge_manage/file/update` | body: package_id, file_id, attr, value | Update file attribute |
| DELETE | `/knowledge_manage/file/delete` | body: file_id | Delete file |
| DELETE | `/knowledge_manage/delete` | — | Clear all Milvus vectors |
| GET | `/knowledge_manage/get` | — | List files in Milvus |
| POST | `/knowledge_manage/retrieval/search` | body: query, package_id?, document_ids?, mode (`vector`/`outline`/`pipeline`), limit, top_k | Retrieval-only test (no LLM) |
| POST | `/knowledge_manage/retrieval/file_search` | body: query, ids, mode (`vector`/`outline`/`pipeline`), limit, top_k | Retrieval-only test scoped by File table ids (no LLM) |

### API config — /api_manage

| Method | Path | Parameters | Description |
|--------|------|------------|-------------|
| POST | `/api_manage/api_insert` | body: data (dict) | Add API config |
| GET | `/api_manage/api_search` | query: api_name | Get API config details |
| GET | `/api_manage/api_list` | — | List all API configs |
| POST | `/api_manage/api_update` | body: api_name, info (dict) | Update API metadata |
| GET | `/api_manage/field_list` | query: api_name | List updatable fields |
| POST | `/api_manage/api_field_insert` | body: api_name, type, field_data (dict) | Add field to config |
| POST | `/api_manage/api_data_insert` | body: api_name, field_name, field_data (dict) | Add field data |
| POST | `/api_manage/api_data_update` | body: api_name, field_name, field_data (dict) | Update field data |
| GET | `/api_manage/api_data_list` | query: page_on, page_size, api_name, field_name | Paginated field data |
| DELETE | `/api_manage/api_data_delete` | body: api_name, field_name, data_list | Delete field data items |

### Unit aliases — /unit_aliases

| Method | Path | Parameters | Description |
|--------|------|------------|-------------|
| POST | `/unit_aliases/unit_insert` | body: data { name, aliases } | Create a unit alias record |
| GET | `/unit_aliases/unit_search` | query: unit_name | Search a unit alias |
| GET | `/unit_aliases/unit_list` | — | List all unit aliases |
| POST | `/unit_aliases/unit_update` | body: unit_id, data { name?, aliases? } | Update a unit alias |
| DELETE | `/unit_aliases/unit_delete` | query: unit_id | Delete a unit alias |

### User config — /user_config_manage

The controller exists in `src/rag/controllers/user_config_manage.py`, but these routes are not currently mounted by `src/rag/api.py`.

| Method | Path | Parameters | Description |
|--------|------|------------|-------------|
| GET | `/user_config_manage/list` | query: user_id | List configs for user |
| GET | `/user_config_manage/get` | query: user_config_id | Get config details |
| POST | `/user_config_manage/create` | body: user_id, config_json, config_name | Create JSON template |
| DELETE | `/user_config_manage/delete` | body: user_config_id | Delete template |
| POST | `/user_config_manage/update` | body: user_config_id, user_id, config_json, config_name | Update template |

---

## Appendix — not in docker-compose

| Method | Path | Parameters | Description |
|--------|------|------------|-------------|
| POST | `/convert` | multipart: file | Standalone doc→docx |
| POST | `/table`, `/structure/{lang}`, `/ocr/{lang}` | internal | Layout/OCR model |
