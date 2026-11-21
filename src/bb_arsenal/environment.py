"""Host detection and shell/PATH management."""

from __future__ import annotations

import os
import platform
import shutil
import subprocess
import sys
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator, List, Optional

from .models import ToolSpec

HOME = Path.home()
STATE_DIR = HOME / ".bb-arsenal"
LOG_DIR = STATE_DIR / "logs"
REPORT_DIR = STATE_DIR / "reports"

_PATH_LINE = 'export PATH="$PATH:$HOME/go/bin"'
_PATH_MARKER = "# added by bb-arsenal"


class Environment:
    """Facts about the host plus helpers that mutate the user's shell setup."""

    def __init__(self, home: Path = HOME) -> None:
        self.home = home
        self.termux = "com.termux" in os.environ.get("PREFIX", "") or Path("/data/data/com.termux").exists()
        self._go_bin: Optional[str] = None

    # -- introspection -------------------------------------------------------
    @property
    def system_name(self) -> str:
        return "Termux (Android)" if self.termux else platform.system()

    def free_disk_gb(self) -> float:
        return shutil.disk_usage(str(self.home)).free / 1e9

    def describe(self) -> str:
        """One-line summary used in the TUI header."""
        return (f"{self.system_name} • {platform.machine()} • "
                f"Python {sys.version.split()[0]} • {self.free_disk_gb():.1f} GB free")

    def go_bin(self) -> str:
        """Directory where ``go install`` places binaries."""
        if self._go_bin:
            return self._go_bin
        base = self.home / "go"
        if shutil.which("go"):
            try:
                out = subprocess.run(["go", "env", "GOPATH"], capture_output=True,
                                     text=True, timeout=20).stdout.strip()
                if out:
                    base = Path(out.split(os.pathsep)[0])
            except (OSError, subprocess.SubprocessError):
                pass
        self._go_bin = str(base / "bin")
        return self._go_bin

    # -- mutation ------------------------------------------------------------
    def ensure_path(self) -> List[str]:
        """Make ``go/bin`` available now and in future shells.

        Returns:
            Paths of the rc files that were modified.
        """
        updated: List[str] = []
        for rc in (self.home / ".bashrc", self.home / ".zshrc"):
            if rc.name == ".zshrc" and not rc.exists():
                continue
            text = rc.read_text() if rc.exists() else ""
            if "go/bin" in text:
                continue
            prefix = "" if not text or text.endswith("\n") else "\n"
            with rc.open("a") as fh:
                fh.write(f"{prefix}{_PATH_MARKER}\n{_PATH_LINE}\n")
            updated.append(str(rc))
        current = os.environ.get("PATH", "")
        go_bin = self.go_bin()
        if go_bin not in current.split(os.pathsep):
            os.environ["PATH"] = current + os.pathsep + go_bin
        return updated

    @contextmanager
    def wake_lock(self) -> Iterator[None]:
        """Keep the CPU awake on Termux while long installs run."""
        acquired = self._termux_wake("termux-wake-lock")
        try:
            yield
        finally:
            if acquired:
                self._termux_wake("termux-wake-unlock")

    def _termux_wake(self, command: str) -> bool:
        if not self.termux or not shutil.which(command):
            return False
        subprocess.call([command], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return True

    # -- queries -------------------------------------------------------------
    def is_installed(self, spec: ToolSpec) -> bool:
        """Best-effort check that ``spec`` is present on this machine."""
        if not spec.binary:
            patterns = self.home / ".gf"
            return patterns.is_dir() and any(patterns.glob("*.json"))
        return bool(shutil.which(spec.binary) or (Path(self.go_bin()) / spec.binary).exists())
