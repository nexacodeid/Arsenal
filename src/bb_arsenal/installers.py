"""One installer per :class:`~bb_arsenal.models.Kind`, plus the system-package step."""

from __future__ import annotations

import shutil
import subprocess
import sys
import time
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Dict, List, Sequence

from .environment import Environment
from .models import Kind, Result, Status, ToolSpec


def run_command(name: str, cmd: Sequence[str], logdir: Path, timeout: int) -> Result:
    """Run ``cmd`` capturing combined output to ``<logdir>/<name>.log``.

    Never raises for ordinary failures: timeouts and missing executables are
    reported through the returned :class:`Result`.
    """
    logdir.mkdir(parents=True, exist_ok=True)
    log = logdir / f"{name}.log"
    start = time.monotonic()
    detail = ""
    try:
        with log.open("wb") as fh:
            code = subprocess.run(list(cmd), stdout=fh, stderr=subprocess.STDOUT, timeout=timeout).returncode
    except subprocess.TimeoutExpired:
        code, detail = 124, f"timed out after {timeout}s"
    except FileNotFoundError:
        code, detail = 127, f"command not found: {cmd[0]}"
    status = Status.OK if code == 0 else Status.FAIL
    return Result(name, status, time.monotonic() - start, str(log), detail or f"exit {code}")


class Installer(ABC):
    """Strategy for installing one kind of tool."""

    #: Seconds allowed before the underlying command is killed.
    timeout: int = 900

    def __init__(self, env: Environment, logdir: Path) -> None:
        self.env = env
        self.logdir = logdir

    @abstractmethod
    def describe(self, spec: ToolSpec) -> str:
        """Human-readable command line (used by ``--dry-run``)."""

    @abstractmethod
    def install(self, spec: ToolSpec) -> Result:
        """Install ``spec`` and report the outcome."""


class GoInstaller(Installer):
    timeout = 2400

    def describe(self, spec: ToolSpec) -> str:
        return f"go install -v {spec.source}"

    def install(self, spec: ToolSpec) -> Result:
        if not shutil.which("go"):
            return Result(spec.name, Status.SKIP, detail="Go toolchain not found")
        return run_command(spec.name, ["go", "install", "-v", spec.source], self.logdir, self.timeout)


class PipInstaller(Installer):
    def describe(self, spec: ToolSpec) -> str:
        return f"{Path(sys.executable).name} -m pip install --upgrade {spec.source}"

    def install(self, spec: ToolSpec) -> Result:
        cmd = [sys.executable, "-m", "pip", "install", "--upgrade", spec.source]
        return run_command(spec.name, cmd, self.logdir, self.timeout)


class GemInstaller(Installer):
    timeout = 1500

    def describe(self, spec: ToolSpec) -> str:
        return f"gem install {spec.source}"

    def install(self, spec: ToolSpec) -> Result:
        if not shutil.which("gem"):
            return Result(spec.name, Status.SKIP, detail="Ruby/gem not found")
        return run_command(spec.name, ["gem", "install", spec.source], self.logdir, self.timeout)


class GitInstaller(Installer):
    """Clone a repository of gf pattern files and copy them to ``~/.gf``."""

    timeout = 300

    def describe(self, spec: ToolSpec) -> str:
        return f"git clone --depth 1 {spec.source} && copy *.json to ~/.gf"

    def install(self, spec: ToolSpec) -> Result:
        checkout = self.logdir / f"{spec.name}-src"
        shutil.rmtree(checkout, ignore_errors=True)
        result = run_command(spec.name, ["git", "clone", "--depth", "1", spec.source, str(checkout)],
                             self.logdir, self.timeout)
        if result.status is not Status.OK:
            return result
        target = self.env.home / ".gf"
        target.mkdir(exist_ok=True)
        copied = 0
        for pattern in checkout.glob("*.json"):
            shutil.copy(pattern, target / pattern.name)
            copied += 1
        result.detail = f"{copied} pattern files copied to ~/.gf"
        if copied == 0:
            result.status = Status.FAIL
        return result


def build_installers(env: Environment, logdir: Path) -> Dict[Kind, Installer]:
    """Create the default installer for every :class:`Kind`."""
    return {
        Kind.GO: GoInstaller(env, logdir),
        Kind.PIP: PipInstaller(env, logdir),
        Kind.GEM: GemInstaller(env, logdir),
        Kind.GIT: GitInstaller(env, logdir),
    }


def install_system_packages(env: Environment, packages: List[str], logdir: Path) -> Result:
    """Install OS packages with ``pkg`` (Termux) or ``apt-get`` (Debian family)."""
    if env.termux:
        cmd = ["pkg", "install", "-y", *packages]
    elif shutil.which("apt-get"):
        cmd = ["apt-get", "install", "-y", *packages]
    else:
        return Result("system-packages", Status.SKIP, detail="neither pkg nor apt-get available")
    return run_command("system-packages", cmd, logdir, 1800)
