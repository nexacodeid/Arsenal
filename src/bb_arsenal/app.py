"""Application flow: wires the engine to the console and the interactive menu."""

from __future__ import annotations

import argparse
from typing import Iterable, List, Optional, Sequence

from rich.console import Console
from rich.prompt import Confirm

from .cli import EXIT_FAILURE, EXIT_OK
from .console import Display, RichReporter
from .engine import Engine, write_report
from .environment import Environment
from .models import Result, Status, ToolSpec
from .registry import (CATEGORIES, CORE_CATEGORIES, TOOLS, select_by_category,
                       select_by_names)
from .tui import Item, Tui, clip

_COMPLETIONS = tuple(t.name for t in TOOLS) + CATEGORIES + ("all", "core")


def _unique(specs: Iterable[ToolSpec]) -> List[ToolSpec]:
    """Deduplicate while keeping registry order."""
    wanted = {s.name for s in specs}
    return [t for t in TOOLS if t.name in wanted]


class App:
    """Runs either a one-shot command or the interactive menu."""

    def __init__(self, console: Optional[Console] = None) -> None:
        self.console = console or Console()
        self.env = Environment()
        self.display = Display(self.console)
        self.tui = Tui(self.env.describe(), _COMPLETIONS)

    # -- entry point ---------------------------------------------------------
    def run(self, args: argparse.Namespace) -> int:
        """Execute according to ``args`` and return a process exit status."""
        specs = self._specs_from_args(args)
        one_shot = bool(specs or args.list or args.verify or args.fix_path)
        if not one_shot:
            self._interactive(args)
            return EXIT_OK

        self.display.banner()
        self.display.environment(self.env)
        if args.list:
            self.display.catalog(TOOLS, self.env)
            return EXIT_OK
        if args.verify:
            self.display.verify(TOOLS, self.env)
            return EXIT_OK
        if args.fix_path:
            self._fix_path()
            return EXIT_OK

        results = self._install(specs, args, interactive=False)
        failed = any(r.status is Status.FAIL for r in results)
        return EXIT_FAILURE if failed else EXIT_OK

    # -- selection -----------------------------------------------------------
    @staticmethod
    def _specs_from_args(args: argparse.Namespace) -> List[ToolSpec]:
        selected: List[ToolSpec] = []
        if args.all:
            selected += list(TOOLS)
        if args.core:
            selected += select_by_category(CORE_CATEGORIES)
        if args.cat:
            selected += select_by_category(args.cat)
        if args.only:
            selected += select_by_names(args.only)[0]
        return _unique(selected)

    # -- actions -------------------------------------------------------------
    def _fix_path(self) -> None:
        updated = self.env.ensure_path()
        message = ", ".join(updated) if updated else "already configured"
        self.console.print(f"[green]PATH updated:[/] {message}")

    def _confirm(self, specs: Sequence[ToolSpec], interactive: bool) -> bool:
        if not interactive:
            return bool(Confirm.ask(f"Install {len(specs)} tool(s) (+ system packages)?", default=True))
        risky = [s.name for s in specs if s.note]
        detail = (
            ("Tools", clip(", ".join(s.name for s in specs), 60)),
            ("Count", f"{len(specs)} tool(s) + system packages"),
            ("Notes", clip(", ".join(risky), 60) if risky else "-"),
        )
        items = [
            Item("y", "Yes, install now", f"{len(specs)} tool(s)", detail=detail),
            Item("n", "Cancel", "back to the menu", detail=detail),
        ]
        return self.tui.select("CONFIRM INSTALL", items) == "y"

    def _install(self, specs: Sequence[ToolSpec], args: argparse.Namespace, *, interactive: bool) -> List[Result]:
        if not specs:
            self.console.print("[yellow]nothing selected[/]")
            return []
        if not (args.yes or args.dry_run) and not self._confirm(specs, interactive):
            return []
        engine = Engine(self.env, RichReporter(self.console), workers=args.workers, dry_run=args.dry_run)
        results = engine.run(specs)
        report = None if args.dry_run else write_report(results)
        self.display.summary(results, report)
        return results

    def _tool_items(self) -> List[Item]:
        items: List[Item] = []
        for spec in TOOLS:
            detail = (
                ("Kind", spec.kind.value),
                ("Source", clip(spec.source, 60)),
                ("Requires", ", ".join(spec.requires) or "-"),
                ("Status", "installed" if self.env.is_installed(spec) else "not installed"),
                ("Note", clip(spec.note or ("optional" if spec.optional else "-"), 60)),
            )
            items.append(Item(spec.name, spec.name, spec.note, spec.category, detail,
                              installed=self.env.is_installed(spec)))
        return items

    def _category_items(self) -> List[Item]:
        items: List[Item] = []
        for category in CATEGORIES:
            specs = select_by_category((category,))
            done = sum(self.env.is_installed(s) for s in specs)
            detail = (
                ("Tools", clip(", ".join(s.name for s in specs), 60)),
                ("Count", f"{len(specs)} tool(s)"),
                ("Status", f"{done}/{len(specs)} installed"),
            )
            items.append(Item(category, category, f"{len(specs)} tool(s)", category, detail))
        return items

    # -- interactive menu ----------------------------------------------------
    @staticmethod
    def _menu_items() -> List[Item]:
        return [
            Item("core", "Core", "recon + urls + fuzzing", detail=(
                ("Action", "install the essential recon toolchain"),
                ("Includes", "subfinder, httpx, dnsx, katana, gau, ffuf, …"),
                ("Requires", "go, git, pip"),
            )),
            Item("all", "Everything", "including scanners and extras", detail=(
                ("Action", "install the whole catalogue"),
                ("Includes", f"{len(TOOLS)} tools (check program policies for scanners)"),
                ("Requires", "go, git, pip, ruby"),
            )),
            Item("categories", "By category", "tick categories", detail=(
                ("Action", "choose one or more categories"),
                ("Categories", ", ".join(CATEGORIES)),
            )),
            Item("pick", "Pick tools", "tick individual tools", detail=(
                ("Action", "choose specific tools, e.g. dalfox"),
                ("Keys", "Space tick • a all • Enter install"),
            )),
            Item("type", "Type a name", "autocomplete + history", detail=(
                ("Action", "type tool names directly"),
                ("Keys", "Tab autocomplete • ↑ history"),
            )),
            Item("verify", "Verify", "check what is installed", detail=(
                ("Action", "report path and version of every tool"),
            )),
            Item("path", "Fix PATH", "add go/bin to your shell", detail=(
                ("Action", "append ~/go/bin to .bashrc / .zshrc"),
                ("Tip", "run `source ~/.bashrc` afterwards"),
            )),
            Item("quit", "Quit", "", detail=(("Action", "close the installer"),)),
        ]

    def _interactive(self, args: argparse.Namespace) -> None:
        items = self._menu_items()
        while True:
            choice = self.tui.select("MAIN MENU", items)
            if choice in (None, "quit"):
                return
            if self._dispatch(choice, args):
                self._pause()

    def _dispatch(self, choice: str, args: argparse.Namespace) -> bool:
        """Handle one menu choice. Returns ``True`` if output was printed."""
        if choice == "core":
            return bool(self._install(select_by_category(CORE_CATEGORIES), args, interactive=True))
        if choice == "all":
            return bool(self._install(list(TOOLS), args, interactive=True))
        if choice == "categories":
            picked = self.tui.multiselect("PICK CATEGORIES", self._category_items())
            return bool(picked) and bool(self._install(select_by_category(picked or []), args, interactive=True))
        if choice == "pick":
            picked = self.tui.multiselect("PICK TOOLS", self._tool_items())
            return bool(picked) and bool(self._install(select_by_names(picked or [])[0], args, interactive=True))
        if choice == "type":
            return self._type_names(args)
        if choice == "verify":
            self.display.clear()
            self.display.verify(TOOLS, self.env)
            return True
        if choice == "path":
            self._fix_path()
            return True
        return False

    def _type_names(self, args: argparse.Namespace) -> bool:
        self.display.clear()
        self.display.catalog(TOOLS, self.env)
        raw = self.tui.ask("which tools? (names, comma or space separated)",
                           toolbar="Tab = autocomplete • ↑ = history • empty = cancel")
        names = [part for part in raw.replace(",", " ").split() if part]
        if not names:
            return False
        specs, unknown = select_by_names(names)
        if unknown:
            self.console.print(f"[red]unknown: {', '.join(unknown)}[/]")
        return bool(self._install(specs, args, interactive=True)) or bool(unknown)

    def _pause(self) -> None:
        try:
            self.console.input("[dim]\n  press Enter to return to the menu…[/]")
        except (EOFError, KeyboardInterrupt):
            pass
