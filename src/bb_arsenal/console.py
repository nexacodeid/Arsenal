"""Rich-based output: banner, tables, progress and the final summary."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path
from typing import Dict, Optional, Sequence

from rich import box
from rich.align import Align
from rich.console import Console
from rich.panel import Panel
from rich.progress import (BarColumn, Progress, SpinnerColumn, TaskID,
                           TaskProgressColumn, TextColumn, TimeElapsedColumn)
from rich.rule import Rule
from rich.table import Table
from rich.text import Text

from . import TAGLINE, __version__
from .engine import summarize
from .environment import Environment
from .models import Result, Status, ToolSpec

CATEGORY_COLORS: Dict[str, str] = {
    "recon": "cyan",
    "urls": "green",
    "fuzzing": "yellow",
    "scanners": "red",
    "extras": "magenta",
}
STATUS_STYLE: Dict[Status, str] = {Status.OK: "green", Status.FAIL: "red", Status.SKIP: "yellow"}
STATUS_ICON: Dict[Status, str] = {Status.OK: "[green]✔[/]", Status.FAIL: "[red]✘[/]", Status.SKIP: "[yellow]⚠[/]"}

SCOPE_REMINDER = (
    "[bold]source ~/.bashrc[/] then try [bold cyan]subfinder -version[/]\n"
    "Scanners (sqlmap, wpscan, naabu, dalfox) are for [bold]in-scope targets only[/] "
    "— read each program's policy first."
)

_ART = (
    "██████╗ ██████╗\n██╔══██╗██╔══██╗\n██████╔╝██████╔╝\n"
    "██╔══██╗██╔══██╗\n██████╔╝██████╔╝\n╚═════╝ ╚═════╝"
)


class RichReporter:
    """Progress bars driven by :class:`bb_arsenal.engine.Engine` events."""

    def __init__(self, console: Console) -> None:
        self.console = console
        self._progress: Optional[Progress] = None
        self._tasks: Dict[str, TaskID] = {}
        self._system: Optional[TaskID] = None

    def begin(self, specs: Sequence[ToolSpec]) -> None:
        self._progress = Progress(
            SpinnerColumn(finished_text=" "),
            TextColumn("[bold cyan]{task.description}"),
            BarColumn(bar_width=None),
            TaskProgressColumn(),
            TimeElapsedColumn(),
            console=self.console,
        )
        self._progress.start()
        self._tasks = {spec.name: self._progress.add_task(spec.name, total=1) for spec in specs}

    def system_started(self) -> None:
        if self._progress is not None:
            self._system = self._progress.add_task("system packages", total=1)

    def system_finished(self, result: Result) -> None:
        if self._progress is not None and self._system is not None:
            self._progress.update(self._system, completed=1,
                                  description=f"{STATUS_ICON[result.status]} system packages")

    def tool_started(self, spec: ToolSpec) -> None:
        if self._progress is not None:
            self._progress.update(self._tasks[spec.name], description=f"{spec.name} …")

    def tool_finished(self, spec: ToolSpec, result: Result) -> None:
        if self._progress is not None:
            self._progress.update(self._tasks[spec.name], completed=1,
                                  description=f"{STATUS_ICON[result.status]} {spec.name}")

    def end(self) -> None:
        if self._progress is not None:
            self._progress.stop()
            self._progress = None


class Display:
    """Static (non-interactive) rendering helpers."""

    def __init__(self, console: Console) -> None:
        self.console = console

    def clear(self) -> None:
        self.console.clear()

    def banner(self) -> None:
        art = Text(_ART, style="bold cyan")
        subtitle = Text(f"A R S E N A L  •  {TAGLINE}  •  v{__version__}", style="bold magenta")
        self.console.print(Align.center(Panel(art, border_style="cyan", subtitle=subtitle)))

    def environment(self, env: Environment) -> None:
        table = Table(box=box.SIMPLE_HEAVY, show_header=False, pad_edge=False)
        table.add_column(style="bold cyan")
        table.add_column(style="white")
        table.add_row("System", env.system_name)
        table.add_row("Go", shutil.which("go") or "not installed")
        table.add_row("Free disk", f"{env.free_disk_gb():.1f} GB")
        table.add_row("Go bin", env.go_bin())
        self.console.print(Panel(table, title="[bold]environment[/]", border_style="cyan"))

    def catalog(self, specs: Sequence[ToolSpec], env: Optional[Environment] = None) -> None:
        table = Table(box=box.ROUNDED, border_style="cyan", title="[bold cyan]TOOLS", header_style="bold white")
        for column in ("#", "TOOL", "CATEGORY", "KIND", "REQUIRES", "NOTE") + (("STATUS",) if env else ()):
            table.add_column(column)
        for index, spec in enumerate(specs, 1):
            color = CATEGORY_COLORS.get(spec.category, "white")
            row = [
                f"[magenta]{index}[/]", f"[bold]{spec.name}[/]", f"[{color}]{spec.category}[/]",
                spec.kind.value, ", ".join(spec.requires) or "-",
                f"[dim]{spec.note or ('optional' if spec.optional else '-')}[/]",
            ]
            if env:
                row.append("[green]installed[/]" if env.is_installed(spec) else "[dim]-[/]")
            table.add_row(*row)
        self.console.print(table)

    def verify(self, specs: Sequence[ToolSpec], env: Environment) -> None:
        table = Table(box=box.ROUNDED, border_style="cyan", header_style="bold cyan")
        for column in ("Tool", "Binary", "Version", "Status"):
            table.add_column(column)
        for spec in specs:
            if not spec.binary:
                continue
            path = shutil.which(spec.binary)
            version = _probe_version(spec) if path and spec.version_flag else "-"
            table.add_row(spec.name, path or "-", version,
                          "[green]found[/]" if path else "[red]missing[/]")
        self.console.print(table)

    def summary(self, results: Sequence[Result], report: Optional[Path]) -> None:
        self.console.print(Rule("[bold]results[/]"))
        table = Table(box=box.ROUNDED, border_style="cyan", header_style="bold cyan")
        for column in ("Tool", "Status", "Time", "Detail"):
            table.add_column(column)
        for result in results:
            style = STATUS_STYLE[result.status]
            table.add_row(result.name, f"[{style}]{result.status.value}[/]",
                          f"{result.elapsed:.1f}s", result.detail or result.log)
        self.console.print(table)

        counts = summarize(results)
        self.console.print(Panel(
            f"[green]{counts[Status.OK]} succeeded[/]   [red]{counts[Status.FAIL]} failed[/]   "
            f"[yellow]{counts[Status.SKIP]} skipped[/]", border_style="cyan"))

        for result in [r for r in results if r.status is Status.FAIL and r.log][:3]:
            path = Path(result.log)
            if path.exists():
                tail = "\n".join(path.read_text(errors="ignore").splitlines()[-6:])
                self.console.print(Panel(tail, title=f"log: {result.name}", border_style="red"))
        if report:
            self.console.print(f"[dim]report: {report}[/]")
        self.console.print(Panel(SCOPE_REMINDER, border_style="magenta"))


def _probe_version(spec: ToolSpec) -> str:
    try:
        out = subprocess.run([spec.binary, *spec.version_flag.split()], capture_output=True,
                             text=True, timeout=25)
        lines = (out.stdout or out.stderr).strip().splitlines()
        return lines[0][:40] if lines else "-"
    except (OSError, subprocess.SubprocessError):
        return "-"
