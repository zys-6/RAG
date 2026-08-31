#!/usr/bin/env python3
"""Evaluate vector retrieval against a golden question set.

Compares four pipeline stages (mirrors src/rag/services/qa.py):
  - vector:     Milvus search only (top-k by embedding similarity)
  - outline:    vector top-30 + parent_id sibling expansion (merge, no rerank)
  - rerank:     vector top-30, then Embedding API /rerank reorder
  - pipeline:   merge + rerank + top-8 (what knowledge_agent uses after the fix)

Usage (from document_fragment project root, services running):

  python scripts/eval_retrieval.py
  python scripts/eval_retrieval.py --mode all --verbose
  python scripts/eval_retrieval.py --golden eval/retrieval_golden.json --report eval/report.json

Requires: requests, pymilvus (included in the project Docker image).
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

import requests

try:
    from pymilvus import MilvusClient
except ImportError as exc:
    raise SystemExit(
        "Missing dependency: pymilvus. Install with `pip install pymilvus requests`, "
        "or run via Docker:\n"
        "  docker run --rm -v \"$(pwd):/work\" -e MILVUS_URI=http://host.docker.internal:19530 "
        "-e EMBEDDING_URL=http://host.docker.internal:12356/embeddings "
        "-e RERANK_URL=http://host.docker.internal:12356/rerank "
        "--add-host=host.docker.internal:host-gateway document_fragment:mupdf-3 "
        "python /work/scripts/eval_retrieval.py"
    ) from exc

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_GOLDEN = PROJECT_ROOT / "eval" / "retrieval_golden.json"

OUTPUT_FIELDS = [
    "id",
    "page_content",
    "pages",
    "coordinates",
    "outline",
    "parent_id",
    "index",
    "type",
    "file_name",
    "document_id",
]

MODES = ("vector", "outline", "rerank", "pipeline", "all")
RERANK_POOL_MAX = 50


def normalize_service_url(url: str) -> str:
    """Map in-compose hostnames to localhost for scripts run on the host."""
    if not url:
        return url
    replacements = (
        ("http://embedding_api:5006", "http://localhost:12356"),
        ("http://host.docker.internal:12356", "http://localhost:12356"),
        ("http://host.docker.internal:19530", "http://localhost:19530"),
    )
    for internal, local in replacements:
        if url.startswith(internal):
            return local + url[len(internal) :]
    return url


def load_yaml_defaults() -> Dict[str, str]:
    """Load Milvus/embedding URLs from app_config_pro.yaml when present."""
    config_path = PROJECT_ROOT / "src" / "rag" / "configs" / "app_config_pro.yaml"
    if not config_path.exists():
        return {}
    try:
        import yaml  # type: ignore
    except ImportError:
        return {}
    with open(config_path, encoding="utf-8") as f:
        cfg = yaml.safe_load(f) or {}
    return {
        "milvus_uri": normalize_service_url(cfg.get("MILVUS_URI", "")),
        "collection": cfg.get("MILVUS_COLLECTION") or cfg.get("COLLECTION_NAME", ""),
        "embedding_url": normalize_service_url(cfg.get("EMBEDDING_URL", "")),
        "rerank_url": normalize_service_url(cfg.get("RERANK_URL", "")),
    }


def build_document_filter(document_ids: Sequence[str]) -> str:
    quoted = ", ".join(f"'{doc_id}'" for doc_id in document_ids)
    return f"document_id in [{quoted}]"


def get_vectors(embedding_url: str, texts: List[str]) -> List[List[float]]:
    resp = requests.post(embedding_url, json={"input": texts}, timeout=120)
    resp.raise_for_status()
    return [item["embedding"] for item in resp.json()["data"]]


def get_rerank_scores(rerank_url: str, query: str, texts: List[str]) -> List[float]:
    resp = requests.post(rerank_url, json={"query": query, "texts": texts}, timeout=300)
    resp.raise_for_status()
    return resp.json()["scores"]


def milvus_hits_to_docs(hits: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    docs: List[Dict[str, Any]] = []
    for item in hits:
        entity = dict(item.get("entity") or {})
        page_content = entity.pop("page_content", "")
        metadata = entity
        metadata["id"] = item.get("id")
        metadata["distance"] = item.get("distance")
        docs.append({"page_content": page_content, "metadata": metadata})
    return docs


def vector_search(
    client: MilvusClient,
    collection: str,
    question: str,
    document_filter: str,
    limit: int,
    embedding_url: str,
) -> List[Dict[str, Any]]:
    query_embed = get_vectors(embedding_url, [question])[0]
    hits = client.search(
        collection,
        data=[query_embed],
        limit=limit,
        filter=document_filter,
        output_fields=OUTPUT_FIELDS,
    )[0]
    return milvus_hits_to_docs(hits)


def metadata_query(client: MilvusClient, collection: str, expr: str) -> List[Dict[str, Any]]:
    rows = client.query(collection, filter=expr, output_fields=OUTPUT_FIELDS)
    seen: set[str] = set()
    docs: List[Dict[str, Any]] = []
    for item in rows:
        page_content = item.get("page_content", "")
        if page_content in seen:
            continue
        seen.add(page_content)
        metadata = {k: v for k, v in item.items() if k != "page_content"}
        docs.append({"page_content": page_content, "metadata": metadata})
    docs.sort(key=lambda d: d["metadata"].get("index", 0))
    return docs


def cap_for_rerank(docs: List[Dict[str, Any]], max_pool: int = RERANK_POOL_MAX) -> List[Dict[str, Any]]:
    """Limit rerank input size. Merged list keeps vector hits first."""
    if len(docs) <= max_pool:
        return docs
    return docs[:max_pool]


def merge_documents(
    primary: List[Dict[str, Any]], secondary: List[Dict[str, Any]]
) -> List[Dict[str, Any]]:
    seen: set[str] = set()
    merged: List[Dict[str, Any]] = []
    for doc in primary + secondary:
        key = doc["metadata"].get("id") or doc["page_content"]
        if key in seen:
            continue
        seen.add(key)
        merged.append(doc)
    return merged


def search_with_same_outline(
    client: MilvusClient,
    collection: str,
    question: str,
    document_filter: str,
    limit: int,
    embedding_url: str,
    with_rerank: bool = False,
    top_k: int = 0,
    rerank_url: str = "",
) -> List[Dict[str, Any]]:
    """Mirrors qa.search_with_same_outline (merge siblings, optional rerank)."""
    vector_docs = vector_search(
        client, collection, question, document_filter, limit, embedding_url
    )
    docs = vector_docs

    parent_ids = list(
        {
            item["metadata"]["parent_id"]
            for item in vector_docs
            if item["metadata"].get("parent_id") not in (None, "None", "")
        }
    )
    if parent_ids:
        sibling_filter = "({}) and type == 'text'".format(
            " or ".join(f"parent_id LIKE '%{_pid}%'" for _pid in parent_ids)
        )
        if document_filter:
            sibling_filter = f"({document_filter}) and ({sibling_filter})"
        sibling_docs = metadata_query(client, collection, sibling_filter)
        docs = merge_documents(vector_docs, sibling_docs)

    if with_rerank and docs and rerank_url:
        pool = cap_for_rerank(docs)
        if len(docs) > len(pool):
            print(
                f"  rerank pool capped: {len(docs)} -> {len(pool)} docs",
                flush=True,
            )
        print(f"  reranking {len(pool)} docs...", flush=True)
        reranked = rerank_documents(rerank_url, question, pool)
        if reranked:
            docs = reranked[:top_k] if top_k else reranked
        elif top_k:
            docs = vector_docs[:top_k]

    return docs


def rerank_documents(
    rerank_url: str,
    question: str,
    documents: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """Mirrors qa.rerank_documents (positive scores only, descending)."""
    if not documents:
        return []
    scores = get_rerank_scores(
        rerank_url, question, [doc["page_content"] for doc in documents]
    )
    ranked = [
        (score, doc) for score, doc in zip(scores, documents) if score > 0
    ]
    ranked.sort(key=lambda x: x[0], reverse=True)
    return [doc for _, doc in ranked]


def retrieve(
    mode: str,
    client: MilvusClient,
    collection: str,
    question: str,
    document_ids: Sequence[str],
    limit: int,
    embedding_url: str,
    rerank_url: str,
) -> List[Dict[str, Any]]:
    doc_filter = build_document_filter(document_ids) if document_ids else ""
    if mode == "vector":
        return vector_search(client, collection, question, doc_filter, limit, embedding_url)
    if mode == "outline":
        return search_with_same_outline(
            client, collection, question, doc_filter, limit, embedding_url,
            with_rerank=False,
        )
    if mode == "rerank":
        docs = vector_search(client, collection, question, doc_filter, limit, embedding_url)
        return rerank_documents(rerank_url, question, docs)
    if mode == "pipeline":
        return search_with_same_outline(
            client, collection, question, doc_filter, limit, embedding_url,
            with_rerank=True, top_k=8, rerank_url=rerank_url,
        )
    raise ValueError(f"Unknown mode: {mode}")


def is_gold_hit(doc: Dict[str, Any], case: Dict[str, Any]) -> bool:
    meta = doc["metadata"]
    if meta.get("document_id") != case["gold_document_id"]:
        return False
    gold_index = case.get("gold_fragment_index")
    if gold_index is not None and meta.get("index") != gold_index:
        return False
    snippet = case.get("gold_text_contains")
    if snippet and snippet not in doc.get("page_content", ""):
        return False
    return True


def find_gold_rank(docs: List[Dict[str, Any]], case: Dict[str, Any]) -> Optional[int]:
    for idx, doc in enumerate(docs):
        if is_gold_hit(doc, case):
            return idx + 1
    return None


def recall_at_k(ranks: List[Optional[int]], k: int) -> float:
    if not ranks:
        return 0.0
    hits = sum(1 for rank in ranks if rank is not None and rank <= k)
    return hits / len(ranks)


def mean_reciprocal_rank(ranks: List[Optional[int]]) -> float:
    if not ranks:
        return 0.0
    total = sum(1.0 / rank for rank in ranks if rank is not None)
    return total / len(ranks)


def summarize_mode(
    mode: str,
    cases: List[Dict[str, Any]],
    k_values: List[int],
    client: MilvusClient,
    collection: str,
    limit: int,
    embedding_url: str,
    rerank_url: str,
    verbose: bool,
) -> Dict[str, Any]:
    ranks: List[Optional[int]] = []
    details: List[Dict[str, Any]] = []

    for case in cases:
        print(f"[{mode}] {case['id']} ...", flush=True)
        docs = retrieve(
            mode,
            client,
            collection,
            case["question"],
            case["document_ids"],
            limit,
            embedding_url,
            rerank_url,
        )
        rank = find_gold_rank(docs, case)
        ranks.append(rank)
        rank_str = str(rank) if rank else "miss"
        print(f"  -> rank={rank_str}, retrieved={len(docs)}", flush=True)

        detail: Dict[str, Any] = {
            "id": case["id"],
            "category": case.get("category"),
            "question": case["question"],
            "gold_rank": rank,
            "hit": rank is not None,
            "retrieved_count": len(docs),
        }
        if verbose:
            detail["top_hits"] = [
                {
                    "rank": i + 1,
                    "document_id": d["metadata"].get("document_id"),
                    "index": d["metadata"].get("index"),
                    "type": d["metadata"].get("type"),
                    "file_name": d["metadata"].get("file_name"),
                    "distance": d["metadata"].get("distance"),
                    "preview": (d.get("page_content") or "")[:160],
                }
                for i, d in enumerate(docs[:5])
            ]
        details.append(detail)

    metrics = {
        "case_count": len(cases),
        "hit_count": sum(1 for r in ranks if r is not None),
        "mrr": round(mean_reciprocal_rank(ranks), 4),
    }
    for k in k_values:
        metrics[f"recall@{k}"] = round(recall_at_k(ranks, k), 4)

    return {"mode": mode, "metrics": metrics, "cases": details}


def load_golden(path: Path, include_disabled: bool) -> Tuple[Dict[str, Any], List[Dict[str, Any]]]:
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    cases = data.get("cases", [])
    if not include_disabled:
        cases = [c for c in cases if c.get("enabled", True)]
    return data, cases


def parse_args() -> argparse.Namespace:
    yaml_defaults = load_yaml_defaults()
    parser = argparse.ArgumentParser(description="Evaluate retrieval against a golden QA set.")
    parser.add_argument(
        "--golden",
        type=Path,
        default=DEFAULT_GOLDEN,
        help=f"Path to golden JSON (default: {DEFAULT_GOLDEN})",
    )
    parser.add_argument(
        "--mode",
        choices=MODES,
        default="all",
        help="Retrieval stage to evaluate (default: all)",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Milvus search limit (default: from golden JSON or 30)",
    )
    parser.add_argument(
        "--milvus-uri",
        default=os.environ.get("MILVUS_URI") or yaml_defaults.get("milvus_uri") or "http://localhost:19530",
    )
    parser.add_argument(
        "--collection",
        default=os.environ.get("COLLECTION_NAME")
        or yaml_defaults.get("collection")
        or "fragments",
    )
    parser.add_argument(
        "--embedding-url",
        default=os.environ.get("EMBEDDING_URL")
        or yaml_defaults.get("embedding_url")
        or "http://localhost:12356/embeddings",
    )
    parser.add_argument(
        "--rerank-url",
        default=os.environ.get("RERANK_URL")
        or yaml_defaults.get("rerank_url")
        or "http://localhost:12356/rerank",
    )
    parser.add_argument(
        "--report",
        type=Path,
        default=None,
        help="Write full JSON report to this path",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Include top-5 hits per case in report output",
    )
    parser.add_argument(
        "--include-disabled",
        action="store_true",
        help="Run cases with enabled=false (for template debugging)",
    )
    return parser.parse_args()


def print_summary(report: Dict[str, Any]) -> None:
    print(f"\nGolden set: {report['golden_path']}")
    print(f"Cases evaluated: {report['case_count']}")
    print(f"Milvus: {report['milvus_uri']}  collection={report['collection']}")
    print(f"Limit: {report['limit']}  k_values: {report['k_values']}\n")

    header = f"{'Mode':<10}" + "".join(f"  R@{k:<3}" for k in report["k_values"]) + "  MRR    Hits"
    print(header)
    print("-" * len(header))
    for block in report["results"]:
        m = block["metrics"]
        row = f"{block['mode']:<10}"
        for k in report["k_values"]:
            row += f"  {m.get(f'recall@{k}', 0):.3f}"
        row += f"  {m['mrr']:.3f}   {m['hit_count']}/{m['case_count']}"
        print(row)

    if report.get("verbose"):
        print("\n--- Per-case (direct view) ---")
        for block in report["results"]:
            print(f"\n[{block['mode']}]")
            for case in block["cases"]:
                rank_str = str(case["gold_rank"]) if case["gold_rank"] else "miss"
                print(f"  {case['id']}: rank={rank_str}  retrieved={case['retrieved_count']}")
                for hit in case.get("top_hits", []):
                    print(
                        f"    #{hit['rank']} idx={hit['index']} "
                        f"{hit['file_name']!r}  {hit['preview'][:80]!r}..."
                    )


def main() -> int:
    args = parse_args()
    golden_data, cases = load_golden(args.golden, args.include_disabled)

    if not cases:
        print(
            "No enabled cases in golden set. Edit eval/retrieval_golden.json "
            "(set enabled: true and replace placeholders), or pass --include-disabled.",
            file=sys.stderr,
        )
        return 1

    defaults = golden_data.get("defaults", {})
    limit = args.limit if args.limit is not None else defaults.get("limit", 30)
    k_values = defaults.get("k_values", [5, 10, 30])

    modes = list(MODES[:-1]) if args.mode == "all" else [args.mode]
    client = MilvusClient(args.milvus_uri)
    print(
        f"Evaluating {len(cases)} case(s), mode(s): {', '.join(modes)}",
        flush=True,
    )
    if "pipeline" in modes or "rerank" in modes:
        print(
            "Note: pipeline/rerank call the CPU reranker — ~30-90s per case is normal.",
            flush=True,
        )

    report: Dict[str, Any] = {
        "golden_path": str(args.golden),
        "case_count": len(cases),
        "milvus_uri": args.milvus_uri,
        "collection": args.collection,
        "embedding_url": args.embedding_url,
        "rerank_url": args.rerank_url,
        "limit": limit,
        "k_values": k_values,
        "verbose": args.verbose,
        "results": [],
    }

    for mode in modes:
        report["results"].append(
            summarize_mode(
                mode,
                cases,
                k_values,
                client,
                args.collection,
                limit,
                args.embedding_url,
                args.rerank_url,
                args.verbose,
            )
        )

    print_summary(report)

    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        with open(args.report, "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
        print(f"\nReport written to {args.report}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
