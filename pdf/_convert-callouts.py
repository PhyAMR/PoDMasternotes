#!/usr/bin/env python3
"""
Repo-wide callout converter.

Walks every *.qmd file under <root>/<sem>/<course>/notes/ and converts
legacy callout / custom-env patterns into the unified theorem-like div
classes recognised by Notes/pdf/code-output.lua, namely:

    .exercise .example .solution
    .theorem .proposition .lemma .corollary
    .definition .remark .note

Decision logic
══════════════
A callout is rewritten when EITHER:

  (a) it carries a `title=` attribute that maps to a known env, e.g.
      `::: {.callout-tip title="Exercise"}`     → `::: {.exercise}`
      `::: {.callout-tip title="Exercise (X)"}` → `::: {.exercise name="X"}`
      `::: {.callout-note title="Definition"}`  → `::: {.definition}`
      `::: {.callout-warning title="Wick's theorem"}` → `::: {.theorem name="…"}`

  (b) it has NO title attribute but the first `## …` heading inside its
      body matches a known env, e.g.
          ::: {.callout-tip}
          ## Question 3 — Filtering Rows with Masking
          …
          :::
      becomes
          ::: {.exercise name="Question 3 — Filtering Rows with Masking"}
          …
          :::
      (the heading is consumed.)

  (c) MAPDA-only: the legacy custom divs `ebox` / `eboxtwo`.

Anything that doesn't match a rule is left untouched.

Idempotent — re-running it on already-converted files is a no-op.
"""
from __future__ import annotations
import re
from pathlib import Path

ROOT = Path("/home/phuniverse/Desktop/master")

# Map first word of inner-heading or title-attribute (lower-case) → env.
# Italian + English keywords supported.
WORD_TO_ENV = {
    "question":     "exercise",
    "questions":    "exercise",
    "exercise":     "exercise",
    "exercises":    "exercise",
    "problem":      "exercise",
    "esercizio":    "exercise",
    "query":        "exercise",
    "solution":     "solution",
    "soluzione":    "solution",
    "definition":   "definition",
    "definizione":  "definition",
    "theorem":      "theorem",
    "teorema":      "theorem",
    "lemma":        "lemma",
    "proposition":  "proposition",
    "proposizione": "proposition",
    "corollary":    "corollary",
    "corollario":   "corollary",
    "example":      "example",
    "esempio":      "example",
    "remark":       "remark",
    "note":         "remark",
    "notes":        "remark",
    "observation":  "remark",
    "osservazione": "remark",
    # We leave .callout-warning / .callout-important alone unless the
    # heading inside identifies them as one of the categories above.
}

# Heading lines: "## Title", possibly "### Title".
HEADING_RE = re.compile(r"^(?P<hashes>#{2,3})\s+(?P<title>.+?)\s*$")
# Callout opener: ::: {.callout-XXX  ...attrs...} optionally with title=.
CALLOUT_OPEN_RE = re.compile(
    r'^(?P<colons>:{3,})\s*\{\s*\.callout-[a-z]+\b(?P<attrs>[^}]*)\}\s*$')
# A bare `:::` (close) — matches if the line is just colons.
CLOSE_RE = re.compile(r'^(?P<colons>:{3,})\s*$')


def _attr_value(attrs: str, key: str) -> str | None:
    m = re.search(rf'\b{key}\s*=\s*"([^"]*)"', attrs)
    return m.group(1) if m else None


def _classify(text: str) -> tuple[str | None, str | None]:
    """
    Look up *text* against WORD_TO_ENV.
    Returns (env, name) where *name* is the trailing part after the keyword,
    suitable as the env's name= attribute, or None if no rule matched.
    """
    if not text:
        return (None, None)
    # Strip Markdown emphasis (italic / bold) so "*Exercise*" matches.
    stripped = re.sub(r"[*_`]", "", text).strip()
    # First word, lowercased.
    parts = stripped.split()
    if not parts:
        return (None, None)
    head = parts[0].rstrip(":.,").lower()
    env = WORD_TO_ENV.get(head)
    # Fallback: try the SECOND word as well, to catch multi-word labels
    # like "Worked Example: …" or "Optional Exercise — …".
    if env is None and len(parts) >= 2:
        env = WORD_TO_ENV.get(parts[1].rstrip(":.,").lower())
        if env is not None:
            # Drop both leading words from the captured "rest".
            stripped = " ".join(parts[2:])
            parts = stripped.split(None, 1) if stripped else [""]
    if env is None:
        return (None, None)
    # The "name" is anything after the keyword (skip a numeric counter and
    # punctuation, then take the rest as the title).
    rest = parts[1] if len(parts) > 1 else ""
    rest = re.sub(r"^\d+\s*[.:—–-]*\s*", "", rest).strip()
    rest = rest.strip(" .,:;—–-")
    return (env, rest or None)


