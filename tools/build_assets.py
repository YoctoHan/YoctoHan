#!/usr/bin/env python3
"""Generates the Field Notebook SVG assets (light + dark) from one shared geometry.

Run (from the repo root):  python3 tools/build_assets.py   -> rewrites assets/*.svg at the repo root.

Guards (the build fails loudly instead of shipping a clipped label):
  * MIN_FONT   - no <text> run may be set below 10.5 units in an 880-wide viewBox.
  * budget()   - every <text> run declares the lane it must fit in; the run's width is
                 estimated pessimistically (0.58 em/char sans, 0.62 mono, 0.55 serif, plus
                 letter-spacing) and must leave >= 12 % slack for Segoe UI / Noto fallbacks.
  * check()    - layout invariants raise SystemExit (never a bare assert, which `python3 -O`
                 would strip); every generated file is parsed as XML before it is written;
                 selftest() exercises the guards themselves.
Only the standard library is used.
"""
import math
import os
import re
import xml.etree.ElementTree as ET
from xml.sax.saxutils import escape

HERE = os.path.dirname(os.path.abspath(__file__))
# The script lives in tools/ inside the profile repo; assets/ sits next to README.md at the root.
ROOT = os.path.dirname(HERE) if os.path.basename(HERE) == "tools" else HERE
OUT = os.path.join(ROOT, "assets")
os.makedirs(OUT, exist_ok=True)

SANS = "-apple-system, BlinkMacSystemFont, 'Segoe UI', 'Noto Sans', Helvetica, Arial, sans-serif"
MONO = "ui-monospace, SFMono-Regular, 'SF Mono', Menlo, Consolas, 'Liberation Mono', monospace"
SERIF = "Georgia, 'Times New Roman', Times, serif"

MIN_FONT = 10.5          # units, in an 880-wide viewBox (~10 px in GitHub's 832 px column)
SLACK = 0.12             # required head-room on top of the pessimistic estimate
EM = {SANS: 0.58, MONO: 0.62, SERIF: 0.55}   # pessimistic average advance, em per character

# Two inks on two papers. `ink2` is the muted ink for 12+ unit text; `ink3` is the darker
# muted ink used for anything smaller than 12 units (>= 5.5:1 on cream). In dark mode the
# pale cyan-grey already clears the bar, so ink3 == ink2 there.
PAL = {
    "light": dict(
        paper="#F6F0E1", grid="#D8CDB2", grid2="#D8CDB2", gridkind="dots",
        ink="#2E2A25", ink2="#6F6556", ink3="#665C4E", line="#3D5A80", accent="#B4472B",
        chip="#FBF7EC", quiet=0.75,     # paper wash behind the hero tagline (dots would run under text)
    ),
    "dark": dict(
        paper="#0E1F38", grid="#1B365A", grid2="#274B75", gridkind="lines",
        ink="#E8F1F8", ink2="#8FB0C9", ink3="#8FB0C9", line="#8FDCF2", accent="#F5B86A",
        chip="#132846", quiet=0.0,      # the blueprint grid is quiet enough already
    ),
}


# ----------------------------------------------------------------- guards
def budget(s, size, font, lane, ls=0.0, raw=False):
    """Pessimistic width estimate of a text run; SystemExit if it cannot fit `lane` with slack.

    Only a `raw` run (pre-escaped markup with <tspan>s) has its tags stripped and entities
    unescaped before counting; a plain string is measured literally, so a '<' in source text
    (the CUDA launch line) counts as a character instead of starting a bogus tag."""
    if raw:
        plain = re.sub(r"<[^>]+>", "", s)
        plain = plain.replace("&lt;", "<").replace("&gt;", ">").replace("&amp;", "&")
    else:
        plain = s
    n = len(plain)
    est = n * size * EM[font] + max(ls, 0.0) * n
    need = est * (1 + SLACK)
    if need > lane + 1e-6:
        raise SystemExit(f"OVERFLOW: {plain!r} @ {size} needs {need:.1f} > lane {lane:.1f}")
    return est


def check(cond, msg):
    """Layout guard that survives `python3 -O` (a bare assert would be stripped)."""
    if not cond:
        raise SystemExit(f"LAYOUT: {msg}")


def attr(s):
    """Escape a string for use inside a double-quoted XML attribute."""
    return escape(s, {'"': "&quot;"})


def muted(p, size):
    """Muted ink, darkened for small sizes (light theme legibility)."""
    return p["ink2"] if size >= 12 else p["ink3"]


# ----------------------------------------------------------------- helpers
def f(n):
    s = f"{n:.1f}"
    return s[:-2] if s.endswith(".0") else s


