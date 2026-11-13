"""Spring's counterparts to maple.py: the cherry petal that falls across the footer (gen_hero.py) and drifts down
the works card (gen_cards.py, in every season but winter), and the cherry blossom on the sprig in the bookshelf's
vase (gen_cards.py), each drawn centred on the origin and taking its colour from the <use>, like the maple leaf.
Where autumn has shafts of sun, spring has the sun through new leaves (leaf_light).  Standard library only.
"""
import math

from sunlight import shifting_light
from winter import PLUM_STALK as BLOSSOM_STALK

# a petal as a plain shape, notched at the tip: what drifts down the works card, and the preface's little flower
BLOSSOM_PETAL = "M0,0 C-3.3,-2.4 -3.5,-6.6 -1.3,-8.2 L0,-6.9 L1.3,-8.2 C3.5,-6.6 3.3,-2.4 0,0 Z"
# cherry pinks, deep enough to show on white paper as well as on a night page
PETAL_COLORS = ["#f29bb5", "#f7b4c8", "#ea86a6", "#f9c6d6", "#e2779a"]


def petal_def(id_="leaf"):
    """One fallen cherry petal, ~16 units long (a maple leaf's size), its middle on the origin: broad, with a shallow
    notch at the tip, narrowing to its claw.  Over the <use>'s colour it is deeper pink at the claw and pales to the
    tip, is lit down one side and shaded down the other as a cupped petal is, and has a faint crease down its middle."""
    d = ("M0,8 C-1.4,5.8 -6.2,1.8 -6.1,-3 C-6,-6.3 -3.4,-8.3 -1.3,-7.7 Q-.4,-7.4 0,-6.6 Q.4,-7.4 1.3,-7.7 "
         "C3.4,-8.3 6,-6.3 6.1,-3 C6.2,1.8 1.4,5.8 0,8 Z")
    return (f'<linearGradient id="{id_}Len" gradientUnits="userSpaceOnUse" x1="0" y1="8" x2="0" y2="-8">'
            f'<stop offset="0" stop-color="#c2336c" stop-opacity=".55"/><stop offset=".4" stop-color="#c2336c" stop-opacity="0"/>'
            f'<stop offset=".55" stop-color="#fff" stop-opacity="0"/><stop offset="1" stop-color="#fff" stop-opacity=".5"/></linearGradient>'
            f'<linearGradient id="{id_}Cup" gradientUnits="userSpaceOnUse" x1="-6.1" y1="0" x2="6.1" y2="0">'
            f'<stop offset="0" stop-color="#fff" stop-opacity=".35"/><stop offset=".5" stop-color="#fff" stop-opacity="0"/>'
            f'<stop offset="1" stop-color="#7a1040" stop-opacity=".16"/></linearGradient>'
            f'<g id="{id_}" stroke="none"><path d="{d}"/><path d="{d}" fill="url(#{id_}Len)"/><path d="{d}" fill="url(#{id_}Cup)"/>'
            f'<path d="M0,6.8 Q.5,1 0,-4.6" fill="none" stroke="#a82a5e" stroke-opacity=".22" stroke-width=".3" stroke-linecap="round"/></g>')


def blossom_def(id_="leaf"):
    """A cherry blossom, ~14 units across: five petals, each notched at the tip, lapping over the next near the
    heart and standing clear of it at the tip; pale at the tips and deep rose at the heart, round a spray of fine
    stamens of uneven length with yellow anthers."""
    d = ("M0,-.4 C-1.2,-1.6 -3.7,-3.4 -3.6,-5.3 C-3.5,-6.8 -1.9,-7.4 -.8,-6.9 Q-.25,-6.65 0,-6.1 Q.25,-6.65 .8,-6.9 "
         "C1.9,-7.4 3.5,-6.8 3.6,-5.3 C3.7,-3.4 1.2,-1.6 0,-.4 Z")
    turns = [f'transform="rotate({a})"' for a in range(0, 360, 72)]
    # each petal: the <use>'s colour, the flower's tint (round the heart, so one gradient does all five), and a
    # shade down the edge the next petal laps over, which is what tells them apart
    petals = "".join(f'<path {t} d="{d}"/><path {t} d="{d}" fill="url(#{id_}Tint)"/><path {t} d="{d}" fill="url(#{id_}Lap)"/>'
                     for t in turns)
    tips = [(r * math.sin(math.radians(a)), -r * math.cos(math.radians(a)))
            for a, r in zip(range(8, 360, 30), (3.1, 2.1, 2.7) * 4)]
    stamens = ("".join(f'<path d="M0,0 L{x:.2f},{y:.2f}"/>' for x, y in tips)
               + "".join(f'<circle cx="{x:.2f}" cy="{y:.2f}" r=".38" fill="#ffd76a" stroke="none"/>' for x, y in tips))
    return (f'<radialGradient id="{id_}Tint" gradientUnits="userSpaceOnUse" cx="0" cy="0" r="7.4">'
            f'<stop offset="0" stop-color="#b3255f" stop-opacity=".6"/><stop offset=".38" stop-color="#b3255f" stop-opacity="0"/>'
            f'<stop offset=".5" stop-color="#fff" stop-opacity="0"/><stop offset="1" stop-color="#fff" stop-opacity=".5"/></radialGradient>'
            f'<linearGradient id="{id_}Lap" gradientUnits="userSpaceOnUse" x1="-3.7" y1="0" x2="3.7" y2="0">'
            f'<stop offset=".6" stop-color="#8a1648" stop-opacity="0"/><stop offset="1" stop-color="#8a1648" stop-opacity=".24"/></linearGradient>'
            f'<g id="{id_}" stroke="none">{petals}<g fill="none" stroke="#fff3f6" stroke-width=".26" stroke-linecap="round">{stamens}</g>'
            f'<circle r=".75" fill="#c93f73"/></g>')


def leaf_light(uid, w, h, dark, seed=1, clip=None, strength=1):
    """The sun through new leaves, on a card: flecks of light, gathered where the boughs let it through, that swell,
    run together and part again as the leaves stir.  Of sunlight.shifting_light's two fields the broad slow one is
    the boughs and the fine quick one the leaves, and only their high ground is lit.  Dark theme: pale green-gold
    light, screen-blended.  Light theme: new-leaf green, laid faintly over the paper.
    `strength`: how bright, beside the stats card's - more, to show against a bright ground.  Returns (defs, body)."""
    color, blend, o = ("#e6f5a8", "screen", .4) if dark else ("#a5d24a", "normal", .28)
    return shifting_light(uid, w, h, color, blend, o * strength, range(8, 17), (5, 12), clip,
                          (".006 .008", seed, (50, 16), 31), (".022 .026", seed + 7, (-30, 16), 13), mid=.62)
