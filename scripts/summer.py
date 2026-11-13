"""Summer's counterparts to maple.py and sunlight.py: the hibiscus petal that falls across the footer (gen_hero.py)
and the hibiscus on the sprig in the bookshelf's vase (gen_cards.py) - spring's petal, and the plum's five petals
grown broad; and, where autumn has shafts of sun, the light the sea throws up (water_light).  Standard library only.
"""
from spring import BLOSSOM_PETAL, BLOSSOM_STALK   # the petal's plain shape, and the same hold on its twig
from sunlight import shifting_light
from winter import plum_def

# the pink and the red of the two hibiscus in pictures/summer/1.jpg
PETAL_COLORS = ["#ee5f8a", "#f781a4", "#e1605f", "#f59ab4", "#d9485a"]


def petal_def(id_="leaf"):
    """One fallen petal, ~16 units long (a maple leaf's size), its middle on the origin."""
    return f'<g id="{id_}" stroke="none"><path transform="translate(0 8.2) scale(2)" d="{BLOSSOM_PETAL}"/></g>'


def hibiscus_def(id_="leaf"):
    """A hibiscus, ~15 units across: the plum's five petals, broad enough to lap over each other, round its stamens."""
    return plum_def(id_, petal="M0,-.6 C-5.6,-1.6 -5.8,-7 0,-7.6 C5.8,-7 5.6,-1.6 0,-.6 Z")


def water_light(uid, w, h, dark, seed=1, clip=None):
    """The light off the sea, playing over a card: a net of bright ripples that never holds its shape, drawn along
    the line where sunlight.shifting_light's two fields together sit at their middle height.  Dark theme: pale light,
    screen-blended.  Light theme: the sky's blue, laid faintly over the paper.  Returns (defs, body)."""
    color, blend, o = ("#d6f0ff", "screen", .5) if dark else ("#58aee8", "normal", .26)
    # a ripple is wider than it is tall, as on water seen from the shore
    return shifting_light(uid, w, h, color, blend, o, (8,), (1.1, 7), clip,
                          (".0042 .0074", seed, (70, 35), 47), (".0054 .0062", seed + 7, (-70, 24), 61))
