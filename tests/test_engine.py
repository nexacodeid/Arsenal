from __future__ import annotations

import json
from pathlib import Path
from typing import List, Tuple

import pytest

from bb_arsenal import engine as engine_mod
from bb_arsenal.engine import Engine, summarize, write_report
from bb_arsenal.environment import Environment
from bb_arsenal.models import Kind, Result, Status, ToolSpec

from conftest import FakeInstaller


def make_engine(env: Environment, tmp_path: Path, outcomes: dict, **kwargs) -> Tuple[Engine, FakeInstaller]:
    fake = FakeInstaller(env, tmp_path, outcomes)
    eng = Engine(env, installers={kind: fake for kind in Kind}, logdir=tmp_path,
                 retry_delay=0, **kwargs)
    return eng, fake


@pytest.fixture(autouse=True)
def _no_system_packages(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(engine_mod, "install_system_packages",
                        lambda env, packages, logdir: Result("system-packages", Status.OK))


def specs(*names: str) -> List[ToolSpec]:
    return [ToolSpec(n, Kind.GO, f"example.com/{n}@latest", "recon") for n in names]


def test_results_follow_input_order(env: Environment, tmp_path: Path) -> None:
    eng, _ = make_engine(env, tmp_path, {}, workers=3)
    results = eng.run(specs("a", "b", "c"))
    assert [r.name for r in results] == ["system-packages", "a", "b", "c"]


def test_failed_install_is_retried_then_succeeds(env: Environment, tmp_path: Path) -> None:
    eng, fake = make_engine(env, tmp_path, {"a": [Status.FAIL, Status.OK]}, retries=2)
    results = eng.run(specs("a"))
    assert results[1].status is Status.OK
    assert fake.calls == ["a", "a"]


def test_persistent_failure_is_reported(env: Environment, tmp_path: Path) -> None:
    eng, fake = make_engine(env, tmp_path, {"a": [Status.FAIL]}, retries=3)
    results = eng.run(specs("a"))
    assert results[1].status is Status.FAIL
    assert len(fake.calls) == 3


def test_skip_is_not_retried(env: Environment, tmp_path: Path) -> None:
    eng, fake = make_engine(env, tmp_path, {"a": [Status.SKIP]}, retries=3)
    eng.run(specs("a"))
    assert fake.calls == ["a"]


def test_crashing_installer_does_not_abort_batch(env: Environment, tmp_path: Path) -> None:
    eng, fake = make_engine(env, tmp_path, {}, retries=1)

    def boom(spec: ToolSpec) -> Result:
        if spec.name == "a":
            raise RuntimeError("kaboom")
        return Result(spec.name, Status.OK)

    fake.install = boom  # type: ignore[method-assign]
    results = eng.run(specs("a", "b"))
    assert [r.status for r in results[1:]] == [Status.FAIL, Status.OK]
    assert "kaboom" in results[1].detail


def test_dry_run_executes_nothing(env: Environment, tmp_path: Path) -> None:
    eng, fake = make_engine(env, tmp_path, {}, dry_run=True)
    results = eng.run(specs("a", "b"))
    assert fake.calls == []
    assert all(r.status is Status.SKIP and r.detail.startswith("dry-run:") for r in results)
    assert len(results) == 2


def test_workers_are_clamped(env: Environment, tmp_path: Path) -> None:
    assert make_engine(env, tmp_path, {}, workers=99)[0].workers == engine_mod.MAX_WORKERS
    assert make_engine(env, tmp_path, {}, workers=0)[0].workers == 1


def test_reporter_receives_every_event(env: Environment, tmp_path: Path) -> None:
    events: List[str] = []

    class Spy:
        def begin(self, s): events.append("begin")
        def system_started(self): events.append("sys+")
        def system_finished(self, r): events.append("sys-")
        def tool_started(self, s): events.append(f"+{s.name}")
        def tool_finished(self, s, r): events.append(f"-{s.name}")
        def end(self): events.append("end")

    fake = FakeInstaller(env, tmp_path, {})
    Engine(env, Spy(), installers={k: fake for k in Kind}, logdir=tmp_path).run(specs("a"))
    assert events == ["begin", "sys+", "sys-", "+a", "-a", "end"]


def test_report_is_valid_json(tmp_path: Path) -> None:
    path = write_report([Result("a", Status.OK, 1.5, "log", "fine")], tmp_path)
    data = json.loads(path.read_text())
    assert data == [{"name": "a", "status": "ok", "elapsed": 1.5, "log": "log", "detail": "fine"}]


def test_summarize_counts_each_status() -> None:
    counts = summarize([Result("a", Status.OK), Result("b", Status.OK), Result("c", Status.FAIL)])
    assert counts == {Status.OK: 2, Status.FAIL: 1, Status.SKIP: 0}