def text(x, y, s, size, fill, font=SANS, lane=None, anchor=None, weight=None, italic=False,
         ls=None, opacity=None, raw=False, transform=None):
    if size < MIN_FONT:
        raise SystemExit(f"MIN_FONT: {s!r} set at {size} < {MIN_FONT}")
    if lane is None:
        raise SystemExit(f"text() needs a lane: {s!r}")
    budget(s, size, font, lane, ls or 0.0, raw=raw)
    a = [f'x="{f(x)}"', f'y="{f(y)}"', f'font-family="{font}"',
         f'font-size="{f(size)}"', f'fill="{fill}"']
    if anchor:
        a.append(f'text-anchor="{anchor}"')
    if weight:
        a.append(f'font-weight="{weight}"')
    if italic:
        a.append('font-style="italic"')
    if ls is not None:
        a.append(f'letter-spacing="{f(ls)}"')
    if opacity is not None:
        a.append(f'opacity="{opacity}"')
    if transform:
        a.append(f'transform="{transform}"')
    body = s if raw else escape(s)
    return f'<text {" ".join(a)}>{body}</text>'


def line(x1, y1, x2, y2, stroke, sw=1, opacity=None, dash=None, cap="round"):
    a = [f'x1="{f(x1)}"', f'y1="{f(y1)}"', f'x2="{f(x2)}"', f'y2="{f(y2)}"',
         f'stroke="{stroke}"', f'stroke-width="{f(sw)}"', f'stroke-linecap="{cap}"']
    if opacity is not None:
        a.append(f'opacity="{opacity}"')
    if dash:
        a.append(f'stroke-dasharray="{dash}"')
    return f'<line {" ".join(a)}/>'


def rect(x, y, w, h, fill="none", stroke=None, sw=1, rx=0, opacity=None,
         fill_opacity=None, dash=None):
    a = [f'x="{f(x)}"', f'y="{f(y)}"', f'width="{f(w)}"', f'height="{f(h)}"',
         f'fill="{fill}"']
    if rx:
        a.append(f'rx="{f(rx)}"')
    if stroke:
        a.append(f'stroke="{stroke}"')
        a.append(f'stroke-width="{f(sw)}"')
    if opacity is not None:
        a.append(f'opacity="{opacity}"')
    if fill_opacity is not None:
        a.append(f'fill-opacity="{fill_opacity}"')
    if dash:
        a.append(f'stroke-dasharray="{dash}"')
    return f'<rect {" ".join(a)}/>'


def path(d, stroke, sw=1.2, fill="none", opacity=None, dash=None):
    a = [f'd="{d}"', f'fill="{fill}"', f'stroke="{stroke}"', f'stroke-width="{f(sw)}"',
         'stroke-linecap="round"', 'stroke-linejoin="round"']
    if opacity is not None:
        a.append(f'opacity="{opacity}"')
    if dash:
        a.append(f'stroke-dasharray="{dash}"')
    return f'<path {" ".join(a)}/>'


def head(tip, frm, color, size=6, sw=1.2):
    """Open chevron arrowhead at `tip`, arriving from `frm`."""
    ang = math.atan2(tip[1] - frm[1], tip[0] - frm[0])
    a1, a2 = ang + math.pi - 0.5, ang + math.pi + 0.5
    p1 = (tip[0] + size * math.cos(a1), tip[1] + size * math.sin(a1))
    p2 = (tip[0] + size * math.cos(a2), tip[1] + size * math.sin(a2))
    d = f"M{f(p1[0])},{f(p1[1])} L{f(tip[0])},{f(tip[1])} L{f(p2[0])},{f(p2[1])}"
    return path(d, color, sw)


def arrow_q(p0, c, p1, color, sw=1.2, dash=None):
    """Quadratic-curve arrow p0 -> p1 with control c."""
    d = f"M{f(p0[0])},{f(p0[1])} Q{f(c[0])},{f(c[1])} {f(p1[0])},{f(p1[1])}"
    return path(d, color, sw, dash=dash) + head(p1, c, color, sw=sw)


def arrow_l(p0, p1, color, sw=1.2, dash=None):
    d = f"M{f(p0[0])},{f(p0[1])} L{f(p1[0])},{f(p1[1])}"
    return path(d, color, sw, dash=dash) + head(p1, p0, color, sw=sw)


def note(p, x, y, s, size, lane):
    """Margin note: a small hooked arrow glyph, then italic text in the annotation ink."""
    g = path(f"M{f(x+2)},{f(y-15)} L{f(x+2)},{f(y-4)} L{f(x+13)},{f(y-4)}", p["accent"], 1.3)
    g += head((x + 13, y - 4), (x + 2, y - 4), p["accent"], size=5, sw=1.3)
    return g + text(x + 21, y, s, size, p["accent"], italic=True, lane=lane - 21)


def sup_T(base, size_main, size_sup, tail=""):
    """`base` with a superscript T as a tspan (avoids the U+1D40 glyph), then `tail`.

    A tspan's dy shifts the current text position and the shift persists after the tspan
    closes, so the tail is wrapped in a second tspan that shifts back down by the same
    amount — otherwise everything after the T would render at superscript height."""
    if size_sup < MIN_FONT:
        raise SystemExit("MIN_FONT: superscript below floor")
    d = size_main * 0.36
    s = f'{escape(base)}<tspan dy="{f(-d)}" font-size="{f(size_sup)}">T</tspan>'
    if tail:
        s += f'<tspan dy="{f(d)}">{escape(tail)}</tspan>'
    return s


