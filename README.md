# Physics of Data Notes

The web can be accessed here: <https://phyamr.github.io/PoDMasternotes/>

---

## Contributing

The repository is meant to be a shared resource. There are two paths. The only available PDF is the one of MAPDA, as is the only course where you can bring your notes to the exam. The rest are intentonally left as html-only books

### Adding or editing a course

The fastest way to start a new course is to copy the template directory
[`Notes/_example_course/`](_example_course/). It ships with a complete
`notes/` skeleton — a book `_quarto.yml`, an `index.qmd`, and three
chapter files that demonstrate every callout type the project preamble
supports (definition, theorem, proposition, lemma, corollary, example,
exercise, solution, remark, note) plus the Quarto built-in callouts
(note, tip, warning, important, caution). The full how-to lives in
[`Notes/_example_course/README.md`](_example_course/README.md).

In short:

1. **Create the semester folder** at the repo root *next to* `Notes/` if
   it doesn't already exist:

   ```bash
   mkdir -p 1sem
   ```

2. **Copy the example into it**, renaming to your course code:

   ```bash
   cp -r Notes/_example_course/  1sem/MYCOURSE/
   ```

3. **Edit `1sem/MYCOURSE/notes/_quarto.yml`** — set the title, replace
   `REPLACE_SEM/REPLACE_COURSE` in `output-dir:` with your real semester
   and course code, and update the `chapters:` list. Leave the
   `metadata-files:` path alone.

4. **Rebuild the site:**

   ```bash
   ./Notes/render_all.sh
   ```

   The new course is auto-discovered and appears in the navbar and on
   the homepage.

For typo fixes, exercise additions, or formatting tweaks in an existing
course, just open a pull request against the relevant chapter file.

This way, if there is a missing course that you want to share, you can contribute it to the repository.

### Discussion and exercise solutions

Every chapter ends with an *Exercises* section, and most `::: {.solution}`
blocks are intentionally left empty — they collapse into a "Solution"
disclosure in the HTML build so the chapter stays useful as study
material.

The main goal of making this public is to create a collaborative space for learning and discussion. Also to serve other students that would like to make their notes available to the community.

The repository's [**Issues page**](../../issues) is the place to:

- **comment and discuss** any chapter, exercise, or worked example;
- **upload your worked solutions** — paste them in a comment in a markdown block
- flag broken links, missing figures, or rendering bugs.

Most chapter-level discussions stay in issues so the books themselves
remain clean. If a community-contributed solution is high-quality and
broadly useful, the maintainers may fold it into the chapter source.
