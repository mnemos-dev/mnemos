"""EntityDetector — two-pass heuristic person/project detection for Mnemos.

Pass 1: Find capitalized word candidates (3+ chars, 3+ occurrences).
Pass 2: Score each candidate with weighted signals and classify into
        persons / projects / uncertain.

Standalone module — no other Mnemos module dependencies.
"""
from __future__ import annotations

import re
from collections import Counter

# ---------------------------------------------------------------------------
# Stopwords
# ---------------------------------------------------------------------------

_STOPWORDS: frozenset[str] = frozenset(
    {
        # Common English articles / determiners / pronouns / conjunctions
        "The", "This", "That", "These", "Those",
        "And", "But", "For", "Not", "With", "From",
        "Its", "His", "Her", "Our", "Their", "Your",
        "All", "Any", "Each", "Few", "More", "Most",
        "Such", "Some", "Both", "Just", "Into", "Over",
        "After", "Also", "Even", "Then", "Than", "When",
        "What", "Where", "Which", "Who", "How", "Why",
        "Here", "There", "Now", "New", "Last", "Next",
        "First", "Second", "Third", "One", "Two", "Three",
        "Four", "Five", "Six", "Seven", "Eight", "Nine", "Ten",
        # Prepositions / auxiliary verbs
        "Are", "Was", "Were", "Has", "Have", "Had",
        "Can", "Could", "Will", "Would", "Should", "May",
        "Might", "Must", "Shall", "Does", "Did", "Let",
        "Been", "Being", "Get", "Got", "Use", "Used",
        "Make", "Made", "Take", "Keep", "Look", "Come",
        "Going", "Done", "See", "Say", "Said", "Know",
        # Common English nouns / adjectives that appear capitalised mid-sentence
        "Good", "Best", "Long", "High", "Many", "Much",
        "Way", "Day", "Week", "Month", "Year", "Time",
        "Work", "Team", "User", "Data", "Type", "Item",
        "List", "Name", "File", "Path", "Line", "Page",
        "Code", "Test", "Build", "Run", "Set", "Key",
        "Value", "Result", "Error", "Info", "Note", "Doc",
        "Step", "Flow", "Plan", "Task", "Done", "Todo",
        "Issue", "Bug", "Fix", "Change", "Update", "Add",
        "Read", "Write", "Send", "Call", "Return", "Check",
        "Open", "Close", "Start", "Stop", "Init", "Load",
        "Save", "Show", "Hide", "Move", "Copy", "Find",
        "Main", "Base", "Core", "Root", "Home", "View",
        "Model", "Class", "Field", "Table", "Query", "Row",
        "Column", "Index", "Token", "Event", "State", "Store",
        "Config", "Setup", "Install", "Deploy", "Release",
        "Version", "Branch", "Commit", "Push", "Pull", "Merge",
        "Request", "Response", "Header", "Body", "Status",
        "Access", "Auth", "Role", "Policy", "Rule", "Scope",
        "Import", "Export", "Module", "Package", "Library",
        "Function", "Method", "Object", "Array", "String",
        "Number", "Boolean", "Null", "True", "False", "None",
        "Default", "Custom", "Global", "Local", "Static",
        "Public", "Private", "Protected", "Abstract", "Interface",
        "Async", "Await", "Promise", "Callback", "Handler",
        "Component", "Service", "Controller", "Provider",
        "Manager", "Factory", "Builder", "Helper", "Utils",
        "Client", "Server", "Host", "Port", "Api", "Rest",
        "Graph", "Node", "Edge", "Link", "Ref", "Var",
        # Programming languages / frameworks (common capitalized names)
        "Python", "React", "Next", "Node", "Java", "Swift",
        "Kotlin", "Ruby", "Rust", "Scala", "Shell", "Bash",
        "Html", "Css", "Json", "Yaml", "Toml", "Xml",
        "Linux", "Docker", "Nginx", "Redis", "Mongo", "Postgres",
        "Mysql", "Sqlite", "Chrome", "Firefox", "Safari",
        # Turkish common words (capitalized at sentence start)
        "Bir", "Bu", "Ile", "Icin", "Olan", "Gibi", "Daha",
        "Bir", "Karar", "Olan", "Sonra", "Once", "Yani",
        "Veya", "Ama", "Ise", "Iken", "Ile", "Den", "Ten",
        "Dan", "Tan", "Nin", "Nun", "Nun", "Nın", "Nın",
        "Tur", "Tir", "Dir", "Dur", "Var", "Yok", "Hem",
        "Nasil", "Neden", "Hangi", "Bunu", "Buna", "Bunun",
        "Onun", "Ona", "Onu", "Biz", "Siz", "Ben", "Sen",
        "Evet", "Hayir", "Tamam", "Peki", "Tabii", "Artik",
        "Zaten", "Sadece", "Ancak", "Fakat", "Lakin",
        "Toplanti", "Proje", "Sistem", "Dosya", "Klasor",
        "Sunucu", "Veri", "Tablo", "Alan", "Kayit",
        "Kullanici", "Yetki", "Erişim", "Akis", "Onay",
        # Mixed / common proper-noun-looking words to skip
        "Monday", "Tuesday", "Wednesday", "Thursday",
        "Friday", "Saturday", "Sunday",
        "January", "February", "March", "April", "May",
        "June", "July", "August", "September", "October",
        "November", "December",
        "English", "Turkish", "French", "German", "Spanish",
    }
)

