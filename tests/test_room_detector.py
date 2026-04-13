"""Tests for mnemos.room_detector — 72+ pattern room detection."""
from __future__ import annotations

from pathlib import Path

import pytest

from mnemos.room_detector import detect_room


# ---------------------------------------------------------------------------
# Folder-path detection tests
# ---------------------------------------------------------------------------


def test_detect_from_folder_path():
    assert detect_room(Path("/project/frontend/App.tsx"), "") == "frontend"


def test_detect_from_nested_folder():
    assert detect_room(Path("/project/api/routes/users.py"), "") == "backend"


def test_detect_backend_src():
    assert detect_room(Path("/project/src/server/index.py"), "") == "backend"


def test_detect_docs_folder():
    assert detect_room(Path("/project/docs/architecture.md"), "") == "documentation"


def test_detect_design_folder():
    assert detect_room(Path("/project/design/wireframes/login.fig"), "") == "design"


def test_detect_costs_folder():
    assert detect_room(Path("/project/costs/q1-budget.xlsx"), "") == "costs"


def test_detect_meetings_folder():
    assert detect_room(Path("/project/meetings/2026-04-10.md"), "") == "meetings"


def test_detect_team_folder():
    assert detect_room(Path("/project/team/onboarding.md"), "") == "team"


def test_detect_research_folder():
    assert detect_room(Path("/project/research/market-analysis.md"), "") == "research"


def test_detect_planning_folder():
    assert detect_room(Path("/project/planning/roadmap.md"), "") == "planning"


def test_detect_testing_folder():
    assert detect_room(Path("/project/tests/test_api.py"), "") == "testing"


def test_detect_scripts_folder():
    assert detect_room(Path("/project/scripts/deploy.sh"), "") == "scripts"


def test_detect_config_folder():
    assert detect_room(Path("/project/config/nginx.conf"), "") == "configuration"


def test_detect_security_folder():
    assert detect_room(Path("/project/security/audit.md"), "") == "security"


# ---------------------------------------------------------------------------
# Case insensitivity and hyphen/underscore normalization
# ---------------------------------------------------------------------------


def test_case_insensitive_folder():
    assert detect_room(Path("/project/Frontend/App.tsx"), "") == "frontend"


def test_hyphen_variant_frontend():
    assert detect_room(Path("/project/front-end/index.html"), "") == "frontend"


def test_underscore_variant_frontend():
    assert detect_room(Path("/project/front_end/index.html"), "") == "frontend"


def test_case_insensitive_backend():
    assert detect_room(Path("/project/BACKEND/api.py"), "") == "backend"


def test_hyphen_variant_backend():
    assert detect_room(Path("/project/back-end/server.py"), "") == "backend"


def test_underscore_variant_backend():
    assert detect_room(Path("/project/back_end/server.py"), "") == "backend"


def test_case_insensitive_testing():
    assert detect_room(Path("/project/TESTS/test_foo.py"), "") == "testing"


def test_hyphen_variant_testing():
    assert detect_room(Path("/project/unit-tests/test_foo.py"), "") == "testing"


# ---------------------------------------------------------------------------
# Keyword scoring tests
# ---------------------------------------------------------------------------


def test_detect_from_keywords():
    text = "We discussed the React component architecture and Tailwind CSS integration."
    assert detect_room(Path("/project/notes/session.md"), text) == "frontend"


def test_detect_from_keyword_scoring():
    text = "Deploy the docker container. Configure kubernetes. Set up the CI/CD pipeline. Terraform init."
    assert detect_room(Path("/project/notes.md"), text) == "configuration"


def test_detect_backend_keywords():
    text = "The REST API endpoint returns JSON. Database query optimization with PostgreSQL indexes."
    assert detect_room(Path("/project/notes.md"), text) == "backend"


def test_detect_documentation_keywords():
    text = "Update the README with installation instructions. Add API reference and changelog entries."
    assert detect_room(Path("/project/notes.md"), text) == "documentation"


