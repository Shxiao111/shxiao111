"""Spring's counterparts to maple.py: the cherry petal that falls across the footer (gen_hero.py) and drifts down
the works card (gen_cards.py, in every season but winter), and the cherry blossom on the sprig in the bookshelf's
vase (gen_cards.py), each drawn centred on the origin and taking its colour from the <use>, like the maple leaf.
Where autumn has shafts of sun, spring has the sun through new leaves (leaf_light).  Standard library only.
"""
from sunlight import shifting_light
from winter import PLUM_STALK as BLOSSOM_STALK, plum_def

BLOSSOM_PETAL = "M0,0 C-3.3,-2.4 -3.5,-6.6 -1.3,-8.2 L0,-6.9 L1.3,-8.2 C3.5,-6.6 3.3,-2.4 0,0 Z"   # notched at the tip
# cherry pinks, deep enough to show on white paper as well as on a night page
PETAL_COLORS = ["#f29bb5", "#f7b4c8", "#ea86a6", "#f9c6d6", "#e2779a"]


def petal_def(id_="leaf"):
    """One fallen petal, ~16 units long (a maple leaf's size), its middle on the origin."""
    return f'<g id="{id_}" stroke="none"><path transform="translate(0 8.2) scale(2)" d="{BLOSSOM_PETAL}"/></g>'


def blossom_def(id_="leaf"):
    """A cherry blossom, ~13 units across: the plum's five petals round its ring of stamens, each notched at the tip."""
    return plum_def(id_, petal="M0,-.6 C-3.9,-1.2 -4.3,-6.2 -1.2,-6.9 L0,-5.8 L1.2,-6.9 C4.3,-6.2 3.9,-1.2 0,-.6 Z")


def leaf_light(uid, w, h, dark, seed=1, clip=None, strength=1):
    """The sun through new leaves, on a card: flecks of light, gathered where the boughs let it through, that swell,
    run together and part again as the leaves stir.  Of sunlight.shifting_light's two fields the broad slow one is
    the boughs and the fine quick one the leaves, and only their high ground is lit.  Dark theme: pale green-gold
    light, screen-blended.  Light theme: new-leaf green, laid faintly over the paper.
    `strength`: how bright, beside the stats card's - more, to show against a bright ground.  Returns (defs, body)."""
    color, blend, o = ("#e6f5a8", "screen", .4) if dark else ("#a5d24a", "normal", .28)
    return shifting_light(uid, w, h, color, blend, o * strength, range(8, 17), (5, 12), clip,
                          (".006 .008", seed, (50, 16), 31), (".022 .026", seed + 7, (-30, 16), 13), mid=.62)
