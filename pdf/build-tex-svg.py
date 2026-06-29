#!/usr/bin/env python3
r"""
build-tex-svg.py — pre-render every TikZ / circuitikz figure that a .qmd
chapter pulls in via raw LaTeX, so the HTML build can serve them as SVG.

Two patterns are handled:

  1. External-file include
     ```{=latex}
     \input{Grafiche/Figure/foo.tex}
     ```
     The .tex file (relative to <course>/notes/) is compiled standalone
     with the shared figure preamble. Output:
        <course>/notes/Grafiche/Figure/foo.svg

  2. Inline raw-LaTeX block containing TikZ / circuitikz / figure env
     ```{=latex}
     \begin{figure}\begin{circuitikz}…\end{circuitikz}\end{figure}
     ```
     Hashed by content, compiled once, cached under
        <course>/notes/Grafiche/_inline_cache/<sha1>.svg

A small JSON index (Grafiche/_inline_cache/index.json) maps each hash
to the original chapter + block index so the Lua filter can replace by
hash without re-walking the AST.

Tools used (all already present on the system):
  * pdflatex
  * pdftocairo -svg   (poppler)

Re-running this script is a no-op for unchanged figures because output
SVGs and cache entries are timestamp/hash-checked.

Usage:
  python3 Notes/pdf/build-tex-svg.py            # scan whole repo
  python3 Notes/pdf/build-tex-svg.py <course>   # one course only
"""

import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

# ── Configuration ──────────────────────────────────────────────────────
ROOT       = Path(__file__).resolve().parents[2]
NOTES_DIR  = Path(__file__).resolve().parent.parent   # …/Notes
SEMESTERS  = ("1sem", "2sem", "3sem", "4sem")

# Standalone preamble used to compile each figure. Keep it minimal but
# matched to what the figures actually use (tikz, circuitikz, libraries,
# the user's colour macros + utility commands). `standalone` crops the
# PDF to the bounding box of the content so the SVG isn't a full page.
PREAMBLE = r"""
\documentclass[border=2pt,varwidth]{standalone}
\PassOptionsToPackage{dvipsnames,svgnames,x11names}{xcolor}
\usepackage{xcolor}
\usepackage{amsmath,amssymb,amsthm,mathtools}
\usepackage{braket}          % \ket, \bra, \braket — used by IQH transmon figures
\usepackage{booktabs,multirow,array,subcaption}
\usepackage{tikz}
\usepackage{circuitikz}
%__PGFPLOTS_SLOT__
\usetikzlibrary{calc, arrows.meta, positioning, shapes.geometric,
                shapes.misc, fit, decorations.pathreplacing,
                decorations.pathmorphing, automata, matrix, chains,
                patterns, patterns.meta, intersections}
\ctikzset{logic ports=ieee, logic ports/scale=0.85}
% Styles defined in the shared Notes preamble — repeated here because
% standalone figures don't see Notes/pdf/preamble.tex.
\tikzset{
  > = stealth,
  thick wire/.style   = {thick, line cap=rect},
  state/.style        = {draw, circle, minimum size=8mm, font=\small},
  initial/.style      = {state, double},
  accepting/.style    = {state, fill=black!8},
  kmap cell/.style    = {draw=gray, minimum size=8mm, font=\small},
  kmap label/.style   = {font=\scriptsize, inner sep=2pt},
  endpoint/.style     = {-{Circle},shorten >=-2pt},
}
\providecommand{\red}   [1]{\textcolor{red}{#1}}
\providecommand{\green} [1]{\textcolor{green!60!black}{#1}}
\providecommand{\orange}[1]{\textcolor{orange}{#1}}
\providecommand{\blue}  [1]{\textcolor{blue!70!black}{#1}}
\providecommand{\purple}[1]{\textcolor{purple}{#1}}
\providecommand{\boldred}   [1]{\textcolor{red}{\boldsymbol{#1}}}
\providecommand{\boldgreen} [1]{\textcolor{green!60!black}{\boldsymbol{#1}}}
\providecommand{\boldorange}[1]{\textcolor{orange}{\boldsymbol{#1}}}
\providecommand{\boldblue}  [1]{\textcolor{blue!70!black}{\boldsymbol{#1}}}
\providecommand{\boldpurple}[1]{\textcolor{purple}{\boldsymbol{#1}}}
\providecommand{\overbar}[1]{\mkern 1.5mu\overline{\mkern-1.5mu#1\mkern-1.5mu}\mkern 1.5mu}
\providecommand{\STAB}[1]{\begin{tabular}{@{}c@{}}#1\end{tabular}}
\providecommand{\thickhline}{\noalign{\hrule height1.2pt}}
% Inside a standalone document, \caption / \label / floats are useless
% (no page to float on, no list of figures). Define them as no-ops so
% chapters that wrap figures in \begin{figure}…\end{figure} still compile.
\providecommand{\caption}[1]{}
\renewcommand{\caption}[2][]{}
\providecommand{\figurelabel}{\label}
\renewcommand{\label}[1]{}
\begin{document}
"""
POSTAMBLE = "\n\\end{document}\n"

