# 34 - Stage 1 Compatibility Baseline

This document freezes the current external contract of the repo as observed on July 30, 2026.

Stage 2 and later cleanup work should preserve this contract unless a later change is explicitly approved and documented.

## Scope

This baseline covers:

- the three FastAPI service entrypoints used by Compose
- published ports and service names
- currently mounted route groups and response envelopes
- startup configuration loading and known import-time key requirements
- the validated `10.42.0.125` deployment assumptions recorded in [33-10.42.0.125-vllm-compose-qa-validation.md](./33-10.42.0.125-vllm-compose-qa-validation.md)

This baseline does not claim every route is good design. It records what exists today so refactors do not break it by accident.

## Frozen runtime entrypoints

These are the entrypoints currently used by [`docker-compose.yaml`](../docker-compose.yaml):

| Compose service | Host port | Container port | Python entrypoint | Purpose |
|---|---:|---:|---|---|
| `document_fragment_api` | `12355` | `5005` | `uvicorn api.main:app` | document parsing and fragmentation |
| `embedding_api` | `12356` | `5006` | `uvicorn embedding.api:app` | embeddings and rerank |
| `qa_api` | `12357` | `5007` | `uvicorn rag.api:app` | RAG, agents, retrieval, config APIs |

These names, ports, and entrypoints are part of the compatibility target.

## App-level behavior

### Document API

- module: `src/api/main.py`
- FastAPI root path: `/api/v1`
- mounted static path: `/static`
- CORS: allow all origins, methods, headers

Mounted routers:

- `/word`
- `/pdf`
- `/ocr`
- `/caj`
- `/zip`
- `/manage`

### Embedding API

- module: `src/embedding/api.py`
- mounted static path: `/static`
- CORS: allow all origins, methods, headers

Exposed routes:

- `POST /embeddings`
- `POST /rerank`

### RAG / QA API

- module: `src/rag/api.py`
- mounted static path: `/static`
- CORS: allow all origins, methods, headers

Mounted routers:

- `/knowledge_manage`
- `/api_manage`
- `/agent`
- `/qa`
- `/unit_aliases`

Current code also includes these important quirks:

- `src/rag/controllers/user_config_manage.py` exists, but its router is not mounted
- `docs/API-Reference.md` must continue to document mounted runtime-only routes such as `/qa/ocr-team`, `/qa/agent/request_agent`, `/qa/agent/mermaid_agent`, `/qa/agent/contract_agent`, and `/unit_aliases/*`

Resolved under Stage 2 coverage on August 31, 2026:

- the duplicate `qa_router` registration in `src/rag/api.py` was removed after Stage 1 route/OpenAPI checks were added

The remaining quirks should be treated as compatibility-sensitive until regression coverage exists.

## Response envelope contract

The code does not use one response shape everywhere. Preserve current shapes for Stage 1 and Stage 2.

| Area | Current response shape |
|---|---|
| most document routes | `{ "data": ..., "detail": str, "status_code": int }` |
| document `/manage/*` | `{ "detail": ..., "status_code": int }` |
| most RAG routes using `construct_response` | `{ "data": ..., "detail": str, "status_code": int }` |
| `/api_manage/*` and `/unit_aliases/*` | `{ "status": int, "detail": str, "data": ... }` |
| SSE routes | `text/event-stream` |
| `POST /qa/agent/request_agent` | `{ "data", "extendMap", "success", "message", "code", "stateCode" }` |
| `POST /qa/report` | binary file download |
| `POST /word/doc2docx` | binary file download |
| embedding `/embeddings` | OpenAI-style embeddings JSON |
| embedding `/rerank` | `{ "scores": [...], "softmax_scores": [...] }` |

## Route inventory

The tables below are the current compatibility surface. They combine current controller code with the existing API reference. Where the docs and code differ, the code wins.

### Document API

| Method | Path | Notes |
|---|---|---|
| `POST` | `/word/sync` | multipart upload; `package_id` and `user_id` fall back to defaults when omitted |
| `POST` | `/word/doc2docx` | converts `.doc` to `.docx`, returns file |
| `POST` | `/pdf/sync` | multipart upload; accepts `max_threads`; `package_id` and `user_id` default when omitted |
| `POST` | `/ocr/sync` | multipart upload |
| `POST` | `/caj/sync/caj` | multipart upload |
| `POST` | `/zip/sync` | multipart upload plus required `package_id` and `user_id` |
| `POST` | `/zip/ftp` | background FTP ZIP ingest |
| `POST` | `/zip/upload_ftp` | background FTP upload into knowledge base |
| `GET` | `/manage/list` | paginated library listing |
| `POST` | `/manage/update` | metadata update by `task_id` |
| `DELETE` | `/manage/document_delete` | delete library by `md5` |
| `POST` | `/manage/file_info` | lookup file rows by `ids` |

### Embedding API

