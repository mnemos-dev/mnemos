import json


def test_install_hook_adds_entry_to_empty_settings(tmp_path, monkeypatch):
    from mnemos.cli import install_hook

    home = tmp_path / "home"
    (home / ".claude").mkdir(parents=True)
    monkeypatch.setattr("pathlib.Path.home", lambda: home)

    result = install_hook(vault=tmp_path, uninstall=False)
    settings = json.loads((home / ".claude" / "settings.json").read_text(encoding="utf-8"))
    assert "hooks" in settings
    assert "SessionStart" in settings["hooks"]
    assert result.status == "installed"


def test_install_hook_idempotent(tmp_path, monkeypatch):
    from mnemos.cli import install_hook

    home = tmp_path / "home"
    (home / ".claude").mkdir(parents=True)
    monkeypatch.setattr("pathlib.Path.home", lambda: home)

    install_hook(vault=tmp_path, uninstall=False)
    result2 = install_hook(vault=tmp_path, uninstall=False)
    assert result2.status == "already-installed"


def test_install_hook_uninstall_removes_entry(tmp_path, monkeypatch):
    from mnemos.cli import install_hook

    home = tmp_path / "home"
    (home / ".claude").mkdir(parents=True)
    monkeypatch.setattr("pathlib.Path.home", lambda: home)

    install_hook(vault=tmp_path, uninstall=False)
    result = install_hook(vault=tmp_path, uninstall=True)
    assert result.status == "uninstalled"
    settings = json.loads((home / ".claude" / "settings.json").read_text(encoding="utf-8"))
    assert "mnemos-auto-refine" not in json.dumps(settings)


def test_install_hook_preserves_existing_settings(tmp_path, monkeypatch):
    from mnemos.cli import install_hook

    home = tmp_path / "home"
    (home / ".claude").mkdir(parents=True)
    monkeypatch.setattr("pathlib.Path.home", lambda: home)

    settings_path = home / ".claude" / "settings.json"
    settings_path.write_text(
        json.dumps({"hooks": {"Stop": [{"matcher": "", "hooks": []}]}, "theme": "dark"}),
        encoding="utf-8",
    )

    install_hook(vault=tmp_path, uninstall=False)
    settings = json.loads(settings_path.read_text(encoding="utf-8"))
    assert settings["theme"] == "dark"
    assert "Stop" in settings["hooks"]
    assert "SessionStart" in settings["hooks"]
