"""Full-screen, arrow-key driven pickers built on prompt_toolkit."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Callable, List, Optional, Sequence, Tuple

from prompt_toolkit import PromptSession
from prompt_toolkit.application import Application
from prompt_toolkit.auto_suggest import AutoSuggestFromHistory
from prompt_toolkit.completion import WordCompleter
from prompt_toolkit.data_structures import Point
from prompt_toolkit.history import InMemoryHistory
from prompt_toolkit.key_binding import KeyBindings, KeyPressEvent
from prompt_toolkit.layout import HSplit, Layout, ScrollOffsets, Window
from prompt_toolkit.layout.controls import FormattedTextControl
from prompt_toolkit.layout.dimension import Dimension
from prompt_toolkit.mouse_events import MouseEvent, MouseEventType
from prompt_toolkit.styles import Style
from prompt_toolkit.widgets import Frame

from . import APP_NAME, TAGLINE

Fragments = List[Tuple[str, str]]
DetailRows = Tuple[Tuple[str, str], ...]

_DESC_WIDTH = 46
_FILL = " " * 200  # extends the highlight bar to the screen edge

THEME = Style.from_dict({
    # plain prompt
    "prompt": "bold #5fd7d7",
    "bottom-toolbar": "bg:#1c1c1c #9e9e9e",
    "completion-menu.completion": "bg:#262626 #d0d0d0",
    "completion-menu.completion.current": "bg:#005f87 #ffffff",
    "auto-suggestion": "#5f5f5f",
    # picker chrome
    "header": "bg:#0b3a47 #e6f7fa",
    "header.brand": "bold #5fffff",
    "header.sub": "#8fb8c2",
    "frame.border": "#2a9d9d",
    "frame.label": "bold #5fd7d7",
    "footer": "bg:#1c1c1c #9e9e9e",
    "key": "bold bg:#005f87 #ffffff",
    # rows
    "row": "#d0d0d0",
    "row.cur": "bold bg:#005f87 #ffffff",
    "desc": "#7f8c8d",
    "desc.cur": "nobold #d7efff",
    "check": "bold #5fd75f",
    "ok": "bold #5fd75f",
    "detail.key": "bold #5fd7d7",
    "detail.val": "#d0d0d0",
    # category tags
    "tag.recon": "#5fd7ff",
    "tag.urls": "#87d787",
    "tag.fuzzing": "#ffd75f",
    "tag.scanners": "#ff8787",
    "tag.extras": "#d787ff",
    "tag.passive": "#87d787",
    "tag.active": "#ff8787",
})


@dataclass
class Item:
    """One selectable row.

    Attributes:
        value: Opaque key returned to the caller.
        label: Primary text.
        desc: Dimmed secondary text on the same line.
        tag: Category label rendered in a category colour.
        detail: ``(key, value)`` pairs shown in the detail panel when highlighted.
        installed: Show a green "installed" marker.
    """

    value: str
    label: str
    desc: str = ""
    tag: str = ""
    detail: DetailRows = ()
    installed: bool = False


def clip(text: str, width: int) -> str:
    """Shorten ``text`` to ``width`` characters, ending with an ellipsis."""
    return text if len(text) <= width else text[: width - 1] + "…"


class Tui:
    """Factory for the interactive widgets used by the application."""

    def __init__(self, subtitle: str = "", completions: Sequence[str] = ()) -> None:
        self.subtitle = subtitle
        self._session: PromptSession[str] = PromptSession(
            history=InMemoryHistory(),
            completer=WordCompleter(list(completions), ignore_case=True, pattern=re.compile(r"[^,\s]+")),
            auto_suggest=AutoSuggestFromHistory(),
            style=THEME,
            complete_while_typing=True,
        )

    def ask(self, label: str, default: str = "", toolbar: Optional[str] = None) -> str:
        """Single-line prompt with completion and history. Returns ``""`` on cancel."""
        try:
            answer = str(self._session.prompt([("class:prompt", f"{label} › ")], default=default,
                                              bottom_toolbar=toolbar))
            return answer.strip()
        except (EOFError, KeyboardInterrupt):
            return ""

    def select(self, title: str, items: Sequence[Item]) -> Optional[str]:
        """Pick one item. Returns its ``value`` or ``None`` when cancelled."""
        result = _Picker(self.subtitle, title, items, multi=False).run()
        return result if isinstance(result, str) else None

    def multiselect(self, title: str, items: Sequence[Item]) -> Optional[List[str]]:
        """Tick any number of items. Returns their values or ``None`` when cancelled."""
        result = _Picker(self.subtitle, title, items, multi=True).run()
        return result if isinstance(result, list) else None


class _Picker:
    """Implementation of the list picker (single or multi selection)."""

    def __init__(self, subtitle: str, title: str, items: Sequence[Item], multi: bool) -> None:
        if not items:
            raise ValueError("a picker needs at least one item")
        self.subtitle = subtitle
        self.title = title
        self.items = list(items)
        self.multi = multi
        self.cursor = 0
        self.chosen: List[str] = []
        self._label_w = max(len(i.label) for i in self.items)
        self._tag_w = max((len(i.tag) for i in self.items), default=0)
        self.app: Application[object] = self._build_app()

    def run(self) -> object:
        return self.app.run()

    # -- state ---------------------------------------------------------------
    def _toggle(self, value: str) -> None:
        if value in self.chosen:
            self.chosen.remove(value)
        else:
            self.chosen.append(value)

    def _move(self, delta: int) -> None:
        self.cursor = (self.cursor + delta) % len(self.items)

    def _current(self) -> Item:
        return self.items[self.cursor]

    # -- rendering -----------------------------------------------------------
    def _header(self) -> Fragments:
        return [
            ("class:header.brand", f"\n  ◆ {APP_NAME}"),
            ("class:header.sub", f"   {TAGLINE}\n"),
            ("class:header.sub", f"  {self.subtitle}"),
        ]

    def _rows(self) -> List[Tuple[str, str, Callable[[MouseEvent], object]]]:
        out: List[Tuple[str, str, Callable[[MouseEvent], object]]] = []
        for index, item in enumerate(self.items):
            current = index == self.cursor
            style = "class:row.cur" if current else "class:row"
            click = self._click_handler(index)
            out.append((style, " ▌ " if current else "   ", click))
            if self.multi:
                on = item.value in self.chosen
                out.append((f"{style} class:check" if on else style, "◉ " if on else "○ ", click))
            out.append((style, item.label.ljust(self._label_w) + "  ", click))
            if self._tag_w:
                tag_style = f"{style} class:tag.{item.tag}" if item.tag else style
                out.append((tag_style, item.tag.ljust(self._tag_w) + "  ", click))
            if item.desc:
                out.append((f"{style} class:desc.cur" if current else "class:desc",
                            clip(item.desc, _DESC_WIDTH), click))
            if item.installed:
                out.append((f"{style} class:ok", "  ✔ installed", click))
            if current:
                out.append((style, _FILL, click))
            out.append(("", "\n", click))
        return out[:-1]

    def _detail(self) -> Fragments:
        item = self._current()
        rows = item.detail or (("Info", item.desc or "-"),)
        out: Fragments = []
        for key, value in rows:
            out.append(("class:detail.key", f"  {key:<9}"))
            out.append(("class:detail.val", f"{value}\n"))
        return out

    def _footer(self) -> Fragments:
        hints = [("↑↓", "Move")]
        if self.multi:
            hints += [("Space", "Tick"), ("a", "All"), ("Enter", "Install"), ("q", "Cancel")]
        else:
            hints += [("Enter", "Select"), ("q", "Quit")]
        out: Fragments = []
        for key, label in hints:
            out.append(("class:key", f" {key} "))
            out.append(("class:footer", f" {label}  "))
        return out

    def _frame_title(self) -> str:
        if self.multi:
            return f" {self.title}  ·  {len(self.chosen)}/{len(self.items)} selected "
        return f" {self.title} "

    # -- input ---------------------------------------------------------------
    def _click_handler(self, index: int) -> Callable[[MouseEvent], object]:
        def handler(event: MouseEvent) -> object:
            if event.event_type != MouseEventType.MOUSE_UP:
                return NotImplemented
            self.cursor = index
            if self.multi:
                self._toggle(self.items[index].value)
            else:
                self.app.exit(result=self.items[index].value)
            return None

        return handler

    def _key_bindings(self) -> KeyBindings:
        kb = KeyBindings()

        @kb.add("up")
        @kb.add("k")
        def _up(event: KeyPressEvent) -> None:
            self._move(-1)

        @kb.add("down")
        @kb.add("j")
        def _down(event: KeyPressEvent) -> None:
            self._move(1)

        @kb.add("pageup")
        def _page_up(event: KeyPressEvent) -> None:
            self.cursor = max(0, self.cursor - 5)

        @kb.add("pagedown")
        def _page_down(event: KeyPressEvent) -> None:
            self.cursor = min(len(self.items) - 1, self.cursor + 5)

        @kb.add("home")
        def _home(event: KeyPressEvent) -> None:
            self.cursor = 0

        @kb.add("end")
        def _end(event: KeyPressEvent) -> None:
            self.cursor = len(self.items) - 1

        if self.multi:
            @kb.add("space")
            @kb.add("right")
            def _tick(event: KeyPressEvent) -> None:
                self._toggle(self._current().value)

            @kb.add("a")
            def _all(event: KeyPressEvent) -> None:
                if len(self.chosen) == len(self.items):
                    self.chosen.clear()
                else:
                    self.chosen[:] = [i.value for i in self.items]

        @kb.add("enter")
        def _enter(event: KeyPressEvent) -> None:
            if self.multi:
                event.app.exit(result=list(self.chosen) or [self._current().value])
            else:
                event.app.exit(result=self._current().value)

        @kb.add("escape", eager=True)
        @kb.add("q")
        @kb.add("left")
        @kb.add("c-c")
        def _cancel(event: KeyPressEvent) -> None:
            event.app.exit(result=None)

        return kb

    # -- layout --------------------------------------------------------------
    def _build_app(self) -> "Application[object]":
        rows = FormattedTextControl(self._rows, show_cursor=False,
                                    get_cursor_position=lambda: Point(0, self.cursor))
        root = HSplit([
            Window(FormattedTextControl(self._header), height=Dimension.exact(3), style="class:header"),
            Frame(
                Window(rows, height=Dimension(min=3, weight=1), wrap_lines=False,
                       scroll_offsets=ScrollOffsets(top=1, bottom=1), always_hide_cursor=True),
                title=self._frame_title,
            ),
            Frame(Window(FormattedTextControl(self._detail), height=Dimension.exact(5), wrap_lines=False),
                  title=" details "),
            Window(FormattedTextControl(self._footer), height=Dimension.exact(1), style="class:footer"),
        ])
        return Application(layout=Layout(root), key_bindings=self._key_bindings(), style=THEME,
                           full_screen=True, mouse_support=True)