| Method | Path | Notes |
|---|---|---|
| `POST` | `/embeddings` | request body contains `input` |
| `POST` | `/rerank` | request body contains `query` and `texts` |

### RAG / QA API

#### Mounted and documented in `docs/API-Reference.md`

| Method | Path |
|---|---|
| `GET` | `/agent/list` |
| `GET` | `/agent/get` |
| `POST` | `/agent/create` |
| `DELETE` | `/agent/delete` |
| `POST` | `/agent/update` |
| `POST` | `/agent/stream` |
| `POST` | `/qa/qa` |
| `POST` | `/qa/ocr-chat` |
| `POST` | `/qa/ocr-org` |
| `POST` | `/qa/agent/db_agent` |
| `POST` | `/qa/agent/knowledge_agent` |
| `POST` | `/qa/agent/knowledge_file_agent` |
| `POST` | `/qa/agent/report_agent` |
| `POST` | `/qa/agent/week_agent` |
| `POST` | `/qa/agent/template_agent` |
| `POST` | `/qa/agent/jira_week_agent` |
| `POST` | `/qa/qa_desc` |
| `POST` | `/qa/get_status` |
| `POST` | `/qa/report` |
| `GET` | `/knowledge_manage/tree` |
| `GET` | `/knowledge_manage/package/list` |
| `GET` | `/knowledge_manage/package/get` |
| `GET` | `/knowledge_manage/package/recommend` |
| `POST` | `/knowledge_manage/package/create` |
| `POST` | `/knowledge_manage/package/update` |
| `DELETE` | `/knowledge_manage/package/delete` |
| `GET` | `/knowledge_manage/file/list` |
| `POST` | `/knowledge_manage/file/create` |
| `POST` | `/knowledge_manage/file/upload` |
| `POST` | `/knowledge_manage/file/update` |
| `DELETE` | `/knowledge_manage/file/delete` |
| `DELETE` | `/knowledge_manage/delete` |
| `GET` | `/knowledge_manage/get` |
| `POST` | `/knowledge_manage/retrieval/search` |
| `POST` | `/knowledge_manage/retrieval/file_search` |
| `POST` | `/api_manage/api_insert` |
| `GET` | `/api_manage/api_search` |
| `GET` | `/api_manage/api_list` |
| `POST` | `/api_manage/api_update` |
| `GET` | `/api_manage/field_list` |
| `POST` | `/api_manage/api_field_insert` |
| `POST` | `/api_manage/api_data_insert` |
| `POST` | `/api_manage/api_data_update` |
| `GET` | `/api_manage/api_data_list` |
| `DELETE` | `/api_manage/api_data_delete` |

#### Mounted in code but missing from `docs/API-Reference.md`

| Method | Path | Notes |
|---|---|---|
| `POST` | `/qa/ocr-team` | non-SSE JSON response |
| `POST` | `/qa/agent/request_agent` | custom success envelope |
| `POST` | `/qa/agent/mermaid_agent` | SSE |
| `POST` | `/qa/agent/contract_agent` | returns JSON result, not SSE |
| `POST` | `/unit_aliases/unit_insert` | custom `ReadyResponse` envelope |
| `GET` | `/unit_aliases/unit_search` | custom `ReadyResponse` envelope |
| `GET` | `/unit_aliases/unit_list` | custom `ReadyResponse` envelope |
| `POST` | `/unit_aliases/unit_update` | custom `ReadyResponse` envelope |
| `DELETE` | `/unit_aliases/unit_delete` | custom `ReadyResponse` envelope |

#### Present in docs but not mounted by `rag.api`

These should be treated as a documentation/runtime mismatch, not silently deleted:

- `/user_config_manage/list`
- `/user_config_manage/get`
- `/user_config_manage/create`
- `/user_config_manage/delete`
- `/user_config_manage/update`

As of August 31, 2026, `docs/API-Reference.md` explicitly marks these `/user_config_manage/*` entries as controller-defined but currently unmounted.

## Streaming contract

Current SSE routes use `StreamingResponse(..., media_type="text/event-stream")`.

Observed streaming routes:

- `POST /agent/stream`
- `POST /qa/qa`
- `POST /qa/ocr-chat`
- `POST /qa/ocr-org`
- `POST /qa/agent/db_agent`
- `POST /qa/agent/knowledge_agent`
- `POST /qa/agent/knowledge_file_agent`
- `POST /qa/agent/report_agent`
- `POST /qa/agent/week_agent`
- `POST /qa/agent/template_agent`
- `POST /qa/agent/jira_week_agent`
- `POST /qa/agent/mermaid_agent`

Current stream generators emit final `data: [DONE]` markers. Keep that behavior unless tests and clients are updated together.

## Configuration loading contract

### Source of truth

RAG configuration is loaded by `src/rag/configs/__init__.py`:

1. read `src/rag/configs/app_config_pro.yaml`
2. override matching keys from process environment

