--[[
  phu-output.lua: standard code output, rendered in the phunotes look.

  Code stays ordinary: print(), cat(), a bare `df` or `A`, a loop that
  prints a line per step. This module reads the text that Python, numpy,
  pandas and R print and turns what it recognises into typeset objects:

    numpy arrays (repr or print)     -> bracketed grid, faint indices,
    R vectors and [,1] matrices         negatives in the accent
    pandas DataFrame / Series, R data.frame, tibble, named matrices
                                     -> booktabs table, faint index
    loops printing the same shape of line ("epoch 3  loss=0.21")
                                     -> table, constant words as headers
    R scalars ([1] 5)                -> just the value
    anything else                    -> console text, tagged "out"

  Big objects keep their head and tail (⋮ ⋯ ⋱) and say their size.
  A pandas table that Quarto already parsed (display output) gets the
  same treatment. Nothing here runs code or changes it.

  Used by phu.lua (doc-kit) and vendored by projects that cannot depend
  on the kit; keep it self-contained.
--]]

local M = {}

M.limits = {
  vector = 12, rows = 10, cols = 8, head = 5, tail = 3,
  frame_rows = 14, frame_head = 6, frame_tail = 4, frame_cols = 8,
}

local VDOTS, CDOTS, DDOTS = "\u{22EE}", "\u{22EF}", "\u{22F1}"
local TIMES, DOT = "\u{00D7}", "\u{00B7}"

-- helpers ------------------------------------------------------------
local function trim(s)
  return (s:gsub("^%s+", ""):gsub("%s+$", ""))
end

