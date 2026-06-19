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

5. **(Optional) add a course repo link** to `Notes/_projects_github.yml`
   so the Projects landing page links to GitHub.

6. **Rebuild the site:**

   ```bash
   ./Notes/render_all.sh
   ```

   The course shows up automatically — `generate_listing.py` scans the
   semester folders and registers any course with a `notes/_quarto.yml`
   or a non-empty `projects/`.

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
