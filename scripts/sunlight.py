"""Animated light for the cards: drifting shafts of light and shade (light_rays), breathing halos (halo), or light
that never holds its shape (shifting_light: the sea's in summer, the leaves' in spring).

Shafts: wide, blurred bands within a card all lean the same way and drift the same way, so nothing crosses.  Two
cards stacked one above the other can share one set of shafts, so a single band runs on down over the seam between
them.  On the dark theme light shafts alternate with shade bands for a clear light/dark contrast; each band fades in,
glides sideways and fades out again, staggered so the pattern keeps shifting.
Halos: soft radial glows with a faint ring that slowly swell, dim and drift.
Dark theme: screen-blended warm glow (black shade bands).  Light theme: light only, a pale warm white laid over the
paper that brightens it; no multiply and no shade, which read as stains and shadows on the light background.
The light takes the season's colour (TINT): autumn's low gold sun, winter's snow light and lantern glow, spring's
sun through new leaves, summer's white noon.
Standard library only; imported by gen_hero.py and gen_cards.py.
"""
import random

from common import EASE, SEASON

# (dark theme, light theme) colours of the shafts and of the halos
TINT = {"autumn": dict(ray=("#ffe9a8", "#fae288"), halo=("#ffe3a0", "#fffdf2")),
        "winter": dict(ray=("#cfdcff", "#ffffff"), halo=("#ffd3e2", "#fff6fa")),
        "spring": dict(ray=("#e6f5a8", "#f1fbb4"), halo=("#eaf7b0", "#fcfff0")),
        "summer": dict(ray=("#dff1ff", "#ffffff"), halo=("#fff0b8", "#fffdf2"))}[SEASON]

SKEW = 22          # degrees each band leans
DRIFT = 90         # px each band glides, in the light's direction, over its lifetime
LIFE = (22, 32)    # s per band: fade in, glide, fade out — slow enough to read as drifting sunlight


def light_rays(uid, x_from, x_to, h, dark, from_left=True, seed=1, count=4, span=None, y0=0, clip=None):
    """Defs and body.  `count` light shafts spread over x_from..x_to (at mid-height), plus a shade band in each gap
    on the dark theme.
    from_left: light falls from the upper left to the lower right and drifts right; False mirrors both.
    Cards stacked one above the other can share one set of shafts: give both calls the same `seed`, `count` and x
    range, pass the height of the whole stack as `span` and this card's offset in it as `y0`, and each shaft is drawn
    as this card's slice of one long band, so it reads as a single shaft running on down over the seam.  The default
    (span=h, y0=0) keeps the light inside one card.
    `clip`: a clipPath id, so a band reaching a card's rounded corner cannot spill past it.
    `uid` keeps ids unique in the document."""
    span = h if span is None else span
    sign = 1 if from_left else -1
    rnd = random.Random(seed)
    if dark:
        light, light_blend, light_peak = TINT["ray"][0], "screen", (.30, .42)
        shade, shade_peak = "#000", (.30, .40)
    else:
        # Soft warm golden afternoon sunlight: gentle sheen that warms the books without bleaching
        light, light_blend, light_peak = TINT["ray"][1], "normal", (.14, .22)
        shade, shade_peak = None, None

    def fall(name, color):
        return (f'<linearGradient id="{uid}{name}" x1="0" y1="0" x2="0" y2="1">'
                f'<stop offset="0" stop-color="{color}" stop-opacity="0"/><stop offset=".18" stop-color="{color}"/>'
                f'<stop offset=".62" stop-color="{color}" stop-opacity=".6"/><stop offset="1" stop-color="{color}" stop-opacity="0"/>'
                f'</linearGradient>')

    defs = (fall("Light", light) + (fall("Shade", shade) if shade else "")
            + f'<filter id="{uid}Soft" x="-150%" y="-10%" width="400%" height="120%"><feGaussianBlur stdDeviation="14 3"/></filter>')

    def band(x, w, peak, grad):
        dur = rnd.uniform(*LIFE)
        begin = -rnd.uniform(0, dur)
        travel = sign * DRIFT * rnd.uniform(.8, 1.2)
        return (f'<g transform="translate({x:.0f} {span / 2 - y0:.0f})"><g opacity="0">'
                f'<animate attributeName="opacity" values="0;{peak:.2f};{peak:.2f};0" keyTimes="0;.3;.7;1" dur="{dur:.1f}s" begin="{begin:.1f}s" repeatCount="indefinite"/>'
                f'<animateTransform attributeName="transform" type="translate" values="{-travel / 2:.0f} 0;{travel / 2:.0f} 0" dur="{dur:.1f}s" begin="{begin:.1f}s" repeatCount="indefinite"/>'
                f'<rect x="{-w / 2:.1f}" y="{-span / 2 - 40:.0f}" width="{w:.1f}" height="{span + 80:.0f}" transform="skewX({sign * SKEW})" '
                f'fill="url(#{uid}{grad})" filter="url(#{uid}Soft)"/></g></g>')

    step = (x_to - x_from) / count
    lights, shades = [], []
    for i in range(count):
        x = x_from + (i + rnd.uniform(.3, .7)) * step
        lights.append(band(x, rnd.uniform(80, 150), rnd.uniform(*light_peak), "Light"))
        if shade:
            shades.append(band(x + step / 2, rnd.uniform(90, 170), rnd.uniform(*shade_peak), "Shade"))
    clip_attr = f' clip-path="url(#{clip})"' if clip else ""
    shade_layer = f'<g{clip_attr} style="mix-blend-mode:multiply">{"".join(shades)}</g>' if shades else ""
    return defs, shade_layer + f'<g{clip_attr} style="mix-blend-mode:{light_blend}">{"".join(lights)}</g>'


