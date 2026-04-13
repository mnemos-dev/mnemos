"""LongMemEval benchmark runner.

Orchestrates the full evaluation pipeline:
    1. Load the LongMemEval dataset
    2. Create a temporary vault and initialise MnemosApp (in-memory ChromaDB)
    3. Write conversations as markdown files
    4. Mine all sessions through the full Mnemos pipeline
    5. For each question: search and check whether ground-truth session IDs
       appear in the top-K results
    6. Compute Recall@5, Recall@10, NDCG@10
    7. Save results to benchmarks/results/
"""
from __future__ import annotations

import json
import tempfile
import time
from datetime import datetime
from pathlib import Path
from typing import Any

from benchmarks.longmemeval.dataset import load_dataset
from benchmarks.longmemeval.metrics import aggregate_metrics, ndcg_at_k, recall_at_k

RESULTS_DIR = Path(__file__).parent.parent / "results"

# Retrieval cut-offs
_K5 = 5
_K10 = 10


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------


def run_benchmark(
    mode: str = "combined",
    limit: int = 10,
    subset: str = "longmemeval_s",
    split: str = "test",
    use_llm: bool = False,
    verbose: bool = True,
) -> dict[str, Any]:
    """Run the LongMemEval benchmark and return aggregated metrics.

    Args:
        mode: One of ``raw-only``, ``mined-only``, ``combined``, ``filtered``.
              Controls which ChromaDB collection is queried.
        limit: Maximum number of dataset questions to evaluate (useful for
               quick smoke-tests; set to ``None`` or ``0`` for all).
        subset: Dataset subset name (default ``longmemeval_s``).
        split: Dataset split (default ``test``).
        use_llm: Pass ``True`` to enable LLM-assisted mining (requires the
                 ``llm`` optional dependency and ``ANTHROPIC_API_KEY``).
        verbose: Print progress to stdout.

    Returns:
        Aggregated metrics dict with keys:
            recall_at_5, recall_at_10, ndcg_at_10, total_questions,
            mode, subset, split, elapsed_seconds, timestamp
    """
    _print = print if verbose else lambda *a, **k: None

    _print(f"[benchmark] Loading dataset ({subset}/{split}) …")
    questions = load_dataset(subset=subset, split=split)

    if limit:
        questions = questions[:limit]

    _print(f"[benchmark] Evaluating {len(questions)} questions  mode={mode}")

    # Map mode → collection argument accepted by MnemosApp.handle_search
    _mode_to_collection = {
        "raw-only": "raw",
        "mined-only": "mined",
        "combined": "both",
        "filtered": "both",
    }
    collection = _mode_to_collection.get(mode, "both")

    start = time.perf_counter()
    per_question_results: list[dict] = []

    with tempfile.TemporaryDirectory(prefix="mnemos_bench_", ignore_cleanup_errors=True) as tmp_dir:
        vault_path = Path(tmp_dir)
        _print(f"[benchmark] Temp vault: {vault_path}")

        # ----------------------------------------------------------------
        # Bootstrap MnemosApp with in-memory ChromaDB
        # ----------------------------------------------------------------
        from mnemos.config import MnemosConfig
        from mnemos.server import MnemosApp

        cfg = MnemosConfig(
            vault_path=str(vault_path),
            languages=["en"],
            use_llm=use_llm,
        )
        app = MnemosApp(cfg, chromadb_in_memory=True)
        app.palace.ensure_structure()

        # ----------------------------------------------------------------
        # Write conversations to markdown files and mine them
        # ----------------------------------------------------------------
        sessions_dir = vault_path / "Sessions"
        sessions_dir.mkdir(exist_ok=True)

        _print("[benchmark] Writing and mining sessions …")
        all_session_paths: dict[str, Path] = {}

        for q_idx, question in enumerate(questions):
            for conv in question.get("conversations", []):
                session_id = str(
                    conv.get("session_id") or conv.get("id") or f"session_{q_idx}_{id(conv)}"
                )
                if session_id in all_session_paths:
                    continue  # Already written

                md_path = sessions_dir / f"{session_id}.md"
                md_content = _conversation_to_markdown(session_id, conv)
                md_path.write_text(md_content, encoding="utf-8")
                all_session_paths[session_id] = md_path

        # Mine all sessions in one pass
        mine_result = app.handle_mine(path=str(sessions_dir), use_llm=use_llm)
        _print(
            f"[benchmark] Mining done — scanned={mine_result['files_scanned']} "
            f"drawers={mine_result['drawers_created']} "
            f"skipped={mine_result['skipped']}"
        )

        # ----------------------------------------------------------------
        # Evaluate each question
        # ----------------------------------------------------------------
        for q_idx, question in enumerate(questions, 1):
            query = question["question"]
            ground_truth_ids = question["session_ids"]

            if not query:
                continue

            # Search with K10 to cover both cut-offs
            raw_results = app.handle_search(
                query=query,
                limit=_K10,
                collection=collection,
            )

            # Extract retrieved IDs — prefer source_path, fall back to doc ID
            retrieved_ids = _extract_ids(raw_results, all_session_paths)

            r5 = recall_at_k(retrieved_ids, ground_truth_ids, k=_K5)
            r10 = recall_at_k(retrieved_ids, ground_truth_ids, k=_K10)
            ndcg10 = ndcg_at_k(retrieved_ids, ground_truth_ids, k=_K10)

            per_question_results.append(
                {
                    "question_index": q_idx,
                    "query": query[:120],
                    "ground_truth_ids": ground_truth_ids,
                    "retrieved_ids": retrieved_ids,
                    "recall_at_5": r5,
                    "recall_at_10": r10,
                    "ndcg_at_10": ndcg10,
                }
            )

            if verbose and q_idx % 10 == 0:
                _print(f"  … evaluated {q_idx}/{len(questions)}")

    elapsed = time.perf_counter() - start

    # ----------------------------------------------------------------
    # Aggregate and save
    # ----------------------------------------------------------------
    agg = aggregate_metrics(per_question_results)
    agg.update(
        {
            "mode": mode,
            "subset": subset,
            "split": split,
            "elapsed_seconds": round(elapsed, 2),
            "timestamp": datetime.utcnow().isoformat(timespec="seconds") + "Z",
        }
    )

    _save_results(agg, per_question_results)

    _print(
        f"\n[benchmark] Results — "
        f"Recall@5={agg['recall_at_5']:.4f}  "
        f"Recall@10={agg['recall_at_10']:.4f}  "
        f"NDCG@10={agg['ndcg_at_10']:.4f}  "
        f"N={agg['total_questions']}  "
        f"({elapsed:.1f}s)"
    )

    return agg


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _conversation_to_markdown(session_id: str, conv: dict) -> str:
    """Convert a conversation dict to a markdown string suitable for mining."""
    lines = [
        f"---",
        f"session_id: {session_id}",
        f"type: benchmark_conversation",
        f"---",
        f"",
        f"# Session {session_id}",
        f"",
    ]

    messages = conv.get("messages") or conv.get("turns") or conv.get("content") or []
    if isinstance(messages, str):
        lines.append(messages)
    elif isinstance(messages, list):
        for msg in messages:
            if isinstance(msg, dict):
                role = msg.get("role") or msg.get("speaker") or "user"
                text = msg.get("content") or msg.get("text") or str(msg)
                lines.append(f"**{role}:** {text}")
                lines.append("")
            else:
                lines.append(str(msg))
                lines.append("")
    else:
        lines.append(str(messages))

    return "\n".join(lines)


