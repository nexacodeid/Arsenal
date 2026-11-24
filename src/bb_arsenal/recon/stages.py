"""The recon pipeline: what each stage runs, in what order, and why.

Every stage chains tools that ``bb-arsenal`` installs. Stages are plain data —
no subprocess is started here, so the pipeline can be inspected, tested and
previewed (``--dry-run``) without a terminal or the tools themselves.

Passive/semi-passive stages (subdomain enumeration, resolution, probing,
crawling, URL mining) run by default. Stages that actively hammer a target
(port scanning, parameter brute-forcing, directory fuzzing, XSS scanning) are
``optional`` and carry a scope note — the same pattern used for risky tools
in :mod:`bb_arsenal.registry`.
"""

from __future__ import annotations

import shlex
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, List, Sequence, Tuple, Union

from .workspace import Workspace

#: ("argv", [...]) runs a single tool directly; ("shell", "...") runs through
#: the shell, for pipelines that chain tools with ``|`` the way they are
#: normally used on the command line.
Command = Union[Tuple[str, List[str]], Tuple[str, str]]


@dataclass(frozen=True)
class RunOptions:
    """Parameters shared by every stage in one run."""

    target: str
    threads: int = 50
    wordlist: str = ""


CommandBuilder = Callable[[Workspace, RunOptions], Command]
OutputLocator = Callable[[Workspace], Path]


@dataclass(frozen=True)
class Stage:
    """One step of the pipeline.

    Attributes:
        key: Stable identifier used on the command line and in the UI.
        label: Short display name.
        description: One line shown in the stage picker.
        requires: Binaries that must be on ``PATH`` for this stage to run.
        needs: Stage keys that must run first; pulled in automatically.
        output: Where this stage's main artefact ends up.
        build: Produces the command to run, given a workspace and options.
        timeout: Seconds before the stage is killed.
        optional: ``True`` for active/intrusive stages, off by default.
        note: Caveat shown next to the stage (scope, flags, requirements).
    """

    key: str
    label: str
    description: str
    requires: Tuple[str, ...]
    needs: Tuple[str, ...]
    output: OutputLocator
    build: CommandBuilder
    timeout: int = 1800
    optional: bool = False
    note: str = ""


def _q(path: Path) -> str:
    return shlex.quote(str(path))


# -- stage command builders ---------------------------------------------------

def _subfinder(ws: Workspace, opt: RunOptions) -> Command:
    out = ws.subdomains / "subfinder.txt"
    return ("argv", ["subfinder", "-d", opt.target, "-all", "-silent", "-o", str(out)])


def _assetfinder(ws: Workspace, opt: RunOptions) -> Command:
    out = ws.subdomains / "assetfinder.txt"
    return ("shell", f"assetfinder --subs-only {shlex.quote(opt.target)} > {_q(out)}")


def _merge_subdomains(ws: Workspace, opt: RunOptions) -> Command:
    a, b = ws.subdomains / "subfinder.txt", ws.subdomains / "assetfinder.txt"
    out = ws.subdomains / "all.txt"
    return ("shell", f"cat {_q(a)} {_q(b)} 2>/dev/null | sort -u | anew {_q(out)} >/dev/null")


def _dnsx(ws: Workspace, opt: RunOptions) -> Command:
    src, out = ws.subdomains / "all.txt", ws.subdomains / "resolved.txt"
    return ("argv", ["dnsx", "-l", str(src), "-silent", "-o", str(out)])


def _httpx(ws: Workspace, opt: RunOptions) -> Command:
    src, out = ws.subdomains / "resolved.txt", ws.subdomains / "httpx.txt"
    return ("argv", ["httpx", "-l", str(src), "-silent", "-status-code", "-title",
                     "-tech-detect", "-threads", str(opt.threads), "-o", str(out)])


def _live_hosts(ws: Workspace, opt: RunOptions) -> Command:
    src, out = ws.subdomains / "httpx.txt", ws.subdomains / "live.txt"
    return ("shell", f"awk '{{print $1}}' {_q(src)} > {_q(out)} 2>/dev/null || true")