That precedence should remain unchanged for Stage 2.

### Document API and Embedding API environment contract

Compose currently injects these environment variables into `document_fragment_api`:

- `DET_MODEL_PATH`
- `REG_MODEL_PATH`
- `DET_MODEL_DEVICE`
- `REG_MODEL_DEVICE`
- `MILVUS_URI`
- `COLLECTION_NAME`
- `TOKENIZE_URL`
- `MODEL_NAME`
- `EMBEDDING_URL`
- `RERANK_URL`

Compose currently injects these into `embedding_api`:

- `EMBEDDING_MODEL_PATH`
- `RERANKER_MODEL_PATH`
- `COLLECTION_NAME`
- `API_BASE`
- `API_KEY`
- `MODEL_NAME`
- `MILVUS_URI`
- `EMBEDDING_URL`
- `RERANK_URL`

### RAG app config keys currently read in code

Static code lookup of `app_config[...]` under `src/` shows these keys currently exist in the codebase:

- `API_BASE_URL`
- `API_BASE_URL2`
- `API_KEY`
- `API_KEY2`
- `API_URL`
- `BQ_DATA_DESC_URL`
- `BQ_DATA_NO_PAGE`
- `EMBEDDING_URL`
- `FTP_HOST`
- `FTP_PASSWORD`
- `FTP_PORT`
- `FTP_USERNAME`
- `GET_TOKEN_URL`
- `JIRA_BOARD`
- `JIRA_TOKEN`
- `JIRA_URL`
- `JIRA_USER`
- `LLM_URL`
- `MAPPING_URL`
- `MAX_NEW_TOKENS`
- `MAX_TOKENS`
- `MILVUS_COLLECTION`
- `MILVUS_URI`
- `MODEL_NAME`
- `MODEL_NAME2`
- `OCR_URL`
- `RAG_URL`
- `REQUEST_URL`
- `RERANK_URL`
- `STATISTIC_URL`
- `TOKEN`
- `TOKENIZE_URL`

### Minimum RAG startup-sensitive keys

Based on the modules imported by `rag.api` and the existing `10.42.0.125` validation notes, these keys must currently be treated as startup-sensitive:

- `MODEL_NAME`
- `API_KEY`
- `API_BASE_URL`
- `MODEL_NAME2`
- `API_KEY2`
- `API_BASE_URL2`
- `MILVUS_COLLECTION`
- `MILVUS_URI`
- `EMBEDDING_URL`
- `RERANK_URL`
- `API_URL`
- `MAX_TOKENS`
- `MAX_NEW_TOKENS`
- `GET_TOKEN_URL`
- `REQUEST_URL`
- `TOKEN`
- `MAPPING_URL`

Do not rename, remove, or delay these lookups in Stage 2 unless compatibility tests replace that protection.

## `10.42.0.125` deployment assumptions to preserve

The currently validated Linux target contract comes from July 29, 2026 and should be preserved during cleanup:

- host: `10.42.0.125`
- project directory: `/home/jj/document_fragment`
- Milvus startup script: `/home/jj/setup/standalone_embed.sh`
- Milvus container-to-host route from backend containers: `http://172.17.0.1:19530`
- host `vLLM` OpenAI-compatible endpoint: `http://10.42.0.125:8000/v1`
- exact served model id used by backend: `/models/Qwen3-14B-AWQ`
- Compose services kept on ports `12355`, `12356`, `12357`
- Compose-internal embedding/rerank URLs kept as:
  - `http://embedding_api:5006/embeddings`
  - `http://embedding_api:5006/rerank`

Stage 2 should not overwrite host-specific files casually. In particular:

- `.env`
- `src/rag/configs/app_config_pro.yaml`
- `docker-compose.yaml`
- `remote-125.docker-compose.yaml`

## Validation checklist for later stages

Any Stage 2 structural cleanup should be checked against this baseline:

1. `docker-compose.yaml` still exposes the same three service names and ports.
2. `uvicorn api.main:app`, `uvicorn embedding.api:app`, and `uvicorn rag.api:app` still boot.
3. `http://localhost:12355/docs`, `http://localhost:12356/docs`, and `http://localhost:12357/docs` still respond.
4. All mounted route groups above still exist.
5. SSE endpoints still respond as `text/event-stream`.
6. The documented `10.42.0.125` topology still works without changing model id, bridge address, or compose service names.

## Current mismatches to carry forward deliberately

These are known inconsistencies that should be preserved until there is explicit test-backed cleanup:

- `docs/API-Reference.md` is incomplete relative to mounted RAG routes.
- `docs/API-Reference.md` lists `/user_config_manage/*`, but `rag.api` does not mount that router.
- `src/rag/api.py` includes `qa_router` twice.
- response shapes differ across controllers.
- document ingestion routes are a mix of awaited threadpool work and background-task behavior.

The existence of a mismatch is not permission to change it during Stage 2.
