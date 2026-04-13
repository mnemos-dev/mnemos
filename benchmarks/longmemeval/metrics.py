"""LongMemEval benchmark metrics — Recall@K and NDCG@K with binary relevance."""
from __future__ import annotations

import math


def recall_at_k(retrieved_ids: list[str], relevant_ids: list[str], k: int) -> float:
    """Binary recall: 1.0 if any relevant item appears in the top-K results, else 0.0.

    Args:
        retrieved_ids: Ordered list of retrieved document IDs (most relevant first).
        relevant_ids: Ground-truth relevant document IDs.
        k: Cut-off rank.

    Returns:
        1.0 if at least one relevant ID is in retrieved_ids[:k], else 0.0.
    """
    if not relevant_ids or not retrieved_ids:
        return 0.0
    top_k = set(retrieved_ids[:k])
    for rid in relevant_ids:
        if rid in top_k:
            return 1.0
    return 0.0


def ndcg_at_k(retrieved_ids: list[str], relevant_ids: list[str], k: int) -> float:
    """NDCG@K with binary relevance.

    Each retrieved item has gain 1 if it is relevant, 0 otherwise.
    The ideal DCG is computed assuming the best possible ordering (all relevant
    items placed at the top).

    Args:
        retrieved_ids: Ordered list of retrieved document IDs (most relevant first).
        relevant_ids: Ground-truth relevant document IDs.
        k: Cut-off rank.

    Returns:
        NDCG score in [0.0, 1.0].
    """
    if not relevant_ids or not retrieved_ids:
        return 0.0

    relevant_set = set(relevant_ids)

    # DCG — actual ranking
    dcg = 0.0
    for rank, doc_id in enumerate(retrieved_ids[:k], start=1):
        if doc_id in relevant_set:
            dcg += 1.0 / math.log2(rank + 1)

    # IDCG — ideal ranking (place all relevant items first)
    ideal_hits = min(len(relevant_set), k)
    idcg = sum(1.0 / math.log2(rank + 1) for rank in range(1, ideal_hits + 1))

    if idcg == 0.0:
        return 0.0

    return dcg / idcg


def aggregate_metrics(results: list[dict]) -> dict:
    """Average per-question metrics across all questions.

    Each element of *results* must contain at least:
        recall_at_5, recall_at_10, ndcg_at_10

    Returns:
        dict with keys: recall_at_5, recall_at_10, ndcg_at_10, total_questions
    """
    if not results:
        return {
            "recall_at_5": 0.0,
            "recall_at_10": 0.0,
            "ndcg_at_10": 0.0,
            "total_questions": 0,
        }

    n = len(results)
    return {
        "recall_at_5": sum(r.get("recall_at_5", 0.0) for r in results) / n,
        "recall_at_10": sum(r.get("recall_at_10", 0.0) for r in results) / n,
        "ndcg_at_10": sum(r.get("ndcg_at_10", 0.0) for r in results) / n,
        "total_questions": n,
    }
