# 18 — Configuration Files Summary

Complete reference for every configuration file in the project: what it does, who reads it, and when to edit it.

For deployment checklists and environment-specific notes, see also [05-configuration.md](./05-configuration.md).

---

## Two config systems (read this first)

The application reads settings from **two independent sources**. Updating only one often leaves the other stale.

| Source | Loaded by | Purpose |
|--------|-----------|---------|
| `document_fragment/.env` | Docker Compose → container environment variables | Model paths, Milvus URI, LLM keys for containers |
| `src/rag/configs/app_config_pro.yaml` | Python at import time | LLM URLs, Milvus, FTP, Jira, embedding/rerank URLs, most RAG logic |

**Common trap:** Changing Milvus or LLM settings in `.env` alone may not fix RAG issues if `app_config_pro.yaml` still has old values.

Active config loader:

```python
# src/rag/configs/__init__.py
app_config = read_app_config()  # loads app_config_pro.yaml
prompt_config = read_prompt_config()  # loads prompt_config.yaml
```

---

## Infrastructure & deployment

### `document_fragment/docker-compose.yaml`

Defines three services from the same image (`document_fragment:mupdf-3`):

| Service | Host port | Internal port | Command | Role |
|---------|-----------|---------------|---------|------|
| `document_fragment_api` | 12355 | 5005 | `uvicorn api.main:app` | Document parsing / fragmentation |
| `embedding_api` | 12356 | 5006 | `uvicorn embedding.api:app` | Embeddings + reranking |
| `qa_api` | 12357 | 5007 | `uvicorn rag.api:app` | RAG / Q&A |

**Volumes:** `./src` (live code), `./models` (ML weights), `./models/.paddleocr` (OCR cache).

**Environment:** All services read variables from `.env` (see below). Service-specific subsets are listed in the compose file.

---

### `document_fragment/.env`

Environment variables injected into Docker containers by Compose.

| Variable | Example | Used by | Description |
|----------|---------|---------|-------------|
| `DET_MODEL_PATH` | `/models/table_detection` | document API | Table detection model path |
| `REG_MODEL_PATH` | `/models/table_recognition` | document API | Table recognition model path |
| `DET_MODEL_DEVICE` | `cpu` | document API | Device for table detection |
| `REG_MODEL_DEVICE` | `cpu` | document API | Device for table recognition |
| `EMBEDDING_MODEL_PATH` | `/models/text2vec-base-multilingual` | embedding API | Sentence embedding model |
| `RERANKER_MODEL_PATH` | `/models/reranker` | embedding API | Reranker model |
| `COLLECTION_NAME` | `fragments` | all services | Milvus collection name |
| `MILVUS_URI` | `http://host.docker.internal:19530` | document API, qa API | Milvus endpoint |
| `MILVUS_URL` | `http://host.docker.internal:19530` | embedding API | Same Milvus (different env var name) |
| `TOKENIZE_URL` | `http://host:7819/tokenize` | document API, qa API | LLM token counting |
| `API_BASE` | `http://host:7819/v1` | embedding API, qa API | OpenAI-compatible LLM base URL |
| `API_KEY` | your key | embedding API, qa API | LLM API key |
| `MODEL_NAME` | `zhuque3` | all LLM services | LLM model identifier |
| `CELERY_BROKER` | `redis` | optional async | Celery broker (no Redis in compose) |
| `TOKEN` | JWT string | enterprise APIs | Auth token for external systems |
| `URL` | (empty) | optional | Legacy/unused placeholder |

**Windows Docker tip:** Use `host.docker.internal` to reach services on the host (e.g. Milvus on port 19530).

---

### `setup/Dockerfile`

Thin image layer on top of `document_fragment:mupdf-3`. Installs Markdown and BeautifulSoup from local `/wheels`. Not the main application image — the base image is loaded from `document_fragment-mupdf-3.tar`.

---

### `setup/embedEtcd.yaml`

Milvus embedded etcd configuration:

- Listen/advertise URLs on port 2379
- 4 GB storage quota (`quota-backend-bytes`)
- Auto-compaction settings

