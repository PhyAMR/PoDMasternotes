"""
generate_listing.py — generates shared configuration for a Quarto site
that hosts multiple book sub-projects (one per course) AND a parallel
"Projects" landing page per course.

ACTUAL directory layout
═══════════════════════
<root>/                              ← root_dir
  Notes/                             ← notes_dir  (this script lives here)
    generate_listing.py
    _metadata.yml                    ← AUTO-GENERATED (shared format + navbar)
    unipd-style.css                  ← hand-written, referenced by all projects
    docs/                            ← ALL rendered output lands here
      index.html                     ← from site/
      1sem/LCPA/index.html           ← theory book   (from 1sem/LCPA/notes/)
      1sem/LCPA/projects.html        ← projects page (from site/1sem/LCPA/projects.qmd)
      1sem/LCPA/projects-files/…     ← copied PDFs/HTMLs/READMEs (by render_all.sh)
      …
    site/                            ← the ONE website project
      _quarto.yml                    ← AUTO-GENERATED  output-dir: ../docs
      index.qmd                      ← hand-written homepage
      _1sem_list.qmd                 ← AUTO-GENERATED semester include
      1sem/LCPA/projects.qmd         ← AUTO-GENERATED projects landing page
      …
  1sem/
    LCPA/
      notes/                         ← theory book   (depth 3 below root)
        _quarto.yml                  ← PATCHED by this script
        index.qmd
        …
      code/
      projects/                      ← scanned for deliverables
    …
  2sem/  …

Two sections per course
═══════════════════════
Every course exposes two URLs:
  /<sem>/<course>/index.html      ← Theory  (the existing Quarto book)
  /<sem>/<course>/projects.html   ← Projects landing (auto-generated)

Both are reachable from the homepage and from the navbar.

Back-to-portal link
═══════════════════
The shared website.navbar from _metadata.yml is inherited by every book
(a book is a website project in Quarto), so the "Home" entry in the navbar
always returns the reader to the portal homepage.
"""

import os
import yaml


# ── helpers ───────────────────────────────────────────────────────────────────

def _rel(target: str, base: str) -> str:
    """POSIX relative path from *base* directory to *target* path."""
    return os.path.relpath(target, base).replace(os.sep, "/")


def _write_yaml(path: str, data: dict) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        yaml.dump(data, fh, default_flow_style=False,
                  sort_keys=False, allow_unicode=True)
    print(f"  wrote {path}")


def _write_text(path: str, text: str) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(text)
    print(f"  wrote {path}")


# ── project discovery ────────────────────────────────────────────────────────

# Folder/file names we always skip when scanning a projects/ directory.
_SKIP_DIRS = {
    "__pycache__", ".venv", "venv", ".ipynb_checkpoints", "node_modules",
    ".quarto", "_freeze", "_extensions", ".git",
}
_SKIP_PREFIXES = (".", "_")  # hidden + underscore-prefixed sidecars
_INTERESTING_EXTS = {".pdf", ".html", ".ipynb", ".qmd", ".md"}


def _interesting(name: str) -> bool:
    return os.path.splitext(name)[1].lower() in _INTERESTING_EXTS


# Folder names that indicate "this is just where the source lives, not the
# project itself" — when found as the build_root, we display the parent name.
_SRC_FOLDER_NAMES = {"report", "report-html", "src", "source", "quarto"}


def _slugify(name: str) -> str:
    """Web-safe slug: lowercase, replace spaces with hyphens, keep alnum/._-."""
    keep = []
    for ch in name.strip():
        if ch.isalnum() or ch in "._-":
            keep.append(ch.lower())
        elif ch in " \t":
            keep.append("-")
    s = "".join(keep).strip("-_.")
    return s or "project"


def _walk_buildable(proj_dir: str) -> list[tuple[str, str]]:
    """
    Walk *proj_dir* and yield (build_root, source_kind) for every folder that
    can be rendered by Quarto. Two passes:

      Pass 1 — folders with a _quarto.yml.
      Pass 2 — folders with a .qmd that have NO ancestor already picked up by
               pass 1 (avoids double-claiming sub-files of a Quarto project).
    """
    yml_roots: list[str] = []
    for root, dirs, files in os.walk(proj_dir):
        dirs[:] = [d for d in dirs
                   if d not in _SKIP_DIRS and not d.startswith(".")]
        if "_quarto.yml" in files:
            yml_roots.append(root)
            # Don't descend further — Quarto owns this subtree.
            dirs[:] = []

    qmd_roots: list[str] = []
    for root, dirs, files in os.walk(proj_dir):
        dirs[:] = [d for d in dirs
                   if d not in _SKIP_DIRS and not d.startswith(".")]
        # Skip anything inside a yml-claimed subtree.
        if any(root == y or root.startswith(y + os.sep) for y in yml_roots):
            continue
        if any(f.endswith(".qmd") for f in files):
            qmd_roots.append(root)

    return [(r, "yml") for r in yml_roots] + [(r, "qmd") for r in qmd_roots]