def grid_patterns(p, sfx="", x0=0):
    """Dot grid (light) or minor+major blueprint grid (dark), anchored at x0 so a sheet that
    does not start at the plate origin still gets a grid line on its own left edge."""
    if p["gridkind"] == "dots":
        return (f'<pattern id="g1{sfx}" x="{x0}" width="16" height="16" patternUnits="userSpaceOnUse">'
                f'<circle cx="8" cy="8" r="1" fill="{p["grid"]}"/></pattern>')
    return (f'<pattern id="g1{sfx}" x="{x0}" width="16" height="16" patternUnits="userSpaceOnUse">'
            f'<path d="M16 0 L0 0 L0 16" fill="none" stroke="{p["grid"]}" stroke-width="0.7"/></pattern>'
            f'<pattern id="g2{sfx}" x="{x0}" width="80" height="80" patternUnits="userSpaceOnUse">'
            f'<path d="M80 0 L0 0 L0 80" fill="none" stroke="{p["grid2"]}" stroke-width="0.8"/></pattern>')


def svg_open(w, h, p, label, origin2=None):
    """Root element + defs. No background: paper is painted per panel by paper().
    `origin2` adds a second grid pattern set (ids g1b/g2b) anchored at that x, for a second sheet."""
    pat = grid_patterns(p)
    if origin2 is not None:
        pat += grid_patterns(p, "b", origin2)
    soft = ('<filter id="soft" x="-10%" y="-40%" width="120%" height="180%">'
            '<feGaussianBlur stdDeviation="9"/></filter>')
    hatch = (soft + f'<pattern id="hatch" width="6" height="6" patternUnits="userSpaceOnUse">'
             f'<path d="M-1,1 L1,-1 M0,6 L6,0 M5,7 L7,5" stroke="{p["ink2"]}" stroke-width="0.8" opacity="0.45"/>'
             f'</pattern>')
    grad = (f'<linearGradient id="heat" x1="0" y1="0" x2="1" y2="0">'
            f'<stop offset="0" stop-color="{p["line"]}" stop-opacity="0.07"/>'
            f'<stop offset="1" stop-color="{p["line"]}" stop-opacity="0.97"/></linearGradient>')
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}" '
            f'role="img" aria-label="{attr(label)}">\n'
            f'<defs>{pat}{hatch}{grad}</defs>\n')


def paper(p, x, y, w, h, sfx=""):
    """One notebook sheet: paper fill + dot grid (light) or minor+major blueprint grid (dark).
    `sfx` selects the pattern set (see svg_open's origin2)."""
    o = rect(x, y, w, h, fill=p["paper"], rx=10)
    o += rect(x, y, w, h, fill=f"url(#g1{sfx})", rx=10)
    if p["gridkind"] != "dots":
        o += rect(x, y, w, h, fill=f"url(#g2{sfx})", rx=10)
    return o + "\n"


def svg_close():
    return "</svg>\n"