def _katana(ws: Workspace, opt: RunOptions) -> Command:
    src, out = ws.subdomains / "live.txt", ws.urls / "katana.txt"
    return ("argv", ["katana", "-list", str(src), "-silent", "-jc", "-o", str(out)])


def _gau(ws: Workspace, opt: RunOptions) -> Command:
    out = ws.urls / "gau.txt"
    return ("shell", f"gau --subs {shlex.quote(opt.target)} > {_q(out)}")


def _merge_urls(ws: Workspace, opt: RunOptions) -> Command:
    a, b = ws.urls / "katana.txt", ws.urls / "gau.txt"
    out = ws.urls / "all.txt"
    return ("shell", f"cat {_q(a)} {_q(b)} 2>/dev/null | sort -u | anew {_q(out)} >/dev/null")


def _uro(ws: Workspace, opt: RunOptions) -> Command:
    src, out = ws.urls / "all.txt", ws.urls / "deduped.txt"
    return ("shell", f"uro -i {_q(src)} -o {_q(out)} 2>/dev/null || true")


GF_PATTERNS: Tuple[str, ...] = ("xss", "sqli", "ssrf", "lfi", "redirect", "idor")


def _gf(ws: Workspace, opt: RunOptions) -> Command:
    src = ws.urls / "deduped.txt"
    steps = " && ".join(
        f"(gf {p} < {_q(src)} > {_q(ws.gf / f'{p}.txt')} 2>/dev/null || true)" for p in GF_PATTERNS
    )
    return ("shell", steps)


def _qsreplace(ws: Workspace, opt: RunOptions) -> Command:
    src, out = ws.urls / "deduped.txt", ws.urls / "fuzz_candidates.txt"
    return ("shell", f"grep '=' {_q(src)} 2>/dev/null | qsreplace FUZZ | sort -u "
                     f"| anew {_q(out)} >/dev/null || true")


def _naabu(ws: Workspace, opt: RunOptions) -> Command:
    src, out = ws.subdomains / "resolved.txt", ws.ports / "naabu.txt"
    return ("argv", ["naabu", "-l", str(src), "-s", "c", "-silent", "-o", str(out)])


def _arjun(ws: Workspace, opt: RunOptions) -> Command:
    src, out = ws.urls / "deduped.txt", ws.params / "arjun.txt"
    return ("argv", ["arjun", "-i", str(src), "-oT", str(out)])


def _ffuf(ws: Workspace, opt: RunOptions) -> Command:
    if not opt.wordlist:
        raise ValueError("the ffuf stage needs --wordlist")
    src, out_dir, wl = ws.subdomains / "live.txt", ws.fuzz, shlex.quote(opt.wordlist)
    script = (
        f"while read -r host; do "
        f"slug=$(echo \"$host\" | sed 's#[^a-zA-Z0-9]#_#g'); "
        f"ffuf -u \"$host/FUZZ\" -w {wl} -mc 200,301,302,403 -t {opt.threads} "
        f"-of csv -o {_q(out_dir)}/\"$slug\".csv -s; "
        f"done < {_q(src)}"
    )
    return ("shell", script)


def _dalfox(ws: Workspace, opt: RunOptions) -> Command:
    src, out = ws.gf / "xss.txt", ws.vulns / "dalfox.txt"
    return ("argv", ["dalfox", "file", str(src), "-o", str(out)])


# -- the pipeline ---------------------------------------------------------------

