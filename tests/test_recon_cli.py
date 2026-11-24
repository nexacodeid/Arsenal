from __future__ import annotations

import pytest

from bb_arsenal import __version__
from bb_arsenal.recon.cli import build_parser


def parse(*argv: str):
    return build_parser().parse_args(list(argv))


def test_defaults() -> None:
    args = parse()
    assert args.target is None
    assert not (args.all or args.yes or args.dry_run or args.list_stages)
    assert args.threads == 50


def test_target_is_positional() -> None:
    assert parse("example.com").target == "example.com"


def test_stages_accepts_commas_and_spaces() -> None:
    assert parse("--stages", "gf,httpx").stages == ["gf", "httpx"]
    assert parse("--stages", "gf httpx").stages == ["gf", "httpx"]


def test_unknown_stage_is_rejected(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as exc:
        parse("--stages", "not-a-real-stage")
    assert exc.value.code == 2
    assert "unknown stages" in capsys.readouterr().err


def test_version_flag(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as exc:
        parse("--version")
    assert exc.value.code == 0
    assert __version__ in capsys.readouterr().out