local function split_lines(text)
  local out = {}
  for line in (text .. "\n"):gmatch("([^\n]*)\n") do
    out[#out + 1] = (line:gsub("%s+$", ""))
  end
  while #out > 0 and out[#out] == "" do out[#out] = nil end
  return out
end

local function words(s)
  local out = {}
  for w in s:gmatch("%S+") do out[#out + 1] = w end
  return out
end

local MISSING = { nan = true, NaN = true, inf = true, ["-inf"] = true, Inf = true,
  ["-Inf"] = true, NA = true, ["<NA>"] = true, None = true, NaT = true }
local ELLIPSIS = { ["..."] = true, [".."] = true, ["\u{2026}"] = true,
  [VDOTS] = true, [CDOTS] = true, [DDOTS] = true }

local function is_ellipsis(s) return ELLIPSIS[s] == true end

local function is_number(s)
  s = s:gsub("^\u{2212}", "-")
  if MISSING[s] then return true end
  return tonumber(s) ~= nil and not s:match("^0[xX]")
end

local function is_numberish(s) return is_number(s) or is_ellipsis(s) end

local function is_negative(s)
  return s:match("^%-%d") ~= nil or s:match("^%-%.%d") ~= nil or s:match("^\u{2212}") ~= nil
end

-- truncation: indices to keep, false where the gap goes
local function pick(n, limit, head, tail)
  local out = {}
  if n <= limit then
    for k = 1, n do out[#out + 1] = k end
  else
    for k = 1, head do out[#out + 1] = k end
    out[#out + 1] = false
    for k = n - tail + 1, n do out[#out + 1] = k end
  end
  return out
end

--[[ A grid: { kind = "array" | "frame", header = {..} | nil,
               rows = { {..}, .. } (first cell = row label), footer } ]]
local function truncate(grid)
  local L = M.limits
  local array = grid.kind == "array"
  local nrow, ncol = #grid.rows, #(grid.header or grid.rows[1] or {}) - 1
  local rows = grid.vector and { 1 } or pick(nrow, array and L.rows or L.frame_rows,
    array and L.head or L.frame_head, array and L.tail or L.frame_tail)
  local cols = pick(ncol, grid.vector and L.vector or (array and L.cols or L.frame_cols), L.head, L.tail)
  if (#rows < nrow or #cols < ncol) and not grid.footer and not array then
    grid.footer = nrow .. " rows " .. TIMES .. " " .. (ncol + (grid.index and 0 or 1)) .. " columns"
  end
  local function cut(row, filler)
    local out = { row[1] }
    for _, c in ipairs(cols) do out[#out + 1] = c and (row[c + 1] or "") or filler end
    return out
  end
  local new = {}
  for _, r in ipairs(rows) do
    if r then
      new[#new + 1] = cut(grid.rows[r], CDOTS)
    else
      local filler = cut(grid.rows[1], DDOTS)
      for k = 1, #filler do filler[k] = (k > 1 and filler[k] == DDOTS) and DDOTS or VDOTS end
      new[#new + 1] = filler
    end
  end
  grid.rows = new
  if grid.header then grid.header = cut(grid.header, CDOTS) end
  return grid
end

-- parsers ------------------------------------------------------------
-- Each takes (lines, i) and returns grid-or-text, last line used.

-- numpy: array([...]) or a printed [[..] [..]]
local function parse_numpy(lines, i)
  local first = lines[i]
  local repr = first:match("^%s*array%(") ~= nil
  if not (repr or first:match("^%s*%[")) then return nil end
  if first:match("^%s*%[%d+%]") or first:match("^%s*%[%d*,%d*%]") then return nil end -- R
  local depth, j, parts = 0, i, {}
  while j <= #lines and j - i < 400 do
    local l = lines[j]
    parts[#parts + 1] = l
    for ch in l:gmatch("[%[%]]") do depth = depth + (ch == "[" and 1 or -1) end
    if depth <= 0 then break end
    j = j + 1
  end
  if depth ~= 0 then return nil end
  local text = table.concat(parts, " ")
  local dtype = text:match("dtype=([%w_]+)")
  text = text:gsub("^%s*array%(", ""):gsub(",%s*dtype=[%w_]+", ""):gsub("%)%s*$", "")
  text = trim(text)
  if not repr and text:find(",") then return nil end -- a Python list, not numpy
  local open = #(text:match("^%[+") or "")
  if not text:match("%]$") or open < 1 or open > 2 then return nil end

  local function tokens(s)
    local out = {}
    for t in s:gmatch("[^%s,]+") do
      if not (is_numberish(t) or t == "True" or t == "False") then return nil end
      out[#out + 1] = t
    end
    return out
  end

  local grid = { kind = "array", rows = {} }
  if open == 1 then
    local vals = tokens(text:sub(2, -2))
    if not vals or #vals == 0 then return nil end
    local row, header, n, gap = { "" }, { "" }, 0, false
    for _, v in ipairs(vals) do
      if is_ellipsis(v) then
        gap = true; row[#row + 1] = CDOTS; header[#header + 1] = CDOTS
      else
        n = n + 1; row[#row + 1] = v; header[#header + 1] = gap and "" or tostring(n - 1)
      end
    end
    grid.header, grid.rows, grid.vector = header, { row }, true
    if gap then grid.footer = dtype
    else grid.footer = (dtype and dtype .. " " .. DOT .. " " or "") .. n end
  else
    local inner, pos, gap = text:sub(2, -2), 1, false
    while true do
      local s, e = inner:find("%b[]", pos)
      local dots = inner:find("%.%.%.", pos, false)
      if dots and (not s or dots < s) then
        grid.rows[#grid.rows + 1] = "gap"; gap = true; pos = dots + 3
      elseif s then
        local vals = tokens(inner:sub(s + 1, e - 1))
        if not vals then return nil end
        grid.rows[#grid.rows + 1] = vals; pos = e + 1
      else
        break
      end
    end
    local width
    for _, r in ipairs(grid.rows) do
      if r ~= "gap" then
        if width and #r ~= width then return nil end
        width = #r
      end
    end
    if not width then return nil end
    local header, colgap = { "" }, false
    local sample
    for _, r in ipairs(grid.rows) do if r ~= "gap" then sample = r; break end end
    local n = 0
    for _, v in ipairs(sample) do
      if is_ellipsis(v) then colgap = true; header[#header + 1] = CDOTS
      else n = n + 1; header[#header + 1] = colgap and "" or tostring(n - 1) end
    end
    local rows, k = {}, 0
    for _, r in ipairs(grid.rows) do
      if r == "gap" then
        local filler = { VDOTS }
        for c = 1, width do filler[#filler + 1] = is_ellipsis(sample[c]) and DDOTS or VDOTS end
        rows[#rows + 1] = filler
      else
        k = k + 1
        local row = { gap and "" or tostring(k - 1) }
        for _, v in ipairs(r) do row[#row + 1] = is_ellipsis(v) and CDOTS or v end
        rows[#rows + 1] = row
      end
    end
    grid.header, grid.rows = header, rows
    if not gap and not colgap then
      grid.footer = (dtype and dtype .. " " .. DOT .. " " or "") .. k .. " " .. TIMES .. " " .. width
    else
      grid.footer = dtype
    end
  end
  return grid, j
end

-- R: [1] 1 2 3 / [13] ... (one vector over several lines)
local function parse_rvector(lines, i)
  local idx, rest = lines[i]:match("^%s*%[(%d+)%]%s+(.*)$")
  if idx ~= "1" then return nil end
  local vals, j, expect = {}, i, 1
  while j <= #lines do
    local k, r = lines[j]:match("^%s*%[(%d+)%]%s+(.*)$")
    if not k or tonumber(k) ~= expect then break end
    local w = words(r)
    for _, v in ipairs(w) do vals[#vals + 1] = v end
    expect = expect + #w
    j = j + 1
  end
  j = j - 1
  local numeric = true
  for _, v in ipairs(vals) do numeric = numeric and is_number(v) end
  if #vals == 1 then -- a scalar: just the value
    local v = vals[1]:gsub('^"(.*)"$', "%1")
    return { text = rest:match('^"(.*)"%s*$') or v }, j
  end
  if not numeric then return nil end
  local header, row = { "" }, { "" }
  for k, v in ipairs(vals) do header[#header + 1] = tostring(k); row[#row + 1] = v end
  return { kind = "array", vector = true, header = header, rows = { row },
           footer = tostring(#vals) }, j
end

-- fixed-width tables (pandas, R data.frame and matrices, tibble body)
local function chars(line)
  local out = {}
  for _, c in utf8.codes(line) do out[#out + 1] = utf8.char(c) end
  return out
end

local function regions_of(block)
  local width = 0
  for _, l in ipairs(block) do width = math.max(width, #l) end
  local gutter = {}
  for k = 1, width do
    local blank = true
    for _, l in ipairs(block) do
      local ch = l[k]
      if ch and ch ~= " " then blank = false; break end
    end
    gutter[k] = blank
  end
  local regions, start = {}, nil
  for k = 1, width + 1 do
    if k <= width and not gutter[k] then
      start = start or k
    elseif start then
      regions[#regions + 1] = { start, k - 1 }; start = nil
    end
  end
  return regions
end

local function cells(line, regions)
  local out = {}
  for _, r in ipairs(regions) do
    out[#out + 1] = trim(table.concat(line, "", r[1], math.min(r[2], #line)))
  end
  return out
end

local function table_grid(text_block, index_name)
  if not utf8.len(table.concat(text_block)) then return nil end
  local block = {}
  for k, l in ipairs(text_block) do block[k] = chars(l) end
  local regions = regions_of(block)
  if #regions < 2 or #regions > 40 then return nil end
  local header = cells(block[1], regions)
  local rows = {}
  for k = 2, #block do rows[#rows + 1] = cells(block[k], regions) end
  if #rows < 1 then return nil end
  -- regions empty in every data row belong to the next (split headers)
  local merged_h, merged_r, carry = {}, {}, nil
  for c = 1, #regions do
    local empty = true
    for _, r in ipairs(rows) do if r[c] ~= "" then empty = false; break end end
    if empty and c < #regions then
      carry = carry and (carry .. " " .. header[c]) or header[c]
    else
      merged_h[#merged_h + 1] = carry and trim(carry .. " " .. header[c]) or header[c]
      for ri, r in ipairs(rows) do merged_r[ri] = merged_r[ri] or {}; table.insert(merged_r[ri], r[c]) end
      carry = nil
    end
  end
  header = merged_h
  for ri = 1, #rows do rows[ri] = merged_r[ri] end
  -- leading regions with a blank header form the index (labels with spaces)
  while #header > 2 and header[1] == "" and header[2] == "" do
    table.remove(header, 1)
    for _, r in ipairs(rows) do
      r[1] = trim(r[1] .. " " .. r[2]); table.remove(r, 2)
    end
  end
  if #header < 2 then return nil end
  for c = 2, #header do if header[c] == "" then return nil end end
  if header[1] ~= "" then
    for _, h in ipairs(header) do if is_number(h) then return nil end end
  end
  -- every data row fills its cells (ellipsis rows aside); one column is numeric
  local numeric_col = false
  for c = 2, #header do
    local all = true
    for _, r in ipairs(rows) do if not is_numberish(r[c]) then all = false; break end end
    numeric_col = numeric_col or all
  end
  if not numeric_col then return nil end
  for _, r in ipairs(rows) do
    local filled, dots = 0, true
    for c = 2, #r do
      if r[c] ~= "" then filled = filled + 1 end
      if r[c] ~= "" and not is_ellipsis(r[c]) then dots = false end
    end
    if dots then
      for c = 1, #r do r[c] = VDOTS end
    elseif filled < #r - 1 then
      return nil
    end
  end
  -- R matrix headers: [,1] -> 1, [1,] -> 1; array when unnamed
  local rmatrix = header[2]:match("^%[,%d+%]$") ~= nil
  for c = 1, #header do header[c] = header[c]:gsub("^%[,(%d+)%]$", "%1") end
  for _, r in ipairs(rows) do r[1] = r[1]:gsub("^%[(%d+),%]$", "%1") end
  local index = header[1] == "" or index_name ~= nil
  if index_name and header[1] == "" then header[1] = index_name end
  return { kind = rmatrix and "array" or "frame", header = header, rows = rows, index = index,
           footer = rmatrix and (#rows .. " " .. TIMES .. " " .. (#header - 1)) or nil }
end

local function frame_footer(grid, line)
  local r, c = line:match("^%[(%d+) rows x (%d+) columns%]$")
  if r then grid.footer = r .. " rows " .. TIMES .. " " .. c .. " columns"; return true end
  local omitted = line:match("omitted (%d+) rows")
  if omitted then grid.footer = omitted .. " more rows"; return true end
  return false
end

local function parse_frame(lines, i)
  local last = i
  while last + 1 <= #lines and lines[last + 1] ~= "" and last - i < 300 do last = last + 1 end
  if last == i then return nil end
  -- pandas puts the index name on its own line under the header
  local index_name
  local second = lines[i + 1]
  if second and second:match("^%S+%s*$") and #words(second) == 1 and #words(lines[i]) > 1 then
    index_name = trim(second)
  end
  for j = last, i + 1, -1 do
    local block = { lines[i] }
    for k = i + (index_name and 2 or 1), j do
      if not lines[k]:match("^%s*%[ reached") then block[#block + 1] = lines[k] end
    end
    if #block >= 2 then
      local grid = table_grid(block, index_name)
      if grid then
        if lines[j + 1] and frame_footer(grid, lines[j + 1]) then j = j + 1
        elseif lines[j + 1] == "" and lines[j + 2] and frame_footer(grid, lines[j + 2]) then j = j + 2
        elseif lines[j]:match("^%s*%[ reached") then frame_footer(grid, lines[j]) end
        return grid, j
      end
    end
  end
  return nil
end

-- pandas Series: rows then "Name: x, dtype: float64"
local function parse_series(lines, i)
  for j = i + 1, math.min(#lines, i + 80) do
    if lines[j] == "" then return nil end
    local name, dtype = lines[j]:match("^Name: (.-), .*dtype: (%S+)$")
    if not dtype then dtype = lines[j]:match("^dtype: (%S+)$") end
    if dtype then
      local first, index_name = i, nil
      if #words(lines[i]) == 1 and j - i > 1 then index_name = trim(lines[i]); first = i + 1 end
      local rows = {}
      for k = first, j - 1 do
        local label, value = lines[k]:match("^(.-)%s+(%S+)$")
        if not label then return nil end
        if not is_numberish(value) then return nil end
        if is_ellipsis(value) then rows[#rows + 1] = { VDOTS, VDOTS }
        else rows[#rows + 1] = { trim(label), value } end
      end
      if #rows == 0 then return nil end
      local length = lines[j]:match("Length: (%d+)")
      return { kind = "frame", header = { index_name or "", name or "" }, rows = rows, index = true,
               footer = (length or #rows) .. " rows " .. DOT .. " " .. dtype }, j
    end
  end
  return nil
end

-- tibble: "# A tibble: 32 × 11", header, <dbl> row, numbered rows, "# ℹ ..."
local function parse_tibble(lines, i)
  local n, m = lines[i]:match("^# A tibble: (%d+) .- (%d+)")
  if not n then return nil end
  local block, j = {}, i + 1
  while j <= #lines and lines[j] ~= "" do
    local l = lines[j]
    if not l:match("^#") and not l:match("^%s*<[^>]+>[%s<>%w]*$") then
      block[#block + 1] = l:gsub("\u{2026}", "~")
    end
    j = j + 1
  end
  local grid = table_grid(block)
  if not grid then return nil end
  grid.kind, grid.index = "frame", true
  grid.footer = n .. " rows " .. TIMES .. " " .. m .. " columns"
  return grid, j - 1
end

-- loops: lines of the same shape with numbers in fixed places
local function loop_tokens(line)
  local out = {}
  for _, w in ipairs(words(line)) do
    w = w:gsub("[,;]$", "")
    local k, v = w:match("^([%a_][%w_%.]*)[=:](.+)$")
    if k and is_number(v) then
      out[#out + 1] = k; out[#out + 1] = "="; out[#out + 1] = v
    elseif w ~= "" then
      out[#out + 1] = w
    end
  end
  return out
end

local PUNCT = { ["="] = true, [":"] = true, ["|"] = true, ["-"] = true, ["->"] = true, ["=>"] = true }

local function parse_loop(lines, i)
  local first = loop_tokens(lines[i])
  local n = #first
  if n < 2 or n > 15 then return nil end
  local rows, j = { first }, i
  while j + 1 <= #lines do
    local t = loop_tokens(lines[j + 1])
    if #t ~= n then break end
    rows[#rows + 1] = t; j = j + 1
  end
  -- an all-text first line over numeric rows is the header
  local header_line
  local text_first = true
  for _, t in ipairs(first) do if is_number(t) then text_first = false end end
  if text_first and #rows >= 3 then header_line = table.remove(rows, 1) end
  if #rows < 2 then return nil end
  local kinds = {}
  for p = 1, n do
    local const, nums = true, 0
    for _, r in ipairs(rows) do
      if r[p] ~= rows[1][p] then const = false end
      if is_number(r[p]) then nums = nums + 1 end
    end
    if nums > 0 and nums < #rows then return nil end -- numbers here in some lines only
    kinds[p] = nums > 0 and "num" or (const and "const" or "text")
  end
  local data = 0
  for p = 1, n do if kinds[p] == "num" then data = data + 1 end end
  if data == 0 then return nil end
  -- constant words before a column name it; trailing ones are its unit
  local header, cols, pending = {}, {}, {}
  for p = 1, n do
    if kinds[p] == "const" and not header_line then
      local w = rows[1][p]:gsub("[:=]$", "")
      if not PUNCT[w] and w ~= "" then pending[#pending + 1] = w end
    else
      cols[#cols + 1] = p
      header[#header + 1] = header_line and header_line[p] or table.concat(pending, " ")
      pending = {}
    end
  end
  if #pending > 0 and #header > 0 then
    header[#header] = trim(header[#header] .. " (" .. table.concat(pending, " ") .. ")")
  end
  local named = false
  for _, h in ipairs(header) do if h ~= "" then named = true end end
  if not named and #rows < 3 then return nil end
  local out = {}
  for _, r in ipairs(rows) do
    local row = { "" }
    for _, p in ipairs(cols) do row[#row + 1] = r[p] end
    out[#out + 1] = row
  end
  table.insert(header, 1, "")
  return { kind = "frame", loop = true, header = named and header or nil, rows = out }, j
end

local PARSERS = { parse_tibble, parse_numpy, parse_rvector, parse_series, parse_frame, parse_loop }

function M.segments(text)
  local lines = split_lines(text)
  local segs, buf = {}, {}
  local function flush()
    if #buf > 0 then segs[#segs + 1] = { text = table.concat(buf, "\n") }; buf = {} end
  end
  local i = 1
  while i <= #lines do
    local found, last
    if lines[i] ~= "" then
      for _, parse in ipairs(PARSERS) do
        found, last = parse(lines, i)
        if found then break end
      end
    end
    if found and found.text then
      buf[#buf + 1] = found.text; i = last + 1
    elseif found then
      flush(); segs[#segs + 1] = truncate(found); i = last + 1
    else
      buf[#buf + 1] = lines[i]; i = i + 1
    end
  end
  flush()
  return segs
end

-- rendering ------------------------------------------------------------
local function latex_escape(s)
  return pandoc.write(pandoc.Pandoc({ pandoc.Plain({ pandoc.Str(s) }) }), "latex"):gsub("%s+$", "")
end

local GLYPH_TEX = { [VDOTS] = "\\vdots", [CDOTS] = "\\cdots", [DDOTS] = "\\ddots" }

local function footer_latex(text)
  return pandoc.RawBlock("latex", "\\begin{center}\\vspace{-4pt}{\\footnotesize\\color{inkFaint}\\phulabel{" ..
    latex_escape(text) .. "}}\\end{center}")
end

local function array_latex(grid)
  local lines = {}
  local all = { grid.header }
  for _, r in ipairs(grid.rows) do all[#all + 1] = r end
  for ri, r in ipairs(all) do
    local out = {}
    for ci, s in ipairs(r) do
      local tex
      if GLYPH_TEX[s] then tex = GLYPH_TEX[s]
      elseif s == "" then tex = ""
      elseif ri == 1 or ci == 1 then tex = "\\phuix{" .. latex_escape(s) .. "}"
      else
        tex = "\\text{\\ttfamily\\small " .. latex_escape(s:gsub("\u{2212}", "-")) .. "}"
        if is_negative(s) then tex = "\\phuneg{" .. tex .. "}" end
      end
      out[#out + 1] = tex
    end
    lines[#lines + 1] = table.concat(out, " & ")
  end
  local blocks = { pandoc.RawBlock("latex", "\\begin{center}\\(\\left[\\begin{array}{r@{\\hspace{1.2em}}" ..
    string.rep("r", #grid.header - 1) .. "}\n" .. table.concat(lines, " \\\\\n") ..
    "\n\\end{array}\\right]\\)\\end{center}") }
  if grid.footer and grid.footer ~= "" then blocks[#blocks + 1] = footer_latex(grid.footer) end
  return blocks
end

local function cell(s, classes)
  local inl = { pandoc.Str(s) }
  if classes then inl = { pandoc.Span(inl, pandoc.Attr("", classes)) } end
  return { pandoc.Plain(inl) }
end

local function grid_table(grid, latex)
  local array = grid.kind == "array"
  local ncol = #(grid.header or grid.rows[1])
  local drop_index = grid.loop -- loops have no row labels
  local aligns, widths, headers, rows = {}, {}, {}, {}
  local first = drop_index and 2 or 1
  for c = first, ncol do
    local numeric = true
    for _, r in ipairs(grid.rows) do
      if r[c] and r[c] ~= "" and not is_numberish(r[c]) then numeric = false end
    end
    aligns[#aligns + 1] = (c == 1 and not array) and pandoc.AlignLeft or
      (numeric and pandoc.AlignRight or pandoc.AlignLeft)
    widths[#widths + 1] = 0
  end
  local function faint(s)
    if latex then return { pandoc.Plain({ pandoc.RawInline("latex", "\\textcolor{inkFaint}{"),
      pandoc.Str(s), pandoc.RawInline("latex", "}") }) } end
    return cell(s, { "ix" })
  end
  if grid.header then
    for c = first, ncol do headers[#headers + 1] = cell(grid.header[c]) end
  end
  for _, r in ipairs(grid.rows) do
    local row = {}
    for c = first, ncol do
      local s = r[c] or ""
      if c == 1 and (grid.index or array) then row[#row + 1] = faint(s)
      elseif array and is_negative(s) then row[#row + 1] = cell(s, { "neg" })
      else row[#row + 1] = cell(s) end
    end
    rows[#rows + 1] = row
  end
  return pandoc.utils.from_simple_table(pandoc.SimpleTable({}, aligns, widths, headers, rows))
end

local function render_grid(grid, latex)
  if latex and grid.kind == "array" then return array_latex(grid) end
  local blocks = { grid_table(grid, latex) }
  if grid.footer and grid.footer ~= "" then
    if latex then blocks[#blocks + 1] = footer_latex(grid.footer)
    else blocks[#blocks + 1] = pandoc.Para({ pandoc.Str(grid.footer) }) end
  end
  return { pandoc.Div(blocks, pandoc.Attr("", { grid.kind == "array" and "phu-array" or "phu-frame" })) }
end

local function render_text(text, latex, label)
  if latex then
    return { pandoc.RawBlock("latex", "\\begin{phuout}[" .. (label or "out") .. "]\n\\begin{Verbatim}\n" .. text ..
      "\n\\end{Verbatim}\n\\end{phuout}") }
  end
  return { pandoc.CodeBlock(text) }
end

-- a pandas table Quarto already parsed from the HTML display output
local function display_table(el, latex)
  local tbl, footer
  el:walk({
    Table = function(t) if t.classes:includes("dataframe") then tbl = tbl or t end end,
    RawBlock = function(r)
      local a, b = r.text:match("(%d+) rows \u{00D7} (%d+) columns")
      if a then footer = a .. " rows " .. TIMES .. " " .. b .. " columns" end
    end,
  })
  if not tbl then return nil end
  for i, spec in ipairs(tbl.colspecs) do tbl.colspecs[i] = { spec[1], pandoc.ColWidthDefault } end
  tbl.classes = {}
  local L, n = M.limits, 0
  for _, body in ipairs(tbl.bodies) do n = n + #body.body end
  if n > L.frame_rows and #tbl.bodies == 1 then
    footer = footer or (n .. " rows " .. TIMES .. " " .. (#tbl.colspecs - 1) .. " columns")
    local body, keep = tbl.bodies[1].body, {}
    for k = 1, L.frame_head do keep[#keep + 1] = body[k] end
    local gap = pandoc.Row(pandoc.List(body[1].cells):map(function()
      return pandoc.Cell({ pandoc.Plain({ pandoc.Str(VDOTS) }) }) end))
    keep[#keep + 1] = gap
    for k = n - L.frame_tail + 1, n do keep[#keep + 1] = body[k] end
    tbl.bodies[1].body = keep
  end
  if latex then
    for _, body in ipairs(tbl.bodies) do
      for _, row in ipairs(body.body) do
        local c = row.cells[1]
        if c then
          local inl = pandoc.utils.blocks_to_inlines(c.contents)
          inl:insert(1, pandoc.RawInline("latex", "\\textcolor{inkFaint}{"))
          inl:insert(pandoc.RawInline("latex", "}"))
          c.contents = { pandoc.Plain(inl) }
        end
      end
    end
  end
  local blocks = { tbl }
  if footer then
    if latex then blocks[#blocks + 1] = footer_latex(footer)
    else blocks[#blocks + 1] = pandoc.Para({ pandoc.Str(footer) }) end
  end
  return { pandoc.Div(blocks, pandoc.Attr("", { "phu-frame" })) }
end

local TEXT_OUTPUTS = { "cell-output-stdout", "cell-output-display" }

--- Transform one cell-output Div; nil leaves it alone.
function M.transform(el, latex)
  if el.classes:includes("cell-output-stderr") then
    if not latex then return nil end
    local out = pandoc.List()
    for _, b in ipairs(el.content) do
      out:extend(b.t == "CodeBlock" and render_text(b.text, true, "msg") or { b })
    end
    el.content = out
    return el
  end
  local text_output = false
  for _, c in ipairs(TEXT_OUTPUTS) do text_output = text_output or el.classes:includes(c) end
  if not text_output then return nil end
  local display = display_table(el, latex)
  if display then el.content = display; return el end
  local out, changed = pandoc.List(), false
  for _, b in ipairs(el.content) do
    if b.t == "CodeBlock" then
      changed = true
      for _, seg in ipairs(M.segments(b.text)) do
        out:extend(seg.text and render_text(seg.text, latex) or render_grid(seg, latex))
      end
    else
      out:insert(b)
    end
  end
  if not changed then return nil end
  el.content = out
  return el
end

return M
