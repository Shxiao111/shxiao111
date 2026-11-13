#!/usr/bin/env python3
"""Regenerate assets/hero-*.svg, chapter-*.svg and footer-*.svg.

Usage:  python scripts/gen_hero.py      (needs fontTools + brotli for text measuring)
Fonts come from scripts/fonts.json (Google Fonts subsets), the art from scripts/art/<season>/{hero,footer}.jpg
(see prep_images.py; common.SEASON picks the season).  Edit the text block below to change the wording.
"""
import base64, io, math, os, random
from fontTools.pens.svgPathPen import SVGPathPen
from fontTools.ttLib import TTFont
from common import CALM, EASE, FONTS as fonts, SEASON, art, esc, fontface, smooth_fade, star_path as star, write_svg
from paper import RIM, punch
from sunlight import halo
if SEASON == "winter":       # what falls across the last page: maple leaves, snow, cherry or hibiscus petals
    from winter import FLAKE_COLORS as LEAF_COLORS, flake_def as leaf_def
elif SEASON == "spring":
    from spring import PETAL_COLORS as LEAF_COLORS, petal_def as leaf_def
elif SEASON == "summer":
    from summer import PETAL_COLORS as LEAF_COLORS, petal_def as leaf_def
else:
    from maple import LEAF_COLORS, leaf_def

# ---- text ----------------------------------------------------------------------------------------
NAME = "shxiao111"
GREETING = "hi there, i'm"
TAGLINE = "code, books, and quiet afternoons"
PILLS = ["BYR Docs", "computer science", "always reading"]
FOOT_LINE = "thanks for stopping by"
FOOT_SUB = "Shxiao  ·  Amano Tooko"
CHAPTERS = ["Chapter I · The Story So Far", "Chapter II · Stories Yet Unfolding", "Afterword"]   # " · " splits a title
# --------------------------------------------------------------------------------------------------

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(os.path.dirname(HERE), "assets")
hero_b64, foot_b64, tree_b64 = art("hero"), art("footer"), art("tree")   # only winter has a tree

_ttf = {}
def ttf(key):
    if key not in _ttf:
        _ttf[key] = TTFont(io.BytesIO(base64.b64decode(fonts[key]["b64"])))
    return _ttf[key]

def width(key, text, size, letter_spacing=0.0):
    f = ttf(key); cmap = f.getBestCmap(); hmtx = f["hmtx"]; upem = f["head"].unitsPerEm
    total = 0.0
    for ch in text:
        g = cmap.get(ord(ch))
        total += hmtx[g][0] / upem * size if g is not None else size * 0.6
        total += letter_spacing
    return total

# Palette pulled from the illustration: sun-bleached cream, window-light gold, olive frames.
AUTUMN = {
 "dark": dict(
   bg0="#121210", bg1="#1b180e", bg2="#0d1413",
   blob1="#c9a227", blob2="#f2e173", blob3="#2f6b62", blob4="#e8c872",
   blob1o=".34", blob2o=".14", blob3o=".34", blob4o=".12",
   name0="#ffffff", name1="#fbf0c2", name2="#e4cf5a", nameGlow="#c9a227", glowO=".55",
   over="#dcc964", tag="#f5ecc8",
   pillStroke="#b8a646", pillFill="#c9a227", pillFillO=".14", pillText="#f3e9b8",
   dust="#fff4c4", dustO="1", spark="#fff2b0",
   border="#e8d98a", borderO=".20", grainO=".045", cursor="#e4cf5a", imgBottom=".35",
   imgTint="0.97 0 0 0 0  0 0.93 0 0 0  0 0 0.84 0 0  0 0 0 1 0",
   footText="#fbf3d4", footMono="#b3a670",
   footGlow="#c2410c", footGlowO=".20", footToneR="0 .55 .92", footToneG="0 .45 .76", footToneB="0 .32 .55",
   chap2="#a0a741", mottle="#000", edge=RIM),
 "light": dict(
   bg0="#fffdf3", bg1="#faf4d9", bg2="#f0f2df",
   blob1="#f2e173", blob2="#fbe2a8", blob3="#d8e3a4", blob4="#f5e9a8",
   blob1o=".55", blob2o=".60", blob3o=".55", blob4o=".70",
   name0="#3b340c", name1="#6b5d12", name2="#a8841a", nameGlow="#f2e173", glowO=".75",
   over="#7a6b12", tag="#4f4516",
   pillStroke="#c7b04a", pillFill="#c9a227", pillFillO=".10", pillText="#5e5214",
   dust="#d9bd4a", dustO=".55", spark="#b8921c",
   border="#8a7a1a", borderO=".18", grainO=".03", cursor="#a8841a", imgBottom=".55",
   imgTint="1 0 0 0 0  0 1 0 0 0  0 0 1 0 0  0 0 0 1 0",
   footText="#3b340c", footMono="#857a45",
   footGlow="#fbd09a", footGlowO=".45", footToneR="0 1", footToneG="0 1", footToneB="0 1",
   chap2="#6f7a1a", mottle="#b08a4a", edge="#bfae7c"),
}

