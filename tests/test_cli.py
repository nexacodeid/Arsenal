from __future__ import annotations

import pytest

from bb_arsenal import __version__
from bb_arsenal.cli import build_parser


def parse(*argv: str):
    return build_parser().parse_args(list(argv))


def test_defaults() -> None:
    args = parse()
    assert not (args.all or args.core or args.list or args.verify or args.dry_run or args.yes)
    assert args.workers == 1 and args.cat is None and args.only is None


def test_only_accepts_commas_and_spaces() -> None:
    assert parse("--only", "dalfox,ffuf").only == ["dalfox", "ffuf"]
    assert parse("--only", "dalfox ffuf").only == ["dalfox", "ffuf"]


def test_unknown_tool_is_rejected(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as exc:
        parse("--only", "definitely-not-a-tool")
    assert exc.value.code == 2
    assert "unknown tools" in capsys.readouterr().err


def test_unknown_category_is_rejected() -> None:
    with pytest.raises(SystemExit):
        parse("--cat", "recon,bogus")


def test_cat_accepts_multiple() -> None:
    assert parse("--cat", "recon,urls").cat == ["recon", "urls"]


def test_short_flags() -> None:
    args = parse("-y", "-n", "-w", "3")
    assert args.yes and args.dry_run and args.workers == 3


def test_version_flag(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as exc:
        parse("--version")
    assert exc.value.code == 0
    assert __version__ in capsys.readouterr().out
