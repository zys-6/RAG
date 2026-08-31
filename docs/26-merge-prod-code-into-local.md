# 26 — Merge Production Code into Local Dev (Git)

How to bring **production Python code** (copied from the server) into your **local `src/`** tree while keeping local-only improvements (retrieval eval, dev config, etc.).

**Related:** [25-deploy-code-updates.md](./25-deploy-code-updates.md) (dev → prod deploy), [23-dev-1gpu-prod-4gpu-migration.md](./23-dev-1gpu-prod-4gpu-migration.md) (dev vs prod config), [22-retrieval-eval.md](./22-retrieval-eval.md) (local retrieval work to preserve).

---

## When you need this doc

Use this when:

- Production code was copied to your machine (e.g. USB) into folders like `rag_for_zss/`, `api_for_zss/`, `embedding_for_zss/`
- Your git repo (`master` / Gitee) has **local commits** that prod does not have (e.g. retrieval API, eval harness)
- You want to **merge** prod updates into local — not blindly overwrite

This is the **reverse** of doc 25 (which ships local → prod).

---

## Folder mapping

Prod copies are usually nested one level deeper than `src/`:

| Local (edit this) | Prod reference (read only) |
|-------------------|----------------------------|
| `src/rag/` | `rag_for_zss/rag/` |
| `src/api/` | `api_for_zss/api/` |
| `src/embedding/` | `embedding_for_zss/embedding/` |

Keep `*_for_zss/` as reference. **Never commit prod config/data into git.**

| Do not merge from prod | Why |
|------------------------|-----|
| `.env` | Prod Milvus URI, API keys |
| `src/rag/configs/app_config_pro.yaml` | Prod LLM / embedding URLs |
| `src/rag/resources/sqlite.db` | Prod knowledge-base metadata |
| `static/file/`, `static/fragment/`, `static/docx/` | Runtime uploads |
| `__pycache__/`, `._*`, `.idea/` | Junk from USB copy |

---

## Three merge approaches (pick one)

| Method | Best for | Conflict UI in Cursor |
|--------|----------|---------------------|
| **A — `git merge-file`** | One or few large files (`qa.py`) | Manual `<<<<<<<` markers |
| **B — Git branch merge** (recommended) | Many files across `rag/`, `api/` | Accept Current / Incoming / Both |
| **C — Copy prod + `git diff`** | Quick review of all changes | Source Control diff view |

---

## Method A — `git merge-file` (single file)

Merges **prod** into your **current working file** using **git HEAD** as the common ancestor. Writes `<<<<<<<` conflict markers where both sides changed the same region.

### 1. Backup

```powershell
cd D:\setup\setup\document_fragment
$ts = Get-Date -Format yyyyMMdd
Copy-Item -Recurse src\rag "src\rag.bak.$ts"
```

### 2. Start from a clean file

```powershell
git checkout -- src/rag/services/qa.py
```

### 3. Export git version as UTF-8 base (Windows — required)

**Do not use PowerShell `>` redirect** — it writes UTF-16 and Git reports:

```text
error: Cannot merge binary files
```

Use this instead:

```powershell
$content = git show HEAD:src/rag/services/qa.py
[System.IO.File]::WriteAllText("$env:TEMP\qa_base.py", $content, [System.Text.UTF8Encoding]::new($false))
```

### 4. Run merge (once only)

```powershell
git merge-file src/rag/services/qa.py $env:TEMP\qa_base.py rag_for_zss/rag/services/qa.py
```

**Exit codes:**

| Code | Meaning |
|------|---------|
| `0` | Merged cleanly |
| `1` | Conflicts — edit conflict markers in the file |
| `17` (Windows) | Often line-ending noise; check file for `<<<<<<<` anyway |

`git merge-file` prints **no output** on success. Check with:

```powershell
git status src/rag/services/qa.py
Select-String -Path src/rag/services/qa.py -Pattern '^<<<<<<<'
```

### 5. Resolve conflicts in Cursor

Open `src/rag/services/qa.py`, search `<<<<<<<`. Each block:

```text
<<<<<<< src/rag/services/qa.py
(local / current)
=======
(prod / other)
>>>>>>> rag_for_zss/rag/services/qa.py
```

| Keep | When |
|------|------|
| **Top (Current)** | Local-only features (e.g. `merge_documents`, `RERANK_POOL_MAX`, `/retrieval/search`, active `prompt.replace`) |
| **Bottom (Incoming)** | Prod-only features (e.g. `request_agent_stream`, `TeamInfo`, ticket ID updates) |
| **Both** | Independent additions (e.g. extra imports) |

Delete all `<<<<<<<`, `=======`, `>>>>>>>` lines. Re-search `<<<<<<<` — must be **0** before save.