# -------------------------------------------------------------------- hero
def hero(p):
    W, H = 880, 320
    o = [svg_open(W, H, p, "YoctoHan - field notebook on deep-learning infrastructure"),
         paper(p, 0, 0, W, H)]
    ink, ink2, ln, ac = p["ink"], p["ink2"], p["line"], p["accent"]

    # drawing-sheet double frame
    o.append(rect(14, 14, 852, 292, stroke=ink, sw=1, rx=6, opacity=0.55))
    o.append(rect(20, 20, 840, 280, stroke=ink, sw=0.6, rx=4, opacity=0.35))

    # quiet paper behind the tagline / margin-note block (keeps the dot grid out from under the
    # text); blurred so the wash fades into the sheet instead of reading as an erased rectangle
    if p["quiet"]:
        o.append(f'<rect x="52" y="152" width="556" height="86" rx="4" fill="{p["paper"]}" '
                 f'opacity="{p["quiet"]}" filter="url(#soft)"/>')

    # left column
    AX = 640                                   # roofline y-axis; the text column ends before it
    o.append(text(48, 66, "FIELD NOTEBOOK · DEEP-LEARNING INFRASTRUCTURE", 10.5, muted(p, 10.5), MONO,
                  ls=1.6, lane=800))
    o.append(text(46, 122, "YoctoHan", 54, ink, weight=700, ls=-1, lane=480))
    o.append(path("M48,134 C110,139 200,129 296,134", ac, 2.2, opacity=0.9))
    o.append(text(48, 164, "Mathematics MSc turned systems engineer.", 17, ink, lane=AX - 16 - 48))
    o.append(text(48, 188, "I make large language models train and serve faster.", 17, ink2,
                  lane=AX - 16 - 48))
    o.append(note(p, 48, 232, "the proof is in the profiler.", 13.5, lane=300))

    # equation (1): parentheses hug the stacked fraction (3 units off the bar ends)
    BAR_L, BAR_R, BAR_Y = 762, 788, 88
    mid = (BAR_L + BAR_R) / 2
    # math convention: operator names, delimiters and relations upright; only variables italic
    IT = '<tspan font-style="italic">{}</tspan>'
    o.append(text(BAR_L - 3, 92,
                  f'Attention({IT.format("Q")},{IT.format("K")},{IT.format("V")}) = softmax(',
                  14, ink, SERIF, anchor="end", raw=True, lane=BAR_L - 3 - 330))
    o.append(line(BAR_L, BAR_Y, BAR_R, BAR_Y, ink, 1))
    o.append(text(mid, 83, sup_T("QK", 12.5, 10.5), 12.5, ink, SERIF, anchor="middle", italic=True, raw=True,
                  lane=BAR_R - BAR_L))
    o.append(text(mid, 101, "√d", 12.5, ink, SERIF, anchor="middle", italic=True, lane=BAR_R - BAR_L))
    o.append(text(BAR_R + 3, 92, f'){IT.format("V")}', 14, ink, SERIF, raw=True, lane=40))
    o.append(text(850, 92, "(1)", 11, muted(p, 11), anchor="end", lane=30))

    # Fig. 0 — roofline sketch (x 640..836, y 120..210); its caption clears the title-block
    # rule at y=256 by 10 units, so the two columns end at comparable heights.
    o.append(line(AX, 120, AX, 210, ink2, 1))
    o.append(head((AX, 120), (AX, 210), ink2, size=5, sw=1))
    o.append(line(AX, 210, 836, 210, ink2, 1))
    o.append(head((836, 210), (AX, 210), ink2, size=5, sw=1))
    o.append(path(f"M{AX+6},206 L740,142 L830,142", ln, 2))
    o.append(line(740, 142, 740, 210, ink2, 0.9, opacity=0.6, dash="2 3"))
    o.append(f'<circle cx="690" cy="176" r="3.5" fill="{ink2}"/>')
    o.append(text(697, 194, "before", 10.5, muted(p, 10.5), lane=60))
    o.append(arrow_q((699, 173), (762, 184), (782, 156), ac, sw=1.1, dash="3 3"))
    o.append(f'<circle cx="788" cy="150" r="4" fill="{ac}">'
             f'<animate attributeName="r" values="4;5.5;4" dur="2.6s" repeatCount="indefinite"/></circle>')
    o.append(text(797, 154, "after", 10.5, ac, lane=40))
    o.append(text(830, 136, "compute roof", 10.5, muted(p, 10.5), anchor="end", lane=120))
    o.append(text((AX + 836) / 2, 226, "arithmetic intensity →", 10.5, muted(p, 10.5), anchor="middle",
                  lane=836 - AX))
    o.append(text(AX - 10, 165, "throughput →", 10.5, muted(p, 10.5), anchor="middle",
                  transform=f"rotate(-90 {AX-10} 165)", lane=90))
    o.append(text(836, 243, "Fig. 0 — roofline, sketched from memory.", 10.5, muted(p, 10.5), italic=True,
                  anchor="end", lane=500))

    # title block: CONTACT | LOCATION | TRAINING | FOCUS | GITHUB
    # Widths are set so every value passes budget() with comparable slack (none above ~0.98
    # of its lane); FOCUS looks roomy on Apple fonts but its pessimistic estimate is the widest.
    o.append(line(20, 256, 860, 256, ink, 0.9, opacity=0.55, cap="butt"))
    cells = [
        (176, "CONTACT", "yoctoinch@gmail.com"),
        (90, "LOCATION", "Beijing"),
        (144, "TRAINING", "MSc Mathematics"),
        (262, "FOCUS", "LLM training · inference · CUDA"),
        (168, "GITHUB", "github.com/YoctoHan"),
    ]
    check(sum(w for w, _, _ in cells) == 840, "title-block cell widths must sum to 840")
    x, PAD = 20, 9
    for i, (w, lab, val) in enumerate(cells):
        if i:
            o.append(line(x, 256, x, 300, ink, 0.7, opacity=0.45, cap="butt"))
        o.append(text(x + PAD, 272, lab, 10.5, muted(p, 10.5), MONO, ls=1.5, lane=w - 2 * PAD))
        o.append(text(x + PAD, 291, val, 12, ink, lane=w - 2 * PAD))
        x += w
    o.append(svg_close())
    return "".join(o)


# ------------------------------------------------------------- figures
def attn_rows():
    rows = []
    for i in range(8):
        sc = []
        for j in range(i + 1):
            # recency decay + an attention-sink bonus on token 0 (2.3 makes k0 the argmax of every
            # row while the diagonal stays clearly visible) + a little deterministic texture
            s = -0.8 * math.sqrt(i - j) + (2.3 if j == 0 else 0.0) + 0.5 * math.sin(1.7 * i + 2.3 * j + 0.4)
            sc.append(s)
        m = max(sc)
        ex = [math.exp(v - m) for v in sc]
        z = sum(ex)
        rows.append([e / z for e in ex])
    return rows


