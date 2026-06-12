#!/usr/bin/env python3
"""
One-shot reorganizer for two specific books:

  * MAPDA  — create the missing  notes/_quarto.yml  +  notes/index.qmd
             and rewrite image paths inside chapters/ to climb back to
             the notes/ root (so `Grafiche/…` becomes `../Grafiche/…`).
  * MAPDB  — move every chapter .qmd from notes/ down into
             notes/chapters/, then rewrite asset / include paths inside
             each moved file by prepending "../" so the asset folders
             (Grafiche, imgs, spark, kafka, dask, mysql, parallel) keep
             resolving from their new home.
             Finally update notes/_quarto.yml's chapter list.

Idempotent: re-runs are no-ops once the structure matches.
"""
from __future__ import annotations
import re
import shutil
from pathlib import Path

ROOT = Path("/home/phuniverse/Desktop/master")

# ─── MAPDA ──────────────────────────────────────────────────────────────
MAPDA_NOTES = ROOT / "1sem/MAPDA/notes"

# Pedagogical order — matches the SAP-1 → SAP-2 → SAP-3 progression and
# places the standalone exercises file last.
MAPDA_CHAPTER_ORDER = [
    "chapters/number-systems.qmd",
    "chapters/fundamentals-of-boolean-algebra.qmd",
    "chapters/from-algebra-to-circuits.qmd",
    "chapters/combinatorial-circuits.qmd",
    "chapters/sequential-circuits.qmd",
    "chapters/sap-1.qmd",
    "chapters/sap-2.qmd",
    "chapters/sap-3.qmd",
    "chapters/exercises.qmd",
    "chapters/appendix.qmd",
]

MAPDA_INDEX = """---
title: "Welcome"
---

This is the notebook for the *Management and Analysis of Physics Datasets — Module A* course. It collects the lectures on number systems, Boolean algebra, combinatorial and sequential circuits, the SAP-1/2/3 educational architectures, and a separate chapter of exam-style exercises.

Use the sidebar to navigate the chapters, or browse straight from the table of contents below.
"""

MAPDA_QUARTO_YML = f"""project:
  type: book

book:
  title: "Management and Analysis of Physics Datasets — Module A"
  author: "Master's notes"
  date: today
  chapters:
    - index.qmd
{chr(10).join("    - " + c for c in MAPDA_CHAPTER_ORDER)}

format:
  pdf:
    documentclass: scrbook

execute:
  freeze: auto
  error: true
  eval: false
"""

# Patterns to fix inside MAPDA's chapter files (they live one level deep
# inside chapters/ but were authored assuming the notes/ root). Image refs
# currently like `(Grafiche/Immagini/foo.png)` must become
# `(../Grafiche/Immagini/foo.png)`.
MAPDA_ASSET_PREFIXES = ["Grafiche"]


# ─── MAPDB ──────────────────────────────────────────────────────────────
MAPDB_NOTES = ROOT / "2sem/MAPDB/notes"

# 13 chapter files currently sitting at notes/ root.
MAPDB_CHAPTER_BASENAMES = [
    "01-datasets.qmd",
    "02-storage.qmd",
    "03-reliability-security.qmd",
    "04-file-system.qmd",
    "05-distributed-file-system.qmd",
    "06-databases.qmd",
    "MySQL.qmd",
    "07-nosql-databases.qmd",
    "08-processing-intro.qmd",
    "09-distributed-processing.qmd",
    "10-spark.qmd",
    "11-dask.qmd",
    "12-kafka.qmd",
]
MAPDB_ASSET_PREFIXES = [
    "Grafiche", "imgs", "spark", "kafka", "dask", "mysql", "parallel",
]


# ─── Helpers ────────────────────────────────────────────────────────────
def add_dotdot(text: str, prefixes: list[str]) -> str:
    """
    Inside *text*, prepend "../" to every reference whose path starts
    with one of *prefixes*/.  Targets:

      * Markdown image / link  ](Grafiche/foo.png)
      * HTML src/href           src="Grafiche/foo.png"
      * Quarto include          {{< include Grafiche/foo.qmd >}}

    Strictly idempotent: each rewrite point asserts that the character
    immediately preceding the path prefix is NOT a "." or "/" — so an
    already-prefixed path like `../Grafiche/…` or `/Grafiche/…` is
    skipped.
    """
    if not prefixes:
        return text
    alt = "|".join(re.escape(p) for p in prefixes)

    # Markdown image / link target: ](Grafiche/…), but NOT ](../Grafiche/…
    # nor ](/Grafiche/…)
    md_re = re.compile(rf'(\]\()({alt})/')
    text = md_re.sub(r"\1../\2/", text)

    # Quarto include shortcode (only matches if the path starts directly
    # after `include ` with no leading ../ or /).
    inc_re = re.compile(rf'(\{{\{{<\s*include\s+)({alt})/')
    text = inc_re.sub(r"\1../\2/", text)

    # HTML attributes: src="Grafiche/…"  /  href="Grafiche/…"
    # Quote MUST be the immediate prior character; this avoids matching
    # at arbitrary word boundaries inside an already-rewritten path.
    html_re = re.compile(rf'((?:src|href)\s*=\s*")({alt})/')
    text = html_re.sub(r"\1../\2/", text)

    return text


