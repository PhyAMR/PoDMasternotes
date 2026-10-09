--[[
  phu-look.lua: the notes look for code and callouts (HTML and PDF).

  - Code output: ordinary print()/cat()/display output that looks like an
    array, a data frame or a loop's table is typeset; the rest stays
    console text tagged "out" (phu-output.lua, vendored from doc-kit).
  - PDF: code cells get their language tag; callouts become phucallout
    (label in the margin), both defined in preamble.tex.
  Code itself is never changed.
--]]
local output = dofile(quarto.utils.resolve_path("phu-output.lua"))

local function is_latex() return quarto.doc.is_format("latex") end

local function latex_inlines(inlines)
  return (pandoc.write(pandoc.Pandoc({ pandoc.Plain(inlines) }), "latex"):gsub("%s+$", ""))
end

local function as_blocks(x)
  local kind = pandoc.utils.type(x)
  if kind == "Block" then return pandoc.Blocks({ x }) end
  if kind == "Inlines" or kind == "Inline" then return pandoc.Blocks({ pandoc.Plain(x) }) end
  return pandoc.Blocks(x or {})
end

return {
  {
    Div = function(el)
      local latex = is_latex()
      if el.classes:includes("cell") then
        if not latex then return nil end
        local out = {}
        for _, b in ipairs(el.content) do
          if b.t == "CodeBlock" and b.classes:includes("cell-code") and b.classes[1] ~= "cell-code" then
            out[#out + 1] = pandoc.RawBlock("latex", "\\phucodelang{" .. b.classes[1] .. "}")
          end
          out[#out + 1] = b
        end
        el.content = out
        return el
      end
      return output.transform(el, latex)
    end,
    Callout = function(el)
      if not is_latex() then return nil end
      local title = el.title and latex_inlines(pandoc.utils.blocks_to_inlines(as_blocks(el.title))) or ""
      local blocks = pandoc.Blocks({ pandoc.RawBlock("latex",
        "\\begin{phucallout}{" .. (el.type or "note") .. "}{" .. title .. "}") })
      blocks:extend(as_blocks(el.content))
      blocks:insert(pandoc.RawBlock("latex", "\\end{phucallout}"))
      return blocks
    end,
  },
}
