# Storage Breakdown — Why This Repo Is Huge Despite “Little Code”

**Scanned:** `D:\setup\setup` on 2026-06-29  
**Total on disk:** ~**38.2 GB**  
**Actual Python source:** ~**256 files**, ~**47,000 lines**, ~**1.6 MB**

The project is a **machine-learning backend**, not a small web app. Most disk space is **Docker images**, **model weights**, **exported image tarballs**, and **leftover runtime uploads** — not application logic.

---

## At a glance

| Category | Size | Share of `setup/` | What it is |
|----------|------|-------------------|------------|
| Docker image tar (app) | 12.5 GB | **33%** | `document_fragment-mupdf-3.tar` — offline export of the main image |
| Junk / misnamed file | 7.4 GB | **19%** | `document_fragment/src_jira_report.py` — **7.3 GB binary blob** with a `.py` extension; **not referenced** anywhere |
| Upload / temp debris | 5.7 GB | **15%** | `src/static/tmp/` — ~4,900 old uploaded PDFs, CAJ, Office docs, one MP4 |
| ML model weights | 4.9 GB | **13%** | `models/` — reranker, embedding, OCR/table models |
| Voice module tars (optional) | 5.1 GB | **13%** | `voice/kokoro-fastapi.tar`, `voice/whisper-api.tar` — not used by main compose |
| Milvus image tar | 1.6 GB | **4%** | `milvus.tar` |
| Test / sample documents | ~0.5 GB | **1%** | `src/api/static/fragment/`, sample files in `tmp/` |
| Real Python + config | ~2 MB | **&lt;0.01%** | All `.py` under 1 MB each |
| Milvus runtime data | 0.7 GB | **2%** | `volumes/milvus/` — grows with indexed vectors |
| Everything else | ~0.3 GB | **&lt;1%** | SQLite, phantomjs binary, docs, YAML, JSON |

> **Docker images after `docker load` (stored in Docker’s VM disk, not always inside `setup/`):**  
> `document_fragment:mupdf-3` ≈ **27 GB** · `milvusdb/milvus:v2.4.4` ≈ **3.5 GB**

If both the **tar files** and **loaded images** exist, you effectively store the same software **twice** until you delete the `.tar` files.

---

## Visual breakdown (workspace folder only)

```
D:\setup\setup  (~38 GB)
├── document_fragment-mupdf-3.tar     ████████████████████  12.5 GB  (33%)
├── document_fragment/                ██████████████████████████████  18.5 GB  (48%)
│   ├── src_jira_report.py            ███████████████       7.4 GB  ← NOT code
│   ├── src/static/tmp/               ████████████          5.7 GB  ← leftover uploads
│   ├── models/                       ██████████            4.9 GB  ← ML weights
│   ├── src/api/static/fragment/      █                      0.5 GB  ← test PDFs
│   └── src/**/*.py (real code)       ▏                     0.002 GB
├── voice/                            ██████████            5.0 GB  (optional voice tars)
├── milvus.tar                        ███                   1.6 GB
└── volumes/milvus/                   █                     0.7 GB
```

---

## Why it *looks* like “less code”

| What you see | What actually uses space |
|--------------|--------------------------|
| ~130 `.py` files in `src/` | Correct — the **logic** is small (~47k lines) |
| File explorer shows many `.py` files | One file (`src_jira_report.py`) is **7.3 GB of binary data** mislabeled as Python — skews any line-count tool |
| `src/` folder ≈ 6.3 GB | **90%** of that is `static/tmp/`, not code |
| `models/` looks like a normal folder | Contains multi-gigabyte **PyTorch / safetensors** weight files |
| Two `.tar` files at repo root | Full **compressed Docker filesystems** (OS + Python + torch + MuPDF + deps) |

**Rule of thumb:** In ML/document-AI projects, **code is usually &lt;1% of deploy size**. The rest is models, containers, and runtime data.

---

## Detail by area

### 1. Docker images and tar exports (~14–44 GB depending on what you count)

| Artifact | Size | Notes |
|----------|------|-------|
| `document_fragment-mupdf-3.tar` | 12.5 GB | Export for air-gapped / offline install |
| Loaded image `document_fragment:mupdf-3` | ~27 GB | Includes Python 3, PyTorch, PyMuPDF, FastAPI stack, system libs |
| `milvus.tar` | 1.6 GB | Milvus standalone export |
| Loaded `milvusdb/milvus:v2.4.4` | ~3.5 GB | Vector database runtime |

The app image is large because it bundles a **full ML runtime**, not because your business logic is large.

### 2. ML models — `document_fragment/models/` (~4.9 GB)

| Subfolder | Size | Main files |
|-----------|------|------------|
| `reranker/` | 4.3 GB | `pytorch_model.bin` + `model.safetensors` (~2.1 GB each — **duplicate format**) |
| `text2vec-base-multilingual/` | 479 MB | Embedding model |
| `table_detection/` | 110 MB | Paddle/table detection weights |
| `table_recognition/` | 110 MB | Table OCR weights |
| `.paddleocr/` | 69 MB | OCR cache/weights |

