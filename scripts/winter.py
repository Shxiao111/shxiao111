"""Winter's counterparts to maple.py and sunlight.py: the snow crystal that falls across the footer (gen_hero.py)
and the plum blossom on the sprig in the bookshelf's vase (gen_cards.py), each drawn centred on the origin and
taking its colour from the <use>, like the maple leaf; and, where autumn has shafts of sun, frost growing in from
a card's edges (ice) and condensation misting it over (mist).  Standard library only.
"""
import math
import random

# pale blues and a lilac, sampled from the snow in pictures/winter/2.jpg: light enough for a night sky, deep enough
# to show on white paper
FLAKE_COLORS = ["#93abec", "#a9bdf4", "#8c9fe6", "#b9cbf9", "#a096e8"]
PLUM_COLORS = ["#d94a64", "#e8718a", "#c93350", "#f29bb0", "#dd5d78"]   # red plum, the flower that opens in snow
PLUM_STALK = (0, 0)           # a blossom sits on its twig by its middle


def flake_def(id_="leaf"):
    """A six-armed crystal, ~20 units across (a maple leaf's size), kept plain so it still reads when small: each arm
    one bar, pointed at the tip, with a single pair of barbs."""
    bar = "M-.7,0 L-.7,-8.8 L0,-10 L.7,-8.8 L.7,0 Z"
    barbs = "".join(f"M0,-5.2 l{s * 2.9:.1f},-2.7 l{s * .95:.2f},.9 l{-s * 2.9:.1f},2.9 Z" for s in (-1, 1))
    arms = "".join(f'<path transform="rotate({a})" d="{bar}{barbs}"/>' for a in range(0, 360, 60))
    return f'<g id="{id_}" stroke="none">{arms}<circle r="1.5"/></g>'


def plum_def(id_="leaf"):
    """A plum blossom, ~13 units across: five round petals, overlapping a little, round a ring of pale stamens."""
    petal = "M0,-.6 C-3.9,-1.2 -4.3,-6.4 0,-6.6 C4.3,-6.4 3.9,-1.2 0,-.6 Z"
    petals = "".join(f'<path transform="rotate({a})" d="{petal}"/>' for a in range(0, 360, 72))
    veil = "".join(f'<path transform="rotate({a})" d="{petal}" fill="url(#{id_}Tint)"/>' for a in range(0, 360, 72))
    stamens = "".join(f'<circle cx="{2.5 * math.sin(math.radians(a)):.2f}" cy="{-2.5 * math.cos(math.radians(a)):.2f}" r=".42"/>'
                      for a in range(18, 360, 36))
    return (f'<radialGradient id="{id_}Tint" gradientUnits="userSpaceOnUse" cx="0" cy="0" r="6.6">'
            f'<stop offset="0" stop-color="#5a0a20" stop-opacity=".35"/><stop offset=".45" stop-color="#fff" stop-opacity="0"/>'
            f'<stop offset="1" stop-color="#fff" stop-opacity=".3"/></radialGradient>'
            f'<g id="{id_}" stroke="none">{petals}{veil}<g fill="#ffe9a8">{stamens}<circle r=".9"/></g></g>')


def _tuft(rnd):
    """One spray of the frost's growing margin, as path data: a fan of fine pointed needles from the origin, growing
    toward +x and longest in the middle, each of the longer ones budding pairs of short spurs toward its tip."""
    d, n = [], rnd.randint(5, 8)
    spread = rnd.uniform(1.3, 2.2)
    for i in range(n):
        a = (i / (n - 1) - .5) * spread + rnd.uniform(-.1, .1)
        ln = rnd.uniform(17, 34) * (1 - .4 * abs(a))
        c, s = math.cos(a), math.sin(a)
        d.append(f"M{s:.1f},{-c:.1f}L{c * ln:.1f},{s * ln:.1f}L{-s:.1f},{c:.1f}Z")
        if ln > 15:
            for t in (.42, .58, .72, .85):
                bud = ln * .3 * (1.08 - t)
                d += [f"M{c * ln * t:.1f},{s * ln * t:.1f}l{math.cos(a + k) * bud:.1f},{math.sin(a + k) * bud:.1f}" for k in (-.75, .75)]
    return "".join(d)