PW = 432          # panel width inside the 880-wide plate
GAP = 16
R = PW - 24       # right content edge of a panel (24-unit margins)


def caption(p, y, fig, title, sub_lines, ox):
    """Ruled caption block: 'Fig. n — title' then muted sub-caption lines."""
    ink = p["ink"]
    o = line(ox + 24, y, ox + R, y, ink, 0.8, opacity=0.4, cap="butt")
    o += text(ox + 24, y + 16, f'<tspan font-weight="600">{escape(fig)}</tspan> — {escape(title)}',
              11.5, ink, raw=True, lane=R - 24)
    for k, s in enumerate(sub_lines):
        o += text(ox + 24, y + 31 + 15 * k, s, 11, muted(p, 11), lane=R - 24)
    return o


def fig1(p, ox):
    """Fig. 1 — causal self-attention heatmap. `ox` is the panel's x offset in the plate."""
    ink, ink2, ln, ac = p["ink"], p["ink2"], p["line"], p["accent"]
    o = []
    X0, Y0, C = ox + 62, 48, 22
    NX = ox + 262                      # notes column
    o.append(text(X0 + 4 * C, 26, "keys j →", 10.5, muted(p, 10.5), italic=True, anchor="middle", lane=8 * C))
    o.append(text(ox + 30, Y0 + 4 * C, "queries i →", 10.5, muted(p, 10.5), italic=True, anchor="middle",
                  transform=f"rotate(90 {ox+30} {Y0+4*C})", lane=8 * C))
    rows = attn_rows()
    o.append(rect(X0 - 2, Y0 - 2, 8 * C + 3, 8 * C + 3, fill=p["paper"], rx=3))  # paper backing
    for j in range(8):
        o.append(text(X0 + j * C + C / 2, 42, f"k{j}", 10.5, muted(p, 10.5), MONO, anchor="middle", lane=C))
    for i in range(8):
        o.append(text(X0 - 7, Y0 + i * C + 15, f"q{i}", 10.5, muted(p, 10.5), MONO, anchor="end", lane=19))
        for j in range(8):
            x, y = X0 + j * C, Y0 + i * C
            if j > i:
                o.append(rect(x, y, C - 1, C - 1, fill="url(#hatch)", rx=2))
                o.append(rect(x, y, C - 1, C - 1, stroke=ink2, sw=0.5, rx=2, opacity=0.35))
            else:
                v = rows[i][j]
                op = 0.07 + 0.9 * min(1.0, v / 0.55) ** 0.75
                o.append(rect(x, y, C - 1, C - 1, fill=ln, rx=2, fill_opacity=round(op, 2)))

    # notes (right column)
    lane = ox + R - NX
    # code-style in the figure's mono register (a 10.5 superscript next to 10.5 text just looks raised);
    # same baseline as the k0…k7 column headers
    o.append(text(NX, 42, "P = softmax(QK^T/√d)", 10.5, muted(p, 10.5), MONO, lane=lane))
    o.append(text(NX, 82, "masked, j > i", 11, ac, italic=True, lane=lane))
    o.append(text(NX, 96, "score → −∞", 10.5, ac, MONO, lane=lane))
    o.append(arrow_q((NX - 6, 87), (X0 + 8.6 * C, 88), (X0 + 7.4 * C, Y0 + 1.2 * C), ac, sw=1.2))

    # one SRAM-resident tile: rows 4-7 x cols 4-7
    o.append(rect(X0 + 4 * C, Y0 + 4 * C, 4 * C, 4 * C, stroke=ac, sw=1.3, rx=2, dash="5 3"))
    o.append(text(NX, 184, "one tile,", 11, ac, italic=True, lane=lane))
    o.append(text(NX, 198, "resident in SRAM", 11, ac, italic=True, lane=lane))
    o.append(arrow_l((NX - 6, 188), (X0 + 8 * C + 3, 180), ac, sw=1.2))

    # attention sink
    o.append(arrow_l((X0 + C / 2, 252), (X0 + C / 2, Y0 + 8 * C + 6), ac, sw=1.2))
    o.append(text(X0, 270, "attention sink — every query leans on token 0", 10.5, ac, italic=True,
                  lane=ox + R - X0))

    # legend 0 … 1: joins the notes column (left edge at NX) just below the heatmap's last row
    o.append(text(NX, 240, "0", 10.5, muted(p, 10.5), lane=10))
    o.append(rect(NX + 11, 234, 72, 6, fill="url(#heat)", stroke=ink2, sw=0.3, rx=1))
    o.append(text(NX + 89, 240, "1", 10.5, muted(p, 10.5), lane=14))

    o.append(caption(p, 280, "Fig. 1", "Causal self-attention, one head, 8 tokens.",
                     ["Future keys are masked; work proceeds", "one on-chip tile at a time."], ox))
    return "".join(o)


