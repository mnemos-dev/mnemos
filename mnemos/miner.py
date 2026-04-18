"""Miner — hybrid regex + LLM mining engine for Mnemos."""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import yaml

from mnemos.config import MnemosConfig
from mnemos.entity_detector import EntityDetector
from mnemos.normalizer import detect_format, normalize_text
from mnemos.obsidian import parse_frontmatter
from mnemos.prose import extract_prose
from mnemos.room_detector import detect_room

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


def _extract_wikilinks(text: str) -> list[str]:
    """Return all [[Target]] wikilink targets from text."""
    return re.findall(r"\[\[([^\]]+)\]\]", text)


# ---------------------------------------------------------------------------
# Exchange-pair chunking
# ---------------------------------------------------------------------------


def chunk_exchanges(transcript: str, max_chunk: int = 800) -> list[str] | None:
    """Split transcript into exchange pairs.

    Returns None if not a conversation (<3 '>' markers).
    Chunk boundary at exchange boundaries.
    If single exchange > max_chunk, split response but keep user question
    in first chunk. Nothing is discarded.

    Default max_chunk=800 to fit within embedding model limits
    (all-MiniLM-L6-v2: 256 tokens ~ 1000 chars).
    """
    # Count '>' markers at line start
    gt_count = sum(1 for line in transcript.splitlines() if line.strip().startswith(">"))
    if gt_count < 3:
        return None

    # Split into exchanges: each exchange starts with a ">" line
    lines = transcript.splitlines()
    exchanges: list[str] = []
    current: list[str] = []

    for line in lines:
        if line.strip().startswith(">") and current:
            exchanges.append("\n".join(current))
            current = [line]
        else:
            current.append(line)
    if current:
        exchanges.append("\n".join(current))

    # Now group exchanges into chunks respecting max_chunk
    chunks: list[str] = []
    buffer = ""

    for exchange in exchanges:
        candidate = (buffer + "\n\n" + exchange).strip() if buffer else exchange
        if len(candidate) <= max_chunk:
            buffer = candidate
        else:
            # If buffer is non-empty, flush it
            if buffer:
                chunks.append(buffer)

            # Check if this single exchange exceeds max_chunk
            if len(exchange) > max_chunk:
                # Split the exchange: find the user question (first > line(s))
                ex_lines = exchange.splitlines()
                user_lines: list[str] = []
                response_lines: list[str] = []
                in_user = True
                for el in ex_lines:
                    if in_user and el.strip().startswith(">"):
                        user_lines.append(el)
                    else:
                        in_user = False
                        response_lines.append(el)

                user_part = "\n".join(user_lines)
                response_text = "\n".join(response_lines)

                # First sub-chunk: user question + beginning of response
                remaining_space = max_chunk - len(user_part) - 2  # for \n\n
                if remaining_space > 0:
                    first_resp = response_text[:remaining_space]
                    chunks.append((user_part + "\n" + first_resp).strip())
                    rest = response_text[remaining_space:]
                else:
                    chunks.append(user_part)
                    rest = response_text

                # Remaining sub-chunks
                while rest:
                    part = rest[:max_chunk]
                    chunks.append(part.strip())
                    rest = rest[max_chunk:]

                buffer = ""
            else:
                buffer = exchange

    if buffer:
        chunks.append(buffer)

    return chunks if chunks else None


# ---------------------------------------------------------------------------
# Segment classification (scoring + disambiguation)
# ---------------------------------------------------------------------------


def classify_segment(
    text: str, language: str, min_confidence: float = 0.3
) -> tuple[str | None, float]:
    """Score text against hall markers, return (hall, confidence).

    1. Count marker hits per hall
    2. Length bonus: >500 char +2, 200-500 +1
    3. Confidence = min(1.0, max_score / 5.0)
    4. Disambiguation: problem + resolution markers → events
    5. Below min_confidence → (None, 0.0)
    """
    pattern_file = _PATTERNS_DIR / f"{language}.yaml"
    if not pattern_file.exists():
        pattern_file = _PATTERNS_DIR / "en.yaml"
    raw = _load_yaml(pattern_file)

    text_lower = text.lower()
    scores: dict[str, int] = {}

    for hall, phrases in raw.items():
        if not isinstance(phrases, list):
            continue
        count = 0
        for phrase in phrases:
            if phrase.lower() in text_lower:
                count += 1
        scores[hall] = count

    # Length bonus
    length_bonus = 0
    if len(text) > 500:
        length_bonus = 2
    elif len(text) >= 200:
        length_bonus = 1

    # Apply length bonus to all halls with hits
    for hall in scores:
        if scores[hall] > 0:
            scores[hall] += length_bonus

    if not scores or max(scores.values()) == 0:
        return (None, 0.0)

    max_score = max(scores.values())
    best_hall = max(scores, key=lambda h: scores[h])
    confidence = min(1.0, max_score / 5.0)

    # Disambiguation: problem + resolution markers → events
    problem_score = scores.get("problems", 0)
    event_score = scores.get("events", 0)
    if problem_score > 0 and event_score > 0:
        # If both problem and event/resolution markers are present, it's an event
        best_hall = "events"
        confidence = min(1.0, (problem_score + event_score) / 5.0)

    if confidence < min_confidence:
        return (None, 0.0)

    return (best_hall, confidence)