def _collect_static_files(folder: str) -> list[str]:
    """Return all renderable files inside *folder*, relative to it."""
    out: list[str] = []
    for root, dirs, files in os.walk(folder):
        dirs[:] = [d for d in dirs
                   if d not in _SKIP_DIRS and not d.startswith(".")]
        for f in sorted(files):
            if f.startswith(_SKIP_PREFIXES):
                continue
            if _interesting(f):
                rel = os.path.relpath(os.path.join(root, f), folder)
                out.append(rel.replace(os.sep, "/"))
    return out


def _project_identity(build_root: str, proj_dir: str) -> tuple[str, str]:
    """
    Decide (display_name, project_root) for a project given its build_root.
    If the build_root is a generic source-folder name like "report", the
    project's logical root is the parent folder. Otherwise it is the build
    root itself. *proj_dir* is the course's projects/ directory.
    """
    rel = os.path.relpath(build_root, proj_dir)
    parts = rel.split(os.sep)
    if len(parts) > 1 and parts[-1] in _SRC_FOLDER_NAMES:
        project_root = os.path.join(proj_dir, *parts[:-1])
        name = parts[-2]
    else:
        project_root = build_root
        name = parts[-1] if parts[-1] != "." else os.path.basename(proj_dir)
    return name, project_root


def _scan_projects(proj_dir: str) -> list[dict]:
    """
    Walk a projects/ directory and return one record per discovered project.

    A "project" is a Quarto buildable (folder with _quarto.yml or .qmd). Many
    can live inside one projects/ directory at any nesting depth. Loose
    renderable files at the top level (PDFs / HTML / READMEs not attached to
    any Quarto source) also become "file" items.

    Record shape:
      {
        "name":         <display name>,
        "slug":         <web-safe relative slug, may contain '/'>,
        "kind":         "renderable" | "file",
        "build_root":   <abs path of folder with _quarto.yml / .qmd, or None>,
        "project_root": <abs path of the logical project folder, or None>,
        "files":        [ rel-paths from project_root, for static deliverables ],
      }
    """
    if not os.path.isdir(proj_dir):
        return []

    items: list[dict] = []
    seen_roots: set[str] = set()

    # ── Renderable projects ──
    # For each renderable, the "files" list is intentionally narrow: only the
    # main deliverable PDFs sitting next to the source or at the project root.
    # Figure PDFs nested inside sub-folders (figures/, images/, etc.) are not
    # surfaced as downloads — they're supporting assets, not deliverables.
    _MAIN_NAMES = {"main.pdf", "report.pdf", "project.pdf", "analysis.pdf",
                   "exam.pdf", "relazione.pdf"}

    def _deliverables(build_root: str, project_root: str) -> list[str]:
        seen: list[str] = []
        # PDFs directly in the build root (alongside the .qmd / _quarto.yml).
        for f in sorted(os.listdir(build_root)):
            if f.lower().endswith(".pdf"):
                rel = os.path.relpath(os.path.join(build_root, f), project_root)
                seen.append(rel.replace(os.sep, "/"))
        # Plus any PDF whose basename matches the well-known "main" patterns,
        # found one level inside the project root.
        if project_root != build_root:
            for f in sorted(os.listdir(project_root)):
                if f.lower() in _MAIN_NAMES:
                    if f not in seen:
                        seen.append(f)
        return seen

    for build_root, _ in _walk_buildable(proj_dir):
        name, project_root = _project_identity(build_root, proj_dir)
        if project_root in seen_roots:
            continue
        seen_roots.add(project_root)
        slug_path = os.path.relpath(project_root, proj_dir).replace(os.sep, "/")
        slug = "/".join(_slugify(p) for p in slug_path.split("/"))
        items.append({
            "name":         name,
            "slug":         slug,
            "kind":         "renderable",
            "build_root":   build_root,
            "project_root": project_root,
            "files":        _deliverables(build_root, project_root),
        })

    # ── Loose top-level files (not inside any discovered project_root) ──
    for entry in sorted(os.listdir(proj_dir)):
        if entry.startswith(_SKIP_PREFIXES):
            continue
        full = os.path.join(proj_dir, entry)
        if os.path.isfile(full) and _interesting(entry):
            items.append({
                "name":         entry,
                "slug":         _slugify(entry),
                "kind":         "file",
                "build_root":   None,
                "project_root": None,
                "files":        [entry],
            })

    # ── Static-only top-level folders ────────────────────────────────────────
    # Only IMMEDIATE children of projects/ qualify; deeper nested folders are
    # not treated as separate projects (they're usually supporting assets like
    # figures/, data/, etc.). For each such folder we list only the renderable
    # files at the folder's TOP level — no deep figure dumps.
    rendered_top_children = {
        os.path.relpath(i["project_root"], proj_dir).split(os.sep)[0]
        for i in items if i["kind"] == "renderable" and i["project_root"]
    }
    for entry in sorted(os.listdir(proj_dir)):
        if entry.startswith(_SKIP_PREFIXES) or entry in _SKIP_DIRS:
            continue
        full = os.path.join(proj_dir, entry)
        if not os.path.isdir(full):
            continue
        if entry in rendered_top_children:
            # Already represented by one or more renderable projects.
            continue
        # Only top-level files inside this folder (no recursion).
        try:
            children = sorted(os.listdir(full))
        except OSError:
            continue
        statics = [f for f in children
                   if not f.startswith(_SKIP_PREFIXES)
                   and os.path.isfile(os.path.join(full, f))
                   and _interesting(f)]
        if not statics:
            continue
        items.append({
            "name":         entry,
            "slug":         _slugify(entry),
            "kind":         "static",
            "build_root":   None,
            "project_root": full,
            "files":        statics,
        })

    # Stable sort: renderable first, then static, then loose files.
    rank = {"renderable": 0, "static": 1, "file": 2}
    items.sort(key=lambda i: (rank[i["kind"]], i["slug"]))
    return items