def _extract_ids(
    search_results: list[dict],
    session_paths: dict[str, Path],
) -> list[str]:
    """Extract session IDs from search results for comparison with ground truth.

    Tries metadata ``source_path`` → derive session ID from filename stem.
    Falls back to the raw document ID stored in the result.
    """
    # Build a reverse map: file stem → session_id
    stem_to_id = {path.stem: sid for sid, path in session_paths.items()}

    ids: list[str] = []
    seen: set[str] = set()

    for result in search_results:
        meta = result.get("metadata") or {}
        source_path = meta.get("source_path") or result.get("source_path") or ""
        if source_path:
            stem = Path(source_path).stem
            sid = stem_to_id.get(stem, stem)
        else:
            # Use the raw document/drawer id if no path available
            sid = result.get("id") or result.get("drawer_id") or str(id(result))

        if sid not in seen:
            seen.add(sid)
            ids.append(sid)

    return ids


def _save_results(agg: dict, per_question: list[dict]) -> None:
    """Persist results to benchmarks/results/ as JSON files."""
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.utcnow().strftime("%Y%m%dT%H%M%S")
    mode = agg.get("mode", "combined")

    summary_path = RESULTS_DIR / f"{ts}_{mode}_summary.json"
    detail_path = RESULTS_DIR / f"{ts}_{mode}_detail.json"

    summary_path.write_text(json.dumps(agg, indent=2, ensure_ascii=False), encoding="utf-8")
    detail_path.write_text(
        json.dumps(per_question, indent=2, ensure_ascii=False), encoding="utf-8"
    )