# pgfplots is heavyweight (~1–2 s startup) and only a minority of figures
# need it, so we splice it in conditionally — see _build_preamble().
PGFPLOTS_SNIPPET = r"\usepackage{pgfplots}" "\n" r"\pgfplotsset{compat=1.18}"
_PGFPLOTS_USE = re.compile(
    r"\\addplot\b|\\begin\{(?:axis|semilogyaxis|semilogxaxis|loglogaxis|polaraxis)\}"
)


def _build_preamble(tex_body: str) -> str:
    """Return the standalone preamble, loading pgfplots only when the
    body actually uses an axis env or \\addplot."""
    if _PGFPLOTS_USE.search(tex_body):
        return PREAMBLE.replace("%__PGFPLOTS_SLOT__", PGFPLOTS_SNIPPET)
    return PREAMBLE.replace("%__PGFPLOTS_SLOT__", "")


# Strip outer figure / center wrappers so `standalone` doesn't choke on
# floats it has no page for. The inner tikzpicture / circuitikz drawing
# is what we want to crop.
_FIGURE_OPEN  = re.compile(r"\\begin\{(?:figure|table)\}\s*\[[^\]]*\]")
_FIGURE_OPEN2 = re.compile(r"\\begin\{(?:figure|table)\}")
_FIGURE_CLOSE = re.compile(r"\\end\{(?:figure|table)\}")
_CENTER_OPEN  = re.compile(r"\\begin\{center\}")
_CENTER_CLOSE = re.compile(r"\\end\{center\}")
_CAPTION_START = re.compile(r"\\caption\s*(?:\[[^\]]*\])?\s*\{")
_LABEL         = re.compile(r"\\label\s*\{[^}]*\}")


def _strip_balanced_caption(body: str) -> str:
    """Remove every ``\\caption{…}`` from *body*, allowing arbitrary brace
    nesting inside the caption argument (e.g.\\ ``$I_{\\text{in}}$`` which
    has two levels of `{` / `}`).

    The old regex-based stripper only handled one level of nesting, which
    left captions intact in the standalone .tex when they contained subscripts
    with `\\text{…}` and similar — silently passing the caption through to
    pdflatex and, on at least one figure (IQH ``02-fig1.tex``), causing
    pdflatex to sit forever in argument-collection.
    """
    out: list[str] = []
    i = 0
    n = len(body)
    while i < n:
        m = _CAPTION_START.search(body, i)
        if not m:
            out.append(body[i:])
            break
        out.append(body[i:m.start()])
        depth = 1
        j = m.end()
        while j < n and depth > 0:
            c = body[j]
            if c == "{":
                depth += 1
            elif c == "}":
                depth -= 1
            j += 1
        i = j  # skip past the closing brace of the caption argument
    return "".join(out)


