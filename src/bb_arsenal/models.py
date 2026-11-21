"""Plain data types shared across the package."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import Enum
from typing import Any, Dict, Tuple


class Kind(str, Enum):
    """How a tool is installed."""

    GO = "go"
    PIP = "pip"
    GEM = "gem"
    GIT = "git"


class Status(str, Enum):
    """Outcome of a single install attempt."""

    OK = "ok"
    FAIL = "fail"
    SKIP = "skip"


@dataclass(frozen=True)
class ToolSpec:
    """Declarative description of an installable tool.

    Attributes:
        name: Unique identifier shown to the user and accepted by ``--only``.
        kind: Installation mechanism.
        source: Go module path, PyPI/gem name, or git URL depending on ``kind``.
        category: One of :data:`bb_arsenal.registry.CATEGORIES`.
        binary: Executable expected on ``PATH`` afterwards (empty for data-only tools).
        version_flag: Argument used by ``--verify`` to print the version.
        requires: Extra system packages needed before installing.
        note: Short caveat shown in the UI (policy warnings, platform quirks).
        optional: Marks tools that are not part of the default workflow.
    """

    name: str
    kind: Kind
    source: str
    category: str
    binary: str = ""
    version_flag: str = ""
    requires: Tuple[str, ...] = ()
    note: str = ""
    optional: bool = False


@dataclass
class Result:
    """Outcome of installing one tool (or the system foundation step)."""

    name: str
    status: Status
    elapsed: float = 0.0
    log: str = ""
    detail: str = ""

    def to_dict(self) -> Dict[str, Any]:
        """Return a JSON-serialisable representation."""
        data = asdict(self)
        data["status"] = self.status.value
        return data