def _load_github_urls(notes_dir: str) -> dict:
    """Read Notes/_projects_github.yml and return a {sem: {course: url}} map.

    The YAML is hand-maintained — one entry per course. Missing entries
    are tolerated; the projects page will then fall through to a
    placeholder URL.
    """
    path = os.path.join(notes_dir, "_projects_github.yml")
    if not os.path.isfile(path):
        return {}
    try:
        with open(path, "r", encoding="utf-8") as fh:
            data = yaml.safe_load(fh) or {}
        return data
    except Exception as exc:
        print(f"  ⚠  could not read {path}: {exc}")
        return {}


def _projects_qmd(course: str, has_theory: bool, github_url: str) -> str:
    """Render the markdown body of a course's projects landing page.

    GitHub-only mode: the page is a short pointer to an external
    repository. Project deliverables are NOT mirrored, NOT rendered
    locally, and NOT linked from this page.
    """
    lines: list[str] = [
        "---",
        f'title: "{course} — Projects"',
        "---",
        "",
    ]
    back_links = []
    if has_theory:
        back_links.append(f"[← {course} notes](index.html)")
    back_links.append("[← Back to portal](/index.html)")
    lines.append("   ·   ".join(back_links))
    lines.append("")
    lines.append("")

    if not github_url or "USERNAME" in github_url:
        lines += [
            f"The project work for **{course}** lives in its own repository.",
            "",
            "<https://github.com/USERNAME/REPO>  *(update this URL in"
            " `Notes/_projects_github.yml`)*",
            "",
        ]
    else:
        lines += [
            f"The project work for **{course}** lives in its own repository.",
            "",
            f"[<i class=\"bi bi-github\"></i>&nbsp; Open the {course} projects"
            f" on GitHub]({github_url}){{.btn .btn-outline-dark .btn-lg role=\"button\"}}",
            "",
            f"<{github_url}>",
            "",
        ]

    return "\n".join(lines)


# ── main ──────────────────────────────────────────────────────────────────────