def _strip_figure_wrapper(body: str) -> str:
    # subfigure / subcaption needs a real `figure` float to live inside.
    # Keep the wrapper when we detect either.
    has_subfig = ("\\begin{subfigure}" in body
                  or "\\subcaption" in body)
    if not has_subfig:
        body = _FIGURE_OPEN.sub("", body)
        body = _FIGURE_OPEN2.sub("", body)
        body = _FIGURE_CLOSE.sub("", body)
    body = _CENTER_OPEN.sub("", body)
    body = _CENTER_CLOSE.sub("", body)
    body = _strip_balanced_caption(body)
    body = _LABEL.sub("", body)
    body = re.sub(r"\\centering\b", "", body)
    return body

# A raw `{=latex}` block is detected by Pandoc's fenced raw block syntax.
RAW_LATEX_BLOCK = re.compile(
    r"^[ \t]*```\s*\{\s*=latex\s*\}\s*\n(?P<body>.*?)\n[ \t]*```",
    re.DOTALL | re.MULTILINE,
)
INPUT_RE = re.compile(r"\\input\s*\{([^}]+)\}")


def _run(cmd, cwd=None, timeout=60):
    """Run *cmd* with the given timeout (seconds).

    Without a timeout, a hung pdflatex (e.g.\\ waiting on stdin because of
    a malformed argument that survived the figure-wrapper stripping) would
    stall the entire batch indefinitely. Surface the timeout as a synthetic
    failure-style CompletedProcess so callers don't have to learn about a
    new exception type.
    """
    try:
        return subprocess.run(
            cmd, cwd=cwd, capture_output=True, text=True,
            check=False, timeout=timeout,
        )
    except subprocess.TimeoutExpired as e:
        sys.stderr.write(
            f"  ✗ timed out after {timeout}s: {' '.join(cmd)}\n")
        return subprocess.CompletedProcess(
            cmd, returncode=124,                # 124 = canonical "timeout"
            stdout=e.stdout or "", stderr=e.stderr or "")


def _compile_to_svg(tex_body: str, out_svg: Path, *, label: str) -> bool:
    """Compile *tex_body* (figure content only, no preamble) to *out_svg*.
    Returns True on success, False otherwise.
    """
    out_svg.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        tex_path = tmp / "fig.tex"
        tex_path.write_text(
            _build_preamble(tex_body)
            + _strip_figure_wrapper(tex_body) + POSTAMBLE,
            encoding="utf-8")
        # pdflatex: one pass is enough for standalone tikz figures.
        r = _run(["pdflatex", "-interaction=nonstopmode", "-halt-on-error",
                  "fig.tex"], cwd=tmp)
        pdf = tmp / "fig.pdf"
        if not pdf.is_file():
            sys.stderr.write(f"  ✗ pdflatex failed for {label}\n")
            log = (tmp / "fig.log")
            if log.is_file():
                # Show the last few error lines.
                tail = log.read_text(errors="replace").splitlines()[-25:]
                sys.stderr.write("    " + "\n    ".join(tail) + "\n")
            return False
        r2 = _run(["pdftocairo", "-svg", str(pdf), str(out_svg)])
        if r2.returncode != 0 or not out_svg.is_file():
            sys.stderr.write(f"  ✗ pdftocairo failed for {label}\n")
            return False
    return True


def _sha1(text: str) -> str:
    return hashlib.sha1(text.encode("utf-8")).hexdigest()[:16]


def _gather_courses(only: str | None):
    """Yield Path objects for every <course>/notes/ that has chapters."""
    for sem in SEMESTERS:
        sem_dir = ROOT / sem
        if not sem_dir.is_dir():
            continue
        for course in sorted(sem_dir.iterdir()):
            if not course.is_dir():
                continue
            if only and course.name.lower() != only.lower():
                continue
            notes = course / "notes"
            if (notes / "_quarto.yml").is_file():
                yield notes


