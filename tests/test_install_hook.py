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


def test_install_hook_prompt_installs_on_yes(tmp_path, monkeypatch, capsys):
    from mnemos.cli import _install_hook_prompt

    home = tmp_path / "home"
    (home / ".claude").mkdir(parents=True)
    monkeypatch.setattr("pathlib.Path.home", lambda: home)
    monkeypatch.setattr("builtins.input", lambda _: "y")

    _install_hook_prompt(lang="en", vault=tmp_path)
    out = capsys.readouterr().out
    assert "installed" in out.lower() or "kuruldu" in out.lower()


def test_install_hook_prompt_skips_on_no(tmp_path, monkeypatch, capsys):
    from mnemos.cli import _install_hook_prompt

    home = tmp_path / "home"
    (home / ".claude").mkdir(parents=True)
    monkeypatch.setattr("pathlib.Path.home", lambda: home)
    monkeypatch.setattr("builtins.input", lambda _: "n")

    _install_hook_prompt(lang="en", vault=tmp_path)
    out = capsys.readouterr().out
    assert "skipped" in out.lower() or "atlandı" in out.lower() or "install later" in out.lower()


def test_install_hook_writes_managed_by_marker(tmp_path, monkeypatch):
    from mnemos.cli import install_hook, HOOK_MARKER

    home = tmp_path / "home"
    (home / ".claude").mkdir(parents=True)
    monkeypatch.setattr("pathlib.Path.home", lambda: home)

    install_hook(vault=tmp_path, uninstall=False)
    settings = json.loads((home / ".claude" / "settings.json").read_text(encoding="utf-8"))
    entry = settings["hooks"]["SessionStart"][0]
    assert entry["_managed_by"] == HOOK_MARKER
    # Command must NOT have a # comment prefix (cmd.exe would fail on it)
    assert not entry["hooks"][0]["command"].startswith("#")
    assert HOOK_MARKER not in entry["hooks"][0]["command"]


def test_install_hook_uses_cli_arg_no_cmd_wrapper(tmp_path, monkeypatch):
    from mnemos.cli import install_hook

    home = tmp_path / "home"
    (home / ".claude").mkdir(parents=True)
    monkeypatch.setattr("pathlib.Path.home", lambda: home)

    install_hook(vault=tmp_path, uninstall=False)
    settings = json.loads((home / ".claude" / "settings.json").read_text(encoding="utf-8"))
    cmd = settings["hooks"]["SessionStart"][0]["hooks"][0]["command"]
    # No cmd /c wrapper
    assert "cmd /c" not in cmd
    # Vault passed as CLI arg
    assert "--vault" in cmd
    # Script invoked directly
    assert "python " in cmd
    assert "auto_refine_hook.py" in cmd


def test_install_hook_detects_legacy_command_marker(tmp_path, monkeypatch):
    from mnemos.cli import install_hook, HOOK_MARKER

    home = tmp_path / "home"
    (home / ".claude").mkdir(parents=True)
    monkeypatch.setattr("pathlib.Path.home", lambda: home)

    # Simulate a settings.json from the buggy version (marker in command)
    legacy = {
        "hooks": {
            "SessionStart": [{
                "matcher": "",
                "hooks": [{
                    "type": "command",
                    "command": f"# {HOOK_MARKER}\necho legacy",
                    "timeout": 5,
                }],
            }]
        }
    }
    (home / ".claude" / "settings.json").write_text(json.dumps(legacy), encoding="utf-8")

    # Re-running install should detect the legacy entry as already-installed,
    # not stack a second one.
    result = install_hook(vault=tmp_path, uninstall=False)
    assert result.status == "already-installed"

    # Uninstall should also find it.
    result2 = install_hook(vault=tmp_path, uninstall=True)
    assert result2.status == "uninstalled"
