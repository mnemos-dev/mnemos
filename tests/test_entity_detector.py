"""Tests for EntityDetector — two-pass heuristic entity detection."""
from __future__ import annotations

import pytest

from mnemos.entity_detector import EntityDetector


# ---------------------------------------------------------------------------
# Required tests from task spec
# ---------------------------------------------------------------------------


def test_detect_person_by_dialogue():
    text = (
        "> Enver: What about the approval flow?\n"
        "We discussed it with Enver and he said the flow looks good.\n"
        "Enver asked about the timeline.\n"
        "Thanks Enver for the review.\n"
    )
    result = EntityDetector().detect(text)
    assert "Enver" in result["persons"]


def test_detect_project_by_code_refs():
    text = (
        "ProcureTrack uses Next.js 14 with Supabase.\n"
        "We shipped ProcureTrack v2 last week.\n"
        "The ProcureTrack architecture is modular.\n"
        "Run: import ProcureTrack from './lib'\n"
        "Check ProcureTrack.py for details.\n"
    )
    result = EntityDetector().detect(text)
    assert "ProcureTrack" in result["projects"]


def test_ignores_stopwords():
    text = "The Python code uses This and That pattern. The React component works. The The The."
    result = EntityDetector().detect(text)
    assert "The" not in result["persons"] and "The" not in result["projects"]


def test_requires_3_occurrences():
    result = EntityDetector().detect("Alice said hello.")
    assert "Alice" not in result["persons"]


def test_turkish_person_signals():
    text = (
        "Enver Bey toplantida konustu.\n"
        "Enver dedi ki onay akisi hazir.\n"
        "Enver Bey'e sordum, tamam dedi.\n"
        "Enver istedi ki deadline uzasin.\n"
    )
    result = EntityDetector().detect(text)
    assert "Enver" in result["persons"]


def test_empty_text():
    assert EntityDetector().detect("") == {"persons": [], "projects": [], "uncertain": []}


def test_mixed_entities():
    text = (
        "> Tugra: Let's deploy Mnemos today.\n"
        "Tugra said the Mnemos architecture is ready.\n"
        "Tugra asked about the Mnemos v0.1 release.\n"
        "Building Mnemos took two weeks.\n"
        "Tugra wants to ship Mnemos this week.\n"
    )
    result = EntityDetector().detect(text)
    assert "Tugra" in result["persons"]
    assert "Mnemos" in result["projects"]


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


def test_result_keys():
    """Result always has persons, projects, uncertain keys."""
    result = EntityDetector().detect("Hello world.")
    assert set(result.keys()) == {"persons", "projects", "uncertain"}


def test_all_values_are_lists():
    result = EntityDetector().detect("Some random text without entities.")
    assert isinstance(result["persons"], list)
    assert isinstance(result["projects"], list)
    assert isinstance(result["uncertain"], list)


def test_max_persons_limit():
    """No more than 15 persons returned."""
    result = EntityDetector().detect("x" * 10)
    assert len(result["persons"]) <= 15


def test_max_projects_limit():
    """No more than 10 projects returned."""
    result = EntityDetector().detect("x" * 10)
    assert len(result["projects"]) <= 10


def test_max_uncertain_limit():
    """No more than 8 uncertain returned."""
    result = EntityDetector().detect("x" * 10)
    assert len(result["uncertain"]) <= 8


def test_no_duplicates_in_result():
    text = (
        "> Enver: Hello.\n"
        "Enver said hi.\n"
        "Enver told us the plan.\n"
        "Enver asked a question.\n"
    )
    result = EntityDetector().detect(text)
    all_entities = result["persons"] + result["projects"] + result["uncertain"]
    assert len(all_entities) == len(set(all_entities))


def test_short_words_excluded():
    """Words shorter than 3 chars are not candidates."""
    text = "He He He said Hi Hi Hi do do do."
    result = EntityDetector().detect(text)
    assert "He" not in result["persons"]
    assert "Hi" not in result["persons"]


def test_code_import_signal():
    text = (
        "import Falcon from './core'\n"
        "Falcon handles routing.\n"
        "Falcon v1 was released.\n"
        "The Falcon pipeline is modular.\n"
    )
    result = EntityDetector().detect(text)
    assert "Falcon" in result["projects"]


def test_version_signal():
    text = (
        "Mnemos v2 ships today.\n"
        "We built Mnemos-core last month.\n"
        "The Mnemos architecture is sound.\n"
        "Mnemos is reliable.\n"
    )
    result = EntityDetector().detect(text)
    assert "Mnemos" in result["projects"]


def test_pronoun_proximity_person():
    text = (
        "Sara completed the task.\n"
        "Sara said the results look good.\n"
        "she confirmed the approach.\n"
        "Sara will present tomorrow.\n"
    )
    result = EntityDetector().detect(text)
    assert "Sara" in result["persons"]


def test_entity_not_in_multiple_categories():
    """An entity should appear in at most one category."""
    text = (
        "> Tugra: Let's deploy Mnemos today.\n"
        "Tugra said the Mnemos architecture is ready.\n"
        "Tugra asked about the Mnemos v0.1 release.\n"
        "Building Mnemos took two weeks.\n"
        "Tugra wants to ship Mnemos this week.\n"
    )
    result = EntityDetector().detect(text)
    persons = set(result["persons"])
    projects = set(result["projects"])
    uncertain = set(result["uncertain"])
    assert not (persons & projects)
    assert not (persons & uncertain)
    assert not (projects & uncertain)


def test_whitespace_only_text():
    result = EntityDetector().detect("   \n\t\n  ")
    assert result == {"persons": [], "projects": [], "uncertain": []}


def test_programming_keywords_excluded():
    """Common programming keywords should be in stopwords and excluded."""
    text = "The Class method uses Return value. Class was called. Return Return."
    result = EntityDetector().detect(text)
    assert "Class" not in result["persons"] and "Class" not in result["projects"]
    assert "Return" not in result["persons"] and "Return" not in result["projects"]
