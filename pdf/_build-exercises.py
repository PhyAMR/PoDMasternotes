#!/usr/bin/env python3
"""
Rebuilds  1sem/MAPDA/notes/chapters/exercises.qmd  from two sources:

  1. The CURRENT exercises.qmd, which holds 25 already-worked exam
     exercises with the solution inlined after the italic question.
     For each such exercise we split the body at the last italic
     paragraph, wrap everything after it in `:::{.solution} … :::`,
     and tag the exercise with the exam date.

  2. The 13 raw exam papers (Exam_<DDMMYY>.md) the user uploaded — each
     with 12 numbered questions. Every question becomes an `.exercise`
     div with the question text italicised and an empty `.solution`
     callout below for the user to fill in.

Output is grouped by exam date (chronological).  Inside each exam
section, the worked exercises come first, followed by every question
from the corresponding exam paper.  Exams with no worked exercises just
get the question list.
"""
from __future__ import annotations
import re
from pathlib import Path
from datetime import date

ROOT = Path("/home/phuniverse/Desktop/master")
EX_FILE = ROOT / "1sem/MAPDA/notes/chapters/exercises.qmd"
UPLOADS = Path(
    "/home/phuniverse/.config/Claude/local-agent-mode-sessions/"
    "78c9b41d-89ec-49d2-accb-bc0d8966e354/"
    "b0be03c0-a51a-427a-8769-7c13676e11d9/"
    "local_cf84192e-4059-4839-9fe1-0b58229219ad/uploads"
)

# Exams that actually have content (the three CamScanner stubs are skipped).
EXAM_FILES = [
    "Exam_221122.md",   # 22 November 2022
    "Exam_030223.md",   # 03 February 2023
    "Exam_240223.md",   # 24 February 2023
    "Exam_230323.md",   # 23 March 2023
    "Exam_230623.md",   # 23 June 2023
    "Exam_210723.md",   # 21 July 2023
    "Exam_010923.md",   # 01 September 2023
    "Exam_131123.md",   # 13 November 2023
    "Exam_250124.md",   # 25 January 2024
    "Exam_220224.md",   # 22 February 2024
    "Exam_200624.md",   # 20 June 2024
    "Exam_110724.md",   # 11 July 2024
    "Exam_290824.md",   # 29 August 2024
]

MONTHS = ["", "January", "February", "March", "April", "May", "June",
          "July", "August", "September", "October", "November", "December"]


def date_from_filename(fname: str) -> date:
    """Exam_DDMMYY.md → date()."""
    m = re.match(r"Exam_(\d{2})(\d{2})(\d{2})\.md", fname)
    d, mm, yy = m.group(1), m.group(2), m.group(3)
    return date(2000 + int(yy), int(mm), int(d))


def short_date(d: date) -> str:
    return f"{d.day:02d}/{d.month:02d}/{d.year % 100:02d}"


def full_date(d: date) -> str:
    return f"{d.day} {MONTHS[d.month]} {d.year}"


# ──────────────────────────────────────────────────────────────────────
# 1. Parse the CURRENT exercises.qmd
# ──────────────────────────────────────────────────────────────────────
EX_OPENER = re.compile(r'^::: \{\.exercise\}\s*$')
EX_CLOSER = re.compile(r'^:::\s*$')
DATE_LINE = re.compile(r'^\(Exam\s*-\s*(\d{2}/\d{2}/\d{2})\)\s*$')

# A paragraph is "italic" if it starts with `*` and ends with `*`
# (allowing the closing `*` to sit at end of last line of the paragraph).
def paragraph_is_italic(par: str) -> bool:
    par = par.strip()
    return par.startswith("*") and par.endswith("*") and len(par) > 1


def split_into_paragraphs(lines: list[str]) -> list[tuple[int, int, str]]:
    """Return list of (start_idx, end_idx_exclusive, joined_text)."""
    out, n = [], len(lines)
    i = 0
    while i < n:
        if lines[i].strip() == "":
            i += 1; continue
        j = i
        while j < n and lines[j].strip() != "":
            j += 1
        out.append((i, j, "\n".join(lines[i:j])))
        i = j + 1
    return out


def split_exercise_body(body_lines: list[str]) -> tuple[str, str]:
    """
    Returns (exercise_text, solution_text), each a string with trailing
    newline. The exercise text is everything up to and including the
    final italic paragraph; the solution is everything after.
    Any leading `(Exam - …)` line is dropped (encoded as the env name
    instead).
    """
    # Drop the date line.
    if body_lines and DATE_LINE.match(body_lines[0]):
        body_lines = body_lines[1:]
    # Drop a leading blank.
    while body_lines and body_lines[0].strip() == "":
        body_lines = body_lines[1:]

    paragraphs = split_into_paragraphs(body_lines)
    last_italic = -1
    for k, (_, _, par) in enumerate(paragraphs):
        if paragraph_is_italic(par):
            last_italic = k

    if last_italic < 0:
        # No italic paragraph at all — treat the whole body as the exercise.
        return "\n".join(body_lines).rstrip() + "\n", ""

    cut_end = paragraphs[last_italic][1]   # exclusive
    exercise_lines = body_lines[:cut_end]
    solution_lines = body_lines[cut_end:]
    # Trim leading/trailing blanks on the solution.
    while solution_lines and solution_lines[0].strip() == "":
        solution_lines = solution_lines[1:]
    while solution_lines and solution_lines[-1].strip() == "":
        solution_lines.pop()
    return ("\n".join(exercise_lines).rstrip() + "\n",
            "\n".join(solution_lines).rstrip() + "\n" if solution_lines else "")


