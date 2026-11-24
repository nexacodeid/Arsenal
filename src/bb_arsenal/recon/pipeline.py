"""Executes a recon pipeline: resolves dependencies, runs each stage, reports progress.

No stage failure is fatal to the batch — a missing tool or an empty upstream
file degrades a stage to ``skip``/``ok-with-nothing-found`` rather than
aborting the run, so one missing binary never blocks the rest of recon.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import time
from pathlib import Path
from typing import List, Optional, Protocol, Sequence

from ..environment import Environment
from ..models import Result, Status
from .stages import Command, RunOptions, Stage, resolve_order
from .workspace import Workspace


class StageReporter(Protocol):
    """Receives progress events while a pipeline runs."""

    def begin(self, stages: Sequence[Stage]) -> None: ...
    def stage_started(self, stage: Stage) -> None: ...
    def stage_finished(self, stage: Stage, result: Result) -> None: ...
    def end(self) -> None: ...


class NullStageReporter:
    """Reporter that ignores every event."""

    def begin(self, stages: Sequence[Stage]) -> None: ...
    def stage_started(self, stage: Stage) -> None: ...
    def stage_finished(self, stage: Stage, result: Result) -> None: ...
    def end(self) -> None: ...


def missing_binaries(stage: Stage) -> List[str]:
    """Binaries ``stage`` needs that are not on ``PATH``."""
    return [b for b in stage.requires if not shutil.which(b)]


def line_count(path: Path) -> int:
    """Count lines in ``path``, or ``0`` if it does not exist."""
    if not path.exists() or not path.is_file():
        return 0
    try:
        with path.open("r", errors="ignore") as fh:
            return sum(1 for _ in fh)
    except OSError:
        return 0


def _run(command: Command, logdir: Path, name: str, timeout: int) -> Result:
    logdir.mkdir(parents=True, exist_ok=True)
    log = logdir / f"{name}.log"
    start = time.monotonic()
    _, payload = command
    argv: List[str] = payload if isinstance(payload, list) else ["bash", "-c", payload]
    detail = ""
    try:
        with log.open("wb") as fh:
            code = subprocess.run(argv, stdout=fh, stderr=subprocess.STDOUT, timeout=timeout).returncode
    except subprocess.TimeoutExpired:
        code, detail = 124, f"timed out after {timeout}s"
    except FileNotFoundError:
        code, detail = 127, f"command not found: {argv[0]}"
    status = Status.OK if code == 0 else Status.FAIL
    return Result(name, status, time.monotonic() - start, str(log), detail or f"exit {code}")


class Pipeline:
    """Runs a set of recon stages against one target.

    Args:
        workspace: Where output files and logs are written.
        options: Target and tuning parameters shared by every stage.
        reporter: Progress sink (defaults to :class:`NullStageReporter`).
        dry_run: Preview the resolved commands without executing anything —
            binaries do not need to be installed for a dry run.
        env: Host environment, used to make ``~/go/bin`` visible to child
            processes even before the user has sourced their shell rc file.
    """

    def __init__(
        self,
        workspace: Workspace,
        options: RunOptions,
        reporter: Optional[StageReporter] = None,
        *,
        dry_run: bool = False,
        env: Optional[Environment] = None,
    ) -> None:
        self.workspace = workspace
        self.options = options
        self.reporter: StageReporter = reporter or NullStageReporter()
        self.dry_run = dry_run
        self.env = env or Environment()

    def run(self, stage_keys: Sequence[str]) -> List[Result]:
        """Run ``stage_keys`` (plus their dependencies) in registry order."""
        stages = resolve_order(stage_keys)
        results: List[Result] = []
        self.workspace.create()
        if not self.dry_run:
            self._expose_go_bin()
        self.reporter.begin(stages)
        try:
            for stage in stages:
                self.reporter.stage_started(stage)
                result = self._run_stage(stage)
                results.append(result)
                self.reporter.stage_finished(stage, result)
        finally:
            self.reporter.end()
        return results

    def _expose_go_bin(self) -> None:
        go_bin = self.env.go_bin()
        current = os.environ.get("PATH", "")
        if go_bin not in current.split(os.pathsep):
            os.environ["PATH"] = f"{current}{os.pathsep}{go_bin}"

    def _run_stage(self, stage: Stage) -> Result:
        try:
            command = stage.build(self.workspace, self.options)
        except ValueError as exc:
            return Result(stage.key, Status.SKIP, detail=str(exc))

        if self.dry_run:
            shown = command[1] if command[0] == "shell" else " ".join(command[1])
            return Result(stage.key, Status.SKIP, detail=f"dry-run: {shown}")

        missing = missing_binaries(stage)
        if missing:
            return Result(stage.key, Status.SKIP, detail=f"missing: {', '.join(missing)}")

        return _run(command, self.workspace.logs, stage.key, stage.timeout)
