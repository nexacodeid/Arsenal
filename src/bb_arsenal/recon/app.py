"""Recon application flow: target input, authorisation gate, stage picker, run, summary."""

from __future__ import annotations

import argparse
import re
from pathlib import Path
from typing import List, Optional

from rich.console import Console

from ..tui import Item, Tui
from .cli import EXIT_FAILURE, EXIT_OK
from .console import ReconDisplay, ReconReporter
from .pipeline import Pipeline
from .stages import DEFAULT_STAGES, STAGES, RunOptions, resolve_order
from .workspace import DEFAULT_ROOT, Workspace

#: Loose hostname check — good enough to reject obvious typos and stray flags,
#: not a full validator. The underlying tools handle real-world edge cases.
_DOMAIN_RE = re.compile(r"^(?!-)[A-Za-z0-9-]{1,63}(?<!-)(\.[A-Za-z0-9-]{1,63})+$")


def looks_like_domain(value: str) -> bool:
    """Reject empty input and obvious non-domains before we touch the network."""
    return bool(_DOMAIN_RE.match(value.strip()))


class ReconApp:
    """Runs either a one-shot recon command or the interactive menu."""

    def __init__(self, console: Optional[Console] = None) -> None:
        self.console = console or Console()
        self.display = ReconDisplay(self.console)
        self.tui = Tui("bb-recon — authorised targets only", [s.key for s in STAGES])

    def run(self, args: argparse.Namespace) -> int:
        """Execute according to ``args`` and return a process exit status."""
        if args.list_stages:
            self.display.list_stages()
            return EXIT_OK

        target = args.target or self._ask_target()
        if not target:
            return EXIT_FAILURE

        if not args.yes and not self._authorize(target):
            self.console.print("[yellow]cancelled — authorisation not confirmed[/]")
            return EXIT_OK

        stage_keys = self._stage_keys(args)
        if not stage_keys:
            self.console.print("[yellow]no stages selected[/]")
            return EXIT_FAILURE

        root = Path(args.workspace) if args.workspace else DEFAULT_ROOT
        workspace = Workspace(target, root=root)
        options = RunOptions(target=target, threads=args.threads, wordlist=args.wordlist or "")
        stages = resolve_order(stage_keys)

        self.display.banner(target)
        pipeline = Pipeline(workspace, options, ReconReporter(self.console), dry_run=args.dry_run)
        results = pipeline.run(stage_keys)
        self.display.summary(stages, results, workspace)

        failed = any(result.status.value == "fail" for result in results)
        return EXIT_FAILURE if failed else EXIT_OK

    # -- target & authorisation ------------------------------------------------
    def _ask_target(self) -> str:
        raw = self.tui.ask("target domain, e.g. example.com")
        if not raw:
            return ""
        if not looks_like_domain(raw):
            self.console.print(f"[red]'{raw}' doesn't look like a domain[/]")
            return ""
        return raw

    def _authorize(self, target: str) -> bool:
        detail = (
            ("Target", target),
            ("Reminder", "Only recon targets you own or are explicitly authorised to test."),
            ("Scope", "Stages below marked 'active' send real traffic — check the program's rules."),
        )
        items = [
            Item("y", "I'm authorised — continue", target, detail=detail),
            Item("n", "Cancel", "", detail=detail),
        ]
        return self.tui.select("CONFIRM AUTHORISATION", items) == "y"

    # -- stage selection ---------------------------------------------------------
    def _stage_keys(self, args: argparse.Namespace) -> List[str]:
        if args.stages:
            return list(args.stages)
        if args.all:
            return [stage.key for stage in STAGES]
        if args.target:
            # non-interactive invocation without explicit --stages/--all
            return list(DEFAULT_STAGES)
        return self._pick_stages()

    def _pick_stages(self) -> List[str]:
        items = [
            Item(stage.key, stage.label, stage.description, tag="active" if stage.optional else "passive",
                detail=(
                    ("Requires", ", ".join(stage.requires) or "-"),
                    ("Depends on", ", ".join(stage.needs) or "-"),
                    ("Note", stage.note or "-"),
                ))
            for stage in STAGES
        ]
        picked = self.tui.multiselect("PICK STAGES", items)
        return picked or []