# ---------------------------------------------------------------------------
# Regex patterns
# ---------------------------------------------------------------------------

# Capitalized word: starts with uppercase, 3+ total chars
_CAP_WORD = re.compile(r"\b([A-Z][a-zA-Z]{2,})\b")

# ---------------------------------------------------------------------------
# Signal patterns — (pattern, weight)
# ---------------------------------------------------------------------------

# Person signals
_P_DIALOGUE = re.compile(r"^>\s*\w+\s*:")                        # > Name:
_P_SAID_LINE = re.compile(r"\b(\w+)\s+said\b", re.IGNORECASE)   # Name said
_P_ACTION_VERBS = re.compile(
    r"\b(\w+)\s+(?:asked|told|thinks|wants|replied|wrote|mentioned)\b",
    re.IGNORECASE,
)
_P_DIRECT_ADDRESS = re.compile(
    r"\b(?:hey|thanks|thank\s+you|hi|hello|dear)\s+([A-Z][a-zA-Z]{2,})\b",
    re.IGNORECASE,
)
_P_TURKISH_TITLE = re.compile(
    r"\b([A-Z][a-zA-Z]{2,})\s+(?:Bey|Han[iı]m|[Hh]oca(?:m)?)\b"
)
# Turkish: "Enver Bey'e" — apostrophe variant
_P_TURKISH_TITLE_APO = re.compile(
    r"\b([A-Z][a-zA-Z]{2,})\s+(?:Bey|Han[iı]m|[Hh]oca(?:m)?)[''']"
)
# Turkish action verbs near a candidate name (weight 2)
_P_TURKISH_VERBS = re.compile(
    r"\b([A-Z][a-zA-Z]{2,})\s+(?:dedi|istedi|sordu|anlatti|soyledi|konustu|"
    r"bildirdi|belirtti|acikladi|onayladi)\b",
    re.IGNORECASE,
)

# Project signals
_PJ_ARCH_VERBS = re.compile(
    r"\b([A-Z][a-zA-Z]{2,})\s+(?:architecture|pipeline|system|framework|platform)\b"
)
_PJ_VERSION = re.compile(r"\b([A-Z][a-zA-Z]{2,})\s+v\d")
_PJ_HYPHEN_CORE = re.compile(r"\b([A-Z][a-zA-Z]{2,})-(?:core|api|sdk|lib|cli|web|app)\b")
_PJ_CODE_IMPORT = re.compile(r"\bimport\s+([A-Z][a-zA-Z]{2,})\b")
_PJ_DOT_PY = re.compile(r"\b([A-Z][a-zA-Z]{2,})\.py\b")
_PJ_BUILD_VERBS = re.compile(
    r"\b(?:building|built|shipped|deploy|deploying|shipped|launched)\s+([A-Z][a-zA-Z]{2,})\b",
    re.IGNORECASE,
)

# Pronoun proximity — pronouns that suggest nearby word is a person
_PRONOUNS = re.compile(r"\b(?:he|she|they|his|her|their|him|herself|himself)\b", re.IGNORECASE)


# ---------------------------------------------------------------------------
# EntityDetector
# ---------------------------------------------------------------------------


