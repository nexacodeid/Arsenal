"""The catalogue of tools BB Arsenal knows how to install."""

from __future__ import annotations

from typing import Iterable, List, Optional, Tuple

from .models import Kind, ToolSpec

CATEGORIES: Tuple[str, ...] = ("recon", "urls", "fuzzing", "scanners", "extras")
CORE_CATEGORIES: Tuple[str, ...] = ("recon", "urls", "fuzzing")

#: System packages installed before any tool (names follow Termux ``pkg``).
BASE_PACKAGES: Tuple[str, ...] = (
    "golang", "git", "python", "python-pip", "nmap", "dnsutils", "whois",
    "jq", "wget", "curl", "tmux", "libpcap", "ripgrep",
)


def _go(name: str, source: str, category: str, *, flag: str = "",
        requires: Tuple[str, ...] = (), note: str = "", optional: bool = False) -> ToolSpec:
    return ToolSpec(name, Kind.GO, source, category, binary=name, version_flag=flag,
                    requires=requires, note=note, optional=optional)


def _pip(name: str, category: str, *, note: str = "", optional: bool = False) -> ToolSpec:
    return ToolSpec(name, Kind.PIP, name, category, binary=name, note=note, optional=optional)


TOOLS: Tuple[ToolSpec, ...] = (
    # recon
    _go("subfinder", "github.com/projectdiscovery/subfinder/v2/cmd/subfinder@latest", "recon", flag="-version"),
    _go("httpx", "github.com/projectdiscovery/httpx/cmd/httpx@latest", "recon", flag="-version"),
    _go("dnsx", "github.com/projectdiscovery/dnsx/cmd/dnsx@latest", "recon", flag="-version"),
    _go("katana", "github.com/projectdiscovery/katana/cmd/katana@latest", "recon", flag="-version"),
    _go("interactsh-client", "github.com/projectdiscovery/interactsh/cmd/interactsh-client@latest", "recon", flag="-version"),
    # urls
    _go("gau", "github.com/lc/gau/v2/cmd/gau@latest", "urls"),
    _go("assetfinder", "github.com/tomnomnom/assetfinder@latest", "urls"),
    _go("anew", "github.com/tomnomnom/anew@latest", "urls"),
    _go("qsreplace", "github.com/tomnomnom/qsreplace@latest", "urls"),
    _go("gf", "github.com/tomnomnom/gf@latest", "urls"),
    _pip("uro", "urls"),
    _pip("arjun", "urls"),
    ToolSpec("gf-patterns", Kind.GIT, "https://github.com/1ndianl33t/Gf-Patterns", "urls",
             note="pattern files for gf, copied to ~/.gf"),
    # fuzzing
    _go("ffuf", "github.com/ffuf/ffuf/v2@latest", "fuzzing", flag="-V"),
    # scanners
    _go("dalfox", "github.com/hahwul/dalfox/v2@latest", "scanners", flag="version",
        note="XSS scanner: in-scope targets only", optional=True),
    _pip("sqlmap", "scanners", note="many programs forbid it: read the policy first", optional=True),
    ToolSpec("wpscan", Kind.GEM, "wpscan", "scanners", binary="wpscan", version_flag="--version",
             requires=("ruby",), note="native extensions may fail to build on Termux", optional=True),
    # extras
    _go("naabu", "github.com/projectdiscovery/naabu/v2/cmd/naabu@latest", "extras", flag="-version",
        requires=("libpcap",), note="non-root: connect scan only (-s c)", optional=True),
)


def get_tool(name: str) -> Optional[ToolSpec]:
    """Return the tool called ``name`` or ``None``."""
    return next((t for t in TOOLS if t.name == name), None)


def select_by_category(categories: Iterable[str]) -> List[ToolSpec]:
    """Return every tool whose category is in ``categories`` (registry order)."""
    wanted = set(categories)
    return [t for t in TOOLS if t.category in wanted]


def select_by_names(names: Iterable[str]) -> Tuple[List[ToolSpec], List[str]]:
    """Resolve ``names`` to specs.

    Returns:
        ``(found, unknown)`` — duplicates are collapsed, order follows ``names``.
    """
    found: List[ToolSpec] = []
    unknown: List[str] = []
    seen = set()
    for raw in names:
        name = raw.strip()
        if not name or name in seen:
            continue
        seen.add(name)
        spec = get_tool(name)
        if spec is None:
            unknown.append(name)
        else:
            found.append(spec)
    return found, unknown
