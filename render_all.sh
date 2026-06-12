#!/usr/bin/env bash
# render_all.sh — renders the whole site: theory books + per-project HTML
# pages + the umbrella website.
#
# Usage:
#   ./render_all.sh                 # full rebuild
#   ./render_all.sh --no-gen        # skip generate_listing.py
#   ./render_all.sh --no-projects   # skip rendering project HTML pages
#   ./render_all.sh --only-projects # only render the projects (and mirror)
#
# Render order:
#   1. generate_listing.py    — writes _metadata.yml, site/_quarto.yml,
#                               patches every book's _quarto.yml,
#                               writes Notes/_projects_manifest.tsv
#   2. Each theory book       — <root>/<sem>/<course>/notes/
#                               output → Notes/docs/<sem>/<course>/
#   3. Each renderable project — from manifest; build_root is the folder
#                               with _quarto.yml or .qmd
#                               PDF stays in place (per the project's yml)
#                               HTML  → Notes/docs/<sem>/<course>/projects/<slug>/
#   4. Main website            — Notes/site/
#                               output → Notes/docs/
#   5. Mirror PDFs / static deliverables from each course's projects/
#      into Notes/docs/<sem>/<course>/projects-files/ so the projects.html
#      landing page's "Download PDF" links resolve.

set -euo pipefail

# ── Flags ────────────────────────────────────────────────────────────────────
DO_GEN=1
DO_BOOKS=1
DO_PROJECTS=1
DO_SITE=1
for arg in "$@"; do
    case "$arg" in
        --no-gen)         DO_GEN=0 ;;
        --no-projects)    DO_PROJECTS=0 ;;
        --only-projects)  DO_GEN=0; DO_BOOKS=0; DO_SITE=0 ;;
        --no-books)       DO_BOOKS=0 ;;
        --no-site)        DO_SITE=0 ;;
        *) echo "unknown flag: $arg" ; exit 2 ;;
    esac
done

# ── Resolve paths ────────────────────────────────────────────────────────────
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"  # <root>/Notes
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
NOTES_DIR="$SCRIPT_DIR"
SITE_DIR="$NOTES_DIR/site"
DOCS_DIR="$NOTES_DIR/docs"
MANIFEST="$NOTES_DIR/_projects_manifest.tsv"

# Run quarto with uv if available, otherwise straight quarto.
quarto_cmd() {
    if command -v uv &>/dev/null; then
        uv run quarto "$@"
    else
        quarto "$@"
    fi
}

echo "╔══════════════════════════════════════════════════╗"
echo "║          Quarto Notes — Full Render              ║"
echo "╠══════════════════════════════════════════════════╣"
echo "  root  : $ROOT_DIR"
echo "  output: $DOCS_DIR"
echo "╚══════════════════════════════════════════════════╝"
echo ""

# ── Step 1: Regenerate configs ───────────────────────────────────────────────
if (( DO_GEN )); then
    echo "▶ Generating metadata & patching configs…"
    if command -v uv &>/dev/null; then
        uv run "$NOTES_DIR/generate_listing.py"
    else
        python3 "$NOTES_DIR/generate_listing.py"
    fi
    echo ""
fi

# ── Step 1b: Pre-render TikZ / \input{} figures to SVG ───────────────────────
# Quarto's HTML target can't draw TikZ / circuitikz. We compile each
# referenced .tex figure (and every inline TikZ block) to PDF→SVG once
# and cache the result alongside the figure. The HTML build's Lua filter
# (Notes/pdf/tex-to-svg.lua) then swaps the raw-LaTeX block for the SVG.
# Idempotent: re-renders only what changed.
if (( DO_BOOKS )) && [[ -f "$NOTES_DIR/pdf/build-tex-svg.py" ]]; then
    echo "▶ Pre-rendering TikZ figures to SVG…"
    if command -v uv &>/dev/null; then
        uv run "$NOTES_DIR/pdf/build-tex-svg.py" || true
    else
        python3 "$NOTES_DIR/pdf/build-tex-svg.py" || true
    fi
    echo ""
fi

# ── Step 2: Render each theory book ──────────────────────────────────────────
SEMESTERS=("1sem" "2sem" "3sem" "4sem")
BOOK_COUNT=0
PROJECT_COUNT=0
FAIL_COUNT=0
FAILED_BOOKS=()
FAILED_PROJECTS=()