def fig2(p, ox):
    """Fig. 2 — CUDA grid -> block -> thread. `ox` is the panel's x offset in the plate."""
    ink, ink2, ln, ac = p["ink"], p["ink2"], p["line"], p["accent"]
    o = []
    GX, BX, TX = ox + 24, ox + 150, ox + 282          # panel x's
    GW, BW, TW, PH, PY = 104, 112, 126, 112, 56       # widths, height, top
    check(TX + TW == ox + R, "Fig. 2 thread card must end on the panel's right content edge")

    # both launch dimensions are printed so the row/col arithmetic below is checkable
    o.append(text(GX, 28, "kernel<<<gridDim (3,3), blockDim (8,8)>>>(…)", 10.5, muted(p, 10.5), MONO,
                  lane=R - 24))
    o.append(text(GX, 48, "grid · 3×3 blocks", 10.5, ink, MONO, lane=BX - GX))
    o.append(text(BX, 48, "block · 64 threads", 10.5, ink, MONO, lane=TX - BX))
    o.append(text(TX, 48, "thread", 10.5, ink, MONO, lane=TW))

    # paper backing under the three panels
    for (px, pw) in ((GX, GW), (BX, BW), (TX, TW)):
        o.append(rect(px, PY, pw, PH, fill=p["paper"], rx=6))

    # grid panel: 3x3 blocks, highlight blockIdx = (2, 1)
    o.append(rect(GX, PY, GW, PH, fill=ln, fill_opacity=0.05, stroke=ln, sw=1.2, rx=6))
    for r in range(3):
        for c in range(3):
            x, y = GX + 4 + c * 34, PY + 8 + r * 34
            hi = (r == 1 and c == 2)
            o.append(rect(x, y, 28, 28, fill=ln if hi else "none", fill_opacity=0.3 if hi else None,
                          stroke=ln, sw=1, rx=3))
    # block panel: 8x8 threads, warp 0 = rows 0-3; highlight threadIdx = (7, 2)
    o.append(rect(BX, PY, BW, PH, fill=ln, fill_opacity=0.05, stroke=ln, sw=1.2, rx=6))
    for r in range(8):
        for c in range(8):
            x, y = BX + 5 + c * 13, PY + 5 + r * 13
            if r == 2 and c == 7:
                o.append(rect(x, y, 11, 11, fill=ac, rx=1.5))
            else:
                o.append(rect(x, y, 11, 11, fill=ln, rx=1.5, fill_opacity=0.38 if r < 4 else 0.16))
    # thread card
    o.append(rect(TX, PY, TW, PH, fill=ac, fill_opacity=0.07, stroke=ln, sw=1.2, rx=6))
    for k, s in enumerate(("threadIdx.x = 7", "threadIdx.y = 2", "blockIdx.x = 2", "blockIdx.y = 1")):
        o.append(text(TX + 8, PY + 19 + 14 * k, s, 10.5, ink, MONO, lane=TW - 16))
    for k, wdt in enumerate((38, 30, 34, 26)):
        o.append(line(TX + 9, PY + 70 + k * 6, TX + 9 + wdt, PY + 70 + k * 6, ink2, 2.5, opacity=0.6))
    o.append(text(TX + 8, PY + 100, "registers", 10.5, muted(p, 10.5), MONO, lane=TW - 16))

    # zoom lines: highlighted block -> block panel, highlighted thread -> thread card
    hb = (GX + 4 + 2 * 34 + 28, PY + 8 + 34)         # right edge of block (2,1)
    ht = (BX + 5 + 7 * 13 + 11, PY + 5 + 2 * 13)     # right edge of thread (7,2)
    for (a, b) in (((hb[0], hb[1]), (BX, PY)), ((hb[0], hb[1] + 28), (BX, PY + PH)),
                   ((ht[0], ht[1]), (TX, PY)), ((ht[0], ht[1] + 11), (TX, PY + PH))):
        o.append(line(a[0], a[1], b[0], b[1], ink2, 0.9, opacity=0.7, dash="3 3"))

    # sub-labels
    SY = PY + PH + 18
    o.append(text(GX, SY, "gridDim = (3, 3)", 10.5, muted(p, 10.5), MONO, lane=BX - GX))
    o.append(rect(BX, SY - 8, 8, 8, fill=ln, fill_opacity=0.38, rx=1.5))
    o.append(text(BX + 12, SY, "warp 0", 10.5, muted(p, 10.5), MONO, lane=52))
    o.append(rect(BX + 64, SY - 8, 8, 8, fill=ln, fill_opacity=0.16, rx=1.5))
    o.append(text(BX + 76, SY, "warp 1", 10.5, muted(p, 10.5), MONO, lane=TX - BX - 76))
    o.append(text(TX, SY, "lane 23, warp 0", 10.5, muted(p, 10.5), MONO, lane=ox + R - TX))

    # 2-D index arithmetic (matches the card: row = 1*8+2 = 10, col = 2*8+7 = 23), set on the
    # panel's left margin like every other run on the plate
    o.append(text(GX, 218, "row = blockIdx.y * blockDim.y + threadIdx.y", 10.5, ink, MONO, lane=R - 24))
    o.append(text(GX, 234, "col = blockIdx.x * blockDim.x + threadIdx.x", 10.5, ink, MONO, lane=R - 24))
    # baseline 270 = the same foot as Fig. 1's attention-sink line, so both sheets end level
    o.append(note(p, GX, 270, "keep neighbouring lanes on neighbouring addresses.", 11, lane=R - 24))

    o.append(caption(p, 280, "Fig. 2", "The CUDA execution hierarchy.",
                     ["A warp of 32 lanes runs in lockstep;", "a block shares on-chip memory."], ox))
    return "".join(o)