Models are **mounted into containers** at runtime (`docker-compose.yaml`); they are not “source code.”

### 3. Runtime upload debris — `src/static/tmp/` (~5.7 GB, ~4,899 files)

Leftover files from document upload/processing during development or demos:

| Extension | Files | Size |
|-----------|-------|------|
| `.pdf` | 863 | 2.2 GB |
| `.caj` | 248 | 1.4 GB |
| `.mp4` | 1 | 1.1 GB |
| `.zip` | 47 | 271 MB |
| `.doc` / `.docx` | 1,053 | 330 MB |
| `.xlsx` / `.xls` | 1,807 | 111 MB |
| Other (ppt, mpp, svn-base, …) | ~880 | ~300 MB |

**Safe to delete** if you do not need historical test uploads. The API will recreate temp dirs as needed.

### 4. Rogue file — `src_jira_report.py` (~7.4 GB)

- Lives at `document_fragment/src_jira_report.py` (project root, not under `src/`).
- **Binary content** — not valid Python text (editors may fail to open it).
- **Not imported or referenced** anywhere in the repo.
- Almost certainly an **accidental dump** (database export, log, or attachment archive) saved with a `.py` name.

Removing this single file drops workspace size by **~19%**.

### 5. Real application source (~1.6 MB)

| Module | Approx. size | Role |
|--------|--------------|------|
| `src/rag/` | 196 MB* | RAG/QA API (*includes phantomjs binary ~65 MB, sqlite ~2 MB, configs) |
| `src/api/` code | &lt;1 MB | Document parsing API |
| `src/embedding/` | 1.5 MB | Embedding/rerank API |
| `src/document_fragment/` | 0.6 MB | Shared parsing library |
| `src/layout_analysis/` | 7 MB | PDF layout (includes vendored pdfminer tables) |

*Without phantomjs and test static files, Python in `rag/` is ~100 KB per large file (`qa.py`, etc.).

### 6. Voice module — `voice/` (~5.0 GB, optional)

| File | Size |
|------|------|
| `kokoro-fastapi.tar` | 3.8 GB |
| `whisper-api.tar` | 1.3 GB |
| `main.py`, static | &lt;2 MB |

Separate from the three main APIs. Only needed if you deploy speech features.

### 7. Databases and indexes

| Location | Size | Grows when |
|----------|------|------------|
| `volumes/milvus/` | 671 MB | Documents are embedded and indexed |
| `src/rag/resources/sqlite.db` | ~2 MB | Agents, packages, dialogue metadata added |

---

## What is *not* taking space

- Frontend — **none** (API-only backend)
- Git history — not measured here; `.git` may add more if present
- Redis / Celery — not in compose; no large Redis dump in tree
- Jira/PM **code** — small JSON/Python config files, not gigabytes

---

## Recommended cleanup (largest wins first)

| Action | Approx. savings | Risk |
|--------|-----------------|------|
| Delete `src_jira_report.py` | **7.4 GB** | None — unused binary |
| Clear `src/static/tmp/` | **5.7 GB** | Lose old test uploads only |
| Delete `.tar` files **after** successful `docker load` | **14 GB** | Must keep images loaded in Docker |
| Remove duplicate reranker format (keep `.safetensors` OR `.bin`, not both) | **~2.1 GB** | Confirm embedding service loads the kept format |
| Move `voice/*.tar` off dev machine if unused | **5 GB** | Voice features unavailable until restored |
| `docker system prune` (unused images) | Varies | Do not prune active project images |

**Conservative cleanup** (upload debris + rogue file): **~13 GB** with no impact on running services.

---

## How to re-scan sizes yourself

PowerShell (Windows):

```powershell
# Total workspace
(Get-ChildItem "D:\setup\setup" -Recurse -File | Measure-Object Length -Sum).Sum / 1GB

# Top-level folders
Get-ChildItem "D:\setup\setup" | ForEach-Object {
  $s = (Get-ChildItem $_.FullName -Recurse -File -ErrorAction SilentlyContinue | Measure-Object Length -Sum).Sum
  [PSCustomObject]@{ Name = $_.Name; GB = [math]::Round($s/1GB, 2) }
} | Sort-Object GB -Descending

# Docker images for this project
docker images --format "{{.Repository}}:{{.Tag}}  {{.Size}}" | Select-String "document_fragment|milvus"
```

Linux / CentOS deploy target:

```bash
du -sh /path/to/setup/*
du -sh /path/to/setup/document_fragment/models/*
du -sh /path/to/setup/document_fragment/src/static/tmp
```

---

## Summary

**The repo is huge because it ships a complete ML + document-AI stack offline:** Docker filesystems, neural network weights, vector DB, and years of temp uploads — not because the Python codebase is large. The **real code is ~1.6 MB**; everything else is **infrastructure, models, and artifacts**.

For day-to-day development, treat `models/`, `*.tar`, `static/tmp/`, and `src_jira_report.py` as **data/deployment bulk**, and `src/**/*.py` as the **actual product**.
