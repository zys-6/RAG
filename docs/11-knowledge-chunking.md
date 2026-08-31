# 11 — Knowledge Feature: Overview, Chunking & Splitting

How the **Knowledge** (知识库) feature works in this project — especially what counts as a “chunk”, whether sliding windows exist, and how documents are split.

---

## What “Knowledge” is

Knowledge is a **document library scoped for RAG**:

| Concept | Storage | Role |
|---------|---------|------|
| **Package** (知识库) | SQLite `Package` | Folder — personal, group, or public (`公共知识库`) |
| **File** | SQLite `File` | One uploaded document; `file_id` = MD5 of file bytes |
| **Fragment / chunk** | Milvus collection `fragments` | Parsed text block + embedding vector |
| **Knowledge agent** | RAG QA API | Q&A limited to files in one package |

**Not included:** a full document management system (versioning, permissions UI, direct browser upload on the knowledge API).

**Package IDs:** Each 知识库 gets a server-generated `package_id` (`package-` + UUID) when created via `POST /knowledge_manage/package/create`. That id scopes retrieval and Q&A to files registered under the library. See [22-retrieval-eval.md](./22-retrieval-eval.md#package-id--search-scope). Retrieval theory: [24-retrieval-pipeline-internals.md](./24-retrieval-pipeline-internals.md).

---

## End-to-end flow

```
1. Create package          POST /knowledge_manage/package/create
2. Upload (via FTP URL)    POST /knowledge_manage/file/upload
         │
         ▼
   RAG API → Document API  POST /zip/upload_ftp
         │
         ├─ Download zip from FTP, unzip
         ├─ For each PDF/Word/CAJ:
         │     parse → fragments (layout-based)
         │     embed each fragment → Milvus
         │     register File row in SQLite
         └─ Callback: file status = success
3. Ask questions           POST /qa/agent/knowledge_agent
         │
         ├─ Load file_ids for package from SQLite
         ├─ Vector search in Milvus (filter by document_id)
         ├─ Expand related fragments via parent_id / outline
         └─ Send top context to LLM → streamed answer
```

**Key files:**

| Layer | Path |
|-------|------|
| Knowledge CRUD | `src/rag/controllers/knowledge_mange.py`, `src/rag/services/knowledge.py` |
| Upload trigger | `src/rag/utils/utils.py` → `requests_upload_file()` |
| Parse + index | `src/api/services/zip.py`, `src/api/services/utils.py` |
| Layout parsing | `src/document_fragment/document/pdf_document.py`, `word_document.py` |
| Q&A | `src/rag/services/qa.py` → `knowledge_agent_stream()` |

---

## Chunking: what this project actually does

### Terminology

The code uses **“fragment”** during parsing and **“chunk”** when writing to Milvus — but they are **1:1** (one fragment → one vector record). There is no second-stage chunking.

```python
# src/api/services/utils.py — convert_format()
for fragment in fragments:
    if fragment['type'] == 'content' and fragment['text'].strip():
        chunks.append({ "text": fragment['text'], ... })  # one row per fragment
```

### How fragments are created (layout-based, not token-based)

Documents are split by **document structure**, not by fixed token size:

| Source | Splitting logic |
|--------|-----------------|
| **PDF** | Layout analysis → paragraphs, titles, tables, figures. Text blocks split by line spacing, punctuation, paragraph alignment (`_split_text_structure` in `pdf_document.py`). |
| **Word** | OOXML structure → runs, headings (`outline` level from styles), tables, pictures. |
| **CAJ** | Converted then processed like PDF/Word. |

Each resulting **ContentFragment** becomes one Milvus record with:

| Field | Meaning |
|-------|---------|
| `page_content` | Full text of that fragment |
| `outline` | Heading level (0 = body, 1+ = titles) |
| `parent_id` | Tree link to parent headings (built in `add_parent_id_into_fragments`) |
| `index` | Order within the document |
| `document_id` | File MD5 |
| `coordinates` | Page bbox for citation |
| `num_tokens` | **Always stored as `0`** (not computed at index time) |

### Typical chunk sizes (from real indexed data)

| Stat | Approx. value |
|------|----------------|
| Median fragment | ~50 characters (many short titles/blocks) |
| Max seen | ~5,000 characters |
| Fixed target (512/1024 tokens) | **None** |

Chunks are **variable length** and follow layout, not a uniform RAG recipe.

---

## Sliding windows: **not used**

This project does **not** implement sliding-window chunking for indexing.

| Standard RAG pattern | This project |
|----------------------|--------------|
| Split text into 512-token blocks | No |
| Overlap 128 tokens between blocks | No |
| LangChain / RecursiveCharacterTextSplitter | Not present |
| Same chunk size for all documents | No |

**Implication:** If an answer sits on a boundary between two fragments, there is **no overlapping text** to help retrieval bridge the gap.

---

## Splitting: all the places “split” appears

### 1. Index-time splitting (document parsing) — **yes**

**PDF paragraph split** (`pdf_document.py`):

- End of sentence + line width change → new paragraph
- Large vertical gap between lines → new paragraph
- Different horizontal alignment → new paragraph

**Word / layout merge** (`pdf_document.py`, `word_document.py`):

- Adjacent text lines merged into one fragment when layout says they belong together
- Headers, footers, references handled separately

This is **semantic/layout splitting**, not sliding windows.

### 2. Outline tree (`parent_id`) — **yes, for structure**

After fragments are built, `add_parent_id_into_fragments()` links each block to its heading hierarchy:

```
Chapter 1 (outline=1, parent_id=None)
  ├─ Section 1.1 (outline=2, parent_id=chapter_id)
  └─ Body text (outline=0, parent_id=section_id)
```

Used at **retrieval time** to pull related sibling text — not to create overlapping chunks.

### 3. Retrieval expansion — **yes, at query time**

```python
# qa.py — search_with_same_outline()
docs = await search(question, filter=package_file_ids, limit=30)
# Then fetch sibling fragments sharing parent_id
docs = query("(...) and type == 'text'")
```

So search may **widen** results using the outline tree — still not sliding-window overlap.

### 4. LLM context batching — **truncate at query time only**

```python
# qa.py — auto_batch()
# If retrieved chunks exceed ~16k tokens budget → truncate page_content
batch[0]['page_content'] = batch[0]['page_content'][:int(batch_tokens * 0.9)]
```

This limits what goes into the **prompt**, not how vectors were stored.

### 5. Other “chunk” uses (not document indexing)

| Location | Purpose |
|----------|---------|
| `request_llm.py` | Split large JSON/API responses for LLM prompts |
| `qa.py` `split_text_by_length` | OCR markdown formatting (mostly unused) |
| Streaming `async for chunk in subscription` | SSE stream chunks from LLM — unrelated to document splitting |

---

## Knowledge Q&A retrieval pipeline

For `POST /qa/agent/knowledge_agent`:

```
question
  → embed query vector
  → Milvus search (top 30, filter: document_id in [package's file_ids])
  → optional rerank (embedding API /rerank)
  → expand via parent_id (search_with_same_outline)
  → merge reference sources by document_id
  → trim to LLM context (auto_batch / max ~10k chars in template)
  → stream LLM answer with citations
```

---

## Comparison: this project vs typical RAG

| Aspect | Typical RAG (Dify, LangChain, etc.) | This project |
|--------|--------------------------------------|--------------|
| Split unit | Fixed tokens (512/1024) | Layout paragraph / title block |
| Overlap | 10–20% sliding window | **None** |
| Chunk size | Uniform | Highly variable |
| Structure preserved | Often lost | **Yes** — outline, coordinates, pages |
| Citation | Chunk text only | Text + page coordinates |
| Token metadata | Stored per chunk | **`num_tokens = 0`** |
| Long paragraph | Split into multiple chunks | **One huge embedding** |

**Design intent:** Optimize for **structured enterprise documents** (headings, tables, PDF layout) and **precise citations**, not for generic “split everything into 512 tokens”.

---

## Knowledge API summary

| Endpoint | Function |
|----------|----------|
| `GET /knowledge_manage/tree` | Package + file tree for a user |
| `GET /knowledge_manage/package/list` | List packages |
| `POST /knowledge_manage/package/create` | Create package (server returns `package-{uuid}`) |
| `POST /knowledge_manage/file/upload` | Start ingest (requires **FTP URL**) |
| `GET /knowledge_manage/file/list` | Files in a package |
| `POST /knowledge_manage/retrieval/search` | Retrieval test **without LLM** (see [22-retrieval-eval.md](./22-retrieval-eval.md)) |
| `DELETE /knowledge_manage/file/delete` | Remove file metadata (Milvus vectors may remain) |
| `GET /knowledge_manage/package/recommend` | Sample questions (needs LLM) |
| `POST /qa/agent/knowledge_agent` | Chat over one package |

---

## Limitations (chunking-related)

1. **No overlap** — cross-boundary answers may miss context.
2. **No max-chunk split** — very long paragraphs produce one weak embedding.
3. **Many tiny chunks** — titles/labels indexed separately; can dominate search.
4. **No re-chunking** — changing strategy requires re-uploading / re-indexing.
5. **Delete file** removes SQLite row but often **not** Milvus vectors.

---

## One-page mental model

```
Document
   │
   ▼  layout parser (NOT sliding window)
Fragments (paragraph / title / table …)
   │
   ▼  1 fragment = 1 Milvus vector (no overlap)
Indexed in Milvus + metadata in SQLite
   │
   ▼  query: vector search + parent_id expansion (NOT overlap retrieval)
LLM answer with sources
```

**Short answer:** Knowledge **does chunk** documents — but by **document layout**, not by **token sliding windows**. Treat “chunk” here as **structural fragment**, not **RAG-standard fixed-size block with overlap**.
