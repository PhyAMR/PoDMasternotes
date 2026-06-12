--[[
  tex-to-svg.lua — HTML-only Pandoc filter.

  Replaces two kinds of raw LaTeX blocks with <img src="…svg"> so the
  HTML build can show TikZ / circuitikz figures that MathJax can't draw.
  PDF output is untouched.

  Pre-rendered SVGs come from Notes/pdf/build-tex-svg.py:

    1. \input{Grafiche/Figure/foo.tex}  →  Grafiche/Figure/foo.svg
       (sibling to the .tex, same basename)

    2. Inline raw blocks containing a tikzpicture / circuitikz / figure
       environment → cached by SHA-1 of the block body under
       Grafiche/_inline_cache/<sha>.svg

  Behaviour for a missing SVG: leave the original raw block in place and
  emit a Pandoc warning so the gap is visible in build logs.
--]]

local function is_html()
  return FORMAT:match("html") or FORMAT:match("epub") or FORMAT:match("revealjs")
end

local function sha1_hex(s)
  -- pandoc.utils.sha1 returns hex.
  return pandoc.utils.sha1(s):sub(1, 16)
end

local function file_exists(path)
  local f = io.open(path, "rb")
  if f then f:close(); return true end
  return false
end

local function img_for(src, attr)
  attr = attr or pandoc.Attr("", {"tikz-figure"}, {})
  return pandoc.Para({
    pandoc.Image({pandoc.Str("")}, src, "", attr)
  })
end

-- The raw \input{X} path is relative to the project root (where the
-- main book .tex file lives). The HTML chapter, however, lives one or
-- more directories deep, so the <img src> needs the matching "../"
-- prefix to step out of those subdirectories first.
local function input_depth_below_root()
  -- PANDOC_STATE.input_files holds the source paths being rendered.
  local inputs = PANDOC_STATE and PANDOC_STATE.input_files or {}
  for _, p in ipairs(inputs) do
    -- Strip a leading "./" then count remaining "/" separators —
    -- that's the depth below project root (e.g. "chapters/foo.qmd" → 1).
    local norm = p:gsub("^%./", "")
    local _, count = norm:gsub("/", "/")
    if count > 0 then return count end
  end
  return 0
end

-- Try the path as given, with progressively more "../" prefixes added,
-- so we hit the right one regardless of where the filter was invoked.
local function resolve_svg(rel)
  local depth = input_depth_below_root()
  local prefix = ""
  for _ = 1, depth do prefix = "../" .. prefix end
  local tried = {prefix .. rel, rel, "../" .. rel, "../../" .. rel}
  for _, p in ipairs(tried) do
    if file_exists(p) then return p end
  end
  -- Even if none of the candidates exists at filter time (cwd is the
  -- intermediate Quarto build dir, not the project), still return the
  -- depth-adjusted relative path so the browser can find the asset
  -- once the site is rendered to docs/.
  return prefix .. rel
end

function RawBlock(el)
  if not is_html() then return nil end
  if el.format ~= "latex" and el.format ~= "tex" then return nil end

  local body = el.text or ""

  -- ── Case 1: pure \input{path.tex} ────────────────────────────────
  local inc = body:match("^%s*\\input%s*{([^}]+)}%s*$")
  if inc then
    local svg = inc:gsub("%.tex$", ".svg")
    local resolved = resolve_svg(svg)
    if resolved then
      return img_for(resolved)
    else
      io.stderr:write(("tex-to-svg: missing %s (referenced by \\input)\n"):format(svg))
      return nil
    end
  end

  -- ── Case 2: inline TikZ / circuitikz / figure environment ────────
  if body:find("\\begin{tikzpicture}", 1, true)
     or body:find("\\begin{circuitikz}", 1, true)
     or body:find("\\begin{figure}", 1, true) then
    local hash = sha1_hex(body)
    local svg  = "Grafiche/_inline_cache/" .. hash .. ".svg"
    local resolved = resolve_svg(svg)
    if resolved then
      return img_for(resolved)
    else
      io.stderr:write(("tex-to-svg: no SVG for inline block %s — run Notes/pdf/build-tex-svg.py\n"):format(hash))
      return nil
    end
  end

  return nil
end