class EntityDetector:
    """Heuristic two-pass person/project entity detector."""

    def detect(self, text: str) -> dict[str, list[str]]:
        """Detect entities in *text*.

        Returns::

            {
                "persons":   [...],   # max 15
                "projects":  [...],   # max 10
                "uncertain": [...],   # max 8
            }
        """
        empty: dict[str, list[str]] = {"persons": [], "projects": [], "uncertain": []}

        if not text or not text.strip():
            return empty

        lines = text.splitlines()

        # -------------------------------------------------------------------
        # Pass 1 — candidates: capitalized words (3+ chars) appearing 3+ times
        # -------------------------------------------------------------------
        all_caps = _CAP_WORD.findall(text)
        freq = Counter(all_caps)
        candidates = [
            word for word, count in freq.items()
            if count >= 3 and word not in _STOPWORDS
        ]

        if not candidates:
            return empty

        # -------------------------------------------------------------------
        # Pass 2 — score each candidate
        # -------------------------------------------------------------------
        persons: list[str] = []
        projects: list[str] = []
        uncertain: list[str] = []

        for candidate in candidates:
            p_score = 0
            p_types: set[str] = set()
            pj_score = 0

            # --- Person signal scoring ---

            # Dialogue: > Candidate: (weight 3)
            for line in lines:
                m = _P_DIALOGUE.match(line.strip())
                if m and candidate in line:
                    p_score += 3
                    p_types.add("dialogue")
                    break

            # "said" / action verbs immediately after candidate (weight 2)
            for m in _P_SAID_LINE.finditer(text):
                if m.group(1) == candidate:
                    p_score += 2
                    p_types.add("action_verb")
                    break
            for m in _P_ACTION_VERBS.finditer(text):
                if m.group(1) == candidate:
                    p_score += 2
                    p_types.add("action_verb")
                    break

            # Direct address: hey/thanks Name (weight 4)
            for m in _P_DIRECT_ADDRESS.finditer(text):
                if m.group(1) == candidate:
                    p_score += 4
                    p_types.add("direct_address")
                    break

            # Turkish title proximity (weight 3)
            for m in _P_TURKISH_TITLE.finditer(text):
                if m.group(1) == candidate:
                    p_score += 3
                    p_types.add("turkish_title")
                    break
            # Apostrophe variant: "Enver Bey'e"
            if "turkish_title" not in p_types:
                for m in _P_TURKISH_TITLE_APO.finditer(text):
                    if m.group(1) == candidate:
                        p_score += 3
                        p_types.add("turkish_title")
                        break

            # Turkish action verbs after candidate (weight 2)
            for m in _P_TURKISH_VERBS.finditer(text):
                if m.group(1) == candidate:
                    p_score += 2
                    p_types.add("turkish_verb")
                    break

            # Pronoun within 3 lines of a line containing the candidate (weight 2)
            for i, line in enumerate(lines):
                if candidate in line:
                    window_start = max(0, i - 3)
                    window_end = min(len(lines), i + 4)
                    window = "\n".join(lines[window_start:window_end])
                    if _PRONOUNS.search(window):
                        p_score += 2
                        p_types.add("pronoun_proximity")
                    break  # score once per candidate

            # --- Project signal scoring ---

            # Architecture / pipeline verbs (weight 2)
            for m in _PJ_ARCH_VERBS.finditer(text):
                if m.group(1) == candidate:
                    pj_score += 2
                    break

            # Version pattern Name v2 (weight 3)
            for m in _PJ_VERSION.finditer(text):
                if m.group(1) == candidate:
                    pj_score += 3
                    break

            # Name-core / Name-api etc. (weight 3)
            for m in _PJ_HYPHEN_CORE.finditer(text):
                if m.group(1) == candidate:
                    pj_score += 3
                    break

            # import Name (weight 3)
            for m in _PJ_CODE_IMPORT.finditer(text):
                if m.group(1) == candidate:
                    pj_score += 3
                    break

            # Name.py (weight 3)
            for m in _PJ_DOT_PY.finditer(text):
                if m.group(1) == candidate:
                    pj_score += 3
                    break

            # building/shipped Name (weight 2)
            for m in _PJ_BUILD_VERBS.finditer(text):
                if m.group(1) == candidate:
                    pj_score += 2
                    break

            # --- Classification ---
            total = p_score + pj_score
            if total == 0:
                uncertain.append(candidate)
                continue

            person_ratio = p_score / total

            if person_ratio >= 0.7 and len(p_types) >= 2 and p_score >= 4:
                persons.append(candidate)
            elif person_ratio >= 0.7 and len(p_types) >= 1 and p_score >= 5:
                persons.append(candidate)
            elif person_ratio <= 0.3 and pj_score >= 4:
                projects.append(candidate)
            else:
                uncertain.append(candidate)

        # Apply max-result limits
        persons = persons[:15]
        projects = projects[:10]
        uncertain = uncertain[:8]

        return {"persons": persons, "projects": projects, "uncertain": uncertain}
