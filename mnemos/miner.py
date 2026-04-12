"""Miner — hybrid regex + LLM mining engine for Mnemos."""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import yaml

from mnemos.config import MnemosConfig
from mnemos.obsidian import parse_frontmatter

# ---------------------------------------------------------------------------
# Pattern directory
# ---------------------------------------------------------------------------

_PATTERNS_DIR = Path(__file__).parent / "patterns"

# ---------------------------------------------------------------------------
# Turkish marker sets (for language detection)
# ---------------------------------------------------------------------------

_TR_CHARS = set("çğıöşüÇĞİÖŞÜ")
_TR_WORDS = {"ve", "ile", "bir", "icin", "için", "karar", "olan", "gibi", "daha", "bu"}


# ---------------------------------------------------------------------------
# Module-level helpers
# ---------------------------------------------------------------------------


def detect_language(text: str) -> str:
    """Return "tr" or "en".

    Counts Turkish-specific characters and common Turkish words.
    If combined score > 5 % of total word count → "tr".
    """
    words = text.split()
    if not words:
        return "en"

    word_count = len(words)

    # Count Turkish characters
    char_score = sum(1 for ch in text if ch in _TR_CHARS)

    # Count Turkish keyword hits (case-insensitive, whole-word)
    word_score = sum(1 for w in words if w.lower().strip(".,!?;:") in _TR_WORDS)

    # Normalise: char_score over total chars, then scale to word units
    total_chars = max(len(text), 1)
    normalised_char = (char_score / total_chars) * word_count

    combined = normalised_char + word_score
    threshold = word_count * 0.05

    return "tr" if combined > threshold else "en"


def chunk_text(
    text: str,
    chunk_size: int = 800,
    overlap: int = 100,
    min_size: int = 50,
) -> list[str]:
    """Split *text* into overlapping chunks.

    - Text below *min_size* → empty list.
    - Text shorter than *chunk_size* → single-element list.
    - Otherwise, slide a window with *overlap* characters of overlap.
    """
    if len(text) < min_size:
        return []

    if len(text) <= chunk_size:
        return [text]

    chunks: list[str] = []
    start = 0
    while start < len(text):
        end = start + chunk_size
        chunk = text[start:end]
        chunks.append(chunk)
        if end >= len(text):
            break
        start = end - overlap

    return chunks


def extract_entities_from_path(filepath: Path) -> list[str]:
    """Find CamelCase words and capitalised words (3+ chars) in *filepath* stem."""
    stem = filepath.stem  # e.g. "2026-04-10-ProcureTrack"

    entities: list[str] = []

    # CamelCase: split on uppercase boundaries
    # Find runs that look like CamelCase tokens (contain embedded uppercase)
    camel_pattern = re.compile(r"[A-Z][a-z]+(?:[A-Z][a-z]+)+")
    entities.extend(camel_pattern.findall(stem))

    # Individual capitalised words >= 3 chars (not already covered by camel)
    cap_pattern = re.compile(r"[A-Z][a-zA-Z]{2,}")
    for match in cap_pattern.finditer(stem):
        word = match.group()
        # Skip if it's a sub-string of a camel entity we already have
        if not any(word in e for e in entities):
            entities.append(word)

    return list(dict.fromkeys(entities))  # deduplicate, preserve order


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _load_yaml(path: Path) -> dict[str, Any]:
    """Load a YAML file and return its contents as a dict."""
    with path.open("r", encoding="utf-8") as fh:
        return yaml.safe_load(fh) or {}


def _build_pattern_map(
    lang_patterns: dict[str, Any],
) -> dict[str, list[re.Pattern[str]]]:
    """Compile language hall patterns into a dict of {hall: [Pattern]}."""
    compiled: dict[str, list[re.Pattern[str]]] = {}
    for hall, phrases in lang_patterns.items():
        if isinstance(phrases, list):
            compiled[hall] = [
                re.compile(re.escape(phrase), re.IGNORECASE) for phrase in phrases
            ]
    return compiled


