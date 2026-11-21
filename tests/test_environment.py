from __future__ import annotations

import os
from pathlib import Path

import pytest

from bb_arsenal.environment import Environment
from bb_arsenal.models import Kind, ToolSpec


def test_ensure_path_appends_once(env: Environment, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PATH", "/usr/bin")
    rc = tmp_path / ".bashrc"
    rc.write_text("alias ll='ls -l'")

    assert env.ensure_path() == [str(rc)]
    assert env.ensure_path() == []  # idempotent

    text = rc.read_text()
    assert text.count("go/bin") == 1
    assert text.startswith("alias ll='ls -l'\n")
    assert env.go_bin() in os.environ["PATH"].split(os.pathsep)


def test_zshrc_is_only_touched_when_present(env: Environment, tmp_path: Path) -> None:
    env.ensure_path()
    assert not (tmp_path / ".zshrc").exists()


def test_data_only_tool_detects_gf_patterns(env: Environment, tmp_path: Path) -> None:
    spec = ToolSpec("gf-patterns", Kind.GIT, "https://example.com/x", "urls")
    assert not env.is_installed(spec)
    (tmp_path / ".gf").mkdir()
    (tmp_path / ".gf" / "xss.json").write_text("{}")
    assert env.is_installed(spec)


def test_wake_lock_is_a_noop_off_termux(env: Environment) -> None:
    env.termux = False
    with env.wake_lock():
        pass
