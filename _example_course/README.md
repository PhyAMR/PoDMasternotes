# Example course template

This directory lives inside `Notes/` (the only public part of the repo)
and is a **template**, not a real course. Copy it whenever you want to
add a new course to the portal.

```
Notes/
└── _example_course/
    ├── README.md                       ← this file
    ├── notes/                          ← the Quarto book sources
    │   ├── _quarto.yml                 ← book config (paths assume depth 3)
    │   ├── index.qmd                   ← preface
    │   ├── references.bib              ← bibliography (BibTeX)
    │   ├── references.qmd              ← the References chapter
    │   └── chapters/
    │       ├── 01-introduction.qmd     ← typical first chapter
    │       ├── 02-callout-tour.qmd     ← every callout type used in the project
    │       └── 03-exercises.qmd        ← exercise + solution pattern
    ├── code/                           ← scratch scripts / experiments
    └── projects/                       ← deliverables (PDFs, notebooks, READMEs)
        └── README.md                   ← surfaces on the course's Projects page
```

## How to add a new course

The portal expects every course to live at `<sem>/<COURSE>/`, where
`<sem>` is a **sibling** of `Notes/` at the repository root. That folder
may not exist yet on a fresh checkout — the steps below create it.

1. **Make sure the semester folder exists** at the repo root, next to
   `Notes/`. Use `1sem`, `2sem`, `3sem`, or `4sem`:

   ```bash
   mkdir -p 1sem        # only if it doesn't already exist
   ```

   Final layout:

   ```
   <repo-root>/
   ├── Notes/                ← stays where it is
   ├── 1sem/                 ← create this if missing
   │   └── MYCOURSE/         ← your new course goes here (next step)
   ├── 2sem/                 ← optional
   └── …
   ```

2. **Copy this template into the semester folder**, renaming it to your
   course code (`LCPA`, `ASPA`, `MAPDB`, …):

   ```bash
   cp -r Notes/_example_course/  1sem/MYCOURSE/
   ```

3. **Edit `1sem/MYCOURSE/notes/_quarto.yml`:**
   - Set the book `title:` and `subtitle:`.
   - Update the `chapters:` list.
   - Replace `REPLACE_SEM/REPLACE_COURSE` in the `output-dir:` with your
     real semester and course code, e.g. `1sem/MYCOURSE`.
   - Leave the `metadata-files:` path alone — it already assumes the
     standard depth `<root>/<sem>/<course>/notes/`.

4. **Write your chapters** in `notes/chapters/`. Use the syntax shown in
   `02-callout-tour.qmd` for definitions, theorems, examples, exercises,
   solutions, remarks, and notes — the preamble in `Notes/pdf/preamble.tex`
   already styles them for PDF and HTML.

   End each chapter with a `## Sources` section that **cites** its
   lectures, books and papers (`@key`, entries in `notes/references.bib`)
   instead of listing them as prose; see *Citations and code in the PDF*
   below.

5. **(Optional) add a course repo link** to `Notes/_projects_github.yml`
   so the Projects landing page links to GitHub.

6. **Rebuild the site:**

   ```bash
   ./Notes/render_all.sh
   ```

   The course shows up automatically — `generate_listing.py` scans the
   semester folders and registers any course with a `notes/_quarto.yml`
   or a non-empty `projects/`.

## Citations and code in the PDF

**Bibliography.** Put every source in `notes/references.bib` and cite it
with Pandoc's syntax: `@feller1968introduction` in running text,
`[@shannon1948mathematical, sec. 2]` in parentheses, `[-@key]` for the
year alone. `references.qmd` (last in the `chapters:` list) prints the full
bibliography; in HTML each chapter page also ends with the works it cites.
Take article metadata from the publisher or Crossref
(`https://api.crossref.org/works?query.bibliographic=...`) rather than
typing it by hand. Course material (slides, lecture notes, homework) goes
in as `@misc` entries.

**Code appendix.** With `code-appendix: true` in `notes/_quarto.yml` (set
in this template), the PDF moves the code of every executed chunk to a
*Code* appendix at the end of the book; the text keeps a linked
reference (*code 2.1 · p. 14*) where the code was, and each block in the
appendix names the figure it draws and links back to its page. Outputs
and plain fenced code (` ```python ` without braces) stay in place; add
`#| classes: keep-code` to a chunk to keep its code in the text. The HTML
build is unchanged: there the code stays folded in place. The filter is
`Notes/pdf/code-appendix.lua`; books without the setting are not affected.

## Math macros

Shared macros (`\abs`, `\norm`, `\sprod`, `\argmin`, `\red`, …) live in
`Notes/pdf/preamble.tex`. The HTML build reads them from there too
(`Notes/pdf/mathjax-macros.lua` hands them to MathJax), so a new macro
works in both outputs as long as it is defined on **one line** with
`\providecommand`, `\newcommand` or `\DeclareMathOperator`. Colour
arguments may use xcolor names and mixes such as `green!60!black`; the
filter converts them for the browser.

## Contributing

This repository is meant as a shared resource. There are two ways to help:

- **Pull requests** for typo fixes, formatting tweaks, new exercises, or
  new chapters. Keep prose changes minimal and aligned with the existing
  voice; the project maintainers will review and merge.
- **GitHub Issues** — the issues page is the place to:
  - **comment and discuss** any chapter or exercise,
  - **upload solutions** to the exercise sets (paste your working in a
    comment, or attach a notebook / photo of paper work),
  - flag broken links, missing figures, or rendering bugs.

Open an issue at the repository's [Issues page](../../issues) — most
discussions stay there so the chapters themselves remain clean.

## Conventions

- **File names** are lowercase with hyphens (`my-chapter.qmd`).
- **Chapter numbers** prefix the filename (`07-clustering.qmd`) so the
  alphabetical order matches the reading order. The book's actual order
  comes from the `chapters:` list in `_quarto.yml`, not the filenames.
- **Math** uses `$ … $` inline and `$$ … $$` block; `align`/`equation`
  environments live inside the block form.
- **Figures** generated from code use `dev: png` (set globally) so the
  HTML build never sees a stray PDF figure.
- **Exercise solutions** are wrapped in `::: {.solution}` — the HTML
  build collapses them by default behind a "Solution" disclosure.
