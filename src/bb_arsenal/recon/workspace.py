"""Per-target output directory for a recon run."""

from __future__ import annotations

import re
from pathlib import Path

DEFAULT_ROOT = Path.home() / "bb-recon"

_UNSAFE = re.compile(r"[^a-zA-Z0-9.-]+")


def slugify(target: str) -> str:
    """Turn a target string into a filesystem-safe directory name."""
    cleaned = target.strip().lower()
    cleaned = re.sub(r"^https?://", "", cleaned)
    cleaned = _UNSAFE.sub("_", cleaned).strip("_")
    return cleaned or "target"


class Workspace:
    """Directory layout holding every artefact a recon run produces.

    Args:
        target: The domain or host being reconned.
        root: Parent directory; the workspace lives at ``root/<slug>``.
    """

    def __init__(self, target: str, root: Path = DEFAULT_ROOT) -> None:
        self.target = target
        self.root = root / slugify(target)
        self.subdomains = self.root / "subdomains"
        self.urls = self.root / "urls"
        self.gf = self.root / "gf"
        self.ports = self.root / "ports"
        self.params = self.root / "params"
        self.fuzz = self.root / "fuzz"
        self.vulns = self.root / "vulns"
        self.logs = self.root / "logs"

    def create(self) -> None:
        """Create every subdirectory (idempotent)."""
        for directory in (self.root, self.subdomains, self.urls, self.gf, self.ports,
                          self.params, self.fuzz, self.vulns, self.logs):
            directory.mkdir(parents=True, exist_ok=True)
