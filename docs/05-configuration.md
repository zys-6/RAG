# 05 — Configuration Guide

## Two config systems (important)

This project reads settings from **two places**. Both may need updating when deploying.

| Source | Used by | Purpose |
|--------|---------|---------|
| `document_fragment/.env` | Docker Compose → container env vars | Model paths, Milvus URI for compose |
| `src/rag/configs/app_config_pro.yaml` | Python code at import time | LLM URLs, FTP, Jira, most RAG settings |

**Trap:** Changing only `.env` may not fix RAG/Milvus issues if code reads `app_config_pro.yaml` directly.

Active config loader:

```python
# src/rag/configs/__init__.py
app_config = read_app_config()  # loads app_config_pro.yaml
```

---

## `.env` (Docker Compose)

Location: `document_fragment/.env`

| Variable | Example | Description |
|----------|---------|-------------|
| `DET_MODEL_PATH` | `/models/table_detection` | Table detection model |
| `REG_MODEL_PATH` | `/models/table_recognition` | Table recognition model |
| `DET_MODEL_DEVICE` | `cpu` | Device for detection |
| `REG_MODEL_DEVICE` | `cpu` | Device for recognition |
| `EMBEDDING_MODEL_PATH` | `/models/text2vec-base-multilingual` | Embedding model |
| `RERANKER_MODEL_PATH` | `/models/reranker` | Reranker model |
| `COLLECTION_NAME` | `fragments` | Milvus collection |
| `MILVUS_URI` | `http://host.docker.internal:19530` | Milvus for Document/RAG API |
| `MILVUS_URL` | same | Milvus for Embedding API (compose uses this name) |
| `TOKENIZE_URL` | LLM tokenize endpoint | Token counting |
| `API_BASE` | `http://host:7819/v1` | LLM OpenAI-compatible base |
| `API_KEY` | your key | LLM API key |
| `MODEL_NAME` | `zhuque3` | LLM model name |
| `CELERY_BROKER` | `redis` | Optional async tasks |

**Windows Docker tip:** Use `host.docker.internal` to reach services on the host (for example Milvus on port 19530).

---

## `app_config_pro.yaml` (application runtime)

Location: `src/rag/configs/app_config_pro.yaml`

Key sections:

### LLM

```yaml
MODEL_NAME: "Zhuque-72b"
API_KEY: "CIPS_API_KEY"
API_BASE_URL: "http://host:7819/v1/"

MODEL_NAME2: 'deepseek-r1-32b:latest'
API_KEY2: 'ollama'
API_BASE_URL2: 'http://host:11434/v1/'
```

### Milvus & embedding

```yaml
MILVUS_URI: 'http://host.docker.internal:19530'
MILVUS_COLLECTION: 'fragments'
EMBEDDING_URL: "http://192.168.1.100:5006/embeddings"
RERANK_URL: "http://192.168.1.100:5006/rerank"
```

Note: `embedding_api:5006` works only when the model service runs in the same Docker network. For a separate GPU server, point both URLs at that server's IP and port.

### Service cross-links

```yaml
API_URL: 'http://host.docker.internal:12355'   # Document API
RAG_URL: 'http://host.docker.internal:12357'   # RAG API
TOKENIZE_URL: "http://host:7819/tokenize"
```

### Enterprise integrations (original deployment)

```yaml
FTP_HOST, FTP_PORT, FTP_USERNAME, FTP_PASSWORD
JIRA_URL, JIRA_USER, JIRA_TOKEN, JIRA_BOARD
MAPPING_URL, STATISTIC_URL, BQ_DATA_DESC_URL
OCR_URL, ...
```

Update or disable these for your environment.

---

## `prompt_config.yaml`

LLM prompt templates for different agent types and RAG scenarios. Edit when changing agent behavior, not for infrastructure.

---

## `app_config_dev.yaml`

Development overrides. **Not loaded by default** — production loader uses `app_config_pro.yaml` only.

---

## Config checklist for new deployment

- [ ] Milvus URI points to running Milvus (`host.docker.internal:19530` or server IP)
- [ ] LLM `API_BASE_URL` reachable from inside container
- [ ] `TOKENIZE_URL` reachable (if used)
- [ ] `EMBEDDING_URL` / `RERANK_URL` point to the GPU model server when embedding/rerank run on a separate host
- [ ] Remove or replace hardcoded `192.168.x.x` addresses
- [ ] Rotate exposed tokens in yaml (security)

---

## Test config from container

```powershell
# LLM reachable?
docker exec document_fragment-qa_api-1 python -c "
import requests
r = requests.get('YOUR_LLM_URL/v1/models', timeout=5)
print(r.status_code)
"

# Milvus reachable?
docker exec document_fragment-qa_api-1 python -c "
from pymilvus import MilvusClient
c = MilvusClient('http://host.docker.internal:19530')
print(c.list_collections())
"
```

---

## Environment-specific notes

| Environment | MILVUS_URI | LLM URL |
|-------------|------------|---------|
| Windows Docker Desktop | `http://host.docker.internal:19530` | `http://host.docker.internal:PORT` or LAN IP |
| Linux same host | `http://172.17.0.1:19530` or host IP | host IP |
| CentOS destination VM | server IP or `localhost` | internal network LLM |

After config changes, restart affected containers:

```powershell
cd document_fragment
docker compose restart
```