STAGES: Tuple[Stage, ...] = (
    Stage("subfinder", "Subfinder", "Passive subdomain enumeration",
         requires=("subfinder",), needs=(),
         output=lambda ws: ws.subdomains / "subfinder.txt", build=_subfinder),
    Stage("assetfinder", "Assetfinder", "More passive subdomain sources",
         requires=("assetfinder",), needs=(),
         output=lambda ws: ws.subdomains / "assetfinder.txt", build=_assetfinder),
    Stage("merge_subdomains", "Merge subdomains", "Deduplicate subfinder + assetfinder",
         requires=("anew",), needs=("subfinder", "assetfinder"),
         output=lambda ws: ws.subdomains / "all.txt", build=_merge_subdomains),
    Stage("dnsx", "Resolve (dnsx)", "Keep only subdomains that resolve",
         requires=("dnsx",), needs=("merge_subdomains",),
         output=lambda ws: ws.subdomains / "resolved.txt", build=_dnsx),
    Stage("httpx", "Probe (httpx)", "Find live hosts, titles, status codes and tech",
         requires=("httpx",), needs=("dnsx",),
         output=lambda ws: ws.subdomains / "httpx.txt", build=_httpx),
    Stage("live_hosts", "Extract live hosts", "Plain URL list for the stages below",
         requires=(), needs=("httpx",),
         output=lambda ws: ws.subdomains / "live.txt", build=_live_hosts),
    Stage("katana", "Crawl (katana)", "Crawl live hosts for in-scope URLs and JS endpoints",
         requires=("katana",), needs=("live_hosts",),
         output=lambda ws: ws.urls / "katana.txt", build=_katana),
    Stage("gau", "Archive URLs (gau)", "Historical URLs from public archives",
         requires=("gau",), needs=(),
         output=lambda ws: ws.urls / "gau.txt", build=_gau),
    Stage("merge_urls", "Merge URLs", "Deduplicate crawled + archived URLs",
         requires=("anew",), needs=("katana", "gau"),
         output=lambda ws: ws.urls / "all.txt", build=_merge_urls),
    Stage("uro", "Clean URLs (uro)", "Drop noisy, duplicate-shaped URLs",
         requires=("uro",), needs=("merge_urls",),
         output=lambda ws: ws.urls / "deduped.txt", build=_uro),
    Stage("gf", "Pattern mining (gf)", "Sort URLs into XSS / SQLi / SSRF / LFI / redirect / IDOR candidates",
         requires=("gf",), needs=("uro",),
         output=lambda ws: ws.gf / "xss.txt", build=_gf,
         note="needs gf-patterns installed (bb-arsenal --only gf-patterns)"),
    Stage("qsreplace", "Fuzz candidates (qsreplace)", "URLs with parameters marked FUZZ, for manual review",
         requires=("qsreplace", "anew"), needs=("uro",),
         output=lambda ws: ws.urls / "fuzz_candidates.txt", build=_qsreplace),
    Stage("naabu", "Port scan (naabu)", "Connect-scan common ports on resolved hosts",
         requires=("naabu",), needs=("dnsx",),
         output=lambda ws: ws.ports / "naabu.txt", build=_naabu,
         optional=True, note="active scan — in-scope hosts only"),
    Stage("arjun", "Parameter discovery (arjun)", "Brute-force hidden GET/POST parameters",
         requires=("arjun",), needs=("uro",),
         output=lambda ws: ws.params / "arjun.txt", build=_arjun,
         optional=True, note="sends many requests — in-scope hosts only"),
    Stage("ffuf", "Directory fuzzing (ffuf)", "Fuzz for hidden paths on each live host",
         requires=("ffuf",), needs=("live_hosts",),
         output=lambda ws: ws.fuzz, build=_ffuf,
         optional=True, note="needs --wordlist; active scan — in-scope hosts only"),
    Stage("dalfox", "XSS scan (dalfox)", "Confirm reflected/DOM XSS on gf-mined candidates",
         requires=("dalfox",), needs=("gf",),
         output=lambda ws: ws.vulns / "dalfox.txt", build=_dalfox,
         optional=True, note="active scan — in-scope hosts only"),
)

#: Stage keys that run when none are explicitly chosen — passive/semi-passive only.
DEFAULT_STAGES: Tuple[str, ...] = tuple(s.key for s in STAGES if not s.optional)

_BY_KEY = {s.key: s for s in STAGES}


def get_stage(key: str) -> "Stage | None":
    """Look up a stage by key."""
    return _BY_KEY.get(key)


def resolve_order(keys: Sequence[str]) -> List[Stage]:
    """Expand ``keys`` to include their dependencies, in registry order."""
    wanted = set(keys)
    changed = True
    while changed:
        changed = False
        for stage in STAGES:
            if stage.key in wanted:
                for dep in stage.needs:
                    if dep not in wanted:
                        wanted.add(dep)
                        changed = True
    return [s for s in STAGES if s.key in wanted]
