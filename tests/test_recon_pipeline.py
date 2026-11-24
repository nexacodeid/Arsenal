from __future__ import annotations

from pathlib import Path
from typing import List

from bb_arsenal.models import Status
from bb_arsenal.recon.pipeline import Pipeline, missing_binaries
from bb_arsenal.recon.stages import STAGES, RunOptions, get_stage, resolve_order
from bb_arsenal.recon.workspace import Workspace


def test_missing_binaries_reports_absent_tools() -> None:
    stage = get_stage("subfinder")
    assert stage is not None
    # subfinder is very unlikely to be installed in a CI/test sandbox.
    assert missing_binaries(stage) in ([], ["subfinder"])


def test_dry_run_previews_every_resolved_stage_without_touching_logs(tmp_path: Path) -> None:
    ws = Workspace("example.com", root=tmp_path)
    pipeline = Pipeline(ws, RunOptions(target="example.com"), dry_run=True)
    results = pipeline.run(["gf"])
    order = resolve_order(["gf"])

    assert [r.name for r in results] == [s.key for s in order]
    assert all(r.status is Status.SKIP and r.detail.startswith("dry-run:") for r in results)
    assert not any(ws.logs.glob("*"))


def test_dry_run_previews_ffuf_without_a_wordlist(tmp_path: Path) -> None:
    ws = Workspace("example.com", root=tmp_path)
    pipeline = Pipeline(ws, RunOptions(target="example.com"), dry_run=True)
    results = pipeline.run(["ffuf"])
    by_name = {r.name: r for r in results}
    assert by_name["ffuf"].status is Status.SKIP
    assert "wordlist" in by_name["ffuf"].detail


def test_missing_tool_is_skipped_not_fatal(tmp_path: Path) -> None:
    ws = Workspace("example.com", root=tmp_path)
    pipeline = Pipeline(ws, RunOptions(target="example.com"))
    results = pipeline.run(["subfinder"])
    assert results[0].name == "subfinder"
    assert results[0].status in (Status.SKIP, Status.OK, Status.FAIL)
    if results[0].status is Status.SKIP:
        assert "missing" in results[0].detail


def test_live_hosts_degrades_gracefully_without_upstream_data(tmp_path: Path) -> None:
    ws = Workspace("example.com", root=tmp_path)
    pipeline = Pipeline(ws, RunOptions(target="example.com"))
    results = pipeline.run(["live_hosts"])
    by_name = {r.name: r for r in results}
    assert by_name["live_hosts"].status is Status.OK
    assert (ws.subdomains / "live.txt").exists()


def test_workspace_is_created_even_for_a_dry_run(tmp_path: Path) -> None:
    ws = Workspace("example.com", root=tmp_path)
    Pipeline(ws, RunOptions(target="example.com"), dry_run=True).run(["subfinder"])
    assert ws.root.is_dir() and ws.subdomains.is_dir()


def test_reporter_receives_every_event(tmp_path: Path) -> None:
    events: List[str] = []

    class Spy:
        def begin(self, stages): events.append("begin")
        def stage_started(self, stage): events.append(f"+{stage.key}")
        def stage_finished(self, stage, result): events.append(f"-{stage.key}")
        def end(self): events.append("end")

    ws = Workspace("example.com", root=tmp_path)
    Pipeline(ws, RunOptions(target="example.com"), Spy(), dry_run=True).run(["subfinder"])
    assert events[0] == "begin" and events[-1] == "end"
    assert "+subfinder" in events and "-subfinder" in events
