"""Spring's counterparts to maple.py: the cherry petal that falls across the footer (gen_hero.py) and drifts down
the works card (gen_cards.py, in every season but winter), and the cherry blossom on the sprig in the bookshelf's
vase (gen_cards.py), each drawn centred on the origin and taking its colour from the <use>, like the maple leaf.
Spring keeps autumn's shafts of sun, in its own colour (sunlight.py).  Standard library only.
"""
from winter import PLUM_STALK as BLOSSOM_STALK, plum_def

BLOSSOM_PETAL = "M0,0 C-3.3,-2.4 -3.5,-6.6 -1.3,-8.2 L0,-6.9 L1.3,-8.2 C3.5,-6.6 3.3,-2.4 0,0 Z"   # notched at the tip
# the pinks of the tree in pictures/spring/extra.jpg, deepened: there they are a breath off white, and these have
# to show on white paper as well as on a night page
PETAL_COLORS = ["#f29bb5", "#f7b4c8", "#ea86a6", "#f9c6d6", "#e2779a"]


def petal_def(id_="leaf"):
    """One fallen petal, ~16 units long (a maple leaf's size), its middle on the origin."""
    return f'<g id="{id_}" stroke="none"><path transform="translate(0 8.2) scale(2)" d="{BLOSSOM_PETAL}"/></g>'


def blossom_def(id_="leaf"):
    """A cherry blossom, ~13 units across: the plum's five petals round its ring of stamens, each notched at the tip."""
    return plum_def(id_, petal="M0,-.6 C-3.9,-1.2 -4.3,-6.2 -1.2,-6.9 L0,-5.8 L1.2,-6.9 C4.3,-6.2 3.9,-1.2 0,-.6 Z")
