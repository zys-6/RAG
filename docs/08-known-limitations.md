# 08 — Known Limitations & Temporarily Unavailable Features

Last updated based on deployment testing on **Windows + Docker Desktop** (local dev environment).

Use this document to know **what works now** vs **what is blocked**, and **why**.

---

## Status legend

| Status | Meaning |
|--------|---------|
| ✅ Available | Tested and working in current setup |
| ⚠️ Partial | Starts but some paths fail |
| ❌ Blocked | Cannot use until listed fix is applied |
| 🚫 Not deployed | Not part of current compose / incomplete code |

---

## Summary table

| Feature / API area | Status | Reason |
|--------------------|--------|--------|
| Document API `/docs`, service up | ✅ | Containers running |
| PDF/Word/OCR/CAJ/ZIP parse & index | ⚠️ | Needs test upload; old tasks in DB show `failed` |
| Embedding `/embeddings` | ✅ | Tested with sample text |
| Embedding `/rerank` | ✅ | Tested with query + texts |
| RAG `/docs`, service up | ✅ | Container running |
| Knowledge base list/tree/CRUD | ✅ | SQLite works; list endpoints tested |
| Agent list / CRUD | ✅ | `/agent/list` returned data |
| General chat `/qa/qa` | ❌ | External LLM unreachable |
| OCR chat `/qa/ocr-chat` | ❌ | Needs LLM + possibly OCR_URL |
| All `/qa/agent/*` streaming agents | ❌ | Needs external LLM |
| Jira weekly report agent | ❌ | Needs LLM + Jira (`JIRA_URL` internal) |
| Report upload/generation | ❌ | Needs LLM + enterprise URLs |
| FTP zip upload `/zip/ftp` | ❌ | FTP server in config not reachable |
| Tokenize / token counting | ❌ | `TOKENIZE_URL` → `192.168.1.100` timeout |
| Document library `/manage/list` | ⚠️ | Works but shows old failed tasks from prior env |
| Milvus vector search | ✅ | Connected; collection `fragments` exists |
| SQLite metadata | ✅ | Auto-used by RAG API |
| Celery async document tasks | 🚫 | Not in docker-compose; needs Redis (`CELERY_BROKER`) |
| Voice / Whisper module | 🚫 | `setup/voice/` incomplete; not in compose |
| Auth / login | 🚫 | No built-in auth; `user_id` passed by client |
| Frontend UI | 🚫 | Not in repository |

---

## Blocked by external LLM (most chat features)

**Affected endpoints (RAG API, port 12357):**

- `POST /qa/qa`
- `POST /qa/ocr-chat`
- `POST /qa/ocr-org`
- `POST /agent/db_agent`
- `POST /agent/knowledge_agent`
- `POST /agent/report_agent`
- `POST /agent/week_agent`
- `POST /agent/template_agent`
- `POST /agent/jira_week_agent`
- `POST /agent/stream`

**Reason:** Config points to LLM at `192.168.1.100:7819` (original internal network). Connection **times out** from your PC/containers.

**Config locations:**

```yaml
# .env
API_BASE=http://192.168.1.100:7819/v1
TOKENIZE_URL=http://192.168.1.100:7819/tokenize

# app_config_pro.yaml
API_BASE_URL: http://192.168.1.100:7819/v1/
TOKENIZE_URL: http://192.168.1.100:7819/tokenize
MODEL_NAME: Zhuque-72b
```

**Fix:** Point to a reachable OpenAI-compatible API (local Ollama, cloud API, or destination server LLM). Update **both** `.env` and `app_config_pro.yaml`. Restart `qa_api`.

---

## Blocked by enterprise / internal network URLs

These features call services hardcoded for the **original deployment LAN**:

| Feature | Config key | Example value | Reason blocked |
|---------|------------|---------------|----------------|
| FTP upload | `FTP_HOST`, `FTP_PORT` | `192.168.1.49:21` | Internal FTP not on your network |
| Jira integration | `JIRA_URL`, `JIRA_USER`, `JIRA_TOKEN` | `192.168.1.143:8080` | Jira not reachable |
| Org mapping | `MAPPING_URL` | `192.168.1.172:8080/...` | Internal gateway |
| Statistics / BQ data | `STATISTIC_URL`, `BQ_DATA_DESC_URL` | `192.168.1.172/...` | Internal runtime API |
| OCR external service | `OCR_URL` | `192.168.1.223:5000/...` | Separate OCR service |
| Token length API | `GET_TOKEN_URL` | `124.16.138.144:8011/...` | External dependency |

**Fix:** Replace with your equivalents, or disable features that call these URLs.

---

## Partially available — Document parsing

**Status:** ⚠️ Partial

**What works:**

- Document API starts and serves Swagger
- Models mounted (`table_detection`, `table_recognition`, PaddleOCR, etc.)
- Milvus connection after config fix

**What may fail:**

- Upload/parse if source files missing from old deployment paths
- Historical tasks in `/manage/list` show `task_status=failed` (from April 2025 runs on old server)
- CAJ / Word paths depend on file availability and format

**Fix:** Test with a new upload via Swagger; ignore old failed task records.

---

## Not deployed — Celery async processing

**Affected:** Async PDF/Word processing in `src/tasks/main.py`

**Reason:**

- `CELERY_BROKER=redis` in `.env` but **no Redis** in project compose
- `docker-compose.yaml` does not include worker or Redis services
- Document API `process_pdf` sync path works; async path raises `NotImplementedError`

**Fix:** Add Redis + Celery worker to compose, or use sync endpoints only.

---

## Not deployed — Voice module

**Path:** `setup/voice/` (Whisper / Kokoro tars exist)

**Reason:**

- Code incomplete (imports missing modules)
- Not referenced in `docker-compose.yaml`

**Fix:** Separate project effort; not required for document/RAG core.

---

## Infrastructure / environment limitations

| Issue | Impact | Notes |
|-------|--------|-------|
| Dual config (`.env` + yaml) | Misconfiguration easy | Milvus URI had to be fixed in yaml separately |
| Milvus not in compose | Extra manual step | Must start Milvus before APIs |
| CPU-only models | Slow inference | `DET_MODEL_DEVICE=cpu` in `.env` |
| No GPU in destination VM | Slow on server too | CentOS VM had 4 vCPU, no GPU |
| Large image tar (~12.5 GB) | Long first-time load | One-time `docker load` wait |
| Naming confusion | Hard to navigate | See `03-structure.md` naming map |

---

## What was verified working (reference)

Tested successfully on current setup:

```
GET  http://localhost:12355/docs  → 200
GET  http://localhost:12356/docs  → 200
GET  http://localhost:12357/docs  → 200
POST http://localhost:12356/embeddings  → vectors returned
POST http://localhost:12356/rerank      → scores returned
GET  http://localhost:12357/agent/list  → agent data returned
GET  http://localhost:12357/knowledge_manage/package/list → data returned
Milvus list_collections → ['fragments']
```

---

## Priority fix order (to unlock most features)

1. **Configure reachable LLM** → unlocks all `/qa/*` chat and agents
2. **Configure TOKENIZE_URL** (if chat uses token limits)
3. **Test document upload** on Document API with a fresh file
4. **Replace or remove** enterprise URLs (FTP, Jira, BQ) as needed
5. Optional: add Redis + Celery for async parsing

See [05-configuration.md](./05-configuration.md) for config details.

---

## How to update this document

When you fix a limitation, change status from ❌ to ✅ and note the date and what was changed.

When new issues are found, add a row to the summary table with endpoint, status, and reason.
