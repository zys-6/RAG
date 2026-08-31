# 17 — Text2Vec Embedding Model

Reference for the **vector embedding model** used by this project: what it is, where files live, how it runs, and how other services call it.

For Milvus storage and search, see [16-milvus-code-locations.md](./16-milvus-code-locations.md). For Docker service layout, see [07-docker.md](./07-docker.md).

---

## Summary

| Item | Value |
|------|--------|
| **Local folder name** | `text2vec-base-multilingual` |
| **Underlying model** | `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2` |
| **Library** | `text2vec.SentenceModel` |
| **Vector dimension** | **384** |
| **Max sequence length** | 256 tokens |
| **Parameters** | ~117M |
| **Service** | Embedding API (`embedding_api` container) |
| **Host port** | **12356** (container internal: **5006**) |
| **Swagger** | http://localhost:12356/docs |

The model turns text into 384-dimensional float vectors for Milvus similarity search (document indexing and RAG query retrieval).

---

## File locations

### Model weights (on disk)

```
document_fragment/models/text2vec-base-multilingual/
├── config.json              ← base: paraphrase-multilingual-MiniLM-L12-v2
├── modules.json
├── 1_Pooling/config.json    ← word_embedding_dimension: 384
├── tokenizer.json
└── ...
```

| Host path | Inside Docker (`embedding_api`) |
|-----------|----------------------------------|
| `./models/text2vec-base-multilingual/` | `/models/text2vec-base-multilingual/` |

Mounted via `docker-compose.yaml`: `./models:/models`

### Application code

| Path | Role |
|------|------|
| `src/embedding/api.py` | **Only file that imports text2vec** — loads model, serves `/embeddings` |
| `src/embedding/static/` | Swagger UI assets |
| `src/api/services/utils.py` | `get_vectors()` — HTTP client for indexing into Milvus |
| `src/rag/services/qa.py` | `get_vectors()` — HTTP client for RAG search |
| `src/rag/services/qa_bak.py` | Backup copy of QA service (same pattern) |
| `src/rag/services.py` | Legacy/alternate QA module (same pattern) |

### Configuration

| File | Key | Value |
|------|-----|-------|
| `.env` | `EMBEDDING_MODEL_PATH` | `/models/text2vec-base-multilingual` |
| `src/rag/configs/app_config_pro.yaml` | `EMBEDDING_URL` | `http://192.168.1.100:5006/embeddings` |
| `src/rag/configs/app_config_pro.yaml` | `RERANK_URL` | `http://192.168.1.100:5006/rerank` |
| `src/rag/configs/app_config_dev.yaml` | `EMBEDDING_URL` | `http://192.168.14.78:12356/embeddings` (host example) |

---

## How it runs

### Docker-only inference

**text2vec runs only inside the `embedding_api` container.** No other service imports the library. If the service moves to a separate GPU host, the app should call it by that host's IP and port instead of the Docker service name.

```yaml
# docker-compose.yaml
embedding_api:
  image: document_fragment:mupdf-3
  ports:
    - 12356:5006
  volumes:
    - ./src:/src
    - ./models:/models
  environment:
    - EMBEDDING_MODEL_PATH=${EMBEDDING_MODEL_PATH}
    - RERANKER_MODEL_PATH=${RERANKER_MODEL_PATH}
  working_dir: /src
  command: uvicorn embedding.api:app --host 0.0.0.0 --port 5006
```

Container name (typical): `document_fragment-embedding_api-1`

### Load and encode (in container)

```python
# src/embedding/api.py
embedding_model = text2vec.SentenceModel(
    os.environ.get("EMBEDDING_MODEL_PATH", "/models/text2vec-base-multilingual")
)
# POST /embeddings → embedding_model.encode(...)
```

The `text2vec` Python package is installed in the Docker image (`document_fragment:mupdf-3`), not on the host.

### Architecture

```
Host filesystem                         Docker network
─────────────────                       ─────────────────────────────────────

models/text2vec-base-multilingual/  ──► embedding_api :5006
  (weights)                                 └─ text2vec.SentenceModel.encode()
                                            └─ POST /embeddings, POST /rerank

src/embedding/api.py (mounted)        ──►   (same container)

src/api/services/utils.py           ──► document_fragment_api ──HTTP──► embedding_api
  get_vectors()                             (index documents → Milvus)

src/rag/services/qa.py              ──► qa_api ──HTTP──► embedding_api
  get_vectors()                             (embed user question → Milvus search)
```

| Caller | URL inside Docker | URL from host |
|--------|-------------------|---------------|
| Document API, QA API | `http://192.168.1.100:5006/embeddings` | `http://192.168.1.100:5006/embeddings` |

If the GPU-hosted `embedding_api` is stopped, indexing and vector search fail — callers have no local fallback model.

---