def _format_div(env: str, name: str | None, colons: str) -> str:
    if name:
        # Escape stray double-quotes
        safe = name.replace('"', '\\"')
        return f'{colons} {{.{env} name="{safe}"}}'
    return f'{colons} {{.{env}}}'


def convert_callouts(text: str) -> str:
    """
    Generic callout converter. Single forward pass; rebuilds the file.
    """
    lines = text.splitlines(keepends=False)
    out: list[str] = []
    i = 0
    while i < len(lines):
        line = lines[i]
        m = CALLOUT_OPEN_RE.match(line)
        if not m:
            out.append(line)
            i += 1
            continue

        colons = m.group("colons")
        attrs  = m.group("attrs") or ""
        title  = _attr_value(attrs, "title")

        # Case (a): title attribute present.
        if title is not None:
            env, name = _classify(title)
            if env is not None:
                # If the title was just the keyword ("Exercise"), drop name;
                # otherwise pick up the remainder.
                # If _classify saw something like "Exercise (Assigned …)",
                # `name` becomes "(Assigned …)" — strip outer parens.
                if name and name.startswith("(") and name.endswith(")"):
                    name = name[1:-1].strip()
                out.append(_format_div(env, name, colons))
                i += 1
                continue
            # No mapping → leave the callout alone.
            out.append(line)
            i += 1
            continue

        # Case (b): no title attribute. Look at the next non-blank line for
        # a "## Title" heading.
        j = i + 1
        while j < len(lines) and lines[j].strip() == "":
            j += 1
        if j >= len(lines):
            out.append(line); i += 1; continue

        h = HEADING_RE.match(lines[j])
        if not h:
            out.append(line); i += 1; continue

        env, name = _classify(h.group("title"))
        if env is None:
            out.append(line); i += 1; continue

        # Rewrite the opener; drop the heading line.
        out.append(_format_div(env, name, colons))
        # Skip the blank lines + the heading line.
        i = j + 1
        continue

    return "\n".join(out) + ("\n" if text.endswith("\n") else "")


# ── MAPDA legacy custom divs (ebox / eboxtwo) ────────────────────────
EBOXTWO_RE = re.compile(r'^::: eboxtwo\s*$', re.MULTILINE)
EBOX_RE    = re.compile(r'^::: ebox\s*$',    re.MULTILINE)


def convert_mapda(text: str) -> str:
    text = EBOXTWO_RE.sub("::: {.example}",  text)
    text = EBOX_RE.sub   ("::: {.exercise}", text)
    text = convert_callouts(text)
    return text


# ── Discovery ─────────────────────────────────────────────────────────
def each_book_notes() -> list[Path]:
    found: list[Path] = []
    for sem in ("1sem", "2sem", "3sem", "4sem"):
        sem_dir = ROOT / sem
        if not sem_dir.is_dir():
            continue
        for course in sorted(sem_dir.iterdir()):
            notes = course / "notes"
            if notes.is_dir():
                found.append(notes)
    return found


# ── Driver ────────────────────────────────────────────────────────────
def main() -> None:
    SKIP_DIRS = {"_freeze", ".quarto", "_extensions", "_book", ".venv"}
    grand_changed = 0
    for notes_dir in each_book_notes():
        course_label = f"{notes_dir.parent.parent.name}/{notes_dir.parent.name}"
        # Decide which converter applies. MAPDA still uses ebox legacy.
        is_mapda = "MAPDA" in str(notes_dir)
        fn = convert_mapda if is_mapda else convert_callouts
        n_files_changed = 0
        n_callouts_rewritten = 0
        for qmd in notes_dir.rglob("*.qmd"):
            if any(p in SKIP_DIRS for p in qmd.parts):
                continue
            src = qmd.read_text(encoding="utf-8")
            dst = fn(src)
            if src == dst:
                continue
            # Count how many opener lines changed (= callouts rewritten).
            src_opens = sum(1 for ln in src.splitlines()
                            if CALLOUT_OPEN_RE.match(ln) or
                            ln.startswith("::: ebox"))
            dst_opens = sum(1 for ln in dst.splitlines()
                            if CALLOUT_OPEN_RE.match(ln) or
                            ln.startswith("::: ebox"))
            rewritten = max(0, src_opens - dst_opens)
            n_callouts_rewritten += rewritten
            n_files_changed += 1
            qmd.write_text(dst, encoding="utf-8")
        if n_files_changed:
            print(f"  {course_label:18s}  files={n_files_changed:3d}  "
                  f"callouts rewritten={n_callouts_rewritten}")
            grand_changed += n_callouts_rewritten
    print(f"\nTOTAL callouts rewritten: {grand_changed}")


if __name__ == "__main__":
    main()
