"""Prose extraction — strip code lines, keep human-readable text.

Used by the miner to pre-filter documents before memory mining so that
code snippets, shell commands, and programming constructs don't pollute
the memory graph.
"""
from __future__ import annotations

import re

# ---------------------------------------------------------------------------
# Patterns
# ---------------------------------------------------------------------------

# Fenced code block: ```lang\n ... \n```  (non-greedy, DOTALL)
_FENCE_RE = re.compile(r"```[^\n]*\n.*?```", re.DOTALL)

# Shell command prefixes ($ or bare command names)
_SHELL_PREFIXES = re.compile(
    r"^\s*"
    r"(?:"
    r"\$\s*"                       # $ prefix  ($ git ..., $ npm ...)
    r"|git\s+"                     # git <subcommand>
    r"|npm\s+"                     # npm install / run / ...
    r"|pip(?:3)?\s+"               # pip install
    r"|pip\s+"                     # pip (redundant but explicit)
    r"|cd\s+"                      # cd /some/path
    r"|docker\s+"                  # docker build / run / ...
    r"|yarn\s+"                    # yarn add / install
    r"|make\s+"                    # make build
    r"|cargo\s+"                   # cargo build (Rust)
    r"|go\s+(?:build|run|test|get)"  # go build / run / test / get
    r"|curl\s+"                    # curl http...
    r"|wget\s+"                    # wget http...
    r")",
    re.IGNORECASE,
)

# Programming constructs — lines that *start* with these keywords
_CODE_KEYWORDS_RE = re.compile(
    r"^\s*"
    r"(?:"
    r"import\s+"                   # import os / import sys
    r"|from\s+\S+\s+import\s+"    # from pathlib import Path
    r"|def\s+\w"                   # def foo():
    r"|class\s+\w"                 # class MyClass:
    r"|return\b"                   # return value
    r"|async\s+def\s+\w"          # async def handler():
    r"|@\w+"                       # decorators  @property, @staticmethod
    r"|#!/"                        # shebang  #!/usr/bin/env python
    r"|pass\s*$"                   # pass (standalone)
    r"|break\s*$"                  # break (standalone)
    r"|continue\s*$"               # continue (standalone)
    r"|raise\b"                    # raise SomeError(...)
    r"|yield\b"                    # yield value
    r"|elif\s+"                    # elif condition:
    r"|else\s*:"                   # else:
    r"|except\b"                   # except Exception:
    r"|finally\s*:"               # finally:
    r"|try\s*:"                    # try:
    r"|with\s+\S+.*:\s*$"         # with open(...) as f:
    r"|if\s+.+:\s*$"              # if condition:  (line ending with colon)
    r"|for\s+\w+\s+in\s+"         # for x in iterable:
    r"|while\s+.+:\s*$"           # while condition:
    r")"
)

# Low-alpha threshold — lines with < 40 % alphabetic chars are dropped
_ALPHA_THRESHOLD = 0.40


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def extract_prose(text: str) -> str:
    """Remove code and return human prose.

    Steps:
    1. Remove fenced code blocks (```...```).
    2. Remove shell command lines.
    3. Remove programming-construct lines.
    4. Remove low-alpha lines (< 40 % alphabetic characters).
    5. Collapse runs of blank lines to a single blank line.
    """
    if not text:
        return ""

    # Step 1 — strip fenced code blocks
    text = _FENCE_RE.sub("", text)

    # Step 2-4 — filter line-by-line
    kept: list[str] = []
    for line in text.splitlines():
        if _is_code_line(line):
            continue
        kept.append(line)

    # Step 5 — collapse multiple blank lines into one
    result = "\n".join(kept)
    result = re.sub(r"\n{3,}", "\n\n", result)

    return result.strip()


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _is_code_line(line: str) -> bool:
    """Return True if *line* should be removed (it looks like code)."""
    stripped = line.strip()

    # Empty lines are kept (they separate paragraphs)
    if not stripped:
        return False

    # Shell prefix match
    if _SHELL_PREFIXES.match(line):
        return True

    # Programming keyword match
    if _CODE_KEYWORDS_RE.match(line):
        return True

    # Low-alpha ratio check
    alpha_count = sum(1 for ch in stripped if ch.isalpha())
    if len(stripped) > 0 and (alpha_count / len(stripped)) < _ALPHA_THRESHOLD:
        return True

    return False