# Winter, from pictures/winter: festival-night violet, lantern pink, snow blue.
WINTER = {
 "dark": dict(
   bg0="#0f1020", bg1="#18152d", bg2="#0b1526",
   blob1="#7a5cc9", blob2="#f29bb5", blob3="#2a5a8f", blob4="#b9a4f2",
   blob1o=".34", blob2o=".14", blob3o=".34", blob4o=".12",
   name0="#ffffff", name1="#ebe6ff", name2="#b9a8ff", nameGlow="#8a6fe0", glowO=".55",
   over="#c4b6ff", tag="#ece8ff",
   pillStroke="#8f7fd6", pillFill="#8a6fe0", pillFillO=".16", pillText="#e2dcff",
   dust="#f4f0ff", dustO="1", spark="#ffe9f1",
   border="#b9b4f0", borderO=".22", grainO=".045", cursor="#b9a8ff", imgBottom=".35",
   imgTint="0.95 0 0 0 0  0 0.93 0 0 0  0 0 0.97 0 0  0 0 0 1 0",
   footText="#eef1ff", footMono="#8f9bc4",
   footGlow="#5b7fd0", footGlowO=".20", footToneR="0 1", footToneG="0 1", footToneB="0 1", footSpill=100,
   chap2="#7fb6e8", mottle="#000", edge=RIM,
   # the tree's own blue is lost on a night page, so there it is frosted: one pale colour, as dense as it was dark
   frost="0 0 0 0 .78  0 0 0 0 .84  0 0 0 0 1  -.36 -1.22 -.12 0 1.64", treeO=".8"),
 "light": dict(
   bg0="#fbfaff", bg1="#f1eefb", bg2="#eaf2fb",
   blob1="#d9cdf7", blob2="#fbd3df", blob3="#cfe3f7", blob4="#e6dcfb",
   blob1o=".55", blob2o=".60", blob3o=".55", blob4o=".70",
   name0="#2a2350", name1="#4a3d8f", name2="#7a5fc8", nameGlow="#cdbdf7", glowO=".75",
   over="#5d4fa3", tag="#3a3170",
   pillStroke="#a99ad9", pillFill="#7a5fc8", pillFillO=".10", pillText="#463a85",
   dust="#b9a6ea", dustO=".55", spark="#8b73d6",
   border="#6a5cb0", borderO=".18", grainO=".03", cursor="#7a5fc8", imgBottom=".55",
   imgTint="1 0 0 0 0  0 1 0 0 0  0 0 1 0 0  0 0 0 1 0",
   footText="#2a2350", footMono="#7c7aa5",
   footGlow="#cfe0fb", footGlowO=".45", footToneR="0 1", footToneG="0 1", footToneB="0 1",
   chap2="#4a86c8", mottle="#6a7ab0", edge="#b4b6d6",
   # on white paper the tree keeps its colours; only its white ground is let go
   frost="1 0 0 0 0  0 1 0 0 0  0 0 1 0 0  -.36 -1.22 -.12 0 1.64", treeO=".9"),
}

# Spring, from pictures/spring: new-leaf green on a wood at night or on white paper, cherry pink beside it.
SPRING = {
 "dark": dict(
   bg0="#0f1610", bg1="#171e0e", bg2="#0b1716",
   blob1="#6fa82a", blob2="#f2a2b8", blob3="#2a6f6a", blob4="#cfe07a",
   blob1o=".34", blob2o=".14", blob3o=".34", blob4o=".12",
   name0="#ffffff", name1="#eefad0", name2="#b4dc5a", nameGlow="#7fb52e", glowO=".55",
   over="#bfe070", tag="#eef7d6",
   pillStroke="#94b84e", pillFill="#7fb52e", pillFillO=".14", pillText="#e4f3bf",
   dust="#f3ffd0", dustO="1", spark="#ffe3ec",
   border="#cfe69a", borderO=".20", grainO=".045", cursor="#b4dc5a", imgBottom=".35",
   imgTint="0.93 0 0 0 0  0 0.95 0 0 0  0 0 0.88 0 0  0 0 0 1 0",
   footText="#f1f9dc", footMono="#9fb07a",
   footGlow="#5f9a2a", footGlowO=".20", footToneR="0 1", footToneG="0 1", footToneB="0 1", footSpill=180,
   chap2="#f29bb5", mottle="#000", edge=RIM),
 "light": dict(
   bg0="#fcfff5", bg1="#f3f9dc", bg2="#eaf5ea",
   blob1="#d6ec8c", blob2="#fbd3df", blob3="#c8e6d0", blob4="#e9f5a8",
   blob1o=".55", blob2o=".60", blob3o=".55", blob4o=".70",
   name0="#1f3210", name1="#3a5c14", name2="#6a9a1c", nameGlow="#d6ec8c", glowO=".75",
   over="#4d7412", tag="#324d14",
   pillStroke="#a3c452", pillFill="#7fb52e", pillFillO=".10", pillText="#3f5f12",
   dust="#b5d44a", dustO=".55", spark="#e0809a",
   border="#5f8a1a", borderO=".18", grainO=".03", cursor="#6a9a1c", imgBottom=".55",
   imgTint="1 0 0 0 0  0 1 0 0 0  0 0 1 0 0  0 0 0 1 0",
   footText="#1f3210", footMono="#7a8a55",
   footGlow="#e3f2a8", footGlowO=".45", footToneR="0 1", footToneG="0 1", footToneB="0 1",
   chap2="#d9627f", mottle="#7a9a4a", edge="#b9c98c"),
}

# Summer, from pictures/summer: the sky's blue over a sea at night or on white paper, hibiscus pink beside it.
SUMMER = {
 "dark": dict(
   bg0="#0c1622", bg1="#0f1d2e", bg2="#0a1a1f",
   blob1="#2a8fd6", blob2="#f2859b", blob3="#1f7a7a", blob4="#8fd0f2",
   blob1o=".34", blob2o=".14", blob3o=".34", blob4o=".12",
   name0="#ffffff", name1="#e3f4ff", name2="#7cc8f5", nameGlow="#3a9be0", glowO=".55",
   over="#8fd0f7", tag="#e6f4fd",
   pillStroke="#5a9fd0", pillFill="#3a9be0", pillFillO=".14", pillText="#d6ecfb",
   dust="#eaf7ff", dustO="1", spark="#fff3c4",
   border="#a9d6f5", borderO=".20", grainO=".045", cursor="#7cc8f5", imgBottom=".35",
   imgTint="0.92 0 0 0 0  0 0.94 0 0 0  0 0 0.97 0 0  0 0 0 1 0",
   footText="#eaf6ff", footMono="#8fb0c8",
   footGlow="#2a8fd6", footGlowO=".20", footToneR="0 1", footToneG="0 1", footToneB="0 1", footSpill=240,
   chap2="#f2859b", mottle="#000", edge=RIM),
 "light": dict(
   bg0="#fafdff", bg1="#e8f5fd", bg2="#e6f7f3",
   blob1="#bfe3fa", blob2="#fbd0d8", blob3="#c4ece4", blob4="#d9f0fc",
   blob1o=".55", blob2o=".60", blob3o=".55", blob4o=".70",
   name0="#0f2c47", name1="#1b5a8f", name2="#2f8fd6", nameGlow="#bfe3fa", glowO=".75",
   over="#1f6fae", tag="#17405f",
   pillStroke="#7fbce8", pillFill="#2f8fd6", pillFillO=".10", pillText="#1d5587",
   dust="#7fc4ee", dustO=".55", spark="#e3a41c",
   border="#2f7fbf", borderO=".18", grainO=".03", cursor="#2f8fd6", imgBottom=".55",
   imgTint="1 0 0 0 0  0 1 0 0 0  0 0 1 0 0  0 0 0 1 0",
   footText="#0f2c47", footMono="#6f8aa0",
   footGlow="#cfeafc", footGlowO=".45", footToneR="0 1", footToneG="0 1", footToneB="0 1",
   chap2="#d9506c", mottle="#5a8ab0", edge="#a9c4d8"),
}
# only autumn's footer picture is toned down for the dark theme (footToneR/G/B): the other seasons' keep their daylight
PAL = {"autumn": AUTUMN, "winter": WINTER, "spring": SPRING, "summer": SUMMER}[SEASON]
# where the footer's picture sits: its width (pinned to the left edge, 380 high) and how far back from its right
# edge it starts to fade - winter's girl is right of the middle of her picture, so it stays whole until past her
# face, and spring's and summer's are two people, the second on the right
FOOT_W, FOOT_FADE = {"autumn": (485, 330), "winter": (520, 125), "spring": (600, 130), "summer": (540, 130)}[SEASON]