def remove_dotdot(text: str, prefixes: list[str], extra: int = 1) -> str:
    """
    Reverse op for cleanup: strip *extra* leading `../` segments from any
    reference targeting one of *prefixes*. Used to walk back over-rewrites
    caused by an earlier buggy run.
    """
    if not prefixes or extra <= 0:
        return text
    alt = "|".join(re.escape(p) for p in prefixes)
    over = "(\\.\\./){" + str(extra + 1) + ",}"  # 2+ ../  → strip one
    md_re = re.compile(rf'(\]\()' + over + rf'({alt})/')
    text = md_re.sub(lambda m: m.group(1) + "../" * (m.group(0).count("../") - 1) + m.group(3) + "/", text)
    return text


def rewrite_in_place(qmd: Path, prefixes: list[str]) -> bool:
    src = qmd.read_text(encoding="utf-8")
    dst = add_dotdot(src, prefixes)
    if src == dst:
        return False
    qmd.write_text(dst, encoding="utf-8")
    return True


# ─── MAPDA actions ──────────────────────────────────────────────────────
def do_mapda() -> None:
    print("── MAPDA ───────────────────────────────")
    if not (MAPDA_NOTES / "chapters").is_dir():
        print(f"  ✗  chapters/ missing — nothing to wire up")
        return

    # 1. Fix image paths inside each chapter.
    n_fixed = 0
    for qmd in sorted((MAPDA_NOTES / "chapters").glob("*.qmd")):
        if rewrite_in_place(qmd, MAPDA_ASSET_PREFIXES):
            print(f"  ↻  rewrote refs in chapters/{qmd.name}")
            n_fixed += 1
    if n_fixed == 0:
        print("  ✓  no chapter paths needed rewriting (already converted)")

    # 2. index.qmd
    idx = MAPDA_NOTES / "index.qmd"
    if not idx.exists():
        idx.write_text(MAPDA_INDEX, encoding="utf-8")
        print(f"  +  created {idx.relative_to(ROOT)}")
    else:
        print(f"  ✓  index.qmd already present")

    # 3. _quarto.yml — only create if missing; never clobber a manual one.
    yml = MAPDA_NOTES / "_quarto.yml"
    if not yml.exists():
        yml.write_text(MAPDA_QUARTO_YML, encoding="utf-8")
        print(f"  +  created {yml.relative_to(ROOT)}")
    else:
        print(f"  ✓  _quarto.yml already present — left untouched")


# ─── MAPDB actions ──────────────────────────────────────────────────────
def do_mapdb() -> None:
    print("── MAPDB ───────────────────────────────")
    chapters_dir = MAPDB_NOTES / "chapters"
    chapters_dir.mkdir(exist_ok=True)

    # 1. Move each chapter file into chapters/ and prepend ../ to refs.
    moved = []
    for basename in MAPDB_CHAPTER_BASENAMES:
        src_path = MAPDB_NOTES / basename
        dst_path = chapters_dir / basename
        if dst_path.exists() and not src_path.exists():
            # Already moved on a previous run.
            moved.append(basename)
            continue
        if not src_path.exists():
            print(f"  !  expected {basename} at notes/ root — skipping")
            continue
        # Rewrite asset paths before moving, so the dst file is correct.
        text = src_path.read_text(encoding="utf-8")
        new_text = add_dotdot(text, MAPDB_ASSET_PREFIXES)
        dst_path.write_text(new_text, encoding="utf-8")
        src_path.unlink()
        moved.append(basename)
        print(f"  →  moved {basename}  →  chapters/{basename}  "
              f"({'paths fixed' if new_text != text else 'paths already ok'})")

    # 2. Update _quarto.yml's chapter list: prefix the bare basenames
    # with `chapters/` if they aren't already.
    yml_path = MAPDB_NOTES / "_quarto.yml"
    if yml_path.exists():
        y = yml_path.read_text(encoding="utf-8")
        new_y = y
        for basename in MAPDB_CHAPTER_BASENAMES:
            bare_pattern = re.compile(
                rf'^(\s*-\s*){re.escape(basename)}\s*$',
                re.MULTILINE)
            new_y = bare_pattern.sub(
                lambda m: f"{m.group(1)}chapters/{basename}",
                new_y)
        if new_y != y:
            yml_path.write_text(new_y, encoding="utf-8")
            print(f"  ↻  updated chapter paths in _quarto.yml")
        else:
            print(f"  ✓  _quarto.yml chapter list already prefixed")

    print(f"  {len(moved)}/{len(MAPDB_CHAPTER_BASENAMES)} chapters in chapters/")


def main() -> None:
    do_mapda()
    print()
    do_mapdb()


if __name__ == "__main__":
    main()
