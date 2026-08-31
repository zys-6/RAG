# 25 — Deploy Code Updates to Production (Docker)

How to ship **Python code changes** from your dev machine to the **production Docker containers** without rebuilding the image.

**Related:** [02-startup.md](./02-startup.md) (start/stop), [07-docker.md](./07-docker.md) (volume mounts), [23-dev-1gpu-prod-4gpu-migration.md](./23-dev-1gpu-prod-4gpu-migration.md) (dev vs prod validation), [21-software-recovery.md](./21-software-recovery.md) (first-time setup on a new server), [26-merge-prod-code-into-local.md](./26-merge-prod-code-into-local.md) (prod → local merge on dev machine).

---

## When you need this doc

Use this guide when you have **already changed code locally** and want those changes to run in production. This is the normal day-to-day deploy path — not first-time server setup (see doc 21) and not image rebuild (see [When to rebuild the image](#when-to-rebuild-the-image)).

---

## Core idea

Production uses the same pattern as dev:

| Layer | Where it lives | Updated how |
|-------|----------------|-------------|
| **Python code** | Host `./src` → mounted as `/src` in containers | Copy from USB/disk, or `git pull` if prod has network |
| **Runtime** | Docker image `document_fragment:mupdf-3` | Usually **unchanged** for code-only deploys |
| **Config** | Host `.env` + `app_config_pro.yaml` | Edit on prod; **do not overwrite** with dev values |
| **Data** | `sqlite.db`, `volumes/milvus/` | Not touched by code deploy |

Containers read live code from the host mount. After updating files on disk, **restart** the affected container(s). Python modules are loaded at startup — there is no hot reload.

---

## Two ways to get code onto prod

| Method | When to use |
|--------|-------------|
| **USB / disk copy** (below) | **CentOS on internal network** — no `git pull`, no internet |
| **Git pull** ([optional](#optional-git-pull-if-prod-has-network)) | Prod server can reach Gitee/GitHub |

For most internal-network deployments, only **`src/`** (and sometimes `docker-compose.yaml`) need to be copied. The Docker image on prod stays the same.

---

## Standard workflow — offline (USB / disk)

This matches a **Windows dev machine → USB → CentOS prod** path.

### 1. Dev — prepare files on USB

Copy **only what changed**. At minimum, copy the whole `src/` tree if unsure.

**Do not copy these onto prod** (keep prod’s existing files):

| Skip on USB | Why |
|-------------|-----|
| `.env` | Prod Milvus URI, API keys, model paths differ from dev |
| `src/rag/configs/app_config_pro.yaml` | Prod LLM / embedding / FTP URLs |
| `src/rag/resources/sqlite.db` | Prod knowledge-base metadata |
| `models/` | Large; only copy if you changed model weights |
| `eval/report.json` | Generated test output |

**Windows — copy changed code to USB:**

```powershell
# Example: USB is E:\
$usb = "E:\deploy\document_fragment"
New-Item -ItemType Directory -Force -Path "$usb\src" | Out-Null

# Option A — full src/ (safest, still small vs models/)
Copy-Item -Recurse -Force "D:\setup\setup\document_fragment\src\*" "$usb\src\"

# Option B — only files you changed (faster)
# Copy-Item -Force "D:\setup\setup\document_fragment\src\rag\services\qa.py" "$usb\src\rag\services\"

# Optional — if docker-compose.yaml changed
Copy-Item -Force "D:\setup\setup\document_fragment\docker-compose.yaml" "$usb\"
```

Keep a note of which service you changed (RAG → `qa_api`, etc.) for the restart step.

### 2. Prod — mount USB and copy into project

```bash
# Mount USB (path varies; often /media/usb or /mnt/usb)
ls /media/
# Example mount point:
USB=/media/usb/deploy/document_fragment
PROD=/path/to/document_fragment    # existing prod install

# Backup current src (quick rollback)
cp -a "$PROD/src" "$PROD/src.bak.$(date +%Y%m%d)"

# Copy code from USB — overwrites Python files only
cp -a "$USB/src/." "$PROD/src/"

# If you brought an updated compose file:
# cp -a "$USB/docker-compose.yaml" "$PROD/docker-compose.yaml"
```

**Verify you did not overwrite prod config:**

```bash
# These should still be prod values, not dev:
grep MILVUS_URI "$PROD/.env"
grep API_BASE "$PROD/src/rag/configs/app_config_pro.yaml"
```

### 3. Prod — restart affected service(s)

```bash
cd /path/to/document_fragment

# Pick the service that owns your changed code (see table below)
docker compose restart qa_api
# docker compose restart embedding_api
# docker compose restart document_fragment_api

# Or restart all three APIs if unsure:
# docker compose restart
```

**Do not restart Milvus** for application code changes. Milvus is a separate container and its data lives in `volumes/milvus/`.

### 4. Prod — smoke test

```bash
docker compose ps

# RAG API
curl -s http://localhost:12357/agent/list

# Embedding API
curl -s -X POST http://localhost:12356/embeddings \
  -H "Content-Type: application/json" \
  -d '{"input":"hello"}'

# Document API — open Swagger in browser if available
# http://<prod-host>:12355/docs

docker compose logs qa_api --tail 50
```

---

## Optional: git pull (if prod has network)

If the CentOS host can reach your Git remote:

### Dev

```powershell
cd D:\setup\setup\document_fragment
git add .
git commit -m "describe your change"
git push
```

### Prod

```bash
cd /path/to/document_fragment
git pull
docker compose restart qa_api   # or affected service
```

Still **do not** let `git pull` replace `.env` or `app_config_pro.yaml` if those were ever committed locally on prod.

---

## Which container to restart?

| Changed path | Service | Restart command |
|--------------|---------|-----------------|
| `src/rag/**` (e.g. `qa.py`, controllers, configs loaded at import) | `qa_api` | `docker compose restart qa_api` |
| `src/embedding/**` | `embedding_api` | `docker compose restart embedding_api` |
| `src/api/**` | `document_fragment_api` | `docker compose restart document_fragment_api` |
| `docker-compose.yaml` | All compose services | `docker compose up -d` |
| `.env` | Services that read those vars | `docker compose restart` (or specific service) |
| `src/rag/configs/app_config_pro.yaml` | RAG (and anything reading YAML at import) | `docker compose restart qa_api` |

**Example:** retrieval fix in `src/rag/services/qa.py` → copy file to prod `src/` + `docker compose restart qa_api` only. No image rebuild.

---

## July 24, 2026 incident notes

One live recovery on July 24, 2026 showed that `docker compose restart` was **not always enough** after config cleanup. The Python code and YAML values were corrected, but one or more running containers still behaved as if they were using old values until the service was recreated.

What happened in that incident:

- Merge-conflict leftovers had been written into `src/rag/configs/__init__.py` and `src/embedding/api.py`; those had to be cleaned first.
- `qa_api` and `document_fragment_api` both failed on Milvus until their effective `MILVUS_URI` matched the reachable host.
- Inside the running environment, `milvus-standalone:19530` **did not resolve**, but `192.168.1.227:19530` **did**.
- `qa_api` later failed on the LLM side because config still referenced a missing Ollama model name (`zhuque3`) instead of an installed one (`qwen2.5:14b`).

Practical lessons:

- If behavior still looks old after fixing `.env` or `app_config_pro.yaml`, use `docker compose up -d --force-recreate <service>` instead of only `docker compose restart <service>`.
- Validate config **inside the target service container**, not only on disk.
- Treat old `docker compose logs` output carefully; stale crash lines can mix with current healthy startup.

Useful commands from that incident:

```bash
# Check what the service actually reads at runtime
docker compose run -T --rm qa_api python - <<'EOF'
from rag.configs import app_config
print("MILVUS_URI =", app_config.get("MILVUS_URI"))
print("TOKENIZE_URL =", app_config.get("TOKENIZE_URL"))
EOF

# Test host reachability from inside the service container
docker compose run -T --rm qa_api python - <<'EOF'
import socket
for host, port in [("milvus-standalone", 19530), ("192.168.1.227", 19530)]:
    s = socket.socket()
    s.settimeout(3)
    try:
        s.connect((host, port))
        print(host, port, "OK")
    except Exception as e:
        print(host, port, "FAIL", repr(e))
    finally:
        s.close()
EOF

# Recreate a service if restart is not enough
docker compose up -d --force-recreate qa_api
docker compose up -d --force-recreate document_fragment_api
```

Final working values in that incident:

- `MILVUS_URI='http://192.168.1.227:19530'`
- `MODEL_NAME='qwen2.5:14b'`

If a service still crashes after config edits, recreate that **specific** service first before changing more files.

---

## August 29, 2026 incident notes

One live recovery on August 29, 2026 started after host `192.168.1.227` suddenly became stuck and had to be restarted. After the host came back, the stack showed a layered failure sequence: remote users first could not reach the published API ports, then `embedding_api` and `qa_api` failed for different dependency reasons even after Docker networking was repaired.

What happened in that incident:

- Host `192.168.1.227` first became unresponsive and was restarted; the later failures were observed after that host-level restart.
- `document_fragment_api`, `embedding_api`, and `qa_api` could answer local `curl` checks, but other devices timed out on `192.168.1.227:12355-12357`.
- The immediate LAN access block was host firewall state on `192.168.1.227`; remote access started working after `firewalld` was explicitly stopped during recovery.
- A later `docker compose restart` hit Docker NAT programming failure with `iptables: No chain/target/match by that name`; restarting Docker recreated the `DOCKER` nat chain and allowed `docker compose up -d` to run again.
- `embedding_api` then exited with `OSError: Incorrect path_or_model_id: ''` while Compose was still warning that `EMBEDDING_MODEL_PATH` and related variables were unset; this was observed during diagnosis, but no `.env` or YAML change was applied in the final recovery sequence.
- `qa_api` then exited on `pymilvus.exceptions.MilvusException` because Milvus was unavailable on `192.168.1.227:19530`.
- After Milvus was started again, the stack finally came back up.

Practical lessons:

- Separate "port not reachable" from "service started but downstream dependency failed"; they are different layers.
- If Docker reports `iptables ... No chain/target/match by that name`, repair Docker host networking first before debugging Python logs.
- Empty Compose substitutions matter: `TOKENIZE_URL`, `EMBEDDING_MODEL_PATH`, `RERANKER_MODEL_PATH`, and `MILVUS_URL` defaulting to blank can cause later startup or runtime failures, even when the final recovery action that restored service was elsewhere.
- `docker compose restart` is only a container restart; if the dependency itself is a separate container like Milvus, restart or validate that dependency explicitly.

Useful commands from that incident:

```bash
# Verify Docker published ports and host firewall state
ss -lntp | grep -E '12355|12356|12357'
systemctl status firewalld --no-pager

# If Docker port publishing breaks, confirm/rebuild the nat chain
iptables -t nat -L -n
systemctl restart docker
docker compose up -d

# Inspect why app containers exited
docker compose ps -a
docker compose logs --tail 200 embedding_api
docker compose logs --tail 200 qa_api

# Validate Milvus separately from the app containers
docker ps --filter name=milvus
ss -lntp | grep 19530
docker restart milvus-standalone
```

Observed failure signatures in that incident:

- Remote browser timeout to `http://192.168.1.227:12355/docs` while local `curl http://127.0.0.1:12355/docs` succeeded.
- `HTTPConnectionPool(host='192.168.1.100', port=15006)` timeout during knowledge-agent embedding calls.
- `OSError: Incorrect path_or_model_id: ''` when `embedding_api` read an empty `EMBEDDING_MODEL_PATH`.
- `MilvusException: Fail connecting to server on 192.168.1.227:19530` when `qa_api` imported its Milvus client.

Final recovery path in that incident:

1. Stop `firewalld` during recovery so other devices can reach `12355`, `12356`, and `12357`, then replace that temporary step with explicit permanent port rules if the firewall should remain enabled later.
2. If Docker port publishing fails, restart Docker and retry `docker compose up -d`.
3. Start or restart `milvus-standalone` and confirm port `19530` is listening before restarting `qa_api`.
4. Re-run `docker compose ps -a` and service-specific logs until all three app containers stay `Up`.

What was not changed in that incident:

- `.env` was not edited during the successful recovery.
- `src/rag/configs/app_config_pro.yaml` was not edited during the successful recovery.

---

## Dev vs prod: what must stay different

Deploying code must **not** replace production-specific config.

| File | Copy from USB? | On deploy |
|------|----------------|-----------|
| `src/**` (Python code) | **Yes** | Overwrite prod `src/` |
| `docker-compose.yaml` | Only if changed | Review diff; then `docker compose up -d` |
| `.env` | **No** | **Keep prod values** — Milvus URI, model paths, API keys |
| `src/rag/configs/app_config_pro.yaml` | **No** | **Keep prod URLs** — LLM, embedding, FTP, Jira |
| `sqlite.db` | **No** | Prod knowledge-base metadata |

Typical differences:

| Setting | Windows dev (Docker Desktop) | CentOS prod |
|---------|-------------------------------|-------------|
| `MILVUS_URI` | `http://host.docker.internal:19530` | Host IP, `172.17.0.1`, or compose network name |
| `EMBEDDING_URL` / `RERANK_URL` in YAML | `http://host.docker.internal:12356/...` | `http://embedding_api:5006/...` if same compose network |
| `API_BASE` / LLM URL | Dev or test model server | 4-GPU production model server |

See [05-configuration.md](./05-configuration.md) and [23-dev-1gpu-prod-4gpu-migration.md](./23-dev-1gpu-prod-4gpu-migration.md).

---

## End-to-end picture (offline prod)

```
Windows dev                         USB / disk              CentOS prod (internal net)
───────────                         ─────────               ──────────────────────────
edit src/rag/services/qa.py
Copy src/ (or changed files)  ──►  E:\deploy\...    ──►   cp to /path/to/document_fragment/src/
(do NOT copy .env / prod yaml)                            docker compose restart qa_api
(local verify)                                            (smoke test on prod ports)
```

Same image tag (`document_fragment:mupdf-3`) on both machines. Same mount layout (`./src:/src`). Only config and restart target differ. **No `git pull` on prod required.**

---

## When to rebuild the image

**You do not need a new image** for normal Python edits under `src/`.

Rebuild or reload a new `.tar` only when you change:

- Python **dependencies** (new pip packages not already in the image)
- **System libraries** or OS packages inside the image
- **`Dockerfile`** or baked-in binaries (e.g. phantomjs)
- Base image version (e.g. new `mupdf-3` tag)

For dependency changes:

```powershell
# On a build machine — then ship new tar to prod
docker build -t document_fragment:mupdf-3 .
docker save document_fragment:mupdf-3 -o document_fragment-mupdf-3.tar
```

On prod: `docker load -i ...` then `docker compose up -d`. Ship the new `.tar` on USB the same way as code.

---

## What does *not* require redeploy

| Change | Action |
|--------|--------|
| New documents indexed | Upload/index via API — no container restart |
| Milvus vector data | Lives in `volumes/milvus/` — independent of app code |
| SQLite metadata | File under mounted `src/` — persists across restarts |
| External LLM server config | Update model server only; app may need config + `qa_api` restart if URL changed |

---

## Rollback

If a deploy causes problems:

**Offline (you made `src.bak.*` before copy):**

```bash
cd /path/to/document_fragment
rm -rf src
mv src.bak.YYYYMMDD src          # use your backup folder name
docker compose restart qa_api      # restart affected service(s)
```

**If prod uses Git:**

```bash
git log -1 --oneline
git checkout HEAD~1 -- src/
docker compose restart qa_api
```

For config mistakes, restore prod `.env` / `app_config_pro.yaml` from backup and restart.

---

## Pre-deploy checklist

- [ ] Tested on dev (same Docker compose + volume mount pattern)
- [ ] No Windows-only paths in changed code
- [ ] USB bundle has `src/` only (not `.env`, not prod yaml, not `sqlite.db`)
- [ ] Backed up prod `src/` before overwrite (`src.bak.YYYYMMDD`)
- [ ] Copied from USB into prod project directory
- [ ] Prod `.env` and `app_config_pro.yaml` unchanged
- [ ] Restarted correct container(s)
- [ ] Smoke test + logs clean
- [ ] If retrieval/Q&A changed: run [22-retrieval-eval.md](./22-retrieval-eval.md) checks on prod

---

## Quick command reference

| Task | Command |
|------|---------|
| Deploy RAG code (offline) | Copy `src/` from USB → prod; `docker compose restart qa_api` |
| Deploy all API code (offline) | Copy `src/` from USB → prod; `docker compose restart` |
| Deploy RAG code (online prod) | `git pull && docker compose restart qa_api` |
| Apply compose file change | Copy yaml + `docker compose up -d` |
| Check status | `docker compose ps` |
| View logs | `docker compose logs -f qa_api` |
| Full first-time prod setup | [21-software-recovery.md](./21-software-recovery.md) |

---

## July 24, 2026 incident notes: merge markers and REQUEST_URL

### Symptoms

- `embedding_api_gpu` failed with `SyntaxError: invalid syntax` at `<<<<<<< HEAD` in `src/embedding/api.py`
- `document_fragment_api` / `qa_api` failed for the same reason in `src/rag/configs/__init__.py`
- After replacing those broken files, `qa_api` still failed with `KeyError: 'REQUEST_URL'`

### Root cause

Two separate issues happened during the sync to `10.42.0.125`:

1. Git conflict markers had already been committed into:
   - `Dockerfile.embedding`
   - `src/embedding/api.py`
   - `src/rag/configs/__init__.py`
2. Updated `src/rag/services/qa.py` requires `REQUEST_URL` at startup, but `10.42.0.125`'s `src/rag/configs/app_config_pro.yaml` did not define it.

### Recovery

1. Fix the committed conflict-marker files in Git first, then verify:

```bash
grep -nE '<<<<<<<|=======|>>>>>>>' src/embedding/api.py src/rag/configs/__init__.py Dockerfile.embedding
```

Expected: no output.

2. Copy the clean files to `10.42.0.125` using exact target paths:

```bash
rsync -av /home/z/projects/rag/src/embedding/api.py jj@10.42.0.125:/home/jj/document_fragment/src/embedding/api.py
rsync -av /home/z/projects/rag/src/rag/configs/__init__.py jj@10.42.0.125:/home/jj/document_fragment/src/rag/configs/__init__.py
rsync -av /home/z/projects/rag/Dockerfile.embedding jj@10.42.0.125:/home/jj/document_fragment/Dockerfile.embedding
```

3. On `10.42.0.125`, verify those three files again:

```bash
cd /home/jj/document_fragment
grep -nE '<<<<<<<|=======|>>>>>>>' src/embedding/api.py src/rag/configs/__init__.py Dockerfile.embedding
```

4. Add the missing `REQUEST_URL` to `src/rag/configs/app_config_pro.yaml` on `10.42.0.125`.

Recovered value used during the incident:

```yaml
REQUEST_URL: "http://192.168.1.43:3000/sysorm/api/word/importLocal?_=1769478462691"
```

5. Restart the affected services:

```bash
docker compose up -d --force-recreate document_fragment_api qa_api
docker restart embedding_api_gpu
docker compose logs --tail 50 document_fragment_api qa_api
docker logs --tail 50 embedding_api_gpu
```

### Notes

- A clean `git status` does not guarantee files are safe; conflict markers can already be committed as normal text.
- Be careful to run copy commands on the machine that owns the source path. Running `rsync /home/z/...` from `10.42.0.125` will fail because that path only exists on machine `z`.

### Change origin

- `REQUEST_URL` became a required startup config in commit `8aa5f85` (`Prod code snapshot from server (2026-07-02)`), because `src/rag/services/qa.py` reads `app_config['REQUEST_URL']` during import.
- Committed merge markers were present in:
  - `Dockerfile.embedding` and `src/embedding/api.py` via `eddda26`
  - `src/rag/configs/__init__.py` via `095601d`
- Those broken file contents were later propagated into `master` by merge commit `9ee87e4`.
