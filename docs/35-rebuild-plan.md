# 35 - Rebuild Plan and Progress Checklist

This document is the execution companion to [34-compatibility-baseline.md](./34-compatibility-baseline.md).

- `34` freezes the compatibility target.
- `35` tracks the phased rebuild plan, what is done, what is pending, and what is deliberately deferred.

Unless explicitly approved and documented later, all stages below must preserve the compatibility baseline in `34`.

## Status legend

- `[x]` done
- `[ ]` not done
- `[-]` deferred by plan
- `[?]` needs verification

## Guardrails

- Preserve the external wire contract first: paths, methods, request fields, response shapes, ports, and SSE behavior.
- Preserve the public entrypoints and Compose service names:
  - `api.main:app`
  - `embedding.api:app`
  - `rag.api:app`
  - `document_fragment_api`
  - `embedding_api`
  - `qa_api`
- Do conservative structure cleanup before behavior changes.
- Validate locally first, then validate on `10.42.0.125` when deployment-related changes are involved.
- Do not introduce `LangChain` or `LangGraph` into the initial cleanup pass.

## Stage 0 - Freeze the baseline

Goal: define what must not break before refactoring internals.

### Checklist

- [x] Create a compatibility baseline document for current entrypoints, ports, routes, envelopes, config keys, and `10.42.0.125` assumptions.
- [x] Record the currently validated `10.42.0.125` topology in `33`.
- [x] Confirm whether `docs/API-Reference.md` fully matches runtime behavior, or mark every mismatch explicitly.
- [x] Decide which current quirks are intentionally preserved until later cleanup is test-backed.

### Exit criteria

- `34` is the accepted compatibility reference.
- Known documentation/runtime mismatches are listed instead of silently ignored.

Stage 0 was closed in `~/rag` on August 31, 2026 by making `docs/API-Reference.md`, `34`, and `35` explicitly record the current mounted-only routes, the unmounted `/user_config_manage/*` controller surface, and the intentional `qa_router` double-include quirk.

## Stage 1 - Add regression and startup protection

Goal: add enough coverage that cleanup can be done without guessing.

### Checklist

- [x] Add startup tests that boot `api.main:app`, `embedding.api:app`, and `rag.api:app`.
- [x] Add contract checks for the three exposed service docs or OpenAPI surfaces.
- [x] Add route-presence checks for the main mounted groups in `34`.
- [x] Add response-shape checks for representative endpoints in each envelope family.
- [x] Add SSE checks for representative streaming endpoints.
- [x] Add a lightweight validation script or command list for local smoke testing.
- [x] Add a lightweight validation script or command list for `10.42.0.125` smoke testing.

### Exit criteria

- The public surface in `34` has automated or scripted checks for boot, route presence, and key response behaviors.

## Stage 2 - Conservative structural cleanup

Goal: improve naming and layout without changing external behavior.

### Checklist

- [x] Inventory naming problems and typo-like modules that can be cleaned safely.
- [x] Clean obviously confusing names such as `knowledge_mange.py` only with compatibility shims or import-safe aliases where needed.
- [ ] Review duplicate or cross-layer imports between `api`, `embedding`, and `rag`.
- [ ] Remove or quarantine obvious backup, temporary, or runtime-artifact files that do not belong in active source trees.
- [x] Reduce duplicate router wiring or registration only after Stage 1 checks exist.
- [ ] Keep existing response envelopes unchanged during this stage.
- [ ] Keep configuration key names and precedence unchanged during this stage.

### Exit criteria

- Internal structure is cleaner.
- Public behavior still matches `34`.
- Compatibility wrappers remain in place wherever internal moves would otherwise break imports.

Stage 2 progress in `~/rag` on August 31, 2026:

- [x] Removed the duplicate `qa_router` registration from `src/rag/api.py` after Stage 1 route/OpenAPI checks were in place.
- [x] Added `docs/39-stage2-inventory.md` to record typo-like names, duplicate asset placement, cross-layer imports, and runtime-artifact candidates before broader cleanup.
- [x] Switched the runtime import to `rag.controllers.knowledge_manage` and kept `knowledge_mange.py` as the compatibility shim path.

## Stage 3 - Isolated bug fixes and behavior corrections

Goal: fix real defects in small, testable steps after the structure is safer.

### Checklist

- [ ] Triage known behavior bugs separately from naming/layout cleanup.
- [ ] Fix one behavior cluster at a time with explicit regression coverage.
- [ ] Re-verify upload/status lifecycle behavior with live endpoint tests where relevant.
- [ ] Re-verify `10.42.0.125` deployment behavior after deployment-sensitive fixes.
- [ ] Update `34` only if an external behavior change is explicitly approved.

### Exit criteria

- Behavior changes are isolated, explained, and verified.
- No mixed "cleanup plus behavior rewrite" commits.

## Stage 4 - Selective framework evaluation

Goal: evaluate whether `LangChain` or `LangGraph` helps after the legacy surface is stabilized.

### Checklist

- [-] Do not adopt `LangChain` during Stages 0-3.
- [-] Do not adopt `LangGraph` during Stages 0-3.
- [ ] Identify concrete pain points that the current code cannot reasonably solve with existing abstractions.
- [ ] Compare candidate framework usage against the frozen wire contract and deployment constraints.
- [ ] Prototype only after earlier stages are stable and measurable.

### Exit criteria

- Any framework adoption is justified by a specific problem and does not start as a broad rewrite.

## Current status snapshot

Known done from the earlier rebuild planning work:

- [x] Compatibility-first sequence agreed.
- [x] `34` created as the baseline document.
- [x] `33` records the validated `10.42.0.125` working topology.
- [x] The decision to defer `LangChain` and `LangGraph` from the first pass is explicit.

Known not done or not yet verified in the current branch:

- [ ] A complete automated regression suite for the frozen external surface.
- [ ] A finished conservative cleanup pass with compatibility shims.
- [ ] A completed isolated bug-fix phase after structural cleanup.
- [ ] A finished framework evaluation phase.
- [?] Full route/documentation parity across `docs/API-Reference.md` and runtime mounts.

Stage 1 progress added in `~/rag` on August 31, 2026:

- [x] `tests/test_stage1_contracts.py` boots all three app entrypoints under import-time stubs and checks OpenAPI, route presence, response envelopes, and an SSE route.
- [x] `scripts/smoke_local_stage1.sh` runs the local Stage 1 pytest smoke suite.
- [x] `scripts/smoke_remote_stage1.sh` checks the three remote OpenAPI surfaces on `10.42.0.125` by default.

## Update rules

- Update `34` only when the accepted compatibility baseline changes.
- Update `35` as tasks move between done, not done, deferred, and needs verification.
- If a task changes external behavior, document the approval and update both `34` and `35`.