def _drift(rnd, n, lo, hi, every=4):
    """n values wandering smoothly between lo and hi, turning about once in `every`."""
    knots = [rnd.uniform(lo, hi) for _ in range(n // every + 2)]
    out = []
    for i in range(n):
        k, f = divmod(i / every, 1)
        f = (1 - math.cos(f * math.pi)) / 2
        out.append(knots[int(k)] * (1 - f) + knots[int(k) + 1] * f)
    return out


def ice(uid, w, h, dark, seed, fade=None):
    """Frost built up round the edges of a pane, after pictures/winter/frost.jpg, in the blues of the ice in
    pictures/winter/2.jpg.  It is one body, not crystals drawn one by one: a crust of rime hard against the edge -
    thin along the top, deeper down the sides, deepest along the sill and banked into the corners, and nowhere the
    same depth for long - that thins as it spreads inward, dense and whole at the edge, mottled further in, crumbling
    to specks where it gives out; a fine grain, lit from the upper left, gives it its sparkle.  Along its growing
    margin it puts out sprays of fine needles, budding at their tips - thick and long in some stretches, sparse in
    others - and a few have taken hold just clear of it.  Behind it the glass is washed ice blue; the middle of the
    pane stays clear.  fade=(x0, x1): the frost thins to nothing from x0 to x1, where a picture takes over.
    Returns (defs, the wash, the frost) - two layers, so a card can keep something between the glass's colour and
    the frost on it; `uid` keeps ids unique in the document."""
    rnd = random.Random(seed)
    blue, line, frost_o, wash_o = (("#2c5aa0", "#dbe7ff", .66, .7) if dark else ("#8fbdf0", "#ffffff", 1, .65))
    pad, tc, bc = 60, 28, 38                  # the filters reach `pad` past the pane; how far the corners are banked
    # the crust's inner margin, clockwise from the top left: (how to place a point t along the edge at depth d,
    # where the edge starts and ends clear of its corners, the crust's usual depth there)
    margin = []
    for at, t0, t1, depth in ((lambda t, d: (t, d), tc, w - tc, 3), (lambda t, d: (w - d, t), tc, h - bc, 6),
                              (lambda t, d: (w - t, h - d), bc, w - bc, 12), (lambda t, d: (d, h - t), bc, h - tc, 6)):
        n = round((t1 - t0) / 12)
        margin += [at(t0 + (t1 - t0) * i / n, depth * m) for i, m in enumerate(_drift(rnd, n + 1, .2, 1.9))]
    crust = (f'<path fill="#f00" fill-rule="evenodd" d="M{-pad},{-pad}H{w + pad}V{h + pad}H{-pad}Z'
             f'M{"L".join(f"{x:.0f},{y:.0f}" for x, y in margin)}Z"/>')
    kinds = 6
    sprays = []
    for (x0, y0), (x1, y1), vigour in zip(margin, margin[1:] + margin[:1], _drift(rnd, len(margin), .6, 1.5, every=6)):
        inward = math.degrees(math.atan2(y1 - y0, x1 - x0)) + 90
        for _ in range(round(math.hypot(x1 - x0, y1 - y0) / 9 * vigour)):
            t = rnd.random()
            x, y = x0 + (x1 - x0) * t, y0 + (y1 - y0) * t
            grow = (.65 + .4 * y / h) * (.55 + .5 * vigour) * rnd.uniform(.75, 1.2)      # longer toward the sill
            # rooted a little way back in the crust, so no glass shows between; now and then a small one clear of it
            for out, size in ((-4 * grow, grow), (rnd.uniform(10, 22) * grow, grow * .5))[:1 + (rnd.random() < .1)]:
                ang = inward + rnd.uniform(-30, 30)
                px, py = x + math.cos(math.radians(inward)) * out, y + math.sin(math.radians(inward)) * out
                if not (fade and px > fade[1]):
                    sprays.append(f'<use href="#{uid}t{rnd.randrange(kinds)}" transform="translate({px:.0f} {py:.0f}) rotate({ang:.0f}) scale({size:.2f})"/>')
    box = f'x="{-pad}" y="{-pad}" width="{w + 2 * pad}" height="{h + 2 * pad}" filterUnits="userSpaceOnUse"'
    defs = ("".join(f'<path id="{uid}t{k}" d="{_tuft(rnd)}"/>' for k in range(kinds))
            + f'<filter id="{uid}W" {box}><feGaussianBlur stdDeviation="40"/></filter>'
            f'<filter id="{uid}R" {box} color-interpolation-filters="sRGB">'
            # the crust is drawn in red and the needles in blue, to tell them apart in here: only the crust is
            # softened and broken up, and then both take the one lit grain, as one body of frost
            f'<feColorMatrix type="matrix" values="0 0 0 0 0  0 0 0 0 0  0 0 0 0 0  1 0 0 1 -1"/>'
            f'<feGaussianBlur stdDeviation="6" result="soft"/>'
            f'<feTurbulence type="fractalNoise" baseFrequency=".045" numOctaves="5" seed="{seed}" result="n"/>'
            # the band plus the noise, less a threshold, then steepened: whole at the edge, mottled and then ragged
            # where it gives out
            f'<feComposite in="soft" in2="n" operator="arithmetic" k1="3" k2="1.6" k3="0" k4="-1"/>'
            f'<feColorMatrix type="matrix" values="0 0 0 0 1  0 0 0 0 1  0 0 0 0 1  0 0 0 2.6 -.1" result="crust"/>'
            f'<feColorMatrix in="SourceGraphic" type="matrix" values="0 0 0 0 1  0 0 0 0 1  0 0 0 0 1  0 0 1 1 -1"/>'
            f'<feComposite in2="crust" result="all"/>'
            f'<feTurbulence type="fractalNoise" baseFrequency=".55" numOctaves="2" seed="{seed + 1}"/>'
            f'<feDiffuseLighting surfaceScale="1.2" diffuseConstant="1.25" lighting-color="{line}">'
            f'<feDistantLight azimuth="225" elevation="58"/></feDiffuseLighting>'
            f'<feComposite in2="all" operator="in"/></filter>')
    attr = ""
    if fade:
        defs += (f'<linearGradient id="{uid}G" gradientUnits="userSpaceOnUse" x1="{fade[0]}" y1="0" x2="{fade[1]}" y2="0">'
                 f'<stop offset="0" stop-color="#fff"/><stop offset="1" stop-color="#fff" stop-opacity="0"/></linearGradient>'
                 f'<mask id="{uid}M"><rect width="{w}" height="{h}" fill="url(#{uid}G)"/></mask>')
        attr = f' mask="url(#{uid}M)"'
    return (defs,
            f'<g{attr}><rect width="{w}" height="{h}" fill="none" stroke="{blue}" stroke-width="230" opacity="{wash_o}" filter="url(#{uid}W)"/></g>',
            f'<g{attr} opacity="{frost_o}"><g filter="url(#{uid}R)"><g fill="#00f" stroke="#00f" stroke-width=".7" stroke-linecap="round" stroke-linejoin="round">'
            f'{"".join(sprays)}</g>{crust}</g></g>')


# the pane is clear for the first third of each half minute, so what is on the card can be read, then mists over
# and clears; it rests clear, so a reader who asked for less motion keeps a clear pane
MIST_CSS = "@keyframes mist{0%,34%,100%{opacity:0}54%,78%{opacity:1}}.mist{opacity:0;animation:mist 30s ease-in-out infinite}"


def mist(uid, content, w, h, dark, seed=1, delay=0):
    """Condensation on a cold pane, over a whole card: the glass mists over - everything behind it (the element
    with id `content`) goes soft and pale, a little less so toward the middle - beads with drops that are clear
    again inside, a few of which have run down and left their tracks, and clears.  Needs MIST_CSS.
    Returns (defs, body)."""
    rnd = random.Random(seed)
    drops = [(rnd.uniform(0, w), rnd.uniform(0, h), rnd.uniform(1.4, 4.6)) for _ in range(round(w * h / 8000))]
    tracks = []
    for _ in range(max(2, round(w / 300))):          # a drop that grew heavy: its wavering track, and it at the foot
        x, y, n = rnd.uniform(.05, .95) * w, rnd.uniform(-.05, .4) * h, rnd.randint(4, 8)
        d = f"M{x:.0f},{y:.0f}"
        for _ in range(n):
            x, y = x + rnd.uniform(-5, 5), y + rnd.uniform(18, 34)
            d += f" L{x:.0f},{y:.0f}"
        tracks.append(d)
        drops.append((x, y, rnd.uniform(4.5, 6)))
    beads = "".join(f'<circle cx="{x:.0f}" cy="{y:.0f}" r="{r:.1f}"/>' for x, y, r in drops)
    glints = "".join(f'<circle cx="{x - r * .3:.1f}" cy="{y - r * .35:.1f}" r="{r * .3:.1f}"/>' for x, y, r in drops if r > 2.5)
    rect = f'width="{w}" height="{h}"'
    defs = (f'<radialGradient id="{uid}G" gradientUnits="userSpaceOnUse" cx="{w / 2:.0f}" cy="{h / 2:.0f}" r="{w / 2:.0f}">'
            f'<stop offset="0" stop-color="#fff" stop-opacity=".72"/><stop offset="1" stop-color="#fff"/></radialGradient>'
            f'<mask id="{uid}M"><rect {rect} fill="url(#{uid}G)"/><g fill="#000">{beads}</g>'
            f'<path d="{" ".join(tracks)}" fill="none" stroke="#000" stroke-opacity=".45" stroke-width="2.6" stroke-linecap="round" stroke-linejoin="round"/></mask>'
            f'<filter id="{uid}B" x="0" y="0" {rect} filterUnits="userSpaceOnUse"><feGaussianBlur stdDeviation="4"/></filter>')
    return defs, (f'<g class="mist" style="animation-delay:{delay}s"><g mask="url(#{uid}M)"><use href="#{content}" filter="url(#{uid}B)"/>'
                  f'<rect {rect} fill="{"#dbe6ff" if dark else "#ffffff"}" opacity="{".3" if dark else ".45"}"/></g>'
                  f'<g fill="#fff" opacity="{".5" if dark else ".9"}">{glints}</g></g>')
