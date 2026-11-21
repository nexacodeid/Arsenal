from __future__ import annotations

from bb_arsenal.models import Kind
from bb_arsenal.registry import (BASE_PACKAGES, CATEGORIES, CORE_CATEGORIES, TOOLS,
                                 get_tool, select_by_category, select_by_names)


def test_tool_names_are_unique() -> None:
    names = [t.name for t in TOOLS]
    assert len(names) == len(set(names))


def test_every_tool_has_a_known_category() -> None:
    assert {t.category for t in TOOLS} <= set(CATEGORIES)


def test_every_category_is_populated() -> None:
    assert {t.category for t in TOOLS} == set(CATEGORIES)


def test_go_tools_pin_a_version_and_have_a_binary() -> None:
    for tool in (t for t in TOOLS if t.kind is Kind.GO):
        assert "@" in tool.source, tool.name
        assert tool.binary == tool.name


def test_git_tools_use_https() -> None:
    for tool in (t for t in TOOLS if t.kind is Kind.GIT):
        assert tool.source.startswith("https://")


def test_core_categories_are_valid() -> None:
    assert set(CORE_CATEGORIES) <= set(CATEGORIES)


def test_base_packages_have_no_duplicates() -> None:
    assert len(BASE_PACKAGES) == len(set(BASE_PACKAGES))


def test_dalfox_is_available() -> None:
    tool = get_tool("dalfox")
    assert tool is not None and tool.category == "scanners"


def test_select_by_category_keeps_registry_order() -> None:
    selected = select_by_category(["fuzzing", "recon"])
    assert [t.name for t in selected] == [t.name for t in TOOLS if t.category in {"fuzzing", "recon"}]


def test_select_by_names_reports_unknown_and_dedupes() -> None:
    found, unknown = select_by_names(["ffuf", "nope", " ffuf ", "dalfox", ""])
    assert [t.name for t in found] == ["ffuf", "dalfox"]
    assert unknown == ["nope"]