def test_detect_design_keywords():
    text = "The wireframe shows a new UI mockup. Typography and color palette defined in Figma."
    assert detect_room(Path("/project/notes.md"), text) == "design"


def test_detect_costs_keywords():
    text = "Monthly budget review shows invoice total. The expense report exceeds our Q1 forecast."
    assert detect_room(Path("/project/notes.md"), text) == "costs"


def test_detect_meetings_keywords():
    text = "Today's standup agenda: sprint review action items. Meeting notes from retrospective."
    assert detect_room(Path("/project/notes.md"), text) == "meetings"


def test_detect_team_keywords():
    text = "Onboarding the new hire. HR submitted the job posting for senior developer recruitment."
    assert detect_room(Path("/project/notes.md"), text) == "team"


def test_detect_research_keywords():
    text = "Literature review of machine learning papers. Hypothesis testing and benchmark analysis."
    assert detect_room(Path("/project/notes.md"), text) == "research"


def test_detect_planning_keywords():
    text = "Q2 roadmap milestones defined. Sprint planning with story points and backlog prioritization."
    assert detect_room(Path("/project/notes.md"), text) == "planning"


def test_detect_testing_keywords():
    text = "Unit test coverage at 85%. Integration tests for the API pass. Regression suite updated."
    assert detect_room(Path("/project/notes.md"), text) == "testing"


def test_detect_scripts_keywords():
    text = "The bash script automates deployment. Python automation script handles file processing."
    assert detect_room(Path("/project/notes.md"), text) == "scripts"


def test_detect_security_keywords():
    text = "Vulnerability assessment found XSS issue. Authentication bypass in the login endpoint."
    assert detect_room(Path("/project/notes.md"), text) == "security"


# ---------------------------------------------------------------------------
# Priority and fallback tests
# ---------------------------------------------------------------------------


def test_fallback_to_general():
    assert detect_room(Path("/random/file.md"), "Nothing specific here.") == "general"


def test_single_keyword_not_enough():
    # Only 1 keyword hit — should not match, falls back to general
    assert detect_room(Path("/project/note.md"), "React is mentioned once.") == "general"


def test_folder_match_beats_keyword():
    # meetings folder beats frontend keywords
    text = "Many react components discussed"
    assert detect_room(Path("/project/meetings/2026-04-10.md"), text) == "meetings"


def test_folder_match_beats_keyword_security():
    # backend folder beats security keywords
    text = "Vulnerability XSS authentication bypass found"
    assert detect_room(Path("/project/backend/api.py"), text) == "backend"


def test_only_first_3000_chars_scored(tmp_path: Path):
    # Keyword hits placed after 3000 chars should not count
    prefix = "x " * 1600  # ~3200 chars, no keywords
    suffix = "React component Tailwind CSS Vue framework TypeScript JSX"
    text = prefix + suffix
    result = detect_room(Path("/project/note.md"), text)
    assert result == "general"


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


def test_empty_path_and_text():
    assert detect_room(Path(""), "") == "general"


def test_root_file_no_folder():
    assert detect_room(Path("/file.md"), "No meaningful content.") == "general"


def test_deep_nested_folder_match():
    # Multiple levels deep — outermost matching segment wins
    assert detect_room(Path("/org/team/backend/src/api/v2/endpoint.py"), "") == "backend"


def test_spec_folder_maps_to_testing():
    assert detect_room(Path("/project/spec/unit/login_spec.rb"), "") == "testing"


def test_infra_folder_maps_to_configuration():
    assert detect_room(Path("/project/infra/terraform/main.tf"), "") == "configuration"


def test_wiki_folder_maps_to_documentation():
    assert detect_room(Path("/project/wiki/setup-guide.md"), "") == "documentation"


def test_hr_folder_maps_to_team():
    assert detect_room(Path("/project/hr/policies.md"), "") == "team"


def test_budget_folder_maps_to_costs():
    assert detect_room(Path("/project/budget/2026-q1.xlsx"), "") == "costs"
