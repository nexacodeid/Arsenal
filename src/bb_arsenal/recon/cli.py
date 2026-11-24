"""Command-line interface for ``bb-recon``."""

from __future__ import annotations

import argparse
import sys
from typing import List, Optional, Sequence

from .. import __version__
from .stages import STAGES

EXIT_OK = 0
EXIT_FAILURE = 1
EXIT_INTERRUPTED = 130


def _stage_keys(value: str) -> List[str]:
    keys = [part for part in value.replace(",", " ").split() if part]
    known = {stage.key for stage in STAGES}
    unknown = [k for k in keys if k not in known]
    if unknown:
        raise argparse.ArgumentTypeError(f"unknown stages: {', '.join(unknown)} (see --list-stages)")
    return keys


def build_parser() -> argparse.ArgumentParser:
    """Create the argument parser (kept separate so it is easy to test)."""
    parser = argparse.ArgumentParser(
        prog="bb-recon",
        description="Automated recon pipeline built on the tools bb-arsenal installs.",
        epilog="Only recon targets you own or are explicitly authorised to test.",
    )
    parser.add_argument("target", nargs="?", help="domain to recon, e.g. example.com")

    pick = parser.add_argument_group("stage selection")
    pick.add_argument("--stages", type=_stage_keys, metavar="STAGES",
                      help="comma/space separated stage keys (default: passive stages only)")
    pick.add_argument("--all", action="store_true", help="run every stage, including active ones")

    act = parser.add_argument_group("other actions")
    act.add_argument("--list-stages", action="store_true", help="list pipeline stages and exit")

    opts = parser.add_argument_group("options")
    opts.add_argument("--workspace", metavar="DIR", help="parent directory for output (default: ~/bb-recon)")
    opts.add_argument("-w", "--wordlist", metavar="FILE", help="wordlist for the ffuf stage")
    opts.add_argument("-t", "--threads", type=int, default=50, metavar="N", help="worker threads (default: 50)")
    opts.add_argument("-n", "--dry-run", action="store_true", help="show the resolved commands; run nothing")
    opts.add_argument("-y", "--yes", action="store_true", help="skip the authorisation confirmation")
    opts.add_argument("-V", "--version", action="version", version=f"%(prog)s {__version__}")
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    """Program entry point. Returns the process exit status."""
    args = build_parser().parse_args(argv)
    try:
        from .app import ReconApp
    except ImportError as exc:  # pragma: no cover - depends on the user's environment
        print(f"bb-recon: missing dependency ({exc}).\n"
              "Install with:  pip install rich prompt_toolkit", file=sys.stderr)
        return EXIT_FAILURE
    try:
        return ReconApp().run(args)
    except KeyboardInterrupt:
        print("\ncancelled", file=sys.stderr)
        return EXIT_INTERRUPTED


__all__ = ["build_parser", "main"]