### 6. Repeat for other files

```powershell
$file = "src/rag/controllers/knowledge_mange.py"
$content = git show "HEAD:$file"
$base = "$env:TEMP\km_base.py"
[System.IO.File]::WriteAllText($base, $content, [System.Text.UTF8Encoding]::new($false))
git merge-file $file $base rag_for_zss/rag/controllers/knowledge_mange.py
```

### 7. Abort / undo merge-file work

```powershell
git checkout -- src/rag/services/qa.py
# or restore entire tree from backup:
# Remove-Item -Recurse -Force src\rag; Copy-Item -Recurse src\rag.bak.YYYYMMDD src\rag
```

---

## Method B — Git branch merge (recommended)

Creates a real git merge with **Accept Current / Incoming / Both** in Cursor Source Control. Use when many files differ.

### Why branch from the initial commit?

If you branch prod from **current** `master` and merge back, Git **fast-forwards** and silently overwrites local work — no conflict UI.

Branch prod from the **initial commit** so local commits and prod snapshot **diverge**:

```text
d64f7f0  Initial commit
   ├── master  →  … → 691c5af  (your local commits)
   └── prod-import  →  one commit with prod src/
```

### Steps

```powershell
cd D:\setup\setup\document_fragment

# 1. Stash or commit any WIP
git status

# 2. Create prod branch from initial commit
git checkout -b prod-import d64f7f0

# 3. Copy prod code (not config/data)
Copy-Item -Recurse -Force rag_for_zss\rag\* src\rag\
Copy-Item -Recurse -Force api_for_zss\api\* src\api\
Copy-Item -Recurse -Force embedding_for_zss\embedding\* src\embedding\

# 4. Commit prod snapshot
git add src/rag src/api src/embedding
git commit -m "Prod code snapshot from server"

# 5. Merge into master
git checkout master
git merge prod-import
```

### Resolve conflicts

1. Cursor → **Source Control** → **Merge Changes**
2. Per file: **Accept Current** (local), **Accept Incoming** (prod), or **Accept Both**
3. Finish:

```powershell
git add src/
git commit -m "Merge prod code with local retrieval improvements"
```

### Abort branch merge

```powershell
git merge --abort          # during conflict resolution
git checkout master
git branch -D prod-import  # delete prod branch if abandoning
```

---

## Method C — Copy prod + `git diff` (review only)

Replace `src/` with prod, then use git to see **prod vs your last commit**:

```powershell
Copy-Item -Recurse -Force rag_for_zss\rag\* src\rag\
git diff --stat src/rag
```

Review in **Source Control** (left = git/original, right = prod). Manually restore local-only pieces from `src/rag.bak.*` or `git checkout HEAD -- <file>`.

Undo everything:

```powershell
git checkout -- src/rag src/api src/embedding
```

---

## What to keep from each side (this project)

| Area | Keep local | Take from prod |
|------|------------|----------------|
| Retrieval pipeline | `merge_documents`, `cap_for_rerank`, `search_with_same_outline`, `docs_to_retrieval_hits` | — |
| Knowledge API | `POST /retrieval/search` in `knowledge_mange.py` | — |
| New prod modules | — | `unit_aliases.py`, `team_info.py`, `request_agent_stream`, etc. |
| Config | `app_config_pro.yaml`, `.env` | — |
| Jira / report ticket IDs | — | Prod values (e.g. `PLTSOM-673`) |

---

## After merge — verify

```powershell
docker compose restart qa_api
docker compose logs qa_api --tail 50
curl -s http://localhost:12357/agent/list
```

If retrieval changed, run checks from [22-retrieval-eval.md](./22-retrieval-eval.md).

---

## Quick command reference

| Task | Command |
|------|---------|
| Merge one file (UTF-8 base) | See [Method A](#method-a--git-merge-file-single-file) |
| Merge many files with UI | See [Method B](#method-b--git-branch-merge-recommended) |
| See prod vs git diff | `git diff src/rag` (after copying prod into `src/`) |
| Undo merge-file on one file | `git checkout -- src/rag/services/qa.py` |
| Abort branch merge | `git merge --abort` |
| Check unresolved conflicts | `Select-String -Path src/rag/services/qa.py -Pattern '^<<<<<<<'` |

---

## Compare view vs Git merge

| Tool | Purpose |
|------|---------|
| **Compare Selected** (two files) | View diffs; mostly read-only; often only **Revert block** |
| **`git merge-file`** | Writes conflict markers into `src/`; you edit manually |
| **`git merge` (branch)** | Full merge with Accept Current / Incoming / Both |

For prod ↔ local work, **Git branch merge (Method B)** is usually easier than Compare Selected or many `merge-file` runs.
