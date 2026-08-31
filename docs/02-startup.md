# 02 — Startup & Deployment Guide

## Prerequisites

- **Docker Desktop** (Windows) or **Docker Engine** (Linux)
- **WSL2** enabled (Windows)
- Sufficient disk space (~35 GB for images + models)
- Image tar files (or registry access):
  - `document_fragment-mupdf-3.tar` (~12.5 GB compressed)
  - `milvus.tar` (~1.7 GB)

Optional for full functionality:

- Reachable **LLM API** (OpenAI-compatible)
- Network access to URLs in config files

## Step 1 — Load Docker images (one-time)

```powershell
docker load -i D:\setup\setup\document_fragment-mupdf-3.tar
docker load -i D:\setup\setup\milvus.tar
```

Verify:

```powershell
docker images document_fragment
docker images milvusdb/milvus
```

Expected: `document_fragment:mupdf-3` and `milvusdb/milvus:v2.4.4`.

> `docker load` has **no progress bar**. A 12 GB tar may take 10–20 minutes.

## Step 2 — Start Milvus

Milvus is **not** in `docker-compose.yaml`. Start it separately:

**Windows (PowerShell):**

```powershell
cd D:\setup\setup
docker run -d `
  --name milvus-standalone `
  --security-opt seccomp:unconfined `
  -p 19530:19530 -p 9091:9091 `
  -v "${PWD}/volumes/milvus:/var/lib/milvus" `
  milvusdb/milvus:v2.4.4 `
  milvus run standalone
```

Important:

- Keep the Milvus data mount stable across restarts: `D:\setup\setup\volumes\milvus -> /var/lib/milvus`.
- Do not recreate `milvus-standalone` against a fresh Docker volume if you want to keep existing collections.
- A running Milvus container with an empty collection list usually means Milvus was started on the wrong storage, not that the app code is broken.

Real incident on July 16, 2026:

- Symptom: `qa_api` and retrieval APIs failed with `collection not found[collection=fragments]` even though `milvus-standalone` was up.
- Cause: after a restart workflow, Milvus had been recreated on a new empty Docker volume (`milvus-data`) instead of the original bind mount `D:\setup\setup\volumes\milvus`.
- Fix: recreate `milvus-standalone` with the original bind mount so `/var/lib/milvus` points back to `D:\setup\setup\volumes\milvus`.

**Linux:**

```bash
cd /path/to/setup
bash standalone_embed.sh start
```

Verify:

```powershell
docker ps --filter name=milvus
```

Quick post-start check:

```powershell
docker exec -it document_fragment-qa_api-1 python
```

```python
from pymilvus import MilvusClient
c = MilvusClient('http://host.docker.internal:19530')
print(c.list_collections())
```

Expected for an already indexed environment:

```python
['fragments']
```

If it prints `[]` but SQLite still has files/packages, check the Milvus mount before debugging APIs.

## Step 3 — Configure environment

Edit `document_fragment/.env` for your network. Minimum for local Docker on Windows:

```env
MILVUS_URI=http://host.docker.internal:19530
MILVUS_URL=http://host.docker.internal:19530
```

Also update `src/rag/configs/app_config_pro.yaml` — many values are read from YAML, not only `.env`. See [05-configuration.md](./05-configuration.md).

## Step 4 — Start the APIs

```powershell
cd D:\setup\setup\document_fragment
docker compose up -d
```

Verify:

```powershell
docker compose ps
```

If embedding/rerank runs on `192.168.1.100`, make sure `document_fragment/.env` and `src/rag/configs/app_config_pro.yaml` point `EMBEDDING_URL` and `RERANK_URL` to `http://192.168.1.100:5006/...` before starting the app services.

## Step 5 — Smoke test

Open in browser:

| URL | Expected |
|-----|----------|
| http://localhost:12355/docs | Document API Swagger |
| http://localhost:12356/docs | Embedding API Swagger |
| http://localhost:12357/docs | RAG API Swagger |

Quick API test:

```powershell
# Embedding
Invoke-RestMethod -Uri "http://localhost:12356/embeddings" `
  -Method POST -Body '{"input":"hello"}' -ContentType "application/json"

# Agent list
Invoke-RestMethod -Uri "http://localhost:12357/agent/list"
```

## Stop services

```powershell
cd D:\setup\setup\document_fragment
docker compose down

docker stop milvus-standalone
```

## Restart after reboot

1. Start **Docker Desktop**
2. `docker start milvus-standalone`
3. `cd document_fragment && docker compose up -d`

## Deploy to CentOS / Linux server

Same steps; replace `host.docker.internal` with server IP or `localhost` as appropriate.

Copy to server:

- `document_fragment/` folder
- `volumes/milvus/` (optional, for existing data)
- Both `.tar` image files

## Common startup failures

| Symptom | Cause | Fix |
|---------|-------|-----|
| `image not found` | Tar not loaded | Run `docker load` |
| Milvus connection error | Milvus not running or wrong URI | Start Milvus; fix `app_config_pro.yaml` |
| LLM timeout | `192.168.x.x` unreachable | Update LLM URLs in config |
| Port in use | Another service on 12355–12357 | Change ports in compose |

## What starts what (file map)

| Action | File / command |
|--------|----------------|
| 3 API containers | `docker-compose.yaml` + `docker compose up -d` |
| Milvus container | Manual `docker run` or `standalone_embed.sh` |
| Env vars for compose | `.env` |
| App runtime config | `src/rag/configs/app_config_pro.yaml` |

See [07-docker.md](./07-docker.md) for image vs container details.