def figures(p):
    """One plate, two sheets: Fig. 1 (left) and Fig. 2 (right) with a transparent gutter."""
    W, H = 880, 352            # captions end at y=326; 352 leaves the sheets ~22 units of foot margin
    check(2 * PW + GAP == W, "figure plate: two panels plus the gutter must equal the plate width")
    o = [svg_open(W, H, p, "Fig. 1 - causal self-attention heatmap; Fig. 2 - CUDA grid, block and thread",
                  origin2=PW + GAP),
         paper(p, 0, 0, PW, H), paper(p, PW + GAP, 0, PW, H, sfx="b")]
    o.append(fig1(p, 0))
    o.append(fig2(p, PW + GAP))
    o.append(svg_close())
    return "".join(o)


# --------------------------------------------------------------- table 1
def instruments(p):
    W, H = 880, 218
    o = [svg_open(W, H, p, "Table 1 - instruments: languages, frameworks, inference engines, tooling"),
         paper(p, 0, 0, W, H)]
    ink, ink2, ln, ac = p["ink"], p["ink2"], p["line"], p["accent"]

    o.append(text(24, 30, "Table 1 — Instruments", 12.5, ink, weight=600, lane=400))

    rows = [
        ("LANGUAGES", False, ["C++", "Python", "CUDA"]),
        ("FRAMEWORKS", False, ["PyTorch", "PaddlePaddle"]),
        ("INFERENCE", True, ["vLLM", "LMDeploy", "SGLang", "TensorRT-LLM"]),
        ("TOOLING", False, ["Docker", "LaTeX"]),
    ]
    ys = [46, 76, 106, 136, 166]
    CX = 190                                   # chips start here; labels own 24..CX
    for k, y in enumerate(ys):
        heavy = k in (0, len(ys) - 1)
        o.append(line(24, y, 856, y, ink, 1 if heavy else 0.7, opacity=0.6 if heavy else 0.3, cap="butt"))
    for k, (lab, now, chips) in enumerate(rows):
        y = ys[k]
        s = escape(lab)
        if now:      # current-focus flag, set in the annotation ink right after the label
            s += (f'<tspan dx="8" fill="{ac}" font-family="{SANS}" font-style="italic" '
                  f'letter-spacing="0">← now</tspan>')
        o.append(text(24, y + 19, s, 11, muted(p, 11), MONO, ls=1.5, raw=True, lane=CX - 24 - 8))
        x = CX
        for c in chips:
            est = budget(c, 11.5, SANS, 10_000)
            w = math.ceil(est * (1 + SLACK)) + 10
            o.append(rect(x, y + 6, w, 18, fill=p["chip"], stroke=ln, sw=1, rx=4))
            o.append(text(x + w / 2, y + 19, c, 11.5, ink, anchor="middle", lane=w - 10))
            x += w + 8
        check(x <= 856, f"chip row {lab} overflows the sheet")
    # The note stays on the chips column. A right-anchored note was tried: a leading hook glyph
    # cannot be pinned to text whose start drifts with the viewer's font, and a mirrored hook at
    # the right edge reads as a return key, not as the notebook's "hence" mark.
    o.append(note(p, CX, 196, "the ideas get written in LaTeX; the speed gets written in CUDA.", 11,
                  lane=856 - CX))
    o.append(svg_close())
    return "".join(o)


# -------------------------------------------------------------- appendix
def icon_mountain(x, y, ln, ac):
    return (path(f"M{x+2},{y+24} L{x+10},{y+8} L{x+15},{y+17} L{x+19},{y+11} L{x+26},{y+24}", ln, 1.5)
            + line(x + 2, y + 24, x + 26, y + 24, ln, 1.5)
            + f'<circle cx="{x+23}" cy="{y+6}" r="2.2" fill="{ac}"/>')


def icon_note(x, y, ln, ac):
    return (f'<circle cx="{x+9}" cy="{y+21}" r="3.5" fill="{ln}"/>'
            + line(x + 12.5, y + 21, x + 12.5, y + 6, ln, 1.5)
            + path(f"M{x+12.5},{y+6} Q{x+21},{y+8} {x+21},{y+15}", ac, 1.5))


