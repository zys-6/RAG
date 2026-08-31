# 07 — Docker: Images, Containers & Deployment

## Concepts

| Term | What it is | This project |
|------|------------|--------------|
| **Image** | Read-only template (filesystem + libs) | `document_fragment:mupdf-3`, `milvusdb/milvus:v2.4.4` |
| **Container** | Running instance of an image | 4 containers total |
| **Volume** | Host folder mounted into container | `./src`, `./models`, `volumes/milvus` |
| **Compose** | Multi-container orchestration | `docker-compose.yaml` (3 services) |

```
tar file  ──docker load──►  image  ──docker run/compose──►  container
```

---

## Images for this project

| Image | Size (approx) | Source |
|-------|---------------|--------|
| `document_fragment:mupdf-3` | ~27 GB | `document_fragment-mupdf-3.tar` |
| `milvusdb/milvus:v2.4.4` | ~3.5 GB | `milvus.tar` |

Load once:

```powershell
docker load -i document_fragment-mupdf-3.tar
docker load -i milvus.tar
```

Export (share to another machine):

```powershell
docker save document_fragment:mupdf-3 -o document_fragment-mupdf-3.tar
docker save milvusdb/milvus:v2.4.4 -o milvus.tar
```

**"Copy image"** means copy the `.tar` file and `docker load` on the target — not copy containers or source code.

---

## Containers (4 total)

| Container | Image | Port | Start method |
|-----------|-------|------|--------------|
| `document_fragment-document_fragment_api-1` | document_fragment:mupdf-3 | 12355 | `docker compose up` |
| `document_fragment-embedding_api-1` | document_fragment:mupdf-3 | 12356 | `docker compose up` |
| `document_fragment-qa_api-1` | document_fragment:mupdf-3 | 12357 | `docker compose up` |
| `milvus-standalone` | milvusdb/milvus:v2.4.4 | 19530 | Manual `docker run` |

**One image → three containers** for the app (different `command` in compose).

---

## docker-compose.yaml breakdown

All three app services share:

```yaml
image: document_fragment:mupdf-3
volumes:
  - ./src:/src          # live code from host
working_dir: /src
```

Differences:

| Service | Extra volumes | Command |
|---------|---------------|---------|
| document_fragment_api | `./models`, paddleocr | `uvicorn api.main:app --port 5005` |
| embedding_api | `./models` | `uvicorn embedding.api:app --port 5006` |
| qa_api | (src only) | `uvicorn rag.api:app --port 5007` |

Environment from `.env` — see [05-configuration.md](./05-configuration.md).

### Important distinction: base app image vs optional GPU embedding image

`document_fragment-mupdf-3.tar` loads the base image tag:

```text
document_fragment:mupdf-3
```

That one image can run all three app services because Compose gives each service a different command:

- `document_fragment_api`
- `embedding_api`
- `qa_api`

So yes, the base app image already contains the runtime needed for `embedding_api`.

The optional GPU embedding path is different. `docker-compose.gpu-host.yaml` does **not** use `document_fragment:mupdf-3` directly. It starts:

```text
embedding_api:cuda12.1
```

That CUDA image is a thin wrapper built `FROM document_fragment:mupdf-3`, so it still reuses the same application/runtime base, but under a different image tag and with GPU intent.

Operational meaning:

- `document_fragment:mupdf-3` = shared base app image for the default Compose stack
- `embedding_api:cuda12.1` = optional GPU-specialized embedding image
- `docker-compose.gpu-host.yaml` only covers the embedding service, not `document_fragment_api` or `qa_api`

### Which image/compose combination is enough?

#### A. Full default local stack on one host

Needed:

- `document_fragment:mupdf-3`
- `milvusdb/milvus:v2.4.4`

Start:

```bash
docker compose up -d embedding_api document_fragment_api qa_api
```

#### B. App host without local embedding, using a remote GPU embedding host

Needed on the app host:

- `document_fragment:mupdf-3`
- `milvusdb/milvus:v2.4.4`

Do **not** start the local CPU `embedding_api` if callers are pointed to the remote GPU endpoint.

Typical start on the app host:

```bash
docker compose up -d document_fragment_api qa_api
```

And point config to the remote embedding service:

```text
EMBEDDING_URL=http://<gpu-host>:15006/embeddings
RERANK_URL=http://<gpu-host>:15006/rerank
```

#### C. GPU host that serves only embedding/rerank

Needed on the GPU host:

- `embedding_api:cuda12.1`

Start:

```bash
docker compose -f docker-compose.gpu-host.yaml up -d embedding_api
```

This is enough only for the embedding/rerank service. It is **not** enough for the default three-service application Compose stack.

---

## Volume mounts (what comes from host)

| Host path | Container path | Content |
|-----------|------------------|---------|
| `./src` | `/src` | All Python code, sqlite.db |
| `./models` | `/models` | ML weights |
| `./models/.paddleocr` | `/root/.paddleocr` | OCR models |
| `../volumes/milvus` | `/var/lib/milvus` | Milvus data (Milvus container only) |

**Implication:** Editing code under `src/` on host affects containers immediately (may need restart for import-time config). For shipping changes to production, see [25-deploy-code-updates.md](./25-deploy-code-updates.md).

---

## Image vs source code

| In image (baked in) | From host mount (overrides) |
|---------------------|----------------------------|
| Python, system libs, pymupdf, torch, etc. | `src/` Python code |
| Default code copy at build time | `models/` weights |
| phantomjs binary | `sqlite.db`, configs |

You can run without rebuilding the image if tar is loaded and `src/` + `models/` are present.

---

## Milvus container (manual start)

Not in compose — typical command:

```powershell
docker run -d `
  --name milvus-standalone `
  --security-opt seccomp:unconfined `
  -p 19530:19530 -p 9091:9091 `
  -v "D:/setup/setup/volumes/milvus:/var/lib/milvus" `
  milvusdb/milvus:v2.4.4 `
  milvus run standalone
```

Linux alternative: `bash standalone_embed.sh start`

---

## Common Docker commands

```powershell
# Status
docker compose ps
docker ps --filter name=milvus

# Logs
docker compose logs -f qa_api
docker logs milvus-standalone

# Restart one service
docker compose restart embedding_api

# Stop project
docker compose down
docker stop milvus-standalone

# Start again
docker start milvus-standalone
docker compose up -d
```

---

## Windows / WSL notes

- Docker Desktop runs Linux containers via WSL2
- `host.docker.internal` lets containers reach host services (Milvus, LLM on host)
- No need to install SQLite or Python on Windows — everything runs in containers
- GPU: default config uses CPU (`DET_MODEL_DEVICE=cpu`)

---

## Deploy to another server checklist

1. Copy `document_fragment/` folder + `volumes/milvus/` (optional)
2. Copy both `.tar` image files
3. `docker load` both images
4. Start Milvus container
5. Update configs for new network
6. `docker compose up -d`

Source code alone is **not enough** without the Docker images.
