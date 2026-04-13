"""Tests for LongMemEval benchmark metrics.

No HuggingFace dependency required — only the metrics module is tested here.
"""
from __future__ import annotations

import pytest

from benchmarks.longmemeval.metrics import aggregate_metrics, ndcg_at_k, recall_at_k


# ---------------------------------------------------------------------------
# recall_at_k
# ---------------------------------------------------------------------------


def test_recall_at_k_hit():
    assert recall_at_k(["a", "b", "c"], ["b"], k=5) == 1.0


def test_recall_at_k_miss():
    assert recall_at_k(["a", "b", "c"], ["z"], k=5) == 0.0


def test_recall_at_k_outside_window():
    # "f" is at rank 6, which is outside the k=3 window
    assert recall_at_k(["a", "b", "c", "d", "e", "f"], ["f"], k=3) == 0.0


def test_recall_at_k_exact_boundary():
    # "c" is at rank 3, which is exactly at k=3
    assert recall_at_k(["a", "b", "c"], ["c"], k=3) == 1.0


def test_recall_at_k_multiple_relevant():
    # Any relevant item in top-K is a hit
    assert recall_at_k(["x", "y", "z"], ["z", "q"], k=3) == 1.0


def test_recall_at_k_empty_retrieved():
    assert recall_at_k([], ["a"], k=5) == 0.0


def test_recall_at_k_empty_relevant():
    assert recall_at_k(["a", "b"], [], k=5) == 0.0


# ---------------------------------------------------------------------------
# ndcg_at_k
# ---------------------------------------------------------------------------


def test_ndcg_perfect():
    # Relevant item at rank 1 → perfect NDCG
    score = ndcg_at_k(["relevant", "other"], ["relevant"], k=5)
    assert score == 1.0


def test_ndcg_lower_rank():
    # Relevant item at rank 2 → score is less than 1 but greater than 0
    score = ndcg_at_k(["other", "relevant"], ["relevant"], k=5)
    assert 0.0 < score < 1.0


def test_ndcg_miss():
    score = ndcg_at_k(["a", "b", "c"], ["z"], k=5)
    assert score == 0.0


def test_ndcg_empty_retrieved():
    assert ndcg_at_k([], ["a"], k=5) == 0.0


def test_ndcg_empty_relevant():
    assert ndcg_at_k(["a", "b"], [], k=5) == 0.0


def test_ndcg_rank1_gt_rank2():
    """Placing the relevant item at rank 1 must score higher than rank 2."""
    score_rank1 = ndcg_at_k(["rel", "other"], ["rel"], k=5)
    score_rank2 = ndcg_at_k(["other", "rel"], ["rel"], k=5)
    assert score_rank1 > score_rank2


def test_ndcg_outside_k():
    # Relevant item beyond cut-off → score = 0
    score = ndcg_at_k(["a", "b", "c", "d", "e", "rel"], ["rel"], k=3)
    assert score == 0.0


# ---------------------------------------------------------------------------
# aggregate_metrics
# ---------------------------------------------------------------------------


def test_aggregate():
    results = [
        {"recall_at_5": 1.0, "recall_at_10": 1.0, "ndcg_at_10": 1.0},
        {"recall_at_5": 0.0, "recall_at_10": 1.0, "ndcg_at_10": 0.5},
    ]
    agg = aggregate_metrics(results)
    assert agg["recall_at_5"] == 0.5
    assert agg["recall_at_10"] == 1.0
    assert agg["ndcg_at_10"] == 0.75
    assert agg["total_questions"] == 2


def test_aggregate_empty():
    agg = aggregate_metrics([])
    assert agg["total_questions"] == 0
    assert agg["recall_at_5"] == 0.0
    assert agg["recall_at_10"] == 0.0
    assert agg["ndcg_at_10"] == 0.0


def test_aggregate_single():
    results = [{"recall_at_5": 1.0, "recall_at_10": 1.0, "ndcg_at_10": 0.63}]
    agg = aggregate_metrics(results)
    assert agg["total_questions"] == 1
    assert agg["recall_at_5"] == 1.0
    assert abs(agg["ndcg_at_10"] - 0.63) < 1e-9


def test_aggregate_all_zeros():
    results = [
        {"recall_at_5": 0.0, "recall_at_10": 0.0, "ndcg_at_10": 0.0},
        {"recall_at_5": 0.0, "recall_at_10": 0.0, "ndcg_at_10": 0.0},
    ]
    agg = aggregate_metrics(results)
    assert agg["recall_at_5"] == 0.0
    assert agg["total_questions"] == 2
