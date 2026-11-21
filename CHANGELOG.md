# Changelog

All notable changes to this project are documented here.
The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project uses [Semantic Versioning](https://semver.org/).

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
