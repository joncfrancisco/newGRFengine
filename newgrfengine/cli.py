"""
Command line: `python -m newgrfengine <command>`.

    palette [out.png]     draw a key of the OpenTTD DOS palette, with the
                          ranges a sprite must not paint into marked
    check <sheet.png>...  audit a finished sheet for the mistakes that only
                          show up in game
    build <module>        import a project module and build it

`check` is the one worth running in a Makefile. A sheet is an ordinary PNG and
anything can produce one - this renderer, a pixel editor, a hand touch-up - and
the failures it catches are all silent: a sprite saved as RGB instead of
paletted, a palette that is nearly but not quite the game's, a highlight that
landed in the company-colour ramp and will repaint itself blue in one player's
hands and red in another's.
"""

from __future__ import annotations

import argparse
import importlib
import os
import sys

import numpy as np
from PIL import Image, ImageDraw

from .palette import (ANIMATED, CC1_RAMP, CC2_RAMP, PAL, PURE_WHITE, rgb_of)

# Ranges the game rewrites at draw time. Two of them are hazards and two are
# features, and telling them apart is the whole job of `check`.
COMPANY_RANGES = [
    ("company colour 1", CC1_RAMP, True,
     "follows the player's colour - intended in most sets, a bug in the rest"),
    ("company colour 2", CC2_RAMP, False,
     "the second company colour, but only in a set that sets a 2CC flag; "
     "an ordinary green otherwise"),
]
HAZARD_RANGES = [
    ("animated", ANIMATED,
     "cycled by the game: fire, water sparkle, the fizzy-drink glow"),
    ("pure white", (PURE_WHITE,),
     "used as a marker in several places and not safe as paint"),
]
RESERVED = [(name, indices, why) for name, indices, _, why in COMPANY_RANGES]
RESERVED += list(HAZARD_RANGES)


def cmd_palette(args):
    """Draw the palette with its reserved ranges called out."""
    cell, cols, scale = 22, 16, 2
    header = 34
    width, height = cols * cell, 16 * cell + header
    img = Image.new("RGB", (width, height), (24, 26, 30))
    draw = ImageDraw.Draw(img)
    for index in range(256):
        col, row = index % cols, index // cols
        x0, y0 = col * cell, row * cell + header
        draw.rectangle([x0, y0, x0 + cell - 1, y0 + cell - 1], fill=rgb_of(index))
        flag = _reserved_of(index)
        if flag:
            draw.rectangle([x0, y0, x0 + cell - 1, y0 + cell - 1],
                           outline=(255, 255, 255))
            draw.line([x0, y0, x0 + cell - 1, y0 + cell - 1], fill=(255, 0, 0))
    img = img.resize((width * scale, height * scale), Image.NEAREST)
    draw = ImageDraw.Draw(img)
    draw.text((8, 8), "OpenTTD DOS palette. Crossed entries are reserved - the "
                      "game rewrites them at draw time:", fill=(230, 232, 236))
    draw.text((8, 24), "0x00 transparent   0x50-0x57 company colour 2   "
                       "0xC6-0xCD company colour 1   0xF5-0xFE animated   "
                       "0xFF white", fill=(180, 186, 194))
    out = args.output or "palette_key.png"
    img.save(out)
    print("wrote", out)
    for name, indices, why in RESERVED:
        print("  0x{:02X}-0x{:02X}  {:<18} {}".format(
            min(indices), max(indices), name, why))
    return 0


def _reserved_of(index):
    if index == 0:
        return "transparent"
    for name, indices, _ in RESERVED:
        if index in indices:
            return name
    return None


def cmd_check(args):
    """Audit sprite sheets for the failures that only appear in game."""
    problems = 0
    for path in args.sheets:
        problems += _check_one(path, args.two_cc)
    print("\n{}".format("{} problem(s) found".format(problems) if problems
                        else "no problems found"))
    return 1 if problems else 0


def _check_one(path, two_cc):
    print("{}:".format(path))
    try:
        img = Image.open(path)
    except (IOError, OSError) as err:
        print("  ERROR  cannot read: {}".format(err))
        return 1
    if img.mode != "P":
        print("  ERROR  mode is {}, not P - an 8bpp NewGRF sprite must be "
              "paletted".format(img.mode))
        return 1

    pixels = np.asarray(img)
    used = set(int(i) for i in np.unique(pixels))
    problems = 0

    palette = np.array(img.getpalette()[:768], dtype=np.int16).reshape(256, 3)
    wrong = sorted(i for i in used if not (palette[i] == PAL[i]).all())
    if wrong:
        problems += 1
        print("  ERROR  {} used indices do not hold the DOS palette's colour "
              "(first: {}) - the sheet was saved through some other "
              "palette".format(len(wrong), wrong[:6]))

    for name, indices, always, why in COMPANY_RANGES:
        hit = sorted(used & set(indices))
        if hit and (always or two_cc):
            print("  info   {} px company colour: {} - {}".format(
                int(np.isin(pixels, hit).sum()), name, why))

    for name, indices, why in HAZARD_RANGES:
        hit = sorted(used & set(indices))
        if hit:
            problems += 1
            print("  WARN   {} px in the {} range {} - {}".format(
                int(np.isin(pixels, hit).sum()), name, hit, why))

    print("  {:<6} {} indices used, {}x{}".format(
        "ok" if not problems else "", len(used), img.width, img.height))
    return problems


def cmd_build(args):
    """Import a module and build the Project it exposes."""
    sys.path.insert(0, os.getcwd())
    module = importlib.import_module(args.module)
    if hasattr(module, "main"):
        return module.main() or 0
    project = getattr(module, "project", None)
    if project is None:
        print("{}: no main() and no `project` object".format(args.module),
              file=sys.stderr)
        return 2
    for key, value in sorted(project.build().items()):
        print("{:<10} {}".format(key, value))
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(
        prog="newgrfengine", description=__doc__.strip().splitlines()[0])
    sub = parser.add_subparsers(dest="command")

    p = sub.add_parser("palette", help="draw a key of the OpenTTD DOS palette")
    p.add_argument("output", nargs="?")
    p.set_defaults(func=cmd_palette)

    p = sub.add_parser("check", help="audit sprite sheets")
    p.add_argument("sheets", nargs="+")
    p.add_argument("--2cc", dest="two_cc", action="store_true",
                   help="the set uses 2CC, so report 0x50-0x57 as company "
                        "colour rather than as ordinary green")
    p.set_defaults(func=cmd_check)

    p = sub.add_parser("build", help="build a project module")
    p.add_argument("module")
    p.set_defaults(func=cmd_build)

    args = parser.parse_args(argv)
    if not getattr(args, "func", None):
        parser.print_help()
        return 0
    return args.func(args)