FADE_OUT = smooth_fade()

W, H = 1200, 480
IMG_W = 560                       # hero.jpg is 1008x864 -> 560x480
TX = 612                          # text column starts just past the picture
TAG_SIZE, FOOT_SIZE = 42, 38      # Caveat runs small; this matches the letter height of the old 33/30px serif

# hero intro, played once per page load: type the greeting, then the name, then hand-write the tagline
TYPE_START = .5                   # s before the first keystroke
GREET_KEY, NAME_KEY = .065, .13   # s per keystroke (jittered a little so it doesn't feel mechanical)
LINE_PAUSE, WRITE_PAUSE = .35, .3
WRITE_SPEED = 230                 # px of handwriting per second

BASE_CSS = """
.over{font-family:'JetBrains Mono',monospace;font-weight:500;font-size:14px;letter-spacing:2.5px}
.name{font-family:'Outfit',sans-serif;font-weight:800;font-size:92px;letter-spacing:-2px}
.pill{font-family:'JetBrains Mono',monospace;font-weight:500;font-size:13px}
.foot-en{font-family:'Caveat',cursive;font-weight:600;font-size:%dpx}
""" % FOOT_SIZE + CALM

GRAIN = ('<filter id="grain" x="0" y="0" width="100%" height="100%"><feTurbulence type="fractalNoise" '
         'baseFrequency="0.85" numOctaves="2" stitchTiles="stitch"/><feColorMatrix type="saturate" values="0"/></filter>')

def dust(p, w, h, seed=7, n=18):
    """Motes drifting up and sideways through the window light: a few soft blurred ones, many small sharp ones."""
    rnd = random.Random(seed)
    soft, sharp = [], []
    for i in range(n):
        cx = rnd.uniform(20, w - 20); cy = rnd.uniform(20, h - 20)
        dx = rnd.uniform(-22, 30); dy = -rnd.uniform(16, 52)
        dur = rnd.uniform(10, 22); beg = -rnd.uniform(0, 14)
        anim = (f'<animateTransform attributeName="transform" type="translate" values="0 0;{dx:.0f} {dy:.0f};0 0" '
                f'dur="{dur:.1f}s" begin="{beg:.1f}s" repeatCount="indefinite"/>')
        if i % 3 == 0:
            r = rnd.uniform(5, 14); o = rnd.uniform(0.12, 0.40) * float(p["dustO"])
            soft.append(f'<circle cx="{cx:.0f}" cy="{cy:.0f}" r="{r:.1f}" opacity="{o:.2f}">{anim}</circle>')
        else:
            r = rnd.uniform(1.0, 2.6); o = rnd.uniform(0.35, 0.85) * float(p["dustO"])
            tw = rnd.uniform(2.5, 5.5)
            sharp.append(f'<circle cx="{cx:.0f}" cy="{cy:.0f}" r="{r:.1f}" opacity="{o:.2f}">{anim}'
                         f'<animate attributeName="fill-opacity" values="1;.25;1" dur="{tw:.1f}s" begin="{beg:.1f}s" repeatCount="indefinite"/></circle>')
    return (f'<g class="mo"><g filter="url(#blur9)" fill="{p["dust"]}">' + "".join(soft) + "</g>"
            f'<g fill="{p["dust"]}">' + "".join(sharp) + "</g></g>")

SPARKS = [(1128,76,9,3.1,0.0),(1150,300,8,2.6,0.8),(660,52,6,3.6,1.5),(1090,428,7,2.9,0.4),(498,64,7,3.3,2.1),(930,40,5,2.4,1.1),(1136,196,5,3.8,0.6)]
def sparkles(p):
    out = []
    for (x, y, s, dur, beg) in SPARKS:
        out.append(
            f'<g transform="translate({x} {y})"><path d="{star(s)}" fill="{p["spark"]}">'
            f'<animate attributeName="opacity" values="0.15;1;0.15" dur="{dur}s" begin="{beg}s" repeatCount="indefinite"/>'
            f'<animateTransform attributeName="transform" type="scale" values="0.7;1.15;0.7" dur="{dur}s" begin="{beg}s" repeatCount="indefinite"/>'
            f'</path></g>')
    return '<g class="mo">' + "\n".join(out) + "</g>"

def pills(p, x0=TX, y0=326, appear=None):
    """`appear`: fade the pills in one after another from this time (s); they stay visible without SMIL."""
    out = []; x = x0
    for i, t in enumerate(PILLS):
        w = width("jbmono", t, 13) + 28
        fade = ("" if appear is None else
                f'<set attributeName="opacity" to="0" begin="0s" fill="freeze"/>'
                f'<animate attributeName="opacity" from="0" to="1" begin="{appear + i * .15:.2f}s" dur=".5s" fill="freeze"/>')
        out.append(
            f'<g>{fade}<rect x="{x:.1f}" y="{y0}" width="{w:.1f}" height="28" rx="14" fill="{p["pillFill"]}" fill-opacity="{p["pillFillO"]}" '
            f'stroke="{p["pillStroke"]}" stroke-opacity=".75" stroke-width="1"/>'
            f'<text x="{x+14:.1f}" y="{y0+18.5}" class="pill" fill="{p["pillText"]}">{t}</text></g>')
        x += w + 10
    if x - 10 > W - 52:           # stay clear of the binder holes on the right edge
        raise SystemExit(f"pills overflow the banner by {x - 10 - (W - 52):.0f}px; shorten PILLS")
    return "\n".join(out)

