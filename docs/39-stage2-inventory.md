# 39 - Stage 2 Inventory

This document records the first Stage 2 inventory pass for `~/rag` on August 31, 2026.

Purpose:

- identify safe structural cleanup candidates
- separate naming cleanup from behavior changes
- distinguish active product files from runtime artifacts and bulk output

All items below must preserve the compatibility baseline in [34-compatibility-baseline.md](./34-compatibility-baseline.md).

## 1. Naming issues that need compatibility handling

These names are confusing enough to justify cleanup, but they are currently referenced and should not be renamed without shims or coordinated import updates.

| Current path/name | Current usage | Risk | Recommended cleanup |
|---|---|---|---|
| `src/rag/controllers/knowledge_mange.py` | historical path still referenced in docs; runtime import can be redirected safely | direct rename would break historical references and any stale imports | add `knowledge_manage.py` as the canonical module, keep `knowledge_mange.py` as a compatibility shim |
| `moudle.json` | referenced by `src/rag/controllers/init/RelectTest.py`; duplicates appear under `controllers/init`, `controllers/reflectAndDoc`, and `services` | typo plus ambiguous ownership | standardize on `modules.json` where code is still relevant; keep legacy file names only where a shim/example loader is needed |
| `src/rag/utils/request_llm0530.py` | still present as a version-stamped helper module | date-stamped naming obscures whether it is active or archival | determine whether it is live; if active, rename to a functional name; if not, move to an archive/quarantine location |

## 2. Duplicate or confusing asset placement

These files exist in multiple locations and make code ownership unclear.

| Duplicate asset | Observed locations | Notes |
|---|---|---|
| `render.html` | `src/render.html`, `src/rag/render.html`, `src/rag/services/render.html`, `src/rag/static/render.html` | likely mixed source-template and generated/runtime copies |
| `echarts.min.js` | `src/echarts.min.js`, `src/rag/echarts.min.js`, `src/rag/services/echarts.min.js`, `src/rag/static/echarts.min.js` | same library appears as both source-local and runtime-static copies |
| `bar_chart.png` | `src/bar_chart.png`, `src/rag/bar_chart.png`, `src/rag/static/bar_chart.png` | generated output is mixed with repo content |
| Swagger UI assets | `src/api/static/*`, `src/embedding/static/*`, `src/rag/static/*` | may be intentional per-service packaging, but ownership should be explicit |
| PhantomJS binary | `src/phantomjs`, `src/rag/phantomjs-2.1.1-linux-x86_64/bin/phantomjs` | runtime choice is inconsistent across code paths |

## 3. Cross-layer import findings

These are not necessarily wrong, but they are structural coupling points to treat carefully.

| Import edge | Why it matters |
|---|---|
| `src/api/services/utils.py` -> `rag.configs` | document API depends on RAG config layer |
| `src/api/services/zip.py` -> `rag.configs` | document ZIP ingest is coupled to RAG config state |
| `src/rag/services/knowledge.py` -> `api.services.utils` | RAG service depends on document-service utility layer |
| `src/rag/services/qa.py` -> `rag.services.user_config`, `rag.services.api_manage`, `rag.utils.*`, `rag.mappers.*` | large service concentration; likely a later split target, but not a Stage 2 blind rewrite |

## 4. Runtime artifacts mixed into source tree

These look like generated or runtime-managed files rather than hand-maintained source.

### High-confidence runtime/generated content

- `src/rag/static/docx/` contains 375 generated `.docx` files
- `src/rag/static/week_report/` contains generated weekly report spreadsheets
- `src/rag/static/xlsx/` contains generated team-template spreadsheets
- `src/static/docx/` contains generated `.docx` output
- `src/api/static/logs/libraries_info.json` looks like runtime state/log output
- `__pycache__/` directories are present across `src/api`, `src/embedding`, and `src/rag`

### Bulk notes

- `src/rag/static` is about `112M`
- `src/static` is about `7.4M`

### Recommendation

Do not delete these blindly during Stage 2. First decide which directories are:

- required seeded fixtures
- generated outputs that should move under a dedicated runtime/output path
- repo junk that can be removed after confirming no code path depends on committed contents

## 5. Low-risk next cleanup candidates

These are the safest next steps after this inventory.

1. Document and standardize one canonical home for chart/render support assets used by report generation.
2. Quarantine or ignore `__pycache__/` and generated `.docx`/`.xlsx` runtime outputs after confirming they are not required fixtures.
3. Decide whether `request_llm0530.py` is active code, an experiment snapshot, or dead backup.

## 6. Explicitly deferred from this inventory step

- breaking route/path changes
- envelope/schema changes
- config precedence changes
- large `qa.py` behavior refactors
- removing PhantomJS without replacement validation