Generated and mounted by `standalone_embed.sh` when starting Milvus standalone. Path on host: `setup/embedEtcd.yaml` → container `/milvus/configs/embedEtcd.yaml`.

---

### `setup/user.yaml`

Milvus user override file. Add custom Milvus settings here to override defaults in `milvus.yaml`. Currently empty (placeholder). Mounted as `/milvus/configs/user.yaml` in the Milvus container.

---

### `setup/standalone_embed.sh`

Shell script (Linux) that:

1. Creates `embedEtcd.yaml` and `user.yaml`
2. Runs `milvusdb/milvus:v2.4.4` standalone on port **19530**
3. Persists data to `setup/volumes/milvus/`

Not a config file itself, but it **generates** Milvus config files and starts the vector database.

---

## Application runtime (Python)

Location: `src/rag/configs/`

### `app_config_pro.yaml` — **primary runtime config**

The main config the RAG application loads at startup. **This is the file most Python code reads.**

| Section | Keys | Purpose |
|---------|------|---------|
| **LLM (primary)** | `MODEL_NAME`, `API_KEY`, `API_BASE_URL` | Main LLM (e.g. Zhuque-72b) |
| **LLM (secondary)** | `MODEL_NAME2`, `API_KEY2`, `API_BASE_URL2` | Fallback LLM (e.g. Ollama / DeepSeek) |
| **Vector DB** | `MILVUS_URI`, `MILVUS_COLLECTION`, `COLLECTION_NAME` | Milvus connection and collection |
| **Embedding** | `EMBEDDING_URL`, `RERANK_URL` | Calls `http://embedding_api:5006/...` inside Docker network |
| **Token limits** | `MAX_TOKENS`, `MAX_NEW_TOKENS`, `TOKENIZE_URL`, `GET_TOKEN_URL` | Context window and token counting |
| **Service links** | `API_URL`, `RAG_URL` | Cross-service HTTP calls (document ↔ RAG) |
| **Enterprise — FTP** | `FTP_HOST`, `FTP_PORT`, `FTP_USERNAME`, `FTP_PASSWORD` | Zip upload via FTP |
| **Enterprise — Jira** | `JIRA_URL`, `JIRA_USER`, `JIRA_TOKEN`, `JIRA_BOARD` | Jira integration |
| **Enterprise — data** | `MAPPING_URL`, `STATISTIC_URL`, `BQ_DATA_DESC_URL`, `BQ_DATA_NO_PAGE` | Internal BQ/statistics APIs |
| **OCR** | `OCR_URL` | External OCR service |
| **Auth** | `TOKEN` | JWT for enterprise API calls |

Token-limit caveat:

- some backend paths also hardcode request-time `max_tokens` values in Python
- example: [`src/rag/services/qa.py`](/home/z/projects/rag/src/rag/services/qa.py:493) used `max_tokens=4080` in `get_question_classification_from_question(...)`
- on 2026-08-26 this caused:
  - `400 BadRequestError`
  - `max_tokens=4080 cannot be greater than max_model_len=max_total_tokens=2048`
- changing only `MAX_TOKENS` / `MAX_NEW_TOKENS` in config may not be enough if the active code path uses a larger hardcoded request limit

Note: `embedding_api` hostname works **inside the Docker network** between containers. From the host, use `localhost:12356`.

---

### `app_config_dev.yaml` — development overrides

Alternative config with LAN IPs and a different Milvus collection (`bqxxzx_test`). **Not loaded by default** — the loader in `__init__.py` always reads `app_config_pro.yaml`. To use dev config, change the loader or symlink.

---

### `prompt_config.yaml`

LLM prompt templates for agents and RAG scenarios. Loaded at import as `prompt_config`.

| Key (examples) | Purpose |
|----------------|---------|
| `intent_prompt` | Classify user intent (database / document / report / other) |
| `db_agent_intent_prompt` | Database-specific intent classification |
| `second_system_template_` | Answer formatting with citation markers `[1][2]` |
| (many more) | Scenario-specific system and user prompts |

Edit when changing **agent behavior or answer style**, not for infrastructure (URLs, Milvus, etc.).

---

### `prompt_config_bk.yaml`

Backup copy of `prompt_config.yaml`. **Not loaded automatically.** Safe to delete if no longer needed (see [10-cleanup-recommendations.md](./10-cleanup-recommendations.md)).

