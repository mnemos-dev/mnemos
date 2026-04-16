"""Tests for `cmd_search` formatting — surfaces metadata.wing / metadata.hall.

The 3.9 new-user pilot caught a long-standing display bug: the formatter read
`r.get("wing")` / `r.get("hall")`, but search results put those keys under
`metadata`, so every CLI search printed `wing=?  hall=?`. This module locks
down the corrected behavior so it can't regress.
"""
from __future__ import annotations

import argparse
from types import SimpleNamespace
from unittest.mock import patch


def _fake_results():
    return [
        {
            "drawer_id": "d1",
            "text": "first hit body",
            "metadata": {"wing": "alpha", "hall": "decisions", "room": "auth"},
            "score": 0.42,
        },
        {
            "drawer_id": "d2",
            "text": "second hit body",
            "metadata": {"wing": "beta", "hall": "facts"},
            "score": 0.31,
        },
    ]


def _run_cmd_search(tmp_path, capsys):
    """Invoke cmd_search with a mocked MnemosApp; return captured stdout."""
    # Prepare a vault dir so _resolve_vault doesn't bail.
    (tmp_path / "mnemos.yaml").write_text(
        "vault_path: " + str(tmp_path).replace("\\", "/") + "\n"
        "languages: [en]\n"
        "use_llm: false\n"
        "halls: [decisions, facts]\n"
        "watcher_ignore: []\n",
        encoding="utf-8",
    )

    args = argparse.Namespace(
        vault=str(tmp_path), query="anything", wing=None, hall=None, limit=5,
    )

    fake_app = SimpleNamespace(handle_search=lambda **kw: _fake_results())

    from mnemos import cli as cli_mod

    with patch.object(cli_mod, "load_config", lambda _vp: SimpleNamespace(vault_path=str(tmp_path))):
        with patch("mnemos.server.MnemosApp", lambda _cfg: fake_app):
            cli_mod.cmd_search(args)

    return capsys.readouterr().out


def test_cmd_search_renders_metadata_wing_and_hall(tmp_path, capsys):
    """The formatter must surface the wing + hall stored under `metadata`."""
    out = _run_cmd_search(tmp_path, capsys)
    assert "wing=alpha" in out, f"expected wing=alpha in output, got:\n{out}"
    assert "hall=decisions" in out, f"expected hall=decisions in output, got:\n{out}"
    assert "wing=beta" in out
    assert "hall=facts" in out
    # Should never print '?' when metadata has the keys.
    assert "wing=?" not in out
    assert "hall=?" not in out


def test_cmd_search_falls_back_to_question_mark_when_metadata_missing(tmp_path, capsys):
    """If metadata is absent (older indexes), the formatter must still render `?` placeholders."""
    args = argparse.Namespace(
        vault=str(tmp_path), query="x", wing=None, hall=None, limit=1,
    )
    fake_app = SimpleNamespace(handle_search=lambda **kw: [{"text": "no meta", "score": 0.1}])
    from mnemos import cli as cli_mod
    with patch.object(cli_mod, "load_config", lambda _vp: SimpleNamespace(vault_path=str(tmp_path))):
        with patch("mnemos.server.MnemosApp", lambda _cfg: fake_app):
            cli_mod.cmd_search(args)
    out = capsys.readouterr().out
    assert "wing=?" in out
    assert "hall=?" in out