if (( DO_BOOKS )); then
    for sem in "${SEMESTERS[@]}"; do
        SEM_PATH="$ROOT_DIR/$sem"
        [[ -d "$SEM_PATH" ]] || continue
        for course_path in "$SEM_PATH"/*/; do
            [[ -d "$course_path" ]] || continue
            notes_dir="$course_path/notes"
            [[ -f "$notes_dir/_quarto.yml" ]] || continue

            course_name="$(basename "$course_path")"
            echo "──────────────────────────────────────────────────"
            echo "  📖  $sem / $course_name  (theory)"
            echo "──────────────────────────────────────────────────"

            pushd "$notes_dir" > /dev/null
            if quarto_cmd render; then
                (( BOOK_COUNT++ )) || true
            else
                echo "  ✗  render failed for $sem/$course_name"
                FAILED_BOOKS+=("$sem/$course_name")
                (( FAIL_COUNT++ )) || true
            fi
            popd > /dev/null
            echo ""
        done
    done
fi

# ── Step 3: Projects — INTENTIONALLY SKIPPED ─────────────────────────────────
# GitHub-only mode: projects are *not* rendered into the website. Each
# course's projects.html is a thin landing page generated by
# generate_listing.py that just points at the external GitHub repo
# (URLs maintained in Notes/_projects_github.yml). The manifest exists
# only as a placeholder and is expected to be empty.
if (( DO_PROJECTS )); then
    echo "──────────────────────────────────────────────────"
    echo "  🧪  Projects: skipped (GitHub-only mode)"
    echo "──────────────────────────────────────────────────"
    echo "  Per-course projects.html landing pages were generated by"
    echo "  generate_listing.py and link to GitHub. No project sub-books,"
    echo "  notebooks, or PDFs are rendered or mirrored into docs/."
    echo ""
fi

# ── Step 4: Render the main website ──────────────────────────────────────────
if (( DO_SITE )); then
    if [[ -f "$SITE_DIR/_quarto.yml" ]]; then
        echo "──────────────────────────────────────────────────"
        echo "  🌐  Main site (Notes/site/)"
        echo "──────────────────────────────────────────────────"
        pushd "$SITE_DIR" > /dev/null
        if quarto_cmd render; then
            echo "  ✓  site rendered → $DOCS_DIR"
        else
            echo "  ✗  site render failed"
            (( FAIL_COUNT++ )) || true
        fi
        popd > /dev/null
    else
        echo "  ✗  Notes/site/_quarto.yml not found — did generate_listing.py run?"
        (( FAIL_COUNT++ )) || true
    fi
fi

# ── Step 5: Sweep any stale projects-files/ left from previous runs ──────────
# Previous versions of this script mirrored project deliverables (PDFs,
# notebooks, HTML reports) into docs/<sem>/<course>/projects-files/. In
# GitHub-only mode none of those should ship with the site — they bloat
# the docs/ tree and the user wants project content to live exclusively
# in the external repo. Remove any leftover directories.
echo ""
echo "──────────────────────────────────────────────────"
echo "  🧹  Removing any stale projects-files/ directories"
echo "──────────────────────────────────────────────────"
removed=0
while IFS= read -r -d '' dir; do
    rm -rf "$dir"
    echo "  ✗  $dir"
    (( removed++ )) || true
done < <(find "$DOCS_DIR" -type d -name "projects-files" -print0 2>/dev/null)
if (( removed == 0 )); then
    echo "  (none found — clean)"
fi

# ── Summary ──────────────────────────────────────────────────────────────────
echo ""
echo "╔══════════════════════════════════════════════════╗"
echo "║                     Summary                      ║"
echo "╠══════════════════════════════════════════════════╣"
printf "  Books rendered    : %d\n" "$BOOK_COUNT"
printf "  Projects rendered : %d\n" "$PROJECT_COUNT"
printf "  Failures          : %d\n" "$FAIL_COUNT"
if (( ${#FAILED_BOOKS[@]} > 0 )); then
    echo "  Failed books:"
    for b in "${FAILED_BOOKS[@]}"; do
        echo "    • $b"
    done
fi
if (( ${#FAILED_PROJECTS[@]} > 0 )); then
    echo "  Failed projects:"
    for p in "${FAILED_PROJECTS[@]}"; do
        echo "    • $p"
    done
fi
echo "╚══════════════════════════════════════════════════╝"

(( FAIL_COUNT == 0 ))   # exits 0 on success, 1 on any failure
