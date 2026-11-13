"""Summer's counterparts to maple.py and sunlight.py: the hibiscus petal that falls across the footer (gen_hero.py)
and the hibiscus on the sprig in the bookshelf's vase (gen_cards.py) - spring's petal, and the plum's five petals
grown broad; and, where autumn has shafts of sun, the light the sea throws up (water_light).  Standard library only.
"""
from common import EASE
from spring import BLOSSOM_STALK, petal_def   # the same petal, and the same hold on its twig
from winter import plum_def

# the pink and the red of the two hibiscus in pictures/summer/1.jpg
PETAL_COLORS = ["#ee5f8a", "#f781a4", "#e1605f", "#f59ab4", "#d9485a"]


def hibiscus_def(id_="leaf"):
    """A hibiscus, ~15 units across: the plum's five petals, broad enough to lap over each other, round its stamens."""
    return plum_def(id_, petal="M0,-.6 C-5.6,-1.6 -5.8,-7 0,-7.6 C5.8,-7 5.6,-1.6 0,-.6 Z")


def water_light(uid, w, h, dark, seed=1, clip=None):
    """The light off the sea, playing over a card: a net of bright ripples that never holds its shape.  Two fields
    of soft noise slide across each other, and the light is drawn along the line where the two of them together sit
    at their middle height - a line that wanders, joins up and breaks as they slide.  Each ripple has a soft glow
    round it.  Dark theme: pale light, screen-blended.  Light theme: the sky's blue, laid faintly over the paper.
    `clip`: a clipPath id, to keep the light off a card's rounded corners.
    Returns (defs, body), like sunlight.light_rays; `uid` keeps ids unique in the document."""
    pad = 70                                  # how far the fields slide; they are drawn that much past the card
    color, blend, o = ("#d6f0ff", "screen", .5) if dark else ("#58aee8", "normal", .26)
    r, g, b = (int(color[i:i + 2], 16) / 255 for i in (1, 3, 5))
    box = f'x="{-pad}" y="{-pad}" width="{w + 2 * pad}" height="{h + 2 * pad}"'
    # a ripple is wider than it is tall, as on water seen from the shore
    fields = [(f"{uid}A", ".0042 .0074", seed, (pad, pad * .5), 47), (f"{uid}B", ".0054 .0062", seed + 7, (-pad, pad * .35), 61)]
    defs = "".join(
        f'<filter id="{fid}" {box} filterUnits="userSpaceOnUse" color-interpolation-filters="sRGB">'
        f'<feTurbulence type="fractalNoise" baseFrequency="{freq}" numOctaves="2" seed="{s}"/>'
        # the noise's alpha as an opaque grey (its colours are no use: they come premultiplied)
        f'<feColorMatrix type="matrix" values="0 0 0 1 0  0 0 0 1 0  0 0 0 1 0  0 0 0 0 1"/></filter>'
        for fid, freq, s, _, _ in fields)
    # the two greys averaged (the second lies half-clear over the first), stretched about their middle, and only the
    # middle kept: the table is 0 everywhere but there
    band = " ".join("1" if i == 8 else "0" for i in range(17))
    defs += (f'<filter id="{uid}N" x="0" y="0" width="{w}" height="{h}" filterUnits="userSpaceOnUse" color-interpolation-filters="sRGB">'
             f'<feColorMatrix type="matrix" values="0 0 0 0 {r:.3f}  0 0 0 0 {g:.3f}  0 0 0 0 {b:.3f}  6 0 0 0 -2.5"/>'
             f'<feComponentTransfer><feFuncA type="table" tableValues="{band}"/></feComponentTransfer>'
             f'<feGaussianBlur stdDeviation="1.1" result="line"/><feGaussianBlur stdDeviation="7"/>'
             f'<feMerge><feMergeNode/><feMergeNode in="line"/></feMerge></filter>')
    body = ""
    for (fid, _, _, (dx, dy), dur), half in zip(fields, ("", ' opacity=".5"')):
        body += (f'<g{half}><animateTransform attributeName="transform" type="translate" '
                 f'values="0 0;{dx:.0f} {dy:.0f};0 0" keyTimes="0;.5;1" calcMode="spline" keySplines="{EASE};{EASE}" '
                 f'dur="{dur}s" repeatCount="indefinite"/><rect {box} filter="url(#{fid})"/></g>')
    clip_attr = f' clip-path="url(#{clip})"' if clip else ""
    return defs, f'<g{clip_attr} style="mix-blend-mode:{blend}" opacity="{o}"><g filter="url(#{uid}N)">{body}</g></g>'