## CPU vs GPU

The embedding service does **not** hardcode CPU.

`text2vec.SentenceModel` auto-selects device when no `device` argument is passed:

```
cuda  → if torch.cuda.is_available()
mps   → else if Apple MPS available
cpu   → otherwise
```

| Factor | This project |
|--------|--------------|
| Explicit `EMBEDDING_DEVICE` in `.env` | **No** (unlike `DET_MODEL_DEVICE=cpu` for table models) |
| GPU in `docker-compose.yaml` | **No** (`nvidia` runtime / device reservation not configured) |
| PyTorch in image | CUDA-enabled (`2.3.1+cu121`) |
| Typical runtime | **CPU** — container has no GPU → `cuda.is_available()` is false |

To use GPU: pass NVIDIA GPU into the container (Container Toolkit + compose device config). The embedding model would pick up CUDA automatically; the **reranker** in the same file would need explicit `.to("cuda")` on model and inputs.

---

## API endpoints

| Method | Path | Body | Returns |
|--------|------|------|---------|
| POST | `/embeddings` | `{ "input": string \| string[] }` | OpenAI-style embedding vectors |
| POST | `/rerank` | `query` (str), `texts` (List[str]) | Relevance scores (uses separate reranker model) |

### Quick test (PowerShell, from host)

```powershell
Invoke-RestMethod -Uri "http://localhost:12356/embeddings" `
  -Method POST -ContentType "application/json" `
  -Body '{"input":"测试"}'
```

Expected: JSON with `data[0].embedding` — a list of **384** floats.

---

## Data flow in the RAG pipeline

### 1. Indexing (write path)

```
PDF/Word upload → parse fragments → get_vectors(chunk text)
  → POST embedding_api /embeddings
  → insert vector + metadata into Milvus collection `fragments`
```

Triggered by `@insert_fragments_into_milvus` in `src/api/services/utils.py` (used from `pdf.py`, `word.py`, `caj.py`).

Milvus collection dimension is inferred at create time:

```python
dimension=len(get_vectors(["测试"])[0])  # → 384
```

### 2. Search (read path)

```
User question → get_vectors(question)
  → POST embedding_api /embeddings
  → milvus_client.search() in src/rag/services/qa.py
  → top-k chunks → LLM context
```

Optional second stage: `/rerank` on the same Embedding API re-scores candidates (BGE reranker in `models/reranker/`).

---

## Related model: reranker (same service)

The Embedding API also loads a **cross-encoder reranker** — not the vector model, but hosted on the same port:

| Item | Value |
|------|--------|
| Path | `models/reranker/` |
| Model | BAAI/bge-reranker (see `models/reranker/README.md`) |
| Config | `RERANKER_MODEL_PATH=/models/reranker` in `.env` |
| Code | `src/embedding/api.py` — `POST /rerank` |

Embedding model = bi-encoder (vectors for Milvus). Reranker = cross-encoder (re-score top-k results).

---

## Model quality (Chinese RAG)

This setup uses a **lightweight multilingual** model, not a top-tier **Chinese retrieval** model.

| Aspect | Current model | Common upgrades |
|--------|---------------|-----------------|
| Strength | Fast, small, 50+ languages, CPU-friendly | — |
| Chinese retrieval (C-MTEB) | Mid-tier vs BGE family | `BAAI/bge-large-zh-v1.5`, `BAAI/bge-m3` |
| Dimensions | 384 | 512–1024 |
| Context | 256 tokens | 512–8192 (BGE-M3) |

Swapping models requires: new weights, update `EMBEDDING_MODEL_PATH`, **recreate Milvus collection** (dimension change), **re-index all documents**.

---

## Troubleshooting

| Symptom | Check |
|---------|--------|
| Indexing/search fails on embed step | `docker ps` — is `document_fragment-embedding_api-1` running? |
| Connection refused from QA/Document API | `EMBEDDING_URL` must point to the running model server, either `embedding_api:5006` on the same Docker network or the GPU host IP |
| Wrong vector dimension / search errors | Collection created with different model; drop `fragments` and re-index |
| Slow bulk indexing | Expected on CPU; consider GPU passthrough or batching |
| `/embeddings` works, Milvus fails | Milvus URI / collection — see [16-milvus-code-locations.md](./16-milvus-code-locations.md) |

---

## See also

| Doc | Topic |
|-----|--------|
| [05-configuration.md](./05-configuration.md) | `.env` and YAML keys |
| [07-docker.md](./07-docker.md) | Compose services and ports |
| [14-milvus-introduction.md](./14-milvus-introduction.md) | Why vectors go into Milvus |
| [16-milvus-code-locations.md](./16-milvus-code-locations.md) | Code that reads/writes Milvus |
| [API-Reference.md](./API-Reference.md) | Embedding API HTTP reference |