def _score_room(body: str, language: str) -> str:
    """Guess a room name from the first H2 heading found in the body."""
    heading_match = re.search(r"^##\s+(.+)", body, re.MULTILINE)
    if heading_match:
        # Normalise: lowercase, replace spaces with hyphens
        return heading_match.group(1).strip().lower().replace(" ", "-")
    return "general"


def _extract_wikilinks(text: str) -> list[str]:
    """Return all [[Target]] wikilink targets from text."""
    return re.findall(r"\[\[([^\]]+)\]\]", text)


# ---------------------------------------------------------------------------
# Miner class
# ---------------------------------------------------------------------------


class Miner:
    """Hybrid regex mining engine.

    Loads language pattern files at init time and uses them to classify
    text paragraphs into hall categories (decisions, facts, events, …).
    """

    def __init__(self, config: MnemosConfig) -> None:
        self.config = config

        # Map: lang → {hall → [Pattern]}
        self._lang_patterns: dict[str, dict[str, list[re.Pattern[str]]]] = {}

        for lang in config.languages:
            pattern_file = _PATTERNS_DIR / f"{lang}.yaml"
            if pattern_file.exists():
                raw = _load_yaml(pattern_file)
                self._lang_patterns[lang] = _build_pattern_map(raw)

        # Base patterns (dates, entities) — always loaded
        base_file = _PATTERNS_DIR / "base.yaml"
        self._base: dict[str, Any] = _load_yaml(base_file) if base_file.exists() else {}

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def mine_file(self, filepath: Path, use_llm: bool = False) -> list[dict[str, Any]]:
        """Mine a Markdown file and return a list of memory fragment dicts.

        Each fragment dict has keys:
            wing, room, hall, text, entities, language, source
        """
        meta, body = parse_frontmatter(filepath)

        # Detect language from body
        language = detect_language(body)

        # --- Wing resolution ---
        # 1. frontmatter "project" field
        # 2. CamelCase entities from filepath
        # 3. fallback "General"
        wing: str = meta.get("project") or ""
        if not wing:
            path_entities = extract_entities_from_path(filepath)
            wing = path_entities[0] if path_entities else "General"

        # --- Room resolution ---
        # 1. first item of frontmatter "tags" list
        # 2. first H2 heading
        # 3. fallback "general"
        tags = meta.get("tags") or []
        if isinstance(tags, list) and tags:
            room = str(tags[0])
        else:
            room = _score_room(body, language)

        # --- Entity extraction ---
        # From path + frontmatter values + wikilinks in body
        entities: list[str] = extract_entities_from_path(filepath)
        # Add wikilinks
        entities.extend(_extract_wikilinks(body))
        # Add string values from meta (project, tags items)
        if meta.get("project"):
            entities.append(str(meta["project"]))
        for tag in tags:
            entities.append(str(tag))
        # Deduplicate
        entities = list(dict.fromkeys(entities))

        source = str(filepath)

        # --- Regex mining per paragraph ---
        paragraphs = [p.strip() for p in re.split(r"\n{2,}", body) if p.strip()]
        results: list[dict[str, Any]] = []

        patterns = self._lang_patterns.get(language, {})

        for para in paragraphs:
            hall = self._classify_paragraph(para, patterns)
            if hall:
                results.append(
                    {
                        "wing": wing,
                        "room": room,
                        "hall": hall,
                        "text": para,
                        "entities": entities,
                        "language": language,
                        "source": source,
                    }
                )

        # --- Fallback: chunk whole body as "facts" if no regex hits ---
        if not results:
            chunks = chunk_text(body)
            if not chunks:
                chunks = [body]
            for chunk in chunks:
                results.append(
                    {
                        "wing": wing,
                        "room": room,
                        "hall": "facts",
                        "text": chunk,
                        "entities": entities,
                        "language": language,
                        "source": source,
                    }
                )

        return results

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _classify_paragraph(
        self,
        text: str,
        patterns: dict[str, list[re.Pattern[str]]],
    ) -> str | None:
        """Return the first hall whose patterns match *text*, or None."""
        for hall, compiled_patterns in patterns.items():
            for pattern in compiled_patterns:
                if pattern.search(text):
                    return hall
        return None