def keystrokes(text, key, size, spacing, start, seed):
    """(time, advance so far) for each character, typed at a slightly uneven pace."""
    rnd = random.Random(seed)
    out, t = [], start
    for i in range(1, len(text) + 1):
        out.append((t, width(TYPE_FONTS[size], text[:i], size, letter_spacing=spacing)))
        t += key * rnd.uniform(.7, 1.4)
    return out

TYPE_FONTS = {14: "jbmono", 92: "outfit"}

def reveal(clip_id, x, y, h, full_w, strokes, pad_l, pad_r):
    """Clip that grows one character per keystroke.  Its base width shows the whole line, so a viewer
    without SMIL still sees the text; the set at 0s hides it, later sets outrank it as they begin."""
    sets = "".join(f'<set attributeName="width" to="{pad_l + w + pad_r:.1f}" begin="{t:.2f}s" fill="freeze"/>' for t, w in strokes)
    return (f'<clipPath id="{clip_id}"><rect x="{x - pad_l}" y="{y}" width="{pad_l + full_w + pad_r:.1f}" height="{h}">'
            f'<set attributeName="width" to="0" begin="0s" fill="freeze"/>{sets}</rect></clipPath>')

def handwriting(text, x, baseline, size, color, start=None):
    """Each Caveat glyph as an outline that is traced like a pen stroke, then inked in.
    Base attributes are the finished glyph (static fallback); the 0s sets blank it before the pen arrives.
    Without `start` the glyphs are simply written out: nobody is watching a title further down the page."""
    f = ttf("caveat"); glyphs = f.getGlyphSet(); cmap = f.getBestCmap(); hmtx = f["hmtx"]
    k = size / f["head"].unitsPerEm
    out, pen_x = [], x
    for ch in text:
        if ord(ch) not in cmap:
            raise SystemExit(f"{ch!r} in {text!r} is not in the Caveat subset in fonts.json")
        name = cmap[ord(ch)]
        pen = SVGPathPen(glyphs); glyphs[name].draw(pen); d = pen.getCommands()
        if d and start is None:
            out.append(f'<path transform="translate({pen_x:.1f} {baseline}) scale({k:.5f} {-k:.5f})" d="{d}" fill="{color}"/>')
        elif d:
            t = start + (pen_x - x) / WRITE_SPEED
            draw = max(.28, hmtx[name][0] * k / WRITE_SPEED * 2.2)
            out.append(
                f'<path transform="translate({pen_x:.1f} {baseline}) scale({k:.5f} {-k:.5f})" d="{d}" pathLength="1" '
                f'fill="{color}" stroke="{color}" stroke-opacity="0" stroke-width="{1.3 / k:.1f}" stroke-linecap="round" stroke-linejoin="round" stroke-dasharray="1 1">'
                f'<set attributeName="fill-opacity" to="0" begin="0s" fill="freeze"/>'
                f'<set attributeName="stroke-opacity" to="1" begin="0s" fill="freeze"/>'
                f'<set attributeName="stroke-dashoffset" to="1" begin="0s" fill="freeze"/>'
                f'<animate attributeName="stroke-dashoffset" from="1" to="0" begin="{t:.2f}s" dur="{draw:.2f}s" fill="freeze"/>'
                f'<animate attributeName="fill-opacity" from="0" to="1" begin="{t + draw * .55:.2f}s" dur=".35s" fill="freeze"/>'
                f'<animate attributeName="stroke-opacity" from="1" to="0" begin="{t + draw:.2f}s" dur=".3s" fill="freeze"/>'
                f'</path>')
        pen_x += hmtx[name][0] * k
    return "\n".join(out)

def hero(theme):
    p = PAL[theme]
    css = "".join(fontface(k) for k in ("outfit", "jbmono")) + BASE_CSS   # the tagline is drawn as glyph paths
    name_w = width("outfit", NAME, 92, letter_spacing=-2)
    cursor_x = TX + name_w + 12
    greet = keystrokes(GREETING, GREET_KEY, 14, 2.5, TYPE_START, seed=1)
    name_start = greet[-1][0] + LINE_PAUSE
    typed = keystrokes(NAME, NAME_KEY, 92, -2, name_start, seed=2)
    name_end = typed[-1][0]
    greet_w = width("jbmono", GREETING, 14, letter_spacing=2.5)
    # cursor: a thin bar on the greeting line, then the tall bar that follows the name and blinks once done;
    # its base attributes are the final resting place after the name
    cur = ('<set attributeName="x" to="{x}" begin="0s" fill="freeze"/><set attributeName="y" to="104" begin="0s" fill="freeze"/>'
           '<set attributeName="width" to="3" begin="0s" fill="freeze"/><set attributeName="height" to="17" begin="0s" fill="freeze"/>').format(x=TX)
    cur += "".join(f'<set attributeName="x" to="{TX + w + 1:.1f}" begin="{t:.2f}s" fill="freeze"/>' for t, w in greet)
    hop = name_start - LINE_PAUSE / 2
    cur += (f'<set attributeName="x" to="{TX}" begin="{hop:.2f}s" fill="freeze"/><set attributeName="y" to="160" begin="{hop:.2f}s" fill="freeze"/>'
            f'<set attributeName="width" to="7" begin="{hop:.2f}s" fill="freeze"/><set attributeName="height" to="64" begin="{hop:.2f}s" fill="freeze"/>')
    cur += "".join(f'<set attributeName="x" to="{TX + w + 12:.1f}" begin="{t:.2f}s" fill="freeze"/>' for t, w in typed)
    cur += f'<animate attributeName="opacity" values="1;1;0;0" keyTimes="0;.5;.5;1" dur="1.1s" begin="{name_end + .15:.2f}s" repeatCount="indefinite"/>'
    # halo: the big glow spills in from the girl's window at the edge of the picture, two smaller ones further out
    sun_defs, sun = halo("sunH", [(640, 140, 280, True), (1030, 380, 140, False), (900, 60, 90, False)], theme == "dark")
    clips = (reveal("typeGreet", TX, 96, 30, greet_w, greet, 4, 0)
             + reveal("typeName", TX, 128, 120, name_w, typed, 10, 0)
             + reveal("typeGlow", TX, 70, 220, name_w, typed, 60, 12))
    write_start = name_end + WRITE_PAUSE
    write_end = write_start + width("caveat", TAGLINE, TAG_SIZE) / WRITE_SPEED + .4
    if TX + width("caveat", TAGLINE, TAG_SIZE) > W - 52:
        raise SystemExit(f"TAGLINE is too wide for the banner ({width('caveat', TAGLINE, TAG_SIZE):.0f}px)")
    if cursor_x + 7 > W - 52:
        raise SystemExit(f"NAME is too wide for the banner ({name_w:.0f}px)")
    label = esc(f"{NAME} — {TAGLINE}")
    return f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}" role="img" aria-label="{label}">