---

## API / agent tool definitions

### `api_config.json`

Schema and metadata for external “tool” APIs the RAG agent can call.

Each API entry (e.g. `project_api`) includes:

- `info` — description, URL, author, create time
- `fields` — searchable parameters (`project_source`, `charge_org`, `project_type`, etc.) with types, examples, and filter operators

**Used by:** `rag/services/api_manage.py`, `rag/utils/utils.py`

**Editable at runtime** via `/api_manage/*` REST endpoints.

---

### `api_data.json`

Lookup and alias data for API tool fields. Maps user phrases to canonical values.

Examples:

- `"海军"` → `"海军装备部"`
- `"在研"` → `"在研"`
- `"型号"` → `"型号研制"`

**Used by:** RAG agents when resolving natural-language queries to API filter values.

**Backups (not loaded):** `api_data_back.json`, `api_data_bk2.json`

---

### `modules.json` / `moudle.json`

Report-generation module definitions:

- Module name, Python class, method
- API query parameters (`viewKey`, `page`, `query`, etc.)
- LLM prompts for report sections and chart generation

**Used by:** report/reflection test code (`RelectTest.py`, `reflectAndDoc/test.py`). Not part of the main config loader.

---

### `test.json`

Similar module/prompt definitions for testing report sections (风险部分, 进展部分, 拖期部分). Test/dev artifact.

---

## Redis

### `src/utils/redis/redis_config.yaml`

```yaml
redis_config:
  host: "192.168.14.76"
  port: 36379
  database: 13
```

**Used by:** `RedisClient` in `src/utils/redis/redis_client.py`, initialized in `src/utils/redis/__init__.py`.

Optional — referenced when Celery or caching is enabled. There is **no Redis service** in `docker-compose.yaml`; `CELERY_BROKER=redis` in `.env` will fail unless Redis is running separately.

---

## Code-level defaults (not files)

### `src/document_fragment/document/layout/config.py`

Pydantic `LayoutConfig` model with defaults for PDF layout parsing:

| Setting | Default | Purpose |
|---------|---------|---------|
| `char2word_x_tolerance_rate` | 0.15 | Horizontal tolerance when grouping chars into words |
| `char2word_y_tolerance` | 1.2 | Vertical tolerance for char→word |
| `word2line_y_overlap_rate` | 0.5 | Overlap threshold for word→line |
| `line2block_y_gap_rate` | 0.6 | Gap threshold for line→block |
| `line2block_h_diff_rate` | 0.5 | Height difference for block grouping |
| `line2block_x_align_rate` | 0.5 | Horizontal alignment for blocks |

Defaults live in code; no YAML file. Override by instantiating `LayoutConfig` with custom values.

---

### User configs (database, not a static file)

Per-user JSON templates are stored in SQLite via the `/user_config_manage/*` API:

- `GET /user_config_manage/list` — list configs for a user
- `POST /user_config_manage/create` — create template
- `POST /user_config_manage/update` — update template

Managed by `user_config_manage.py`, `user_config.py`, `user_config.py` (mapper).

---

## ML model configs (under `models/`)

These are **HuggingFace / Paddle model artifacts**, not application deployment configuration. You normally only set **paths** in `.env`; do not edit these unless replacing the model.

| Path | Purpose |
|------|---------|
| `models/text2vec-base-multilingual/config.json` | Embedding model architecture |
| `models/text2vec-base-multilingual/tokenizer_config.json` | Tokenizer settings |
| `models/text2vec-base-multilingual/sentence_bert_config.json` | Sentence-BERT pooling |
| `models/reranker/config.json` | Reranker model architecture |
| `models/reranker/tokenizer_config.json` | Reranker tokenizer |
| `models/table_detection/config.json` | Table detection (Paddle) |
| `models/table_detection/preprocessor_config.json` | Detection preprocessing |
| `models/table_recognition/config.json` | Table OCR/recognition |
| `models/table_recognition/preprocessor_config.json` | Recognition preprocessing |

See [17-text2vec-embedding-model.md](./17-text2vec-embedding-model.md) for embedding model details.

---

