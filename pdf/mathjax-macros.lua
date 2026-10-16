--[[
  mathjax-macros.lua — HTML-only Pandoc filter.

  Gives MathJax the math macros the PDF build has, so \abs{x}, \sprod{w}{x}
  or \argmin don't show up as red raw commands in the HTML notes.

    1. The one-line \providecommand / \newcommand / \DeclareMathOperator
       definitions at the top level of preamble.tex are read and handed to
       MathJax's configuration. preamble.tex stays the single list: a macro
       added there reaches the HTML on the next render.
    2. MathJax's own mathtools and dsfont extensions are loaded, as the
       preamble loads those packages (\xrightleftharpoons, \mathds{1}).
    3. EXTRA holds stand-ins for the few commands the PDF takes from
       packages MathJax doesn't have, or from one course's own header.
    4. xcolor names and mixes such as green!60!black are not CSS colours,
       and MathJax would draw them black: colour arguments in the macros
       and in the formulas are rewritten as [RGB]{r,g,b}. (Not as #hex: a
       # inside a macro body reads as a parameter.)

  PDF output is untouched.
--]]

local function is_html()
  return FORMAT:match("html") ~= nil
end

-- \providecommand leaves LaTeX's own \vec alone, so keep MathJax's too.
-- The others are text or table helpers that never appear in formulas.
local SKIP = { vec = true, q = true, STAB = true, thickhline = true, exrule = true }

local EXTRA = {
  num = { "#1", 1 },                                -- siunitx \num{…} (MAPDA)
  Tr = "\\operatorname{Tr}",                       -- MTP's PDF header
  raisebox = { "\\raise{#1}{#2}", 2 },              -- text-mode LaTeX (MTP)
  textcircled = { "\\enclose{circle}{#1}", 1 },     -- text-mode LaTeX (MTP)
}

-- xcolor's base colours and the dvipsnames the notes use, as RGB in [0, 1].
local RGB = {
  red = { 1, 0, 0 }, green = { 0, 1, 0 }, blue = { 0, 0, 1 },
  black = { 0, 0, 0 }, white = { 1, 1, 1 }, gray = { .5, .5, .5 },
  orange = { 1, .5, 0 }, purple = { .75, 0, .25 }, brown = { .75, .5, .25 },
  cyan = { 0, 1, 1 }, magenta = { 1, 0, 1 }, yellow = { 1, 1, 0 },
  ForestGreen = { .0792, .88, .1056 }, BurntOrange = { 1, .49, 0 },
  BrickRed = { .72, .0792, .0432 },
}

-- "c1!p!c2!q!c3" mixes left to right; a trailing "!p" mixes with white.
local function xcolor_rgb(spec)
  local parts = {}
  for p in (spec .. "!"):gmatch("([^!]*)!") do table.insert(parts, p) end
  local c = RGB[parts[1]]
  if not c then return nil end
  local i = 2
  while i <= #parts do
    local pct = tonumber(parts[i])
    local other = RGB[parts[i + 1] or "white"]
    if not pct or not other then return nil end
    local t = pct / 100
    c = { t * c[1] + (1 - t) * other[1], t * c[2] + (1 - t) * other[2], t * c[3] + (1 - t) * other[3] }
    i = i + 2
  end
  return string.format("[RGB]{%d,%d,%d}", math.floor(c[1] * 255 + .5),
    math.floor(c[2] * 255 + .5), math.floor(c[3] * 255 + .5))
end

local function css_colours(tex)
  local function fix(cmd)
    return function(spec)
      return cmd .. (xcolor_rgb(spec) or "{" .. spec .. "}")
    end
  end
  tex = tex:gsub("\\textcolor%s*{([^{}]*)}", fix("\\textcolor"))
  return (tex:gsub("\\color%s*{([^{}]*)}", fix("\\color")))
end

local function preamble_macros()
  local macros = {}
  local f = io.open(quarto.utils.resolve_path("preamble.tex"), "r")
  if not f then
    quarto.log.warning("mathjax-macros.lua: preamble.tex not found")
    return macros
  end
  for line in f:lines() do
    local star, name, body = line:match("^\\DeclareMathOperator(%*?)%s*{\\(%a+)}%s*(%b{})")
    if name then
      macros[name] = "\\operatorname" .. star .. body
    else
      local rest
      name, rest = line:match("^\\providecommand%s*{\\(%a+)}%s*(.*)$")
      if not name then name, rest = line:match("^\\newcommand%s*{\\(%a+)}%s*(.*)$") end
      if name and not SKIP[name] then
        local n, after = rest:match("^%[(%d)%]%s*(.*)$")
        body = (after or rest):match("^%b{}")          -- nil for multi-line definitions
        if body then
          body = css_colours(body:sub(2, -2))
          macros[name] = n and { body, tonumber(n) } or body
        end
      end
    end
  end
  f:close()
  return macros
end

function Pandoc(doc)
  if not is_html() then return nil end
  local macros = preamble_macros()
  for k, v in pairs(EXTRA) do macros[k] = v end
  local config = {
    loader = { load = { "[tex]/mathtools", "[tex]/dsfont" } },
    tex = { packages = { ["[+]"] = { "mathtools", "dsfont" } }, macros = macros },
  }
  quarto.doc.include_text("in-header",
    "<script>\nwindow.MathJax = " .. pandoc.json.encode(config) .. ";\n</script>")
  return doc:walk({
    Math = function(m)
      m.text = css_colours(m.text)
      return m
    end,
  })
end
