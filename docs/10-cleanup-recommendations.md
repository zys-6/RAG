# 10 — Cleanup Recommendations (What You Can Delete)

**Purpose:** Free disk space without breaking the three APIs + Milvus stack.  
**Related:** [09-storage-breakdown.md](./09-storage-breakdown.md) explains *why* the repo is large.

---

## Quick decision table

| Tier | Action | Savings | Safe? |
|------|--------|---------|-------|
| **A — Do now** | Rogue file + temp uploads + backup copies | **~13 GB** | Yes |
| **B — After verify** | Docker `.tar` files (images already loaded) | **~14 GB** | Yes, if `docker images` OK |
| **C — Optional module** | `voice/` folder | **~5 GB** | Yes, if you don't use voice |
| **D — Test first** | Duplicate reranker weight file | **~2.1 GB** | Only after `/rerank` test |
| **E — Never** | `models/`, live configs, `sqlite.db`, `volumes/milvus/` | — | No |

---

## Tier A — Safe to delete (recommended)

These are unused, backups, or runtime debris. **No config changes needed.**

### A1. Rogue binary (~7.2 GB)

| Path | Size | Reason |
|------|------|--------|
| `document_fragment/src_jira_report.py` | ~7.2 GB | Binary blob with `.py` extension; not imported anywhere |

### A2. Upload temp debris (~5.6 GB)

| Path | Size | Reason |
|------|------|--------|
| `document_fragment/src/static/tmp/` | ~5.6 GB | ~4,900 old uploaded PDFs, CAJ, Office docs, etc. from dev/demo runs |

The API recreates temp dirs as needed. You only lose historical test uploads.

### A3. Backup / duplicate source files (~1 MB total)

Not referenced by running code. Live files are the non-`_bak` / non-`_bk` versions.

| Path | Replace with |
|------|--------------|
| `src/rag/services/qa_bak.py` | `src/rag/services/qa.py` |
| `src/rag/utils/request_llm_bak.py` | `src/rag/utils/request_llm.py` |
| `src/rag/utils/request_llm_bk.py` | `src/rag/utils/request_llm.py` |
| `src/rag/utils/request_llm0530.py` | `src/rag/utils/request_llm.py` |
| `src/rag/utils/request_llm (1).py` | `src/rag/utils/request_llm.py` |
| `src/rag/utils/utils_bk.py` | `src/rag/utils/utils.py` |
| `src/rag/utils/mapping_bk.py` | active mapping module |
| `src/rag/configs/api_data_bk2.json` | `api_data.json` |
| `src/rag/configs/api_data_back.json` | `api_data.json` |
| `src/rag/configs/prompt_config_bk.yaml` | `prompt_config.yaml` |
| `src/rag/services.py` | superseded by `src/rag/services/` package (unused) |
| `src/rag/controllers/reflectAndDoc/test.py` | one-off test script |

### A4. IDE metadata (tiny)

| Path | Reason |
|------|--------|
| `src/rag/.idea/` | PyCharm project files; not used at runtime |

**Tier A total: ~13 GB**

---

## Tier B — Docker tar exports (~14 GB)

Delete **only after** images are loaded and verified:

```powershell
docker images document_fragment
docker images milvusdb/milvus
```

Expected: `document_fragment:mupdf-3` (~27 GB) and `milvusdb/milvus:v2.4.4` (~3.5 GB).

| Path | Size | When to delete |
|------|------|----------------|
| `setup/document_fragment-mupdf-3.tar` | ~12.5 GB | After successful `docker load` on this machine **and** you have another copy for restore/offline deploy |
| `setup/milvus.tar` | ~1.6 GB | Same |

**Keep the tars if:** you plan to restore on CentOS VM, air-gapped server, or after a full Docker reinstall. See [07-docker.md](./07-docker.md).

**Tier A + B total: ~27 GB**

---

## Tier C — Optional voice module (~5 GB)

Not used by `docker-compose.yaml` (main three APIs).

| Path | Size | Delete if |
|------|------|-----------|
| `setup/voice/kokoro-fastapi.tar` | ~3.8 GB | You don't deploy speech/TTS |
| `setup/voice/whisper-api.tar` | ~1.3 GB | You don't deploy speech-to-text |
| Rest of `setup/voice/` | ~2 MB | Small Python/static files |

---

## Tier D — Duplicate model weights (test first, ~2.1 GB)

| Path | Size | Notes |
|------|------|-------|
| `models/reranker/pytorch_model.bin` | ~2.1 GB | Duplicate of `model.safetensors` in same folder |

