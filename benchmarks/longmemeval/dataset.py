"""LongMemEval dataset downloader and parser.

Install the optional benchmark dependency before using this module:

    pip install "mnemos-dev[benchmark]"
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

DATASET_DIR = Path(__file__).parent / "data"
HF_REPO = "xiaowu0162/LongMemEval"

# The dataset has several splits; we default to the *combined* test split.
_DEFAULT_SPLIT = "test"
# Parquet files are named like this inside the HF dataset repository.
_DEFAULT_SUBSET = "longmemeval_s"


def download_dataset(subset: str = _DEFAULT_SUBSET) -> Path:
    """Download the LongMemEval dataset from HuggingFace if not already cached.

    Requires the ``huggingface_hub`` package (install via ``pip install
    'mnemos-dev[benchmark]'``).

    Args:
        subset: Dataset subset name (default: ``longmemeval_s``).

    Returns:
        Path to the local data directory containing the downloaded files.
    """
    try:
        from huggingface_hub import snapshot_download
    except ImportError as exc:
        raise ImportError(
            "huggingface_hub is required for benchmark downloads.\n"
            "Install with: pip install 'mnemos-dev[benchmark]'"
        ) from exc

    DATASET_DIR.mkdir(parents=True, exist_ok=True)
    local_dir = DATASET_DIR / subset

    if local_dir.exists() and any(local_dir.iterdir()):
        return local_dir

    print(f"[benchmark] Downloading {HF_REPO} ({subset}) …")
    snapshot_download(
        repo_id=HF_REPO,
        repo_type="dataset",
        local_dir=str(local_dir),
        ignore_patterns=["*.gitattributes", ".git*"],
    )
    print(f"[benchmark] Downloaded to {local_dir}")
    return local_dir


def load_dataset(
    subset: str = _DEFAULT_SUBSET,
    split: str = _DEFAULT_SPLIT,
    auto_download: bool = True,
) -> list[dict[str, Any]]:
    """Load and parse the LongMemEval dataset.

    Each returned item is a dict with keys:
        question      (str)   — the benchmark question
        answer        (str)   — ground-truth answer
        session_ids   (list)  — IDs of sessions that contain the answer
        conversations (list)  — list of {session_id, messages} dicts

    Args:
        subset: Dataset subset (default: ``longmemeval_s``).
        split: Dataset split, e.g. ``"test"`` (default).
        auto_download: If True (default) download the dataset when missing.

    Returns:
        List of parsed question dicts.
    """
    local_dir = DATASET_DIR / subset

    if auto_download and (not local_dir.exists() or not any(local_dir.iterdir())):
        download_dataset(subset=subset)

    # Try to load a JSONL file first (common HF format for this dataset).
    for candidate in [
        local_dir / f"{split}.jsonl",
        local_dir / f"{split}.json",
        local_dir / "data" / f"{split}.jsonl",
        local_dir / "data" / f"{split}.json",
    ]:
        if candidate.exists():
            return _parse_jsonl(candidate)

    # Fall back: try every .jsonl / .json in the directory tree.
    for path in sorted(local_dir.rglob("*.jsonl")):
        return _parse_jsonl(path)
    for path in sorted(local_dir.rglob("*.json")):
        return _parse_json(path)

    raise FileNotFoundError(
        f"No dataset files found in {local_dir}.\n"
        "Run download_dataset() first or check the subset/split names."
    )


# ---------------------------------------------------------------------------
# Internal parsers
# ---------------------------------------------------------------------------


def _parse_jsonl(path: Path) -> list[dict[str, Any]]:
    """Parse a JSONL file into a list of normalised question dicts."""
    items: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            raw = json.loads(line)
            items.append(_normalise(raw))
    return items


def _parse_json(path: Path) -> list[dict[str, Any]]:
    """Parse a JSON array file into a list of normalised question dicts."""
    with path.open("r", encoding="utf-8") as fh:
        data = json.load(fh)
    if isinstance(data, list):
        return [_normalise(item) for item in data]
    # Some splits store data under a key
    for key in ("data", "examples", "questions"):
        if key in data and isinstance(data[key], list):
            return [_normalise(item) for item in data[key]]
    raise ValueError(f"Unexpected JSON structure in {path}")


def _normalise(raw: dict[str, Any]) -> dict[str, Any]:
    """Map raw dataset fields to a canonical schema."""
    # LongMemEval uses various field names; we normalise them here.
    question = (
        raw.get("question")
        or raw.get("query")
        or raw.get("q")
        or ""
    )
    answer = (
        raw.get("answer")
        or raw.get("ground_truth")
        or raw.get("a")
        or ""
    )
    # session_ids may be a list or a single string
    raw_session_ids = (
        raw.get("session_ids")
        or raw.get("relevant_session_ids")
        or raw.get("evidence_session_ids")
        or []
    )
    if isinstance(raw_session_ids, str):
        raw_session_ids = [raw_session_ids]

    conversations = raw.get("conversations") or raw.get("sessions") or []

    return {
        "question": question,
        "answer": answer,
        "session_ids": list(raw_session_ids),
        "conversations": conversations,
        # Preserve original fields for debugging
        "_raw": raw,
    }