def halo(uid, glows, dark, strength=1):
    """Defs and body for soft halos.  `glows` is a list of (cx, cy, r, ring): each glow breathes (grows ~12% and
    dims) and drifts a little on its own slow cycle; `ring` adds the faint ring a bright light throws around itself.
    `strength`: how bright, beside the hero's - more, to show against a bright ground."""
    color, blend, core = (TINT["halo"][0], "screen", .55 * strength) if dark else (TINT["halo"][1], "normal", .85)
    ease = ".45 0 .55 1;.45 0 .55 1"
    defs = (f'<radialGradient id="{uid}Glow"><stop offset="0" stop-color="{color}"/>'
            f'<stop offset=".3" stop-color="{color}" stop-opacity=".62"/><stop offset=".65" stop-color="{color}" stop-opacity=".2"/>'
            f'<stop offset="1" stop-color="{color}" stop-opacity="0"/></radialGradient>'
            f'<filter id="{uid}Ring" x="-30%" y="-30%" width="160%" height="160%"><feGaussianBlur stdDeviation="7"/></filter>')
    body = []
    for i, (cx, cy, r, ring) in enumerate(glows):
        breathe, wander = 9 + 2.5 * i, 31 + 6 * i
        dx, dy = (22, 14) if i % 2 == 0 else (-18, 12)
        swell = (f'values="1;1.12;1" keyTimes="0;.5;1" calcMode="spline" keySplines="{ease}" '
                 f'dur="{breathe}s" begin="{-i * 3.1:.1f}s" repeatCount="indefinite"')
        ring_el = (f'<circle r="{r * .78:.0f}" fill="none" stroke="{color}" stroke-width="{max(6, r * .05):.0f}" '
                   f'opacity="{.42 * strength if dark else .8:g}" filter="url(#{uid}Ring)"/>' if ring else "")
        body.append(
            f'<g transform="translate({cx} {cy})"><g>'
            f'<animateTransform attributeName="transform" type="translate" values="0 0;{dx} {dy};0 0" keyTimes="0;.5;1" '
            f'calcMode="spline" keySplines="{ease}" dur="{wander}s" begin="{-i * 7}s" repeatCount="indefinite"/>'
            f'<g opacity="{core:.2f}"><animate attributeName="opacity" values="{core:.2f};{core * .6:.2f};{core:.2f}" keyTimes="0;.5;1" '
            f'calcMode="spline" keySplines="{ease}" dur="{breathe}s" begin="{-i * 3.1:.1f}s" repeatCount="indefinite"/>'
            f'<g><animateTransform attributeName="transform" type="scale" {swell}/>'
            f'<circle r="{r}" fill="url(#{uid}Glow)"/>{ring_el}</g></g></g></g>')
    return defs, f'<g style="mix-blend-mode:{blend}">{"".join(body)}</g>'


