"""Rich rendering for recon runs: progress, the stage catalogue, and the summary."""

from __future__ import annotations

from typing import Dict, Optional, Sequence

from rich import box
from rich.console import Console
from rich.panel import Panel
from rich.progress import BarColumn, Progress, SpinnerColumn, TaskID, TextColumn, TimeElapsedColumn
from rich.rule import Rule
from rich.table import Table

from ..models import Result, Status
from .pipeline import line_count
from .stages import STAGES, Stage
from .workspace import Workspace

STATUS_ICON: Dict[Status, str] = {Status.OK: "[green]✔[/]", Status.FAIL: "[red]✘[/]", Status.SKIP: "[yellow]⚠[/]"}
STATUS_STYLE: Dict[Status, str] = {Status.OK: "green", Status.FAIL: "red", Status.SKIP: "yellow"}

SCOPE_REMINDER = (
    "[bold]Only run recon against targets you own or are explicitly authorised to test.[/]\n"
    "Stages marked [red]active[/] send real traffic designed to find or confirm issues — "
    "check each program's policy before enabling them."
)


class ReconReporter:
    """Progress bars driven by :class:`bb_arsenal.recon.pipeline.Pipeline` events."""

    def __init__(self, console: Console) -> None:
        self.console = console
        self._progress: Optional[Progress] = None
        self._tasks: Dict[str, TaskID] = {}

    def begin(self, stages: Sequence[Stage]) -> None:
        self._progress = Progress(
            SpinnerColumn(finished_text=" "),
            TextColumn("[bold cyan]{task.description}"),
            BarColumn(bar_width=None),
            TimeElapsedColumn(),
            console=self.console,
        )
        self._progress.start()
        self._tasks = {stage.key: self._progress.add_task(stage.label, total=1) for stage in stages}

    def stage_started(self, stage: Stage) -> None:
        if self._progress is not None:
            self._progress.update(self._tasks[stage.key], description=f"{stage.label} …")

    def stage_finished(self, stage: Stage, result: Result) -> None:
        if self._progress is not None:
            self._progress.update(self._tasks[stage.key], completed=1,
                                  description=f"{STATUS_ICON[result.status]} {stage.label}")

    def end(self) -> None:
        if self._progress is not None:
            self._progress.stop()
            self._progress = None


class ReconDisplay:
    """Static (non-interactive) rendering helpers for the recon command."""

    def __init__(self, console: Console) -> None:
        self.console = console

    def banner(self, target: str) -> None:
        self.console.print(Panel(f"[bold cyan]RECON[/]  ·  target: [bold]{target}[/]", border_style="cyan"))

    def list_stages(self, stages: Sequence[Stage] = STAGES) -> None:
        table = Table(box=box.ROUNDED, border_style="cyan", title="[bold cyan]RECON STAGES",
                      header_style="bold white")
        for column in ("KEY", "STAGE", "REQUIRES", "DEPENDS ON", "TYPE", "NOTE"):
            table.add_column(column)
        for stage in stages:
            kind = "[red]active[/]" if stage.optional else "[green]passive[/]"
            table.add_row(stage.key, stage.label, ", ".join(stage.requires) or "-",
                         ", ".join(stage.needs) or "-", kind, stage.note or "-")
        self.console.print(table)

    def summary(self, stages: Sequence[Stage], results: Sequence[Result], workspace: Workspace) -> None:
        self.console.print(Rule("[bold]recon summary[/]"))
        table = Table(box=box.ROUNDED, border_style="cyan", header_style="bold cyan")
        for column in ("Stage", "Status", "Time", "Output", "Lines", "Detail"):
            table.add_column(column)
        by_key = {stage.key: stage for stage in stages}
        for result in results:
            stage = by_key[result.name]
            out = stage.output(workspace)
            location = str(out.relative_to(workspace.root)) if out.exists() else "-"
            count = line_count(out) if out.is_file() else "-"
            style = STATUS_STYLE[result.status]
            table.add_row(stage.label, f"[{style}]{result.status.value}[/]", f"{result.elapsed:.1f}s",
                         location, str(count), result.detail)
        self.console.print(table)
        self.console.print(f"[dim]workspace: {workspace.root}[/]")
        self.console.print(Panel(SCOPE_REMINDER, border_style="magenta"))
