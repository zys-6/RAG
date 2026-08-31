# 21 — Software Recovery (Git Pull + Extras)

Recover **application code and running APIs** on a new machine. This guide does **not** restore old knowledge-base data (Milvus vectors, SQLite history) unless you also restore those backups separately.

**Related:** [02-startup.md](./02-startup.md) (daily startup), [07-docker.md](./07-docker.md) (images), [17-text2vec-embedding-model.md](./17-text2vec-embedding-model.md) (models).

---

## What Git gives you vs what you must bring

| Source | You get |
|--------|---------|
| **Gitee `git pull`** | Python source, `docker-compose.yaml`, docs, config templates (`.env.example`, `app_config_pro.yaml.example`), non-secret JSON/YAML |
| **Extras (offline copy)** | Docker `.tar` images, `models/` weights, real `.env` + `app_config_pro.yaml` |
| **Optional data backup** | `volumes/milvus/`, `sqlite.db` — only if you want old indexed content back |

Without extras, `docker compose up` fails with **image not found** or **model path missing**.

---

## Fast Milvus recovery note

If all of these are true at the same time:

- `milvus-standalone` is running
- `docker exec document_fragment-qa_api-1 python` can connect to Milvus
- `MilvusClient('http://host.docker.internal:19530').list_collections()` returns `[]`
- SQLite still has `File` rows / packages

then the most likely problem is **wrong Milvus storage attachment**, not broken QA code.

Real incident on July 16, 2026:

- The active Milvus container had been recreated on a new empty Docker volume.
- The original persisted data still existed on disk at `D:\setup\setup\volumes\milvus`.
- Recreating `milvus-standalone` with `D:\setup\setup\volumes\milvus:/var/lib/milvus` restored collection `fragments`.

Recovery pattern:

1. Inspect the current Milvus mounts:

```powershell
docker inspect milvus-standalone --format "{{json .Mounts}}"
```

2. If `/var/lib/milvus` is not mounted from your expected persistent path, stop and recreate Milvus with the correct bind mount.

3. Re-check collections:

```powershell
docker exec -it document_fragment-qa_api-1 python
```

```python
from pymilvus import MilvusClient
c = MilvusClient('http://host.docker.internal:19530')
print(c.list_collections())
```

Expected after recovery:

```python
['fragments']
```

---

## Checklist before you start

- [ ] Docker Desktop (Windows) or Docker Engine (Linux), WSL2 on Windows
- [ ] ~35 GB free disk (images + models)
- [ ] `document_fragment-mupdf-3.tar` (~12.5 GB)
- [ ] `milvus.tar` (~1.7 GB)
- [ ] `models/` folder copied from old machine **or** downloaded per [17-text2vec-embedding-model.md](./17-text2vec-embedding-model.md)
- [ ] Reachable LLM API (OpenAI-compatible) for Q&A features
- [ ] Saved copies of `.env` and `app_config_pro.yaml` (or willingness to fill templates)

---

## Recommended folder layout (new machine)

```text
D:\work\
├── rag\                          ← git clone (repo root)
│   ├── src\
│   ├── docker-compose.yaml
│   ├── models\                   ← you create & populate
│   ├── .env                      ← you create (not in Git)
│   └── src\rag\configs\
│       └── app_config_pro.yaml   ← you create (not in Git)
├── artifacts\
│   ├── document_fragment-mupdf-3.tar
│   └── milvus.tar
└── volumes\
    └── milvus\                   ← Milvus data (empty = fresh index)
```

Milvus mounts `volumes/milvus` from **outside** the app repo. Any path is fine; keep it stable across restarts.

---

## Step 1 — Clone code

```powershell
cd D:\work
git clone https://gitee.com/zys123321/rag.git
cd rag
```

---

## Step 2 — Load Docker images (one-time)

```powershell
docker load -i D:\work\artifacts\document_fragment-mupdf-3.tar
docker load -i D:\work\artifacts\milvus.tar
```

Verify:

```powershell
docker images document_fragment
docker images milvusdb/milvus
```

Expected tags: `document_fragment:mupdf-3`, `milvusdb/milvus:v2.4.4`.

> `docker load` has no progress bar; large tars may take 10–20 minutes.

---

## Step 3 — Install ML models

Create `models/` under the repo root and copy from your old machine, or download weights.

Minimum folders (paths match `.env.example`):

| Folder under `models/` | Used by |
|------------------------|---------|
| `text2vec-base-multilingual/` | Embedding API |
| `reranker/` | Embedding API `/rerank` |
| `table_detection/` | Document API (tables) |
| `table_recognition/` | Document API (tables) |

`.paddleocr/` is created automatically on first OCR use; optional to copy from old machine to save download time.

Quick check:

```powershell
dir D:\work\rag\models\text2vec-base-multilingual\config.json
dir D:\work\rag\models\reranker\config.json
```

---

## Step 4 — Start Milvus

