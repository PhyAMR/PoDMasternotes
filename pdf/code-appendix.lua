--[[
  code-appendix.lua: in the PDF, move the code of every executed cell to a
  final "Code" appendix and leave a numbered, linked reference in the text.

  On only when the book's metadata says so (in its _quarto.yml):
      code-appendix: true
  HTML and every other format are left alone (there the code stays folded
  in place).

  - What moves: the code of Quarto cells (```{python}, ```{r}, ...). Their
    outputs (figures, printed text) stay where they are. Plain fenced code
    (```python, not executed) is part of the prose and stays too.
  - In the text, where the code was:  CODE 5.1 · p. 141  (a link)
  - In the appendix: the code grouped by chapter, each block with its
    number, the figure it draws (if any) and a link back to its page.
    ("Code 5.1" rather than "Listing 5.1", which Quarto uses for
    captioned `lst-` listings; those stay in the text.)
  - Keep one cell's code inline with `#| classes: keep-code`.
  - The appendix goes before a final References chapter (the one holding
    the `#refs` div); otherwise it is the last thing in the book.
  Must run before phu-look.lua, which tags the code blocks left in cells.
--]]

local HEADER = [[
\makeatletter
\providecommand*\phulabel[1]{\textsc{#1}}
\providecommand*\phucodelang[1]{}
\@ifundefined{c@chapter}
  {\newcounter{phucode}\renewcommand*\thephucode{\arabic{phucode}}}
  {\newcounter{phucode}[chapter]\renewcommand*\thephucode{\thechapter.\arabic{phucode}}}
\newif\ifphu@inappendix
\AtBeginDocument{%
  \ifcsname\string\color@inkFaint\endcsname\else\colorlet{inkFaint}{black!55}\fi
  \let\phu@origappendix\appendix
  \def\appendix{\global\phu@inappendixtrue\phu@origappendix}}
% switch to appendix numbering unless the book already did
\newcommand*\phucodeappendix{\ifphu@inappendix\else\appendix\fi}
% in the text, where the code was
\newcommand*\phucoderef[1]{%
  \par\addvspace{2pt}\noindent\refstepcounter{phucode}\label{phucode:src:#1}%
  {\footnotesize\color{inkFaint}\phulabel{code}\enspace
   \hyperref[phucode:lst:#1]{\thephucode\enspace\textperiodcentered\enspace p.~\pageref*{phucode:lst:#1}}}\par}
% in the appendix, above a code block: #1 id, #2 what it draws (or empty)
\newcommand*\phucodelisting[2]{%
  \par\addvspace{\medskipamount}\noindent\phantomsection\label{phucode:lst:#1}%
  \phulabel{Code}~\ref*{phucode:src:#1}\hfill
  {\footnotesize\color{inkFaint}#2\hyperref[phucode:src:#1]{from p.~\pageref*{phucode:src:#1}}}%
  \par\nopagebreak}
\makeatother
]]

local INTRO = "The code of every computational cell in these notes, in the order it "
  .. "appears. Each block carries the number shown in the text where its output is, "
  .. "and links back to that page."

local function enabled(meta)
  local v = meta["code-appendix"]
  if v == nil then return false end
  if type(v) == "boolean" then return v end
  return pandoc.utils.stringify(v) == "true"
end

local function latex(inlines)
  return (pandoc.write(pandoc.Pandoc({ pandoc.Plain(inlines) }), "latex"):gsub("%s+$", ""))
end

-- A cell with `#| label: fig-x` writes its plot to .../fig-x-output-1.pdf;
-- the label is not on the cell itself at this stage, so read it from there.
local function figure_label(cell)
  local label
  cell:walk({
    Image = function(img)
      label = label or img.src:match("(fig%-[%w_%-]-)%-output%-%d+%.%w+$")
    end,
  })
  return label
end

return {
  {
    Pandoc = function(doc)
      if not quarto.doc.is_format("latex") or not enabled(doc.meta) then return nil end

      local listings, chapter, n = {}, nil, 0

      local function take_code(cell)
        local code, rest = {}, pandoc.Blocks({})
        for _, b in ipairs(cell.content) do
          if b.t == "CodeBlock" and b.classes:includes("cell-code") then
            code[#code + 1] = b
          else
            rest:insert(b)
          end
        end
        if #code == 0 then return cell end
        n = n + 1
        listings[#listings + 1] = { id = tostring(n), code = code,
                                    figure = figure_label(cell), chapter = chapter }
        rest:insert(1, pandoc.RawBlock("latex", "\\phucoderef{" .. n .. "}"))
        cell.content = rest
        return cell
      end

      local function walk(blocks)
        local out = pandoc.Blocks({})
        for _, b in ipairs(blocks) do
          if b.t == "Header" and b.level == 1 then
            chapter = b
          elseif b.t == "Div" then
            if b.classes:includes("cell") and not b.classes:includes("keep-code") then
              b = take_code(b)
            else
              b.content = walk(b.content)
            end
          end
          out:insert(b)
        end
        return out
      end

      doc.blocks = walk(doc.blocks)
      if #listings == 0 then return doc end
      quarto.doc.include_text("in-header", HEADER)

      local app = pandoc.Blocks({
        pandoc.RawBlock("latex", "\\phucodeappendix"),
        pandoc.Header(1, "Code", pandoc.Attr("code-appendix")),
      })
      app:extend(pandoc.read(INTRO, "markdown").blocks)
      local shown
      for _, l in ipairs(listings) do
        if l.chapter and l.chapter ~= shown then
          shown = l.chapter
          local h = l.chapter
          local num = (h.identifier ~= "" and not h.classes:includes("unnumbered"))
            and ("Chapter~\\ref{" .. h.identifier .. "}\\quad ") or ""
          app:insert(pandoc.RawBlock("latex", "\\section*{" .. num .. latex(h.content) .. "}"))
        end
        local what = l.figure
          and ("Figure~\\ref{" .. l.figure .. "}\\enspace\\textperiodcentered\\enspace ") or ""
        app:insert(pandoc.RawBlock("latex", "\\phucodelisting{" .. l.id .. "}{" .. what .. "}"))
        for _, c in ipairs(l.code) do
          if c.classes[1] ~= "cell-code" then
            app:insert(pandoc.RawBlock("latex", "\\phucodelang{" .. c.classes[1] .. "}"))
          end
          app:insert(c)
        end
      end

      -- Before a final References chapter, else at the end.
      local at = #doc.blocks + 1
      for i = #doc.blocks, 1, -1 do
        local b = doc.blocks[i]
        if b.t == "Header" and b.level == 1 then
          for j = i, #doc.blocks do
            local d = doc.blocks[j]
            if d.t == "Div" and d.identifier == "refs" then
              at = i
              local prev = doc.blocks[i - 1]
              if prev and prev.t == "RawBlock" and prev.text:match("^<!%-%- quarto%-file%-metadata") then
                at = i - 1
              end
              break
            end
          end
          break
        end
      end
      for k = #app, 1, -1 do doc.blocks:insert(at, app[k]) end
      return doc
    end,
  },
}