<title>{label}</title>
<defs>
<style><![CDATA[{css}]]></style>
<clipPath id="card"><rect x="0" y="0" width="{W}" height="{H}" rx="28" ry="28"/></clipPath>
<linearGradient id="bg" x1="0" y1="0" x2="1" y2="1">
  <stop offset="0" stop-color="{p['bg1']}"/><stop offset=".45" stop-color="{p['bg0']}"/><stop offset="1" stop-color="{p['bg2']}"/>
</linearGradient>
<linearGradient id="nameGrad" x1="0" y1="0" x2="1" y2="0">
  <stop offset="0" stop-color="{p['name0']}"/><stop offset=".6" stop-color="{p['name1']}"/><stop offset="1" stop-color="{p['name2']}"/>
</linearGradient>
<linearGradient id="fadeH" gradientUnits="userSpaceOnUse" x1="{IMG_W-270}" y1="0" x2="{IMG_W}" y2="0">
{FADE_OUT}
</linearGradient>
<linearGradient id="fadeV" gradientUnits="userSpaceOnUse" x1="0" y1="330" x2="0" y2="{H}">
  <stop offset="0" stop-color="#fff"/><stop offset="1" stop-color="#fff" stop-opacity="{p['imgBottom']}"/>
</linearGradient>
<mask id="mV"><rect x="0" y="0" width="{IMG_W}" height="{H}" fill="url(#fadeV)"/></mask>
<mask id="mImg"><g mask="url(#mV)"><rect x="0" y="0" width="{IMG_W}" height="{H}" fill="url(#fadeH)"/></g></mask>
<filter id="blur70" x="-50%" y="-50%" width="200%" height="200%"><feGaussianBlur stdDeviation="45"/></filter>
<filter id="blur9" x="-50%" y="-50%" width="200%" height="200%"><feGaussianBlur stdDeviation="4.5"/></filter>
<filter id="blur18" x="-60%" y="-30%" width="220%" height="160%"><feGaussianBlur stdDeviation="18"/></filter>
<filter id="tint" color-interpolation-filters="sRGB"><feColorMatrix type="matrix" values="{p['imgTint']}"/></filter>
{GRAIN}
{clips}
{sun_defs}
</defs>
<g clip-path="url(#card)">
<rect width="{W}" height="{H}" fill="url(#bg)"/>
<g filter="url(#blur70)">
<ellipse cx="560" cy="120" rx="360" ry="200" fill="{p['blob1']}" opacity="{p['blob1o']}"><animate attributeName="cx" values="560;660;560" dur="17s" repeatCount="indefinite"/></ellipse>
<ellipse cx="880" cy="-10" rx="340" ry="150" fill="{p['blob2']}" opacity="{p['blob2o']}"><animate attributeName="cy" values="-10;50;-10" dur="21s" repeatCount="indefinite"/></ellipse>
<ellipse cx="1080" cy="470" rx="300" ry="140" fill="{p['blob3']}" opacity="{p['blob3o']}"/>
<ellipse cx="760" cy="300" rx="210" ry="220" fill="{p['blob4']}" opacity="{p['blob4o']}"><animate attributeName="rx" values="210;260;210" dur="14s" repeatCount="indefinite"/></ellipse>
</g>
<image href="data:image/jpeg;base64,{hero_b64}" x="0" y="0" width="{IMG_W}" height="{H}" preserveAspectRatio="xMidYMid slice" mask="url(#mImg)" filter="url(#tint)"/>
{sun}
{dust(p, W, H)}
{sparkles(p)}
<rect width="{W}" height="{H}" filter="url(#grain)" opacity="{p['grainO']}"/>
<text x="{TX}" y="118" class="over" fill="{p['over']}" clip-path="url(#typeGreet)">{GREETING}</text>
<g clip-path="url(#typeGlow)"><text x="{TX}" y="222" class="name" fill="{p['nameGlow']}" opacity="{p['glowO']}" filter="url(#blur18)">{NAME}</text></g>
<text x="{TX}" y="222" class="name" fill="url(#nameGrad)" clip-path="url(#typeName)">{NAME}</text>
<rect class="mo" x="{cursor_x:.1f}" y="160" width="7" height="64" rx="2" fill="{p['cursor']}">{cur}</rect>
{handwriting(TAGLINE, TX, 282, TAG_SIZE, p['tag'], write_start)}
{pills(p, appear=write_end)}
<rect x="1" y="1" width="{W-2}" height="{H-2}" rx="27" fill="none" stroke="{p['border']}" stroke-opacity="{p['borderO']}" stroke-width="1.5"/>
</g>
</svg>
'''

def chapter(theme, title):
    """A chapter opener: the title hand-written between two rules that fade out to the page's edges, a slowly
    turning star at the inner end of each.  The Caveat subset has no middle dot, so the one between the parts of a
    title is drawn; the part before it is inked in the accent colour."""
    c1, c2 = PAL[theme]["name2"], PAL[theme]["chap2"]
    size, base, mid, dot_gap, pad = 44, 47, 34, 34, 36
    parts = title.split(" · ")
    w = sum(width("caveat", t, size) for t in parts) + dot_gap * (len(parts) - 1)
    x0, x1 = 600 - w / 2 - pad, 600 + w / 2 + pad
    if x0 < 140:
        raise SystemExit(f"{title!r} is too wide for a chapter opener ({w:.0f}px)")
    ink, x = [], x0 + pad
    for k, t in enumerate(parts):
        if k:
            ink.append(f'<circle cx="{x - dot_gap / 2:.1f}" cy="{base - 11}" r="2.6" fill="{c1}"/>')
        ink.append(handwriting(t, x, base, size, PAL[theme]["tag"] if k == len(parts) - 1 else c1))
        x += width("caveat", t, size) + dot_gap
    label, ink = esc(title), "\n".join(ink)
    # the gradients are laid out in user space: a horizontal line's bounding box has no height, and a gradient sized
    # to such a box isn't painted at all, so the line would vanish
    return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1200 68" width="1200" height="68" role="img" aria-label="{label}">
<title>{label}</title>
<defs>
<style>@keyframes turn{{to{{transform:rotate(90deg)}}}}.s{{transform-box:fill-box;transform-origin:center;animation:turn 6s linear infinite}}{CALM}</style>
<linearGradient id="l" gradientUnits="userSpaceOnUse" x1="60" y1="0" x2="{x0:.1f}" y2="0"><stop offset="0" stop-color="{c1}" stop-opacity="0"/><stop offset="1" stop-color="{c1}" stop-opacity=".9"/></linearGradient>
<linearGradient id="r" gradientUnits="userSpaceOnUse" x1="{x1:.1f}" y1="0" x2="1140" y2="0"><stop offset="0" stop-color="{c1}" stop-opacity=".9"/><stop offset="1" stop-color="{c2}" stop-opacity="0"/></linearGradient>
</defs>
<line x1="60" y1="{mid}" x2="{x0 - 12:.1f}" y2="{mid}" stroke="url(#l)" stroke-width="1.5"/>
<line x1="{x1 + 12:.1f}" y1="{mid}" x2="1140" y2="{mid}" stroke="url(#r)" stroke-width="1.5"/>
<g transform="translate({x0:.1f} {mid})"><path class="s" d="{star(7)}" fill="{c1}"/></g>
<g transform="translate({x1:.1f} {mid})"><path class="s" d="{star(7)}" fill="{c1}"/></g>
{ink}
</svg>
"""

SWING = f"{EASE};{EASE}"          # keySplines for a there-and-back animation (values a;b;a)

def leaves(w, h, seed=21):
    """Maple leaves (in winter snow crystals, in spring and summer petals) drifting down: each one falls, sways side to side, rocks with the
    sway and flips over.
    Three depths - small faint far leaves, mid leaves, and a few big soft-focus ones up close."""
    rnd = random.Random(seed)
    layers = ["far"] * 3 + ["mid"] * 7 + ["near"] * 2
    rnd.shuffle(layers)
    out = []
    for i, layer in enumerate(layers):
        x = (i + rnd.uniform(.15, .85)) / len(layers) * (w + 60) - 30
        if layer == "far":
            s, o, fall = rnd.uniform(.85, 1.1), rnd.uniform(.45, .6), rnd.uniform(22, 30)
        elif layer == "mid":
            s, o, fall = rnd.uniform(1.5, 2.0), rnd.uniform(.85, 1), rnd.uniform(15, 21)
        else:
            s, o, fall = rnd.uniform(2.7, 3.3), rnd.uniform(.75, .9), rnd.uniform(11, 15)
        blur = ' filter="url(#leafBlur)"' if layer == "near" else ""
        sway = rnd.uniform(18, 46) * s ** .5
        sdur = rnd.uniform(4.5, 7.5); flip = rnd.uniform(2.6, 4.8)
        tilt = rnd.uniform(25, 50); spin = rnd.uniform(0, 360)
        fbeg = -rnd.uniform(0, fall); sbeg = -rnd.uniform(0, sdur)
        c = rnd.choice(LEAF_COLORS)
        swing = f'keyTimes="0;.5;1" calcMode="spline" keySplines="{SWING}" dur="{sdur:.1f}s" begin="{sbeg:.1f}s" repeatCount="indefinite"'
        out.append(
            f'<g transform="translate({x:.0f} 0)" opacity="{o:.2f}"{blur}>'
            f'<g><animateTransform attributeName="transform" type="translate" values="0 {-14*s:.0f};0 {h+14*s:.0f}" dur="{fall:.1f}s" begin="{fbeg:.1f}s" repeatCount="indefinite"/>'
            f'<g><animateTransform attributeName="transform" type="translate" values="{-sway:.0f} 0;{sway:.0f} 0;{-sway:.0f} 0" {swing}/>'
            f'<g><animateTransform attributeName="transform" type="rotate" values="{spin-tilt:.0f};{spin+tilt:.0f};{spin-tilt:.0f}" {swing}/>'
            f'<g transform="scale({s:.2f})"><use href="#leaf" fill="{c}">'
            f'<animateTransform attributeName="transform" type="scale" values="1 1;.25 1;1 1" keyTimes="0;.5;1" calcMode="spline" keySplines="{SWING}" dur="{flip:.1f}s" begin="{fbeg:.1f}s" repeatCount="indefinite"/>'
            f'</use></g></g></g></g></g>')
    return '<g class="mo">' + "\n".join(out) + "</g>"

# the rip down the last page's right edge, traced from a sketch: (how far in from the rightmost point, px of the
# sketch; how far down, 0-1).  It starts in from the top corner, cuts back further, bellies out, bites in sharply
# halfway down, eases out again and runs down to a point at the foot.
RIP = [(155, 0), (170, .036), (187, .07), (182, .125), (185, .164), (158, .246), (130, .309), (115, .364),
       (120, .414), (142, .474), (178, .559), (164, .588), (142, .651), (130, .717), (132, .803), (108, .855),
       (70, .928), (0, 1)]

def paper_sheet(x0, y0, x1, y1, depth=.38, seed=101):
    """The last page as a loose sheet, torn out of the book: its top, foot and outer edge are cut - square corners,
    straight to the eye but faintly uneven - and its right edge, where a right-opening book is bound, is ripped all
    the way down along RIP (scaled `depth` px per sketch px across, to the sheet's height down), finely frayed;
    along the rip the paper split in its thickness, leaving a pale strip of core of uneven width.
    Returns (outline, the rip and the inner edge of its core as polylines, the core as a polygon)."""
    rnd = random.Random(seed)

    def cut(a, b, step=18, amp=.6):   # a trimmed edge from a up to (not including) b
        n = max(1, round(math.dist(a, b) / step))
        return [(a[0] + (b[0] - a[0]) * k / n + (rnd.uniform(-amp, amp) if k else 0),
                 a[1] + (b[1] - a[1]) * k / n + (rnd.uniform(-amp, amp) if k else 0)) for k in range(n)]

    # walk the sketch's segments a few px at a time; the rip frays finely along the way, and now and then a few
    # fibres pull away in a small nick
    rip = []
    for (u0, v0), (u1, v1) in zip(RIP, RIP[1:]):
        a, b = (x1 - u0 * depth, y0 + v0 * (y1 - y0)), (x1 - u1 * depth, y0 + v1 * (y1 - y0))
        k = 0.0
        while k < 1:
            y = a[1] + (b[1] - a[1]) * k
            fray = (1.5 * math.sin((y - y0) / (y1 - y0) * 23) + rnd.uniform(-2, 2)
                    + (rnd.uniform(3, 7) if rnd.random() < .08 else 0)) if rip else 0
            rip.append((a[0] + (b[0] - a[0]) * k - fray, y))
            k += rnd.uniform(2.5, 6) / max(math.dist(a, b), 1)
    rip.append((x1, y1))
    inner, core = [], 3.0
    for x, y in rip:
        core = max(1, min(7, core + rnd.uniform(-1.2, 1.2)))
        inner.append((x - core - rnd.uniform(0, 1.2), y))
    pts = cut((x0, y0), rip[0]) + rip + cut(rip[-1], (x0, y1))[1:] + cut((x0, y1), (x0, y0))
    line = lambda ps: " ".join(f"{x:.1f},{y:.1f}" for x, y in ps)
    outline = "M" + " L".join(f"{x:.1f},{y:.1f}" for x, y in pts) + " Z"
    return outline, line(rip), line(inner), line(rip + inner[::-1])

# the lights on the tree that twinkle: (x, y) as fractions of tree.jpg, picked off its brightest bulbs
TREE_LIGHTS = [(.50, .31), (.53, .41), (.46, .52), (.36, .60), (.50, .66), (.57, .69), (.77, .55), (.76, .77),
               (.60, .47), (.33, .82), (.54, .86), (.88, .38), (.21, .70), (.70, .90)]

def lit_tree(p, x, foot, w=250, h=318):
    """Winter's extra picture (tree.jpg, 500x636): the tree hung with lights, growing up from the foot of the last
    page between the picture and the words.  Its white ground is turned to nothing (alpha from darkness, the
    `frost` matrix), its tip fades in under where the passage above it was cut off, and its bulbs twinkle."""
    y = foot - h
    defs = (f'<filter id="frost" color-interpolation-filters="sRGB"><feColorMatrix type="matrix" values="{p["frost"]}"/></filter>'
            f'<linearGradient id="treeTop" gradientUnits="userSpaceOnUse" x1="0" y1="{y}" x2="0" y2="{y + 46}">{smooth_fade(fade_in=True)}</linearGradient>'
            f'<mask id="treeMask"><rect x="{x}" y="{y}" width="{w}" height="{h}" fill="url(#treeTop)"/></mask>')
    rnd = random.Random(5)
    lights = "".join(
        f'<g transform="translate({x + fx * w:.0f} {y + fy * h:.0f})"><path d="{star(rnd.uniform(3, 5.5))}" fill="{p["spark"]}">'
        f'<animate attributeName="opacity" values="0;1;0" dur="{rnd.uniform(2.4, 4.2):.1f}s" begin="{-rnd.uniform(0, 4):.1f}s" repeatCount="indefinite"/>'
        f'</path></g>' for fx, fy in TREE_LIGHTS)
    return defs, (f'<g mask="url(#treeMask)" opacity="{p["treeO"]}"><image href="data:image/jpeg;base64,{tree_b64}" x="{x}" y="{y}" '
                  f'width="{w}" height="{h}" filter="url(#frost)"/></g><g class="mo">{lights}</g>')

def footer(theme):
    p = PAL[theme]
    dark = theme == "dark"
    css = "".join(fontface(k) for k in ("caveat", "jbmono")) + BASE_CSS
    FW, FH = 1200, 380
    IW = FOOT_W                   # footer.jpg at half its size, pinned to the left edge
    TR = FW - 100                 # the text's right edge, clear of the rip
    # the sheet sits a few px in from the lower right, leaving room for the shadow it casts
    outline, rip, inner, core = paper_sheet(1, 1, FW - 7, FH - 8)
    # the rip: the paper's pale core along it, its frayed edge, and a faint shadow where the core lifts
    rim, coreO, rimO, shadeO = (RIM, ".16", ".35", ".4") if dark else ("#ffffff", ".85", "1", ".12")
    # the paper itself: its fine tooth lit from the upper left, a faint mottle, and the cut edge; the picture is
    # printed over the tooth, so it stays sharp and the paper only shows through where it fades out
    toothO, mottleO = (".22", ".14") if dark else (".16", ".07")
    edgeO, dropO = (".14", ".6") if dark else (".7", ".22")
    mottle, edge = p["mottle"], p["edge"]
    foot_label = esc(FOOT_LINE)
    tree_defs, tree = lit_tree(p, 508, FH) if tree_b64 else ("", "")
    # footSpill: a daylit picture ends hard against a night page, so its white paper carries on that many px past
    # its right edge, giving out slowly - the picture fades into paper, and only the paper into the dark.  It stops
    # short of the words; and winter's is shorter still, gone before the frosted tree, which is as pale as it is
    spill = (f'<linearGradient id="fspill" gradientUnits="userSpaceOnUse" x1="{IW - FOOT_FADE}" y1="0" x2="{IW + p["footSpill"]}" y2="0">{FADE_OUT}</linearGradient>',
             f'<rect width="{IW + p["footSpill"]}" height="{FH}" fill="url(#fspill)"/>') if "footSpill" in p else ("", "")
    return f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {FW} {FH}" width="{FW}" height="{FH}" role="img" aria-label="{foot_label}">
<title>{foot_label}</title>
<defs>
<style><![CDATA[{css}]]></style>
<clipPath id="fcard"><path d="{outline}"/></clipPath>
<linearGradient id="fbg" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="{p['bg1']}"/><stop offset=".5" stop-color="{p['bg0']}"/><stop offset="1" stop-color="{p['bg2']}"/></linearGradient>
<linearGradient id="ffade" gradientUnits="userSpaceOnUse" x1="{IW-FOOT_FADE}" y1="0" x2="{IW}" y2="0">
{FADE_OUT}
</linearGradient>
<mask id="fmask"><rect x="0" y="0" width="{IW}" height="{FH}" fill="url(#ffade)"/></mask>
<filter id="blur70" x="-50%" y="-50%" width="200%" height="200%"><feGaussianBlur stdDeviation="45"/></filter>
<filter id="leafBlur" x="-50%" y="-50%" width="200%" height="200%"><feGaussianBlur stdDeviation="2"/></filter>
<filter id="fibre" x="-5%" y="-50%" width="110%" height="200%"><feGaussianBlur stdDeviation=".7"/></filter>
<filter id="drop" x="-5%" y="-10%" width="110%" height="130%"><feGaussianBlur stdDeviation="3.5"/></filter>
<filter id="tooth" x="0" y="0" width="100%" height="100%">
  <feTurbulence type="fractalNoise" baseFrequency=".5" numOctaves="2" seed="7"/>
  <feDiffuseLighting surfaceScale="1.1" lighting-color="#fff" result="lit"><feDistantLight azimuth="225" elevation="50"/></feDiffuseLighting>
  <feColorMatrix in="lit" values="0 0 0 0 0  0 0 0 0 0  0 0 0 0 0  -3 0 0 0 2.3" result="shade"/>
  <feColorMatrix in="lit" values="0 0 0 0 1  0 0 0 0 1  0 0 0 0 1  3 0 0 0 -2.3" result="light"/>
  <feMerge><feMergeNode in="shade"/><feMergeNode in="light"/></feMerge>
</filter>
<filter id="mottle" x="0" y="0" width="100%" height="100%">
  <feTurbulence type="fractalNoise" baseFrequency=".008" numOctaves="2" seed="11"/>
  <feColorMatrix values="0 0 0 0 0  0 0 0 0 0  0 0 0 0 0  2 0 0 0 -.9"/>
</filter>
<filter id="ftone" color-interpolation-filters="sRGB"><feComponentTransfer>
  <feFuncR type="table" tableValues="{p['footToneR']}"/><feFuncG type="table" tableValues="{p['footToneG']}"/><feFuncB type="table" tableValues="{p['footToneB']}"/>
</feComponentTransfer></filter>
{leaf_def()}{tree_defs}{spill[0]}
{GRAIN}
</defs>
<path d="{outline}" transform="translate(3 5)" fill="#000" opacity="{dropO}" filter="url(#drop)"/>
<g clip-path="url(#fcard)">
<rect width="{FW}" height="{FH}" fill="url(#fbg)"/>
<g filter="url(#blur70)">
<ellipse cx="470" cy="230" rx="240" ry="190" fill="{p['footGlow']}" opacity="{p['footGlowO']}"><animate attributeName="rx" values="260;310;260" dur="16s" repeatCount="indefinite"/></ellipse>
<ellipse cx="900" cy="10" rx="320" ry="110" fill="{p['blob2']}" opacity="{p['blob2o']}"/>
<ellipse cx="1110" cy="390" rx="300" ry="140" fill="{p['blob3']}" opacity="{p['blob3o']}"><animate attributeName="cy" values="390;350;390" dur="19s" repeatCount="indefinite"/></ellipse>
</g>{spill[1]}
<rect width="{FW}" height="{FH}" fill="{mottle}" opacity="{mottleO}" filter="url(#mottle)"/>
<rect width="{FW}" height="{FH}" opacity="{toothO}" filter="url(#tooth)"/>
<image href="data:image/jpeg;base64,{foot_b64}" x="0" y="0" width="{IW}" height="{FH}" preserveAspectRatio="xMidYMid slice" mask="url(#fmask)" filter="url(#ftone)"/>{tree}
{leaves(FW, FH)}
<rect width="{FW}" height="{FH}" filter="url(#grain)" opacity="{p['grainO']}"/>
<text x="{TR}" y="196" text-anchor="end" class="foot-en" fill="{p['footText']}">{FOOT_LINE}</text>
<line x1="{TR-180}" y1="248" x2="{TR}" y2="248" stroke="{p['border']}" stroke-opacity=".5"/>
<text x="{TR}" y="278" text-anchor="end" class="over" fill="{p['footMono']}">{FOOT_SUB}</text>
<path d="{outline}" fill="none" stroke="{edge}" stroke-opacity="{edgeO}" stroke-width="1.6"/>
<polygon points="{core}" fill="{rim}" fill-opacity="{coreO}" filter="url(#fibre)"/>
<polyline points="{inner}" fill="none" stroke="#000" stroke-opacity="{shadeO}" stroke-width="1" stroke-linejoin="round"/>
<polyline points="{rip}" fill="none" stroke="{rim}" stroke-opacity="{rimO}" stroke-width="3" stroke-linejoin="round" filter="url(#fibre)"/>
</g>
</svg>
'''


def main():
    os.makedirs(OUT, exist_ok=True)
    for theme in ("dark", "light"):
        # the hero's art sits on the left, so its binder holes go down the right edge; a chapter opener is a rule,
        # and the footer is the last page, torn loose from the binder
        pages = [("hero", punch(hero(theme), theme == "dark", side="right")), ("footer", footer(theme))]
        pages += [(f"chapter-{i}", chapter(theme, t)) for i, t in enumerate(CHAPTERS, 1)]
        for name, svg in pages:
            path = os.path.join(OUT, f"{name}-{theme}.svg")
            write_svg(path, svg)
            print(f"{path}: {os.path.getsize(path)/1024:.0f} KB")


if __name__ == "__main__":
    main()