def process_course(notes_dir: Path) -> tuple[int, int, int]:
    """Pre-render every \\input{} target and every inline TikZ block found
    in this course's chapters. Returns (new, cached, failed) counts."""
    new = cached = failed = 0
    chapter_dir = notes_dir / "chapters"
    if not chapter_dir.is_dir():
        return 0, 0, 0

    inline_cache_dir = notes_dir / "Grafiche" / "_inline_cache"
    index_path       = inline_cache_dir / "index.json"
    inline_index: dict[str, dict] = {}
    if index_path.is_file():
        try:
            inline_index = json.loads(index_path.read_text())
        except json.JSONDecodeError:
            inline_index = {}

    for qmd in sorted(chapter_dir.glob("*.qmd")):
        text = qmd.read_text(encoding="utf-8", errors="replace")

        # ── Pattern 1: \input{X.tex} ────────────────────────────────────
        for m in INPUT_RE.finditer(text):
            inc_rel = m.group(1)
            inc_path = (notes_dir / inc_rel).resolve()
            if not inc_path.is_file():
                sys.stderr.write(
                    f"  ✗ {qmd.name}: \\input{{{inc_rel}}} not found\n")
                failed += 1
                continue
            svg_path = inc_path.with_suffix(".svg")
            if svg_path.is_file() and svg_path.stat().st_mtime >= inc_path.stat().st_mtime:
                cached += 1
                continue
            body = inc_path.read_text(encoding="utf-8", errors="replace")
            print(f"  … compiling {inc_rel}", flush=True)
            if _compile_to_svg(body, svg_path, label=str(inc_rel)):
                print(f"  ✓ {inc_rel}", flush=True)
                new += 1
            else:
                failed += 1

        # ── Pattern 2: inline {=latex} blocks with TikZ-y content ──────
        for i, m in enumerate(RAW_LATEX_BLOCK.finditer(text)):
            body = m.group("body").strip()
            # Skip pure \input{} blocks — handled above.
            if INPUT_RE.fullmatch(body.strip()):
                continue
            # Only the figure-y blocks. Cheap heuristic: must contain a
            # tikzpicture / circuitikz / figure environment.
            if not re.search(r"\\begin\{(tikzpicture|circuitikz|figure|tabular|table)\}", body):
                continue
            h = _sha1(body)
            svg_path = inline_cache_dir / f"{h}.svg"
            if svg_path.is_file():
                cached += 1
            else:
                print(f"  … compiling inline-{h} ({qmd.name})", flush=True)
                if _compile_to_svg(body, svg_path,
                                   label=f"{qmd.name} block #{i}"):
                    print(f"  ✓ inline-{h}.svg ({qmd.name})", flush=True)
                    new += 1
                else:
                    failed += 1
                    continue
            inline_index[h] = {"chapter": qmd.name, "block": i}

    if inline_cache_dir.is_dir():
        index_path.write_text(json.dumps(inline_index, indent=2))
    return new, cached, failed


def main():
    # Line-buffer stdout so each "✓ figure" line appears as it happens, not
    # after the whole batch finishes (Python defaults to block buffering when
    # stdout is not a TTY, e.g. piped or redirected).
    try:
        sys.stdout.reconfigure(line_buffering=True)
    except AttributeError:
        pass  # Python < 3.7 fallback — not expected on this project's stack

    only = sys.argv[1] if len(sys.argv) > 1 else None
    if not shutil.which("pdflatex") or not shutil.which("pdftocairo"):
        sys.stderr.write("error: pdflatex and pdftocairo are required\n")
        sys.exit(2)

    total_new = total_cached = total_failed = 0
    for notes_dir in _gather_courses(only):
        rel = notes_dir.relative_to(ROOT)
        print(f"▶ {rel}", flush=True)
        n, c, f = process_course(notes_dir)
        total_new    += n
        total_cached += c
        total_failed += f

    print()
    print(f"  rendered: {total_new}   cached: {total_cached}   failed: {total_failed}")
    sys.exit(0 if total_failed == 0 else 1)


if __name__ == "__main__":
    main()
