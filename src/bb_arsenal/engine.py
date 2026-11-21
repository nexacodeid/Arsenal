"""Orchestrates installation runs; free of any UI dependency."""

from __future__ import annotations

import json
import logging
import shutil
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Protocol, Sequence, Tuple

from .environment import LOG_DIR, REPORT_DIR, Environment
from .installers import Installer, build_installers, install_system_packages
from .models import Kind, Result, Status, ToolSpec
from .registry import BASE_PACKAGES

log = logging.getLogger(__name__)

MAX_WORKERS = 3


class Reporter(Protocol):
    """Receives progress events. Implementations must be thread-safe."""

    def begin(self, specs: Sequence[ToolSpec]) -> None: ...
    def system_started(self) -> None: ...
    def system_finished(self, result: Result) -> None: ...
    def tool_started(self, spec: ToolSpec) -> None: ...
    def tool_finished(self, spec: ToolSpec, result: Result) -> None: ...
    def end(self) -> None: ...


class NullReporter:
    """Reporter that ignores every event."""

    def begin(self, specs: Sequence[ToolSpec]) -> None: ...
    def system_started(self) -> None: ...
    def system_finished(self, result: Result) -> None: ...
    def tool_started(self, spec: ToolSpec) -> None: ...
    def tool_finished(self, spec: ToolSpec, result: Result) -> None: ...
    def end(self) -> None: ...


class Engine:
    """Install a batch of tools, with retries, optional parallelism and dry-run.

    Args:
        env: Host environment.
        reporter: Progress sink (defaults to :class:`NullReporter`).
        workers: Parallel installs, clamped to ``1..MAX_WORKERS``.
        dry_run: Describe what would run without executing anything.
        retries: Attempts per tool before giving up.
        retry_delay: Base back-off in seconds (multiplied by attempt number).
        logdir: Where per-tool logs are written.
        installers: Override the installer table (used by tests).
    """

    def __init__(
        self,
        env: Environment,
        reporter: Optional[Reporter] = None,
        *,
        workers: int = 1,
        dry_run: bool = False,
        retries: int = 2,
        retry_delay: float = 5.0,
        logdir: Path = LOG_DIR,
        installers: Optional[Dict[Kind, Installer]] = None,
    ) -> None:
        self.env = env
        self.reporter: Reporter = reporter or NullReporter()
        self.workers = max(1, min(workers, MAX_WORKERS))
        self.dry_run = dry_run
        self.retries = max(1, retries)
        self.retry_delay = retry_delay
        self.logdir = logdir
        self.installers = installers if installers is not None else build_installers(env, logdir)

    # -- public API ----------------------------------------------------------
    def run(self, specs: Sequence[ToolSpec]) -> List[Result]:
        """Install ``specs`` and return one :class:`Result` per tool.

        The first element is the system-package step (omitted for dry runs);
        tool results follow in the order of ``specs``.
        """
        results: List[Result] = []
        self.reporter.begin(specs)
        try:
            if self.dry_run:
                results.extend(self._plan(spec) for spec in specs)
                for spec, result in zip(specs, results):
                    self.reporter.tool_finished(spec, result)
                return results

            with self.env.wake_lock():
                results.append(self._install_system(self._packages_for(specs)))
                self.env.ensure_path()
                results.extend(self._install_tools(specs))
            return results
        finally:
            self.reporter.end()

    # -- internals -----------------------------------------------------------
    @staticmethod
    def _packages_for(specs: Sequence[ToolSpec]) -> List[str]:
        extra = [pkg for spec in specs for pkg in spec.requires]
        return list(dict.fromkeys([*BASE_PACKAGES, *extra]))

    def _plan(self, spec: ToolSpec) -> Result:
        installer = self.installers.get(spec.kind)
        text = installer.describe(spec) if installer else "no installer"
        return Result(spec.name, Status.SKIP, detail=f"dry-run: {text}")

    def _install_system(self, packages: List[str]) -> Result:
        self.reporter.system_started()
        result = install_system_packages(self.env, packages, self.logdir)
        self.reporter.system_finished(result)
        return result

    def _install_tools(self, specs: Sequence[ToolSpec]) -> List[Result]:
        ordered: List[Tuple[int, ToolSpec]] = list(enumerate(specs))
        out: Dict[int, Result] = {}

        def work(item: Tuple[int, ToolSpec]) -> None:
            index, spec = item
            self.reporter.tool_started(spec)
            result = self._install_with_retry(spec)
            out[index] = result
            self.reporter.tool_finished(spec, result)

        if self.workers > 1:
            with ThreadPoolExecutor(max_workers=self.workers) as pool:
                list(pool.map(work, ordered))
        else:
            for item in ordered:
                work(item)
        return [out[i] for i, _ in ordered]

    def _install_with_retry(self, spec: ToolSpec) -> Result:
        installer = self.installers.get(spec.kind)
        if installer is None:
            return Result(spec.name, Status.SKIP, detail=f"no installer for kind '{spec.kind.value}'")

        result = Result(spec.name, Status.FAIL, detail="not attempted")
        for attempt in range(1, self.retries + 1):
            try:
                result = installer.install(spec)
            except Exception as exc:  # noqa: BLE001 - one broken tool must not abort the batch
                log.exception("installer crashed for %s", spec.name)
                result = Result(spec.name, Status.FAIL, detail=f"{type(exc).__name__}: {exc}")
            if result.status is not Status.FAIL:
                break
            if attempt < self.retries:
                time.sleep(self.retry_delay * attempt)

        if result.status is Status.OK and spec.binary:
            located = self._locate(spec.binary)
            result.detail = located or "installed; run `source ~/.bashrc` to refresh PATH"
        return result

    def _locate(self, binary: str) -> Optional[str]:
        found = shutil.which(binary)
        if found:
            return found
        candidate = Path(self.env.go_bin()) / binary
        return str(candidate) if candidate.exists() else None


def write_report(results: Sequence[Result], directory: Path = REPORT_DIR) -> Path:
    """Persist ``results`` as a timestamped JSON file and return its path."""
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"report-{datetime.now():%Y%m%d-%H%M%S}.json"
    path.write_text(json.dumps([r.to_dict() for r in results], indent=2), encoding="utf-8")
    return path


def summarize(results: Sequence[Result]) -> Dict[Status, int]:
    """Count results per :class:`Status`."""
    return {status: sum(r.status is status for r in results) for status in Status}
