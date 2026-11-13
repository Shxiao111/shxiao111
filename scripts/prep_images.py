#!/usr/bin/env python3
"""Prepare the crops that gen_hero.py and gen_cards.py embed into the cards.

Inputs (not tracked): the "文学少女" illustrations in pictures/<season>/, numbered in the order of the cards they
go to - 1.jpg the hero, 2.jpg the stats panel, 3.jpg the works-in-progress card, 4.jpg the footer (spring's 1-3.jpg
is one spread for cards 1 and 3) - plus, for a season that has one, extra.jpg.
Outputs: scripts/art/<season>/{hero,stats,works,footer}.jpg (and tree.jpg from winter's and spring's extra.jpg).
Needs Pillow (pip install Pillow; CI never runs this, so it is not in requirements.txt).
Run only when the source art changes:
    python scripts/prep_images.py [season]
"""
import os
import sys

from PIL import Image, ImageEnhance

HERE = os.path.dirname(os.path.abspath(__file__))

# season: name: (source, crop box in source pixels, output size)
CROPS = {
    "autumn": {
        # the girl waving from behind the classroom window: head to hand, cut right after the panel she hides
        # behind; aspect matches the 560x480 slot
        "hero": ("1.jpg", (0, 120, 2484, 2250), (1008, 864)),
        # the girl reaching up to the window (right page only; the book on the left page is dropped): head to waist
        # with the raised hand and the pink book; aspect matches the 524x480 slot of the stats panel
        "stats": ("2.jpg", (2300, 100, 4700, 2300), (1048, 960)),
        # the girl under the golden tree: head to skirt with the red book held to her chest and the braid swinging
        # out, clear of the vertical passage on her left and the folio at the foot; pinned to the top left of the
        # works-in-progress card and cut to fill up to the bookcase
        "works": ("3.jpg", (819, 298, 3054, 2922), (930, 1092)),
        # the girl sitting in fallen maple leaves: her and both braids, stopping short of the vertical poem on the
        # right; aspect matches the 485x380 slot
        "footer": ("4.jpg", (0, 20, 1200, 960), (970, 760)),
    },
    "winter": {
        # the right page only, the girl in the yukata looking back under the festival lanterns: her face in the
        # left half, where the picture is still whole, the passage beside her out in the last of the fade
        "hero": ("1.jpg", (2950, 714, 4807, 2307), (1008, 864)),
        # the girl on the right only, looking up into the snow: head to skirt with the scarf and braid blown out
        # behind her and the frosted branches beyond, starting just past the mitten the girl in the middle throws up
        # (the picture's fade takes the last of it)
        "stats": ("2.jpg", (2376, 60, 4476, 1984), (1048, 960)),
        # the girl crouching with a book in her arms: head to knees, as wide as the page goes on her right, the
        # braid running out under the bookcase
        "works": ("3.jpg", (640, 280, 3186, 3268), (930, 1092)),
        # the girl breathing on her hands, seen from above: all the page between the grey gutters, from the scarf
        # blowing off the top to her skirt; aspect matches winter's 520x380 slot
        "footer": ("4.jpg", (60, 70, 1152, 868), (1040, 760)),
        # the tree hung with lights, from just under the passage above it to the foot of the page, between the
        # captions in the two bottom corners
        "tree": ("extra.jpg", (165, 585, 1001, 1649), (500, 636)),
    },
    # spring has three scans for the four cards: 1-3.jpg is a spread, its left page the hero's (card 1) and its
    # right page the works card's (card 3)
    "spring": {
        # the left page, the girl in the pale green dress with anemones and a book in her lap: braid to book, her
        # face in the left half, where the picture is still whole
        "hero": ("1-3.jpg", (360, 229, 2197, 1804), (1008, 864)),
        # the girl leaning out of the classroom window (the right of the spread, past the boy writing at the desk):
        # head to waist, between two window posts
        "stats": ("2.jpg", (3524, 754, 4918, 2030), (1048, 960)),
        # the right page, the girl under the tree in new leaf with a book held to her chest: all the page across,
        # from the branches over her head to the skirt, both braids looping out
        "works": ("1-3.jpg", (2500, 60, 4920, 2901), (930, 1092)),
        # the two girls lying head to head in the grass with their books: both faces, hers on the left, down to
        # the book in her arms; aspect matches spring's 600x380 slot
        "footer": ("4.jpg", (846, 382, 3766, 2230), (1200, 760)),
        # the cherry tree in bloom, all of it: the blossom from where it thins out on the left to the page's right
        # edge, down to the girl asleep at its foot and the petals on the ground
        "tree": ("extra.jpg", (1556, 0, 4965, 3473), (500, 510)),
    },
}


def main(season="autumn"):
    src_dir = os.path.join(os.path.dirname(HERE), "pictures", season)
    out_dir = os.path.join(HERE, "art", season)
    os.makedirs(out_dir, exist_ok=True)
    for name, (src, box, size) in CROPS[season].items():
        crop = Image.open(os.path.join(src_dir, src)).convert("RGB").crop(box)
        # the scans are slightly washed out; a touch of contrast keeps linework readable once scaled down
        crop = ImageEnhance.Contrast(crop).enhance(1.06)
        out = crop.resize(size, Image.LANCZOS)
        path = os.path.join(out_dir, f"{name}.jpg")
        out.save(path, "JPEG", quality=80, optimize=True, subsampling=2)
        print(f"{path}: {os.path.getsize(path)//1024} KB")


if __name__ == "__main__":
    main(*sys.argv[1:])
