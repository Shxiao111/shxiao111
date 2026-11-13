"""Pieces shared by gen_hero.py and gen_cards.py: the season the profile wears, the embedded fonts, the four-point
sparkle, the smoothstep fade and the easing curve.  Standard library only.
"""
import base64
import html
import json
import os
from datetime import datetime, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
with open(os.path.join(HERE, "fonts.json"), encoding="utf-8") as fh:
    FONTS = json.load(fh)

# the season in wear: its art (scripts/art/<season>/, see prep_images.py), palettes and falling things.  It follows
# the calendar: cards.yml's daily run draws the cards in it and, when it turns, redraws and commits assets/ (which
# check.yml compares byte for byte).  SEASON=winter in the environment previews one whatever the date
SEASONS = ("autumn", "winter", "spring")
MONTHS = "winter winter spring spring spring summer summer summer autumn autumn autumn winter".split()  # Jan..Dec
# shortcut: summer has no theme yet, so autumn stands in; add it to SEASONS once it is drawn
STAND_IN = {"summer": "autumn"}


def season_of(month):
    season = MONTHS[month - 1]
    return season if season in SEASONS else STAND_IN[season]


# the month by UTC, so a run at home agrees with CI's
SEASON = os.environ.get("SEASON") or season_of(datetime.now(timezone.utc).month)
if SEASON not in SEASONS:
    raise SystemExit(f"SEASON={SEASON!r}: no such season, pick one of {', '.join(SEASONS)}")


def art(name):
    """A crop of the season's art, base64 for a data: url; None if this season has no such picture."""
    path = os.path.join(HERE, "art", SEASON, f"{name}.jpg")
    if not os.path.exists(path):
        return None
    with open(path, "rb") as fh:
        return base64.b64encode(fh.read()).decode()

EASE = ".45 0 .55 1"          # one keySplines segment; join it with ";" once per interval of the animation
# for a reader who has asked for less motion: css animations are dropped, so each thing rests in its finished state,
# and what is only there to move (.mo: dust, leaves, petals, sparkles, the cursor) is put away.  Slow light and a
# sprig's sway stay: svg's own <animate> can't be switched off from css, and they keep to their place
CALM = "@media (prefers-reduced-motion:reduce){*{animation:none!important}.mo{display:none}}"


def fontface(key):
    f = FONTS[key]
    return ("@font-face{font-family:'%s';font-style:%s;font-weight:%s;"
            "src:url(data:font/woff2;base64,%s) format('woff2');}\n"
            % (f["family"], f["style"], f["weight"], f["b64"]))


def star_path(s):
    k = s * 0.22
    return f"M0,{-s:.1f} L{k:.1f},{-k:.1f} L{s:.1f},0 L{k:.1f},{k:.1f} L0,{s:.1f} L{-k:.1f},{k:.1f} L{-s:.1f},0 L{-k:.1f},{-k:.1f} Z"


def smooth_fade(n=10, fade_in=False):
    """Smoothstep opacity stops, 1 -> 0 (or 0 -> 1 with fade_in).  A linear ramp stops dead where the picture ends
    and the eye reads that kink as a hard edge on the dark theme; smoothstep eases out to a flat tail."""
    stops = []
    for i in range(n + 1):
        t = i / n
        s = 3*t*t - 2*t*t*t
        stops.append(f'<stop offset="{t:.2f}" stop-color="#fff" stop-opacity="{s if fade_in else 1 - s:.3f}"/>')
    return "".join(stops)


def write_svg(path, svg):
    """LF line endings on every platform, so a run on Windows matches the one in CI."""
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(svg)


def esc(s):
    return html.escape(str(s), quote=True)
