-- =====================================================================
-- Notes filter — three jobs:
--
--  1. (PDF only) Wrap Quarto code-output cells (cell-output*) in the
--     LaTeX env `codeoutput` (defined in preamble.tex). Visual: thin
--     grey rule on the left, mono, small.
--
--  2. (PDF only) Convert theorem-like Divs (.theorem, .proposition,
--     .lemma, .corollary, .definition, .example, .exercise, .solution,
--     .remark, .note) into raw `\begin{<env>}[optional name]…\end{<env>}`
--     so the LaTeX preamble can style them. The class is stripped from
--     the AST so Pandoc's template does NOT auto-emit `\newtheorem*{…}`
--     for them.
--
--  3. (Both HTML and PDF) Move standalone-image figures into the right
--     margin by default. Figures inside an exercise / example / theorem
--     / definition / solution / etc. div are LEFT in the body column.
--     Implementation: walk the document, track box-depth, and wrap any
--     image-only Para outside a box in a `.column-margin` Div. This
--     pass runs FIRST so the Div transforms in pass 2 still see the
--     original .exercise / .example classes.
--
-- HTML / docx pass through pass 1 and pass 2's logic. Pass 3 runs in
-- both formats.
-- =====================================================================

local OUTPUT_CLASSES = {
  ["cell-output"]         = true,
  ["cell-output-stdout"]  = true,
  ["cell-output-stderr"]  = true,
  ["cell-output-display"] = true,
}

local THEOREM_ENVS = {
  theorem     = true,
  proposition = true,
  lemma       = true,
  corollary   = true,
  definition  = true,
  example     = true,
  exercise    = true,
  solution    = true,
  remark      = true,
  note        = true,
}

local function is_pdf()
  return FORMAT:match("latex") or FORMAT:match("pdf") or FORMAT:match("beamer")
end

local function which_theorem(classes)
  for _, c in ipairs(classes) do
    if THEOREM_ENVS[c] then return c end
  end
  return nil
end

local function is_output(div)
  for _, c in ipairs(div.classes) do
    if OUTPUT_CLASSES[c] then return true end
  end
  return false
end

-- ── PASS 1 ───────────────────────────────────────────────────────────
-- Walk the document tree, track whether we're inside a "box" (any
-- theorem-like env), and wrap every image-only Para outside a box in a
-- `.column-margin` Div. Runs for HTML + PDF.

local function is_box_div(el)
  if el.t ~= "Div" then return false end
  for _, c in ipairs(el.classes) do
    if THEOREM_ENVS[c] then return true end
  end
  return false
end

local function is_image_only(para)
  local has_image = false
  for _, inl in ipairs(para.content) do
    local t = inl.t
    if t == "Image" then
      has_image = true
    elseif t == "Space" or t == "SoftBreak" or t == "LineBreak" then
      -- ignore whitespace
    else
      return false
    end
  end
  return has_image
end

local function already_columned(div)
  if div.t ~= "Div" then return false end
  for _, c in ipairs(div.classes) do
    if c:match("^column%-") then return true end
  end
  return false
end

local function walk_blocks(blocks, inside_box)
  local out = {}
  for _, blk in ipairs(blocks) do
    if blk.t == "Div" then
      -- Don't move into the margin anything already explicitly placed.
      if already_columned(blk) then
        table.insert(out, blk)
      else
        local now_inside = inside_box or is_box_div(blk)
        blk.content = walk_blocks(blk.content, now_inside)
        table.insert(out, blk)
      end
    elseif blk.t == "Para" and not inside_box and is_image_only(blk) then
      table.insert(out, pandoc.Div(
        {blk},
        pandoc.Attr("", {"column-margin"}, {})))
    elseif blk.t == "Figure" and not inside_box then
      -- Pandoc 3.x Figure node — wrap likewise.
      table.insert(out, pandoc.Div(
        {blk},
        pandoc.Attr("", {"column-margin"}, {})))
    else
      table.insert(out, blk)
    end
  end
  return out
end

local pass_margins = {
  Pandoc = function(doc)
    -- LaTeX `\marginnote{…}` cannot contain a `\begin{figure}` float,
    -- so margin-wrapping figures in PDF triggers
    --   "LaTeX Error: Not in outer par mode."
    -- Restrict the margin pass to HTML where it shines; in PDF figures
    -- stay in the body column. Users can still opt-in per-figure by
    -- wrapping explicitly in `:::{.column-margin}`.
    if FORMAT:match("latex") or FORMAT:match("pdf") or FORMAT:match("beamer") then
      return doc
    end
    doc.blocks = walk_blocks(doc.blocks, false)
    return doc
  end,
}

-- ── PASS 2 ───────────────────────────────────────────────────────────
-- LaTeX-only div-to-env conversions (theorem-style envs + code output).

local pass_pdf = {
  Div = function(el)
    if not is_pdf() then return nil end

    -- Theorem-like envs.
    local env = which_theorem(el.classes)
    if env then
      local name = el.attributes["name"]
      local opt  = name and ("[" .. name .. "]") or ""
      local out  = { pandoc.RawBlock("latex", "\\begin{" .. env .. "}" .. opt) }
      for _, blk in ipairs(el.content) do
        table.insert(out, blk)
      end
      table.insert(out, pandoc.RawBlock("latex", "\\end{" .. env .. "}"))
      return out
    end

    -- Code output cells.
    if is_output(el) then
      return {
        pandoc.RawBlock("latex", "\\begin{codeoutput}"),
        el,
        pandoc.RawBlock("latex", "\\end{codeoutput}"),
      }
    end
  end,
}

return { pass_margins, pass_pdf }