# ---------------------------------------------------------------------------
# Miner class
# ---------------------------------------------------------------------------


class Miner:
    """Hybrid regex mining engine.

    Loads language pattern files at init time and uses them to classify
    text paragraphs into hall categories (decisions, facts, events, ...).
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

        # Entity detector instance
        self._entity_detector = EntityDetector()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def mine_file(
        self,
        filepath: Path,
        use_llm: bool = False,
        wing_override: str | None = None,
    ) -> list[dict[str, Any]]:
        """Mine a Markdown file and return a list of memory fragment dicts.

        Each fragment dict has keys:
            wing, room, hall, text, entities, language, source

        If *wing_override* is given it supersedes both the frontmatter
        ``project`` field and any path-derived wing. Used when the project
        is known from the parent directory of the file (e.g. Claude Code
        memory dirs or JSONL transcripts, which carry no frontmatter).
        """
        meta, body = parse_frontmatter(filepath)

        # 1. Detect format
        fmt = detect_format(body)

        # 2. If conversation format → normalize to transcript
        if fmt != "plain_text":
            body = normalize_text(body)

        # 3. Detect language from body
        language = detect_language(body)

        # 4. Wing resolution: explicit override > frontmatter > path > "General"
        if wing_override:
            wing = wing_override
        else:
            wing = meta.get("project") or ""
            if not wing:
                path_entities = extract_entities_from_path(filepath)
                wing = path_entities[0] if path_entities else "General"

        # 5. Room detection via detect_room() only. Frontmatter tags are
        #    NOT promoted to room names — tags describe the note, rooms are
        #    a fixed taxonomy from rooms.yaml (13 categories + "general"
        #    fallback). See v0.3.2 spec problems 4 and 5.
        tags = meta.get("tags") or []
        room = detect_room(filepath, body)

        # Invariant: room must never equal the wing (redundant nesting).
        # If detect_room picked "mnemos" for a file in wing=Mnemos, flatten.
        from mnemos.palace import _normalize_for_match
        if _normalize_for_match(room) == _normalize_for_match(wing):
            room = "general"

        # 6. Entity detection (EntityDetector + merge)
        path_entities = extract_entities_from_path(filepath)
        detected = self._entity_detector.detect(body)
        wikilinks = _extract_wikilinks(body)

        entities: list[str] = list(path_entities)
        entities.extend(detected.get("persons", []))
        entities.extend(detected.get("projects", []))
        # Add wikilinks
        entities.extend(wikilinks)
        # Add frontmatter values
        if meta.get("project"):
            entities.append(str(meta["project"]))
        for tag in tags:
            entities.append(str(tag))
        # Deduplicate, preserve order
        entities = list(dict.fromkeys(entities))

        source = str(filepath)

        # 7. Filter prose (remove code lines)
        prose_body = extract_prose(body)

        # 8. Chunk
        exchange_chunks = chunk_exchanges(prose_body)

        if exchange_chunks is not None:
            # Conversation → exchange-pair chunking
            raw_chunks = exchange_chunks
        else:
            # Non-conversation → paragraph splitting
            paragraphs = [p.strip() for p in re.split(r"\n{2,}", prose_body) if p.strip()]
            raw_chunks = paragraphs if paragraphs else [prose_body]

        # 9. Classify each chunk
        results: list[dict[str, Any]] = []
        for chunk in raw_chunks:
            if not chunk.strip():
                continue
            hall, confidence = classify_segment(chunk, language)
            if hall is None:
                hall = "facts"  # fallback

            results.append(
                {
                    "wing": wing,
                    "room": room,
                    "hall": hall,
                    "text": chunk,
                    "entities": entities,
                    "language": language,
                    "source": source,
                }
            )

        # Fallback: if still no results, chunk whole body as "facts"
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