## Runtime data (not configuration)

These files use JSON but are **generated at runtime**, not hand-edited config:

| Path | Purpose |
|------|---------|
| `src/api/static/fragment/*.json` | Parsed document fragment cache |
| `src/rag/static/log/task_status.json` | Background task status |
| `src/api/static/logs/libraries_info.json` | Library metadata cache |

---

## Quick reference: what to edit when

| Goal | Edit |
|------|------|
| Fix Milvus connection in containers | `.env` **and** `app_config_pro.yaml` |
| Change LLM endpoint | `.env` (qa/embedding APIs) **and** `app_config_pro.yaml` |
| Change embedding/rerank URLs from RAG service | `app_config_pro.yaml` (`EMBEDDING_URL`, `RERANK_URL`) |
| Switch CPU/GPU for table models | `.env` (`DET_MODEL_DEVICE`, `REG_MODEL_DEVICE`) |
| Change embedding model path | `.env` (`EMBEDDING_MODEL_PATH`) |
| Tune agent prompts / intent classification | `prompt_config.yaml` |
| Add or modify database query tools | `api_config.json` + `api_data.json` (or via `/api_manage` API) |
| Milvus etcd / storage tuning | `embedEtcd.yaml`, `user.yaml` |
| Start or stop Milvus | `standalone_embed.sh` |
| Redis connection | `src/utils/redis/redis_config.yaml` |
| PDF layout parsing tuning | `layout/config.py` (code) |

---

## Config checklist for new deployment

- [ ] Milvus URI points to running Milvus (`host.docker.internal:19530` on Windows Docker, or server IP)
- [ ] LLM `API_BASE_URL` / `API_BASE` reachable from inside containers
- [ ] `TOKENIZE_URL` reachable (if used)
- [ ] `EMBEDDING_URL` / `RERANK_URL` use Docker service name `embedding_api:5006` when all services share the same compose network
- [ ] Replace hardcoded `192.168.x.x` addresses with your environment
- [ ] Rotate exposed tokens and passwords in yaml and `.env`
- [ ] Restart affected containers after changes: `docker compose restart`

---

## Environment-specific notes

| Environment | MILVUS_URI | LLM URL |
|-------------|------------|---------|
| Windows Docker Desktop | `http://host.docker.internal:19530` | `http://host.docker.internal:PORT` or LAN IP |
| Linux same host | `http://172.17.0.1:19530` or host IP | host IP |
| Remote VM | server IP or `localhost` | internal network LLM |

---

## File tree (config files only)

```
setup/
├── Dockerfile
├── embedEtcd.yaml              # Milvus etcd
├── user.yaml                   # Milvus overrides
├── standalone_embed.sh         # Milvus start script
└── document_fragment/
    ├── .env                    # Docker Compose env
    ├── docker-compose.yaml     # Three FastAPI services
    └── src/
        ├── rag/configs/
        │   ├── __init__.py     # Config loader
        │   ├── app_config_pro.yaml   # ★ Primary runtime config
        │   ├── app_config_dev.yaml   # Dev overrides (not loaded)
        │   ├── prompt_config.yaml    # LLM prompts
        │   ├── prompt_config_bk.yaml # Backup
        │   ├── api_config.json       # Tool API schemas
        │   ├── api_data.json         # Tool API aliases
        │   ├── api_data_back.json    # Backup
        │   ├── api_data_bk2.json     # Backup
        │   └── test.json             # Test modules
        ├── rag/services/
        │   ├── modules.json          # Report modules
        │   └── moudle.json           # Typo duplicate
        └── utils/redis/
            └── redis_config.yaml     # Redis connection
```

---

## Related documents

| Document | Topic |
|----------|-------|
| [05-configuration.md](./05-configuration.md) | Deployment checklist, test commands |
| [07-docker.md](./07-docker.md) | Images, compose, tar load |
| [16-milvus-code-locations.md](./16-milvus-code-locations.md) | Where Milvus config is used in code |
| [17-text2vec-embedding-model.md](./17-text2vec-embedding-model.md) | Embedding model paths and runtime |
| [08-known-limitations.md](./08-known-limitations.md) | Dual-config pitfalls, blocked features |