def icon_tent(x, y, ln, ac):
    return (path(f"M{x+3},{y+24} L{x+14},{y+7} L{x+25},{y+24} Z", ln, 1.5)
            + path(f"M{x+11},{y+24} L{x+14},{y+18} L{x+17},{y+24}", ln, 1.5)
            + path(f"M{x+23},{y+1.5} L{x+24.3},{y+4.7} L{x+27.5},{y+6} L{x+24.3},{y+7.3} "
                   f"L{x+23},{y+10.5} L{x+21.7},{y+7.3} L{x+18.5},{y+6} L{x+21.7},{y+4.7} Z",
                   ac, 0.8, fill=ac))


def icon_cards(x, y, ln, ac, paper_fill):
    return (f'<rect x="{x+9}" y="{y+4}" width="13" height="18" rx="2" fill="none" stroke="{ln}" '
            f'stroke-width="1.5" transform="rotate(12 {x+15.5} {y+13})"/>'
            + rect(x + 4, y + 7, 13, 18, fill=paper_fill, stroke=ln, sw=1.5, rx=2)
            + text(x + 10.5, y + 19, "A", 10.5, ac, weight=700, anchor="middle", lane=13))


def appendix(p):
    W, H = 880, 100
    o = [svg_open(W, H, p, "Appendix A - off the keyboard: hiking, rock music, camping, Texas Hold'em"),
         paper(p, 0, 0, W, H)]
    ink, ink2, ln, ac = p["ink"], p["ink2"], p["line"], p["accent"]
    items = [
        ("Hiking", icon_mountain),
        ("Rock music", icon_note),
        ("Camping under the stars", icon_tent),
        ("Texas Hold'em with friends", lambda x, y, l, a: icon_cards(x, y, l, a, p["paper"])),
    ]
    # Layout: the last item is pinned so its pessimistic width still fits before the right
    # margin; the first three are spaced with equal gaps at a *realistic* 0.50 em/char, and
    # every item is then asserted (via text()'s lane) not to reach the next icon even at
    # the pessimistic width.
    ICON, L, RGT = 40, 24, 868      # the last label may run to 12 units inside the paper edge
    pess = [ICON + budget(lab, 12, SANS, 10_000) * (1 + SLACK) for lab, _ in items]
    real = [ICON + len(lab) * 12 * 0.50 for lab, _ in items]
    xs = [0.0] * len(items)
    xs[-1] = RGT - pess[-1]
    gap = (xs[-1] - L - sum(real[:-1])) / (len(items) - 1)
    check(gap >= 40, f"appendix items too wide (gap {gap:.0f})")
    x = float(L)
    for i in range(len(items) - 1):
        xs[i] = x
        x += real[i] + gap
    for i, ((lab, ic), x) in enumerate(zip(items, xs)):
        x = math.floor(x)
        limit = xs[i + 1] - 12 if i + 1 < len(items) else RGT     # next icon, or the paper edge
        o.append(ic(x, 18, ln, ac))
        o.append(text(x + ICON, 38, lab, 12, ink, lane=limit - (x + ICON)))
    o.append(line(24, 60, 856, 60, ink, 0.7, opacity=0.35, cap="butt"))
    o.append(text(24, 80, "Beijing · hand-drawn SVG, no widgets · set in your system fonts", 10.5,
                  muted(p, 10.5), MONO, lane=832))
    o.append(svg_close())
    return "".join(o)


# ------------------------------------------------------------------ main
BUILDERS = {
    "hero": hero,
    "figures": figures,
    "table1-instruments": instruments,
    "appendix-offkeyboard": appendix,
}

def selftest():
    """Guards on the guards: a plain '<' must count as a character, a raw tag must not,
    and attribute escaping must survive a double quote."""
    check(budget("a<b>c", 10, SANS, 10_000) == 5 * 10 * EM[SANS], "budget() must count '<' in plain text")
    check(budget("a<b>c", 10, SANS, 10_000, raw=True) == 2 * 10 * EM[SANS], "budget() must strip raw tags")
    check(attr('say "hi"') == "say &quot;hi&quot;", "attr() must escape double quotes")
    ET.fromstring(f'<svg xmlns="http://www.w3.org/2000/svg" aria-label="{attr(chr(34))}"/>')


if __name__ == "__main__":
    selftest()
    expected = {f"{n}-{v}.svg" for n in BUILDERS for v in PAL}
    for name, fn in BUILDERS.items():
        for variant, p in PAL.items():
            out = os.path.join(OUT, f"{name}-{variant}.svg")
            content = fn(p)
            try:
                ET.fromstring(content)          # malformed XML would ship as a silently broken image
            except ET.ParseError as e:
                raise SystemExit(f"MALFORMED: {name}-{variant}.svg — {e}")
            with open(out, "w", encoding="utf-8") as fh:
                fh.write(content)
            print(f"wrote {out} ({os.path.getsize(out)} bytes)")
    stale = sorted(set(os.listdir(OUT)) - expected)
    if stale:
        print("note: stale files in assets/ (not generated by this script):", ", ".join(stale))
