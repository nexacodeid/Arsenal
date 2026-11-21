"""Shared fixtures. Tests never touch the network or the real home directory."""

from __future__ import annotations

from pathlib import Path
from typing import Dict, List

import pytest

from bb_arsenal.environment import Environment
from bb_arsenal.installers import Installer
from bb_arsenal.models import Kind, Result, Status, ToolSpec


class FakeInstaller(Installer):
    """Installer whose outcome is scripted per tool name."""

    def __init__(self, env: Environment, logdir: Path, outcomes: Dict[str, List[Status]]) -> None:
        super().__init__(env, logdir)
        self.outcomes = outcomes
        self.calls: List[str] = []

    def describe(self, spec: ToolSpec) -> str:
        return f"fake install {spec.name}"

    def install(self, spec: ToolSpec) -> Result:
        self.calls.append(spec.name)
        queue = self.outcomes.get(spec.name, [Status.OK])
        status = queue.pop(0) if len(queue) > 1 else queue[0]
        return Result(spec.name, status, detail="scripted")


@pytest.fixture()
def env(tmp_path: Path) -> Environment:
    return Environment(home=tmp_path)


@pytest.fixture()
def spec() -> ToolSpec:
    return ToolSpec("demo", Kind.GO, "example.com/demo@latest", "recon")