Milvus is **not** in `docker-compose.yaml`. Start it before the three APIs.

```powershell
mkdir D:\work\volumes\milvus -Force

docker run -d `
  --name milvus-standalone `
  --security-opt seccomp:unconfined `
  -p 19530:19530 -p 9091:9091 `
  -v "D:/work/volumes/milvus:/var/lib/milvus" `
  milvusdb/milvus:v2.4.4 `
  milvus run standalone
```

Verify:

```powershell
docker ps --filter name=milvus
```

**Linux:** use `standalone_embed.sh` from your old `setup/` backup if you have it, or the same `docker run` command with Linux paths.

---

## Step 5 — Configure environment

### 5a. `.env` (Docker Compose)

**Option A — restore from backup** (easiest if URLs still valid):

```powershell
copy D:\backup\.env D:\work\rag\.env
```

**Option B — from template:**

```powershell
cd D:\work\rag
copy .env.example .env
notepad .env
```

Minimum for local Docker on Windows:

```env
MILVUS_URI=http://host.docker.internal:19530
MILVUS_URL=http://host.docker.internal:19530
API_BASE=http://YOUR_LLM_HOST:7819/v1
API_KEY=your-key
MODEL_NAME=your-model
```

### 5b. `app_config_pro.yaml` (RAG runtime)

Python loads this at import time — **both** `.env` and YAML must agree on Milvus and LLM URLs.

```powershell
copy src\rag\configs\app_config_pro.yaml.example src\rag\configs\app_config_pro.yaml
notepad src\rag\configs\app_config_pro.yaml
```

Set at least:

```yaml
MILVUS_URI: "http://host.docker.internal:19530"
EMBEDDING_URL: "http://embedding_api:5006/embeddings"
RERANK_URL: "http://embedding_api:5006/rerank"
API_BASE_URL: "http://YOUR_LLM_HOST:7819/v1/"
API_KEY: "your-key"
TOKEN: "your-jwt-if-needed"
```

See [05-configuration.md](./05-configuration.md) and [18-configuration-files-summary.md](./18-configuration-files-summary.md) for every key.

---

## Step 6 — Start the three APIs

```powershell
cd D:\work\rag
docker compose up -d
docker compose ps
```

Expected: three containers `document_fragment_api`, `embedding_api`, `qa_api`, all running.

---

## Step 7 — Smoke test

| URL | Expected |
|-----|----------|
| http://localhost:12355/docs | Document API Swagger |
| http://localhost:12356/docs | Embedding API Swagger |
| http://localhost:12357/docs | RAG API Swagger |

```powershell
Invoke-RestMethod -Uri "http://localhost:12356/embeddings" `
  -Method POST -Body '{"input":"hello"}' -ContentType "application/json"

Invoke-RestMethod -Uri "http://localhost:12357/agent/list"
```

Embedding should return a 384-dimensional vector. Agent list may be empty on a **fresh** SQLite database — that is normal.

---

## After reboot

```powershell
docker start milvus-standalone
cd D:\work\rag
docker compose up -d
```

---

## What is **not** restored by this guide

| Missing without extra backup | Effect |
|------------------------------|--------|
| `volumes/milvus/` (old data) | Empty vector index — re-upload and re-index documents |
| `src/rag/resources/sqlite.db` | No agents/packages/chat history — recreated on use |
| Uploaded files in `src/static/tmp/` | Gone (temp storage anyway) |

To restore **data** as well, copy those folders/files from the old machine **before** decommissioning it. See [06-database.md](./06-database.md).

---

## Copy bundle from old machine (quick reference)

From `D:\setup\setup` on the source PC, copy to USB/NAS:

```text
document_fragment-mupdf-3.tar
milvus.tar
document_fragment/models/          → rag/models/
document_fragment/.env             → rag/.env
document_fragment/src/rag/configs/app_config_pro.yaml
volumes/milvus/                    → optional (vector data)
document_fragment/src/rag/resources/sqlite.db   → optional (metadata)
```

Then on the new PC: clone repo → load tars → paste models and configs → start Milvus → `docker compose up -d`.

---

## Troubleshooting

| Symptom | Fix |
|---------|-----|
| `image not found: document_fragment:mupdf-3` | Run `docker load` on app tar |
| Milvus connection error | Start `milvus-standalone`; fix `MILVUS_URI` in **both** `.env` and `app_config_pro.yaml` |
| Embedding 500 / model error | Check `models/text2vec-base-multilingual/` exists and `.env` paths use `/models/...` |
| LLM timeout | Update `API_BASE` / `API_BASE_URL` to a reachable host |
| Port in use | Change host ports in `docker-compose.yaml` |

---

## Summary

```text
git clone  +  docker load (2 tars)  +  models/  +  .env & yaml  +  Milvus container
        →  three APIs running (fresh or restored data depending on backups)
```

Gitee stores **code**. Everything else is your **deployment artifact bundle**.
