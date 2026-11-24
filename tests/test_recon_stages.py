from __future__ import annotations

from pathlib import Path

from bb_arsenal.recon.stages import DEFAULT_STAGES, STAGES, RunOptions, get_stage, resolve_order
from bb_arsenal.recon.workspace import Workspace, slugify


def test_stage_keys_are_unique() -> None:
    keys = [s.key for s in STAGES]
    assert len(keys) == len(set(keys))


def test_default_stages_exclude_optional() -> None:
    optional = {s.key for s in STAGES if s.optional}
    assert optional.isdisjoint(DEFAULT_STAGES)


def test_dependencies_point_to_real_stages() -> None:
    keys = {s.key for s in STAGES}
    for s in STAGES:
        assert set(s.needs) <= keys, s.key


def test_resolve_order_pulls_in_transitive_dependencies_once() -> None:
    order = resolve_order(["dalfox"])
    keys = [s.key for s in order]
    assert keys.count("dalfox") == 1
    assert "gf" in keys and keys.index("gf") < keys.index("dalfox")
    assert "subfinder" in keys  # transitive: dalfox -> gf -> uro -> merge_urls -> ... -> subfinder


def test_resolve_order_preserves_registry_order() -> None:
    order = resolve_order(["httpx", "subfinder"])
    wanted = {s.key for s in order}
    assert [s.key for s in order] == [s.key for s in STAGES if s.key in wanted]


def test_every_stage_builds_a_syntactically_valid_command(tmp_path: Path) -> None:
    ws = Workspace("example.com", root=tmp_path)
    opt = RunOptions(target="example.com", wordlist=str(tmp_path / "wl.txt"))
    for stage in STAGES:
        kind, payload = stage.build(ws, opt)
        assert kind in ("argv", "shell")
        assert payload


def test_ffuf_requires_a_wordlist(tmp_path: Path) -> None:
    ws = Workspace("example.com", root=tmp_path)
    stage = get_stage("ffuf")
    assert stage is not None
    try:
        stage.build(ws, RunOptions(target="example.com"))
        raise AssertionError("expected ValueError when no wordlist is given")
    except ValueError:
        pass


def test_slugify_is_filesystem_safe() -> None:
    assert "/" not in slugify("https://Example.COM/a:b")
    assert slugify("") == "target"
