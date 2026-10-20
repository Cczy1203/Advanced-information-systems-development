#!/usr/bin/env python3
"""
Cut the rendered diagram into readable sections.

    python3 tools/render_sections_v16.py <full.png> <out.pdf> [<captions.json>]

One pool 17,500 px wide cannot be read on a screen or a page. The sections give
the marker the same drawing at a size where the text is legible, one stage of the
pathway per page, each page captioned with the stage it covers.
"""

import json
import os
import sys

from PIL import Image, ImageDraw, ImageFont

FONT_CANDIDATES = [
    "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
    "/System/Library/Fonts/Helvetica.ttc",
    "/Library/Fonts/Arial.ttf",
]

# (caption, x from, x to) in pixels of the full render
SECTIONS = [
    ("1. Referral intake, the missing-information loop and the clinical decision",
     130, 3100),
    ("2. Booking the new patient appointment and telling the patient", 2900, 5300),
    ("3. The new patient consultation, consent and the clinic letter", 4900, 7600),
    ("4. Funding, the charge, payment and the urgent-treatment exception", 6900, 11000),
    ("5. Planning and delivering the treatment series, cycle by cycle", 10100, 14000),
    ("6. Treatment change, follow-up and the end of the pathway", 13100, 17600),
    ("7. Enquiries, booking delays and the weekly correspondence sweep", 130, 5600),
]

BAR = 56
DPI = 96


def font(size):
    for path in FONT_CANDIDATES:
        if os.path.exists(path):
            try:
                return ImageFont.truetype(path, size)
            except OSError:
                continue
    return ImageFont.load_default()


def main(argv):
    if len(argv) < 3:
        raise SystemExit(__doc__)
    src, out = argv[1], argv[2]
    sections = SECTIONS
    if len(argv) > 3 and argv[3] != "-":
        sections = [(c, a, b) for c, a, b in
                    [(s[0], s[1], s[2]) for s in json.load(open(argv[3]))]]

    im = Image.open(src).convert("RGB")
    W, H = im.size
    title_font = font(30)
    pages = []
    for caption, x0, x1 in sections:
        x0, x1 = max(0, x0), min(W, x1)
        page = Image.new("RGB", (x1 - x0, H + BAR), "white")
        page.paste(im.crop((x0, 0, x1, H)), (0, BAR))
        d = ImageDraw.Draw(page)
        d.line([(0, BAR - 2), (x1 - x0, BAR - 2)], fill=(120, 120, 120), width=2)
        d.text((18, 12), caption, fill=(20, 20, 20), font=title_font)
        pages.append(page)
        print("  %-72s %d x %d" % (caption, page.size[0], page.size[1]))

    first, rest = pages[0], pages[1:]
    first.save(out, "PDF", resolution=DPI, save_all=True, append_images=rest)
    print("  wrote %s (%.1f MB, %d pages)" % (out, os.path.getsize(out) / 1e6, len(pages)))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