**Procedure:**
1. Call embedding API rerank endpoint (or hit `/rerank` via Swagger on port 12356).
2. If OK, delete `pytorch_model.bin` only (keep `model.safetensors` + tokenizer files).
3. If it fails, restore the file.

Do **not** delete anything under `models/text2vec-base-multilingual/`, `table_detection/`, or `table_recognition/` — all are in use.

---

## Tier E — Do NOT delete

| Path | Why you need it |
|------|-----------------|
| `document_fragment/src/` (active `.py`) | Application code |
| `document_fragment/models/` | Mounted into containers; embedding + OCR depend on it |
| `document_fragment/.env` | Docker Compose environment |
| `src/rag/configs/app_config_pro.yaml` | Primary runtime config (LLM, Milvus, URLs) |
| `src/rag/configs/api_data.json` | Live API field mappings |
| `src/rag/configs/prompt_config.yaml` | Live LLM prompts |
| `src/rag/resources/sqlite.db` | Agents, packages, dialogue metadata |
| `setup/volumes/milvus/` | Vector index data (loss = re-embed documents) |
| Loaded Docker images | Required to run containers |

---

## Recommended cleanup scripts

### Minimal safe cleanup (~13 GB)

```powershell
# Rogue file
Remove-Item "D:\setup\setup\document_fragment\src_jira_report.py" -Force

# Temp uploads
Remove-Item "D:\setup\setup\document_fragment\src\static\tmp\*" -Recurse -Force

# Backup Python
Remove-Item "D:\setup\setup\document_fragment\src\rag\services\qa_bak.py" -Force
Remove-Item "D:\setup\setup\document_fragment\src\rag\services.py" -Force
Remove-Item "D:\setup\setup\document_fragment\src\rag\utils\*_bak.py" -Force
Remove-Item "D:\setup\setup\document_fragment\src\rag\utils\*_bk.py" -Force
Remove-Item "D:\setup\setup\document_fragment\src\rag\utils\request_llm0530.py" -Force
Remove-Item "D:\setup\setup\document_fragment\src\rag\utils\request_llm (1).py" -Force

# Backup configs
Remove-Item "D:\setup\setup\document_fragment\src\rag\configs\api_data_bk2.json" -Force
Remove-Item "D:\setup\setup\document_fragment\src\rag\configs\api_data_back.json" -Force
Remove-Item "D:\setup\setup\document_fragment\src\rag\configs\prompt_config_bk.yaml" -Force

# IDE + test junk
Remove-Item "D:\setup\setup\document_fragment\src\rag\.idea" -Recurse -Force -ErrorAction SilentlyContinue
Remove-Item "D:\setup\setup\document_fragment\src\rag\controllers\reflectAndDoc\test.py" -Force -ErrorAction SilentlyContinue
```

### After verifying Docker images (~14 GB more)

```powershell
Remove-Item "D:\setup\setup\document_fragment-mupdf-3.tar" -Force
Remove-Item "D:\setup\setup\milvus.tar" -Force
```

### Optional voice module (~5 GB)

```powershell
Remove-Item "D:\setup\setup\voice" -Recurse -Force
```

---

## Verify services still work

After Tier A cleanup:

```powershell
cd D:\setup\setup\document_fragment
docker compose ps
curl http://localhost:12355/docs -UseBasicParsing | Select-Object StatusCode
curl http://localhost:12356/docs -UseBasicParsing | Select-Object StatusCode
curl http://localhost:12357/docs -UseBasicParsing | Select-Object StatusCode
```

All three should return `200`.

---

## Suggested strategy by goal

| Your goal | Delete |
|-----------|--------|
| **Free space on dev laptop, keep running locally** | Tier A only |
| **Maximum local cleanup, have backup USB/network copy of tars** | Tier A + B |
| **Deploy to CentOS — keep restore kit** | Tier A only; **keep** both `.tar` files |
| **Never use voice features** | Tier A + C |
| **Aggressive cleanup on prod server after stable run** | Tier A; keep tars off-server |

---

## Summary

- **Biggest wins:** `src_jira_report.py` + `src/static/tmp/` (~13 GB), safe anytime.
- **Tars:** save environment-restore effort, not application config — keep at least one copy off the dev machine if you deploy elsewhere.
- **Backup `*_bak*` / `*_bk*` files:** tiny but clutter; safe to remove.
- **Never delete** `models/`, live YAML/JSON config, SQLite, or Milvus volume without a plan.
