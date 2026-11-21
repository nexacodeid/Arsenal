"""Command-line interface."""

from __future__ import annotations

import argparse
import sys
from typing import List, Optional, Sequence

from . import __version__
from .registry import CATEGORIES, TOOLS, select_by_names

EXIT_OK = 0
EXIT_FAILURE = 1
EXIT_INTERRUPTED = 130


def _categories(value: str) -> List[str]:
    chosen = [part.strip() for part in value.split(",") if part.strip()]
    unknown = [c for c in chosen if c not in CATEGORIES]
    if unknown:
        raise argparse.ArgumentTypeError(
            f"unknown categories: {', '.join(unknown)} (choose from {', '.join(CATEGORIES)})")
    return chosen


def _tool_names(value: str) -> List[str]:
    names = [part for part in value.replace(",", " ").split() if part]
    _, unknown = select_by_names(names)
    if unknown:
        raise argparse.ArgumentTypeError(
            f"unknown tools: {', '.join(unknown)} (see --list)")
    return names


def build_parser() -> argparse.ArgumentParser:
    """Create the argument parser (kept separate so it is easy to test)."""
    parser = argparse.ArgumentParser(
        prog="bb-arsenal",
        description="Install and verify bug bounty tooling. Run without options for the interactive menu.",
        epilog="Only test systems you are explicitly authorised to test.",
    )
    pick = parser.add_argument_group("selection")
    pick.add_argument("--all", action="store_true", help="install every tool")
    pick.add_argument("--core", action="store_true", help="install the core set (recon, urls, fuzzing)")
    pick.add_argument("--cat", type=_categories, metavar="CATS",
                      help=f"comma-separated categories: {', '.join(CATEGORIES)}")
    pick.add_argument("--only", type=_tool_names, metavar="TOOLS",
                      help="comma- or space-separated tool names, e.g. dalfox,ffuf")

    act = parser.add_argument_group("other actions")
    act.add_argument("--list", action="store_true", help="show the tool catalogue and exit")
    act.add_argument("--verify", action="store_true", help="check which tools are installed and exit")
    act.add_argument("--fix-path", action="store_true", help="add the Go bin directory to your shell PATH")

    opts = parser.add_argument_group("options")
    opts.add_argument("-w", "--workers", type=int, default=1, metavar="N",
                      help="parallel installs, 1-3 (default: 1)")
    opts.add_argument("-n", "--dry-run", action="store_true", help="show what would run without installing")
    opts.add_argument("-y", "--yes", action="store_true", help="do not ask for confirmation")
    opts.add_argument("-V", "--version", action="version", version=f"%(prog)s {__version__}")
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    """Program entry point. Returns the process exit status."""
    args = build_parser().parse_args(argv)
    try:
        from .app import App
    except ImportError as exc:  # pragma: no cover - depends on the user's environment
        print(f"bb-arsenal: missing dependency ({exc}).\n"
              "Install with:  pip install rich prompt_toolkit", file=sys.stderr)
        return EXIT_FAILURE
    try:
        return App().run(args)
    except KeyboardInterrupt:
        print("\ncancelled", file=sys.stderr)
        return EXIT_INTERRUPTED


__all__ = ["build_parser", "main", "TOOLS"]