def shifting_light(uid, w, h, color, blend, opacity, keep, blur, clip, *fields, mid=.5):
    """Light that never holds its shape, playing over a card.  Two fields of soft noise slide across each other,
    and the light is drawn where the two of them together sit at the heights in `keep` - a place that wanders, joins
    up and breaks as they slide - with a soft glow round it.
    keep: which of 17 steps, across the heights within a twelfth of `mid`, are lit (8: `mid` itself).
    blur: the light's own softness, and its glow's.
    fields: two of (baseFrequency, seed, how far it slides (dx, dy), seconds there and back).
    `clip`: a clipPath id, to keep the light off a card's rounded corners.
    Returns (defs, body), like light_rays; `uid` keeps ids unique in the document."""
    pad = 70                                  # the fields are drawn this far past the card, to slide within
    r, g, b = (int(color[i:i + 2], 16) / 255 for i in (1, 3, 5))
    box = f'x="{-pad}" y="{-pad}" width="{w + 2 * pad}" height="{h + 2 * pad}"'
    fields = [(f"{uid}{k}", *f) for k, f in zip("AB", fields)]
    defs = "".join(
        f'<filter id="{fid}" {box} filterUnits="userSpaceOnUse" color-interpolation-filters="sRGB">'
        f'<feTurbulence type="fractalNoise" baseFrequency="{freq}" numOctaves="2" seed="{s}"/>'
        # the noise's alpha as an opaque grey (its colours are no use: they come premultiplied)
        f'<feColorMatrix type="matrix" values="0 0 0 1 0  0 0 0 1 0  0 0 0 1 0  0 0 0 0 1"/></filter>'
        for fid, freq, s, _, _ in fields)
    # the two greys averaged (the second lies half-clear over the first), stretched about `mid`, and only the
    # steps in `keep` kept: the table is 0 everywhere else
    table = " ".join("1" if i in keep else "0" for i in range(17))
    defs += (f'<filter id="{uid}N" x="0" y="0" width="{w}" height="{h}" filterUnits="userSpaceOnUse" color-interpolation-filters="sRGB">'
             f'<feColorMatrix type="matrix" values="0 0 0 0 {r:.3f}  0 0 0 0 {g:.3f}  0 0 0 0 {b:.3f}  6 0 0 0 {.5 - 6 * mid:g}"/>'
             f'<feComponentTransfer><feFuncA type="table" tableValues="{table}"/></feComponentTransfer>'
             f'<feGaussianBlur stdDeviation="{blur[0]}" result="line"/><feGaussianBlur stdDeviation="{blur[1]}"/>'
             f'<feMerge><feMergeNode/><feMergeNode in="line"/></feMerge></filter>')
    body = ""
    for (fid, _, _, (dx, dy), dur), half in zip(fields, ("", ' opacity=".5"')):
        body += (f'<g{half}><animateTransform attributeName="transform" type="translate" '
                 f'values="0 0;{dx} {dy};0 0" keyTimes="0;.5;1" calcMode="spline" keySplines="{EASE};{EASE}" '
                 f'dur="{dur}s" repeatCount="indefinite"/><rect {box} filter="url(#{fid})"/></g>')
    clip_attr = f' clip-path="url(#{clip})"' if clip else ""
    return defs, f'<g{clip_attr} style="mix-blend-mode:{blend}" opacity="{opacity}"><g filter="url(#{uid}N)">{body}</g></g>'