def generate_site_structure() -> None:

    # ── 0. Resolve directories ────────────────────────────────────────────────
    notes_dir = os.path.dirname(os.path.abspath(__file__))      # <root>/Notes
    root_dir  = os.path.abspath(os.path.join(notes_dir, ".."))  # <root>
    site_dir  = os.path.join(notes_dir, "site")                 # <root>/Notes/site
    docs_dir  = os.path.join(notes_dir, "docs")                 # <root>/Notes/docs

    semesters = ["1sem", "2sem", "3sem", "4sem"]
    sem_labels = {
        "1sem": "First Semester",
        "2sem": "Second Semester",
        "3sem": "Third Semester",
        "4sem": "Fourth Semester",
    }

    # ── 1. Discover book projects + their companion project pages ────────────
    # A valid course has:  <root>/<sem>/<course>/notes/_quarto.yml
    # A course "has projects" if  <root>/<sem>/<course>/projects/  contains
    # any renderable file/dir (see _scan_projects).
    sem_to_courses: dict[str, list[dict]] = {s: [] for s in semesters}

    for sem in semesters:
        sem_path = os.path.join(root_dir, sem)
        if not os.path.isdir(sem_path):
            continue
        for course in sorted(os.listdir(sem_path)):
            course_path = os.path.join(sem_path, course)
            if not os.path.isdir(course_path):
                continue

            notes_path = os.path.join(course_path, "notes")
            book_yml   = os.path.join(notes_path, "_quarto.yml")
            has_theory = os.path.isdir(notes_path) and os.path.isfile(book_yml)

            proj_dir   = os.path.join(course_path, "projects")
            proj_items = _scan_projects(proj_dir)

            # Register the course if EITHER side exists. A course with only
            # projects gets a Projects page; its Theory link is suppressed.
            if not has_theory and not proj_items:
                continue

            sem_to_courses[sem].append({
                "text":           course,
                "has_theory":     has_theory,
                # Absolute hrefs — resolve from any page or book
                "theory_href":   (f"/{sem}/{course}/index.html"
                                  if has_theory else None),
                "projects_href": (f"/{sem}/{course}/projects.html"
                                  if proj_items else None),
                # Relative hrefs for the homepage include lists
                "theory_rel":    (f"{sem}/{course}/index.html"
                                  if has_theory else None),
                "projects_rel":  (f"{sem}/{course}/projects.html"
                                  if proj_items else None),
                "proj_items":     proj_items,
            })

    # ── 2. Build navbar (Quarto navbar max depth = 2) ─────────────────────────
    courses_menu: list[dict] = []
    for i, sem in enumerate(semesters):
        label   = sem_labels[sem]
        courses = sem_to_courses[sem]

        if i > 0:
            courses_menu.append({"text": "---"})

        # Semester heading row — links to the homepage anchor
        courses_menu.append({"text": label, "href": f"/index.html#{sem}"})

        if courses:
            for c in courses:
                # Em-space ( ) gives a visual indent without nested menus
                if c["theory_href"]:
                    courses_menu.append({
                        "text": f" {c['text']} · Theory",
                        "href": c["theory_href"],
                    })
                if c["projects_href"]:
                    courses_menu.append({
                        "text": f" {c['text']} · Projects",
                        "href": c["projects_href"],
                    })
        else:
            courses_menu.append({"text": " (none yet)", "href": "#"})

    navbar_left = [
        {"href": "/index.html", "text": "Home"},
        {"text": "Courses", "menu": courses_menu},
    ]
    navbar_right = [{"icon": "github", "href": "https://github.com/"}]

    # ── 3. Write Notes/_metadata.yml ─────────────────────────────────────────
    metadata_path = os.path.join(notes_dir, "_metadata.yml")
    book_css      = "../../../Notes/unipd-style.css"

    # Anti-copy lockdown: disable text selection / right-click / save / drag
    # on prose & images, but keep code blocks fully selectable so readers
    # can still copy snippets. Trivially defeated by DevTools — this just
    # blocks casual copy-paste, not determined extraction.
    image_protect = (
        "<style>\n"
        "  body, p, li, h1, h2, h3, h4, h5, h6, .quarto-title-block,\n"
        "  .sidebar, .toc-active, .nav-link, table, th, td, blockquote,\n"
        "  figcaption, .callout, .callout-body, .quarto-figure {\n"
        "    user-select: none; -webkit-user-select: none;\n"
        "    -moz-user-select: none; -ms-user-select: none;\n"
        "  }\n"
        "  img, svg, .figure-img, .quarto-figure img {\n"
        "    pointer-events: none; user-select: none;\n"
        "    -webkit-user-drag: none; -webkit-touch-callout: none;\n"
        "  }\n"
        "  pre, pre code, code, .sourceCode, .sourceCode * {\n"
        "    user-select: text !important;\n"
        "    -webkit-user-select: text !important;\n"
        "    -moz-user-select: text !important;\n"
        "  }\n"
        "</style>\n"
        "<script>\n"
        "  document.addEventListener('contextmenu', function(e) {\n"
        "    if (!e.target.closest('pre, code, .sourceCode')) e.preventDefault();\n"
        "  });\n"
        "  document.addEventListener('dragstart', function(e) {\n"
        "    if (e.target.tagName === 'IMG' || e.target.tagName === 'SVG') e.preventDefault();\n"
        "  });\n"
        "  document.addEventListener('copy', function(e) {\n"
        "    var sel = window.getSelection();\n"
        "    if (!sel || sel.rangeCount === 0) return;\n"
        "    var node = sel.getRangeAt(0).commonAncestorContainer;\n"
        "    var el = node.nodeType === 1 ? node : node.parentElement;\n"
        "    if (el && el.closest('pre, code, .sourceCode')) return;\n"
        "    e.preventDefault();\n"
        "  });\n"
        "  document.addEventListener('keydown', function(e) {\n"
        "    var k = e.key.toLowerCase();\n"
        "    if ((e.ctrlKey || e.metaKey) && (k === 's' || k === 'u' || k === 'p')) {\n"
        "      if (!e.target.closest('pre, code, .sourceCode')) e.preventDefault();\n"
        "    }\n"
        "  });\n"
        "</script>"
    )

    # Path from a book's notes/ dir (3 levels below root) to Notes/pdf/…
    pdf_preamble = "../../../Notes/pdf/preamble.tex"
    pdf_filter   = "../../../Notes/pdf/code-output.lua"
    html_filter  = "../../../Notes/pdf/tex-to-svg.lua"

    shared_metadata = {
        "website": {
            "title":  "University Course Portal",
            "navbar": {"left": navbar_left, "right": navbar_right},
        },
        "format": {
            "pdf": {
                # Books can still override / set documentclass in their yml.
                "papersize":         "a4",
                "fontsize":          "11pt",
                "linestretch":       1.15,
                "geometry":          ["margin=2.3cm", "top=2.5cm",
                                      "bottom=2.6cm", "footskip=1.1cm"],
                "colorlinks":        True,
                "linkcolor":         "ink",
                "urlcolor":          "unipdRed",
                "citecolor":         "unipdRed",
                "number-sections":   True,
                "toc-depth":         3,
                "include-in-header": [pdf_preamble],
                "filters":           [pdf_filter],
                "highlight-style":   "tango",
                # Subtle gray fill so code blocks read as a distinct chip
                # against the white body. Pair with the left border.
                "code-block-bg":     "#f3f3f3",
                "code-block-border-left": True,
                # Wrap long code lines instead of letting them overflow.
                "code-overflow":     "wrap",
            },
            "html": {
                "theme":                   ["cosmo", book_css],
                "toc":                     True,
                "toc-depth":               3,
                "number-sections":         True,
                "callout-appearance":      "simple",
                "code-fold":               True,
                "code-tools":              True,
                "code-summary":            "Show code",
                "highlight-style":         "tango",
                # Keep HTML lightweight: figures and JS libs stay as sibling
                # files so chapters are ~100 KB instead of ~150 MB each.
                "embed-resources":         False,
                "self-contained":          False,
                "page-layout":             "full",
                "link-external-icon":      True,
                "link-external-newwindow": True,
                "other-formats":           False,
                # Swap `\input{X.tex}` and inline TikZ blocks for the
                # SVGs pre-rendered by Notes/pdf/build-tex-svg.py. The
                # filter is a no-op for non-HTML output.
                "filters":                 [html_filter],
                "include-after-body":      {"text": image_protect},
            }
        },
    }
    _write_yaml(metadata_path, shared_metadata)

    # ── 4. Write Notes/site/_quarto.yml ──────────────────────────────────────
    os.makedirs(site_dir, exist_ok=True)
    site_quarto_path = os.path.join(site_dir, "_quarto.yml")
    site_config = {
        "project": {
            "type":       "website",
            "output-dir": "../docs",
        },
        "website": {
            "title":  "University Course Portal",
            "navbar": {"left": navbar_left, "right": navbar_right},
            "search": True,
        },
        "format": {
            "html": {
                "theme":           ["cosmo", "../unipd-style.css"],
                "toc":             True,
                "toc-depth":       2,
                "embed-resources": False,
                "self-contained":  False,
                "page-layout":     "full",
            }
        },
    }
    _write_yaml(site_quarto_path, site_config)

    # ── 5. Remove stale Notes/_quarto.yml if present ─────────────────────────
    stale_root_yml = os.path.join(notes_dir, "_quarto.yml")
    if os.path.isfile(stale_root_yml):
        os.remove(stale_root_yml)
        print(f"  removed stale {stale_root_yml}")

    # ── 6. Write homepage semester include files ─────────────────────────────
    # Each entry shows the course name with a Theory link and (if applicable)
    # a Projects link, all relative to the rendered site root (docs/).
    for sem in semesters:
        out_path = os.path.join(site_dir, f"_{sem}_list.qmd")
        courses  = sem_to_courses[sem]
        if courses:
            lines = []
            for c in courses:
                parts = []
                if c["theory_rel"]:
                    parts.append(f"[Theory]({c['theory_rel']})")
                if c["projects_rel"]:
                    parts.append(f"[Projects]({c['projects_rel']})")
                lines.append(f"- **{c['text']}** — " + " · ".join(parts))
        else:
            lines = ["*No courses yet.*"]
        with open(out_path, "w", encoding="utf-8") as fh:
            fh.write("\n".join(lines))
        print(f"  wrote {out_path}")

    # ── 7. Write per-course Projects landing pages ───────────────────────────
    # GitHub-only mode: each page is a short pointer to an external repo.
    # The repo URLs are read from Notes/_projects_github.yml.
    print("\nGenerating Projects landing pages…")
    github_urls = _load_github_urls(notes_dir)
    for sem in semesters:
        for c in sem_to_courses[sem]:
            if not c["projects_rel"]:
                continue
            qmd_path = os.path.join(site_dir, sem, c["text"], "projects.qmd")
            url = github_urls.get(sem, {}).get(c["text"], "")
            _write_text(qmd_path,
                        _projects_qmd(c["text"], c["has_theory"], url))

    # ── 7b. Write empty project build manifest ───────────────────────────────
    # GitHub-only mode: no project sub-books are rendered locally. The
    # manifest is emitted empty so render_all.sh treats every course as
    # "nothing to render here" without needing extra flags.
    manifest_path = os.path.join(notes_dir, "_projects_manifest.tsv")
    _write_text(manifest_path,
                "# sem\tcourse\tslug\tbuild_root\tdocs_html_dir\n")
    print("  (GitHub-only mode — no renderable projects)")

    # ── 8. Patch each book's _quarto.yml ─────────────────────────────────────
    print("\nPatching book _quarto.yml files…")
    for sem in semesters:
        for course_info in sem_to_courses[sem]:
            if not course_info["has_theory"]:
                continue
            course     = course_info["text"]
            notes_path = os.path.join(root_dir, sem, course, "notes")
            book_yml   = os.path.join(notes_path, "_quarto.yml")

            meta_rel = _rel(metadata_path, notes_path)
            out_rel  = _rel(os.path.join(docs_dir, sem, course), notes_path)

            with open(book_yml, "r", encoding="utf-8") as fh:
                cfg = yaml.safe_load(fh) or {}

            cfg.setdefault("project", {})
            cfg["project"]["type"]       = "book"
            cfg["project"]["output-dir"] = out_rel

            existing = cfg.get("metadata-files", [])
            if meta_rel not in existing:
                existing = [meta_rel] + [e for e in existing if e != meta_rel]
            cfg["metadata-files"] = existing

            _write_yaml(book_yml, cfg)

    # ── 9. Summary ───────────────────────────────────────────────────────────
    print("\nDone — all configs written.")
    print("\nDiscovered courses (T = theory, P = projects):")
    for sem in semesters:
        courses = sem_to_courses[sem]
        tag     = sem_labels[sem]
        if courses:
            badges = []
            for c in courses:
                tags = []
                if c["has_theory"]:
                    tags.append("T")
                if c["projects_rel"]:
                    tags.append("P")
                badges.append(f"{c['text']}[{'+'.join(tags)}]")
            print(f"  {tag}: {', '.join(badges)}")
        else:
            print(f"  {tag}: (none)")


if __name__ == "__main__":
    generate_site_structure()