def parse_existing() -> list[dict]:
    raw = EX_FILE.read_text(encoding="utf-8").splitlines()
    out: list[dict] = []
    i, n = 0, len(raw)
    while i < n:
        if EX_OPENER.match(raw[i]):
            # Capture the date line (if present) then body until closer.
            i += 1
            body: list[str] = []
            d_str = None
            if i < n:
                m = DATE_LINE.match(raw[i])
                if m:
                    d_str = m.group(1)
            # Read until closing :::
            while i < n and not EX_CLOSER.match(raw[i]):
                body.append(raw[i]); i += 1
            i += 1  # skip the closer
            ex_text, sol_text = split_exercise_body(body)
            if d_str:
                dd, mm, yy = d_str.split("/")
                dt = date(2000 + int(yy), int(mm), int(dd))
            else:
                dt = None
            out.append({"date": dt, "exercise": ex_text, "solution": sol_text})
        else:
            i += 1
    return out


# ──────────────────────────────────────────────────────────────────────
# 2. Parse exam papers
# ──────────────────────────────────────────────────────────────────────
QUESTION_OPEN = re.compile(r'^(\d{1,2})\)\s+(.*)')
PTS = re.compile(r'\((\d+)\s*pts?\)')


def parse_exam(path: Path) -> list[dict]:
    """Returns a list of {n, text, pts} for each question."""
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines()
    # Locate the start of question 1
    start = None
    for i, ln in enumerate(lines):
        if QUESTION_OPEN.match(ln) and QUESTION_OPEN.match(ln).group(1) == "1":
            start = i; break
    if start is None:
        return []
    # Walk forward; each question runs until the next "N)" or EOF.
    questions: list[dict] = []
    cur_n = None
    cur_lines: list[str] = []

    def flush():
        if cur_n is None: return
        body = "\n".join(cur_lines).strip()
        # Pull out the pts marker.
        pts_match = PTS.search(body)
        pts = pts_match.group(1) if pts_match else ""
        if pts_match:
            body = PTS.sub("", body).strip()
        # Collapse runs of blank lines and dangling whitespace.
        body = re.sub(r"\n{3,}", "\n\n", body)
        questions.append({"n": int(cur_n), "text": body, "pts": pts})

    for ln in lines[start:]:
        m = QUESTION_OPEN.match(ln)
        if m and m.group(1).isdigit() and 1 <= int(m.group(1)) <= 20:
            flush()
            cur_n = m.group(1)
            cur_lines = [m.group(2)]
        else:
            if cur_n is not None:
                cur_lines.append(ln)
    flush()
    return questions


# ──────────────────────────────────────────────────────────────────────
# 3. Emit the rebuilt file
# ──────────────────────────────────────────────────────────────────────
HEADER = """# Exercises

Past-exam exercises for *Management and Analysis of Physics Datasets — Module A*, grouped chronologically by exam date.

Each item is presented as a self-contained problem (the question text is *italic*) followed by a collapsible solution block: previously worked solutions are pre-filled, the new exam papers carry empty `Solution` placeholders ready to be filled in.

"""


def safe(s: str) -> str:
    """Escape stray double-quotes for use as an HTML attribute."""
    return s.replace('"', '\\"')


def emit_exercise(name: str, body: str, solution: str | None) -> str:
    parts = [f'::: {{.exercise name="{safe(name)}"}}\n',
             body.rstrip() + "\n",
             ':::\n\n',
             '::: {.solution}\n']
    if solution and solution.strip():
        parts.append(solution.rstrip() + "\n")
    else:
        parts.append("*(to fill in)*\n")
    parts.append(":::\n\n")
    return "".join(parts)


def main() -> None:
    existing = parse_existing()
    print(f"  parsed {len(existing)} existing exercises")

    exams: dict[date, list[dict]] = {}
    for fname in EXAM_FILES:
        d = date_from_filename(fname)
        qs = parse_exam(UPLOADS / fname)
        exams[d] = qs
        print(f"  parsed {fname:18s}  {len(qs):2d} question(s)")

    # Collect every date that appears anywhere, sort ascending.
    all_dates = sorted(set(exams) | {e["date"] for e in existing if e["date"]})

    out = [HEADER]
    for d in all_dates:
        out.append(f"## Exam — {full_date(d)}\n\n")
        worked = [e for e in existing if e["date"] == d]
        if worked:
            for i, ex in enumerate(worked, start=1):
                name = f"Worked exercise {i} — {short_date(d)}"
                out.append(emit_exercise(name, ex["exercise"], ex["solution"]))
        if d in exams and exams[d]:
            if worked:
                out.append("### From the exam paper\n\n")
            for q in exams[d]:
                name = f"Q{q['n']}"
                if q["pts"]:
                    name += f" — {q['pts']} pts"
                body = "*" + q["text"].strip().rstrip("*").lstrip("*") + "*"
                out.append(emit_exercise(name, body, None))

    EX_FILE.write_text("".join(out), encoding="utf-8")
    print(f"\n  wrote {EX_FILE} ({len(out)} chunks)")


if __name__ == "__main__":
    main()
