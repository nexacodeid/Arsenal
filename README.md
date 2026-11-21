<div align="center">

# BB Arsenal

**A fast, polished installer for bug bounty tooling — built for Termux, works on any Debian-family Linux.**

[![CI](https://github.com/nexacodeid/bb-arsenal/actions/workflows/ci.yml/badge.svg)](https://github.com/nexacodeid/bb-arsenal/actions/workflows/ci.yml)
![Python](https://img.shields.io/badge/python-3.9%2B-blue)
![License](https://img.shields.io/badge/license-MIT-green)
![Platform](https://img.shields.io/badge/platform-Termux%20%7C%20Linux-lightgrey)

</div>

---

BB Arsenal sets up a complete recon toolchain in minutes. Pick tools from a full-screen,
arrow-key menu, or drive it from scripts with flags. Every install is logged, retried on
failure, and summarised in a JSON report.

<!-- Add a screenshot or asciinema GIF here: docs/demo.gif -->

## Features

- **Arrow-key TUI** — move with ↑ ↓, tick with Space, confirm with Enter. Tap works on touch screens.
- **Live details panel** — kind, source, requirements, install status and policy notes for the highlighted tool.
- **Smart installs** — `go install`, `pip`, `gem` and git-based pattern packs behind one interface.
- **Resilient** — automatic retries with back-off; one failing tool never aborts the batch.
- **Fast** — up to 3 parallel installs (`--workers`).
- **Safe to preview** — `--dry-run` prints the exact commands without running anything.
- **Scriptable** — non-interactive flags and meaningful exit codes for CI or dotfiles bootstrap.
- **Termux-aware** — acquires a wake lock during long builds and fixes `PATH` for `~/go/bin`.
- **Typed and tested** — strict type hints, unit tests, and CI on Python 3.9 – 3.13.

## Installation

### Termux (Android)

```bash
pkg update && pkg install -y python git
pip install git+https://github.com/nexacodeid/bb-arsenal.git
```

### Debian / Ubuntu / Kali

```bash
sudo apt install -y python3-pip git
pipx install git+https://github.com/nexacodeid/bb-arsenal.git   # or: pip install --user ...
```

Then run:

```bash
bb-arsenal
```

> **Requirements:** Python 3.9+, a working network connection, and roughly 1 GB of free storage
> (the Go toolchain and module cache are the heavy parts).

## Usage

### Interactive menu

```bash
bb-arsenal
```

| Menu entry | What it does |
|---|---|
| **Core** | Installs the essential recon toolchain (`recon`, `urls`, `fuzzing`). |
| **Everything** | Installs the whole catalogue, including scanners and extras. |
| **By category** | Tick one or more categories. |
| **Pick tools** | Tick individual tools (e.g. just `dalfox`). |
| **Type a name** | Type tool names with Tab-completion and history. |
| **Verify** | Reports the path and version of every tool. |
| **Fix PATH** | Adds `~/go/bin` to `.bashrc` / `.zshrc`. |

| Key | Action |
|---|---|
| `↑` `↓` / `k` `j` | Move |
| `Space` / `→` | Tick (multi-select) |
| `a` | Tick / untick all |
| `Enter` | Confirm |
| `q` / `Esc` / `←` | Cancel / back |

### Command line

```bash
bb-arsenal --core                 # core toolchain
bb-arsenal --only dalfox,ffuf     # specific tools
bb-arsenal --cat recon,urls -y    # categories, no confirmation
bb-arsenal --all --workers 3      # everything, 3 in parallel
bb-arsenal --only dalfox --dry-run
bb-arsenal --verify
```

| Option | Description |
|---|---|
| `--all` | Install every tool. |
| `--core` | Install `recon`, `urls` and `fuzzing`. |
| `--cat CATS` | Comma-separated categories. |
| `--only TOOLS` | Comma- or space-separated tool names. |
| `--list` | Show the catalogue and install status. |
| `--verify` | Check installed tools and versions. |
| `--fix-path` | Add the Go bin directory to your shell `PATH`. |
| `-w`, `--workers N` | Parallel installs, 1–3 (default 1). |
| `-n`, `--dry-run` | Show what would run; change nothing. |
| `-y`, `--yes` | Skip the confirmation prompt. |
| `-V`, `--version` | Print the version. |

Selection flags can be combined; duplicates are removed.

**Exit codes:** `0` success · `1` at least one install failed · `2` invalid arguments · `130` interrupted.

After installing, reload your shell so new binaries are found:

```bash
source ~/.bashrc
subfinder -version
```

## Tool catalogue

| Category | Tools |
|---|---|
| `recon` | subfinder, httpx, dnsx, katana, interactsh-client |
| `urls` | gau, assetfinder, anew, qsreplace, gf, uro, arjun, gf-patterns |
| `fuzzing` | ffuf |
| `scanners` | dalfox, sqlmap, wpscan |
| `extras` | naabu |

Tools with caveats (for example `sqlmap`, which many programs forbid) show a note in the menu and
in the confirmation screen. Run `bb-arsenal --list` for the live view.

### Adding a tool

Add one line to `TOOLS` in [`src/bb_arsenal/registry.py`](src/bb_arsenal/registry.py):

```python
_go("nuclei", "github.com/projectdiscovery/nuclei/v3/cmd/nuclei@latest", "scanners", flag="-version"),
```

The CLI, menu, details panel and tests pick it up automatically.

## Files and logs

| Path | Content |
|---|---|
| `~/.bb-arsenal/logs/<tool>.log` | Full output of each install command. |
| `~/.bb-arsenal/reports/report-*.json` | Machine-readable result of every run. |
| `~/.gf/` | Pattern files installed by `gf-patterns`. |

## Project layout

```text
src/bb_arsenal/
├── registry.py      # tool catalogue (data only)
├── models.py        # ToolSpec, Result, Status, Kind
├── environment.py   # host detection, PATH management, wake lock
├── installers.py    # one strategy per install kind
├── engine.py        # retries, parallelism, dry-run, reporting (no UI imports)
├── console.py       # Rich output: banner, tables, progress, summary
├── tui.py           # prompt_toolkit pickers
├── app.py           # application flow and menu
└── cli.py           # argument parsing and entry point
```

The engine reports progress through a small `Reporter` protocol, so the core is fully testable
without a terminal.

## Development

```bash
git clone https://github.com/nexacodeid/bb-arsenal.git
cd bb-arsenal
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"

pytest          # tests
mypy            # strict type checking
ruff check .    # lint
```

Contributions are welcome. Please open an issue first for larger changes, keep new code typed and
covered by tests, and describe user-visible changes in `CHANGELOG.md`.

## Responsible use

BB Arsenal only **installs** publicly available security tools. You are responsible for how you use
them. Test only systems you own or are explicitly authorised to test, follow each bug bounty
program's scope and rules (many prohibit automated scanning or specific tools), and comply with
local law. The authors accept no liability for misuse.

## License

Released under the [MIT License](LICENSE).
