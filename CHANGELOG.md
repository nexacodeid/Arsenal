# Changelog

All notable changes to this project are documented here.
The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project uses [Semantic Versioning](https://semver.org/).

## [1.1.0] - 2026-11-25

### Added
- `bb-recon`: an automated recon pipeline chaining every tool `bb-arsenal` installs
  (subfinder/assetfinder → anew → dnsx → httpx → katana/gau → uro → gf, with optional
  active stages for port scanning, parameter discovery, directory fuzzing and XSS confirmation).
- Dependency-resolved stage selection — picking one stage pulls in whatever it needs.
- An authorisation confirmation screen before any stage runs (skippable with `-y`).
- `--dry-run`, `--list-stages`, and a per-target workspace under `~/bb-recon/<target>/`.
- A stage that is missing its tool, or has nothing to work with yet, is reported as `skip`
  rather than aborting the run.

## [1.0.0] - 2026-11-22

### Added
- Full-screen, arrow-key menu with tick-box selection, a live details panel and touch support.
- `--list`, `--dry-run`, `--version` and short flags (`-y`, `-n`, `-w`).
- Per-tool retries with back-off, optional parallel installs (up to 3), JSON run reports.
- Unit tests, strict type hints and CI.

### Changed
- Restructured the single script into an installable package (`bb-arsenal` command).
- Dependencies are declared in `pyproject.toml` instead of being installed at start-up.
- The tool `gf-paterns` is now correctly named `gf-patterns`.
- State directory moved from `~/.bb-installer` to `~/.bb-arsenal`.
- Non-interactive runs exit with status 1 when any install fails.
