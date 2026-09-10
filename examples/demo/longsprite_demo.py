#!/usr/bin/env python3
"""
The long-sprite path: drawing a vehicle 25% longer than its slot.

The technique comes from JPplusShinkansen, where each unit is three
articulated parts in a 1-8-1 length pattern and the cab art runs past the
middle part's reserved length onto the two near-zero-length parts either side.
What this script demonstrates is the part that is miserable by hand: cutting
the model at the slot boundaries, and working out what the overhang's sprite
offsets become once a *different* vehicle is drawing them.

Run it and it writes, into longsprite/:

    longsprite.png       the four sprite groups packed onto one sheet
    longsprite.pnml      their templates, spritesets and switch scaffolding
    reassembled.png      the three pieces laid back down side by side with
                         the single full sprite, which should be identical

The identity is not approximate. The pieces are cut out of the finished sprite
rather than rendered one at a time, so every pixel belongs to exactly one
piece and the three add back up to the one exactly - which the test suite
checks in all eight directions.
"""

import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__),
                                                "..", "..")))

import numpy as np                                                  # noqa: E402
from PIL import Image                                               # noqa: E402

from newgrfengine import (RAIL, SpriteSheet, TIGHT, bogies, cab_glass,  # noqa: E402
                          headlights, loft, section, window_row)
from newgrfengine.longsprite import nml_switches, render_long, step_vector

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "longsprite")

SLOT = 8                 # the NML `length` this vehicle reserves
PROTOTYPE_FT = 106       # ...and the prototype it is actually drawn to
OVERHANG = 0.25          # how far past the slot the art may run

HW = 1.62
STEEL = (226, 230, 236)
ROOF = (118, 124, 130)
GLASS = (44, 58, 76)


def nosed_cab():
    """A cab car whose nose is the reason the sprite will not fit its slot."""
    body = loft([
        section(-6.6, HW, 3.0, 9.0),
        section(2.4, HW, 3.0, 9.0),
        section(4.4, HW * 0.86, 3.0, 8.4, half_w_top=HW * 0.52),
        section(5.9, HW * 0.56, 3.1, 7.5, half_w_top=HW * 0.24),
        section(6.8, HW * 0.24, 3.4, 6.5, half_w_top=HW * 0.09),
    ], STEEL, top_mat=ROOF)
    model = bogies(13.2, HW, inset=2.4)
    model += body
    model += window_row(-5.8, 2.0, 6.4, 8.1, HW, 6, GLASS)
    model += cab_glass(5.9, 1, HW * 0.58, 6.5, 7.6, GLASS, depth=1.8)
    model += headlights(6.8, 1, HW * 0.24, 5.3, 5.8)
    return model


def compose(pieces, background=0):
    """Lay sprites at their reference points, `pieces` being (sprite, units)."""
    placed = []
    for sprite, units in pieces:
        if sprite.is_empty():
            continue
        sx, sy = step_vector(sprite.direction)
        placed.append((sprite, int(round(sprite.offset_x + units * sx)),
                       int(round(sprite.offset_y + units * sy))))
    x0 = min(x for _, x, _ in placed)
    y0 = min(y for _, _, y in placed)
    width = max(x + s.width for s, x, _ in placed) - x0
    height = max(y + s.height for s, _, y in placed) - y0
    canvas = np.full((height, width), background, dtype=np.uint8)
    for sprite, x, y in placed:
        region = canvas[y - y0:y - y0 + sprite.height,
                        x - x0:x - x0 + sprite.width]
        mask = sprite.indices != 0
        region[mask] = sprite.indices[mask]
    return canvas


def main():
    os.makedirs(OUT, exist_ok=True)
    model, drawn = RAIL.fit(nosed_cab(), PROTOTYPE_FT, SLOT, overhang=OVERHANG)
    print("drawn {:.2f} world units in a slot of {} - {:.0f}% of the slot"
          .format(drawn, SLOT, 100 * drawn / SLOT))

    parts = render_long(model, SLOT)
    for key in ("full", "back", "body", "front"):
        widths = [s.width for s in parts[key]]
        print("  {:<6} widths {}".format(key, widths))

    sheet = SpriteSheet("longsprite", layout=TIGHT)
    for key in ("full", "back", "body", "front"):
        sheet.add("cab_" + key, parts[key])
    sheet.save(os.path.join(OUT, "longsprite.png"))

    nml = [sheet.nml_templates(),
           sheet.nml_spritesets("longsprite/longsprite.png", prefix="ss_"),
           # The predicate is the caller's: it depends on how the set lays its
           # articulation out, and this engine will not guess it.
           # prefix matches the "ss_" given to nml_spritesets() above, not
           # that plus the vehicle name too - see nml_switches()'s docstring.
           nml_switches("cab",
                        "other_veh_curv_info(1) == 0 && "
                        "other_veh_curv_info(-1) == 0 && "
                        "other_veh_z_offset(1) == 0 && "
                        "other_veh_z_offset(-1) == 0")]
    with open(os.path.join(OUT, "longsprite.pnml"), "w") as fh:
        fh.write("\n\n".join(nml))

    # Proof: the three pieces on three consecutive reference points against the
    # single full sprite. These should be the same picture.
    from newgrfengine.palette import PAL
    rows = []
    for direction in (1, 2, 3):
        whole = compose([(parts["full"][direction], 0)])
        split = compose([(parts["back"][direction], -SLOT),
                         (parts["body"][direction], 0),
                         (parts["front"][direction], SLOT)])
        assert whole.shape == split.shape and (whole == split).all(), direction
        rows.append(np.concatenate([whole, np.zeros((whole.shape[0], 4),
                                                    dtype=np.uint8), split],
                                   axis=1))
    width = max(r.shape[1] for r in rows)
    stack = np.zeros((sum(r.shape[0] + 4 for r in rows), width), dtype=np.uint8)
    y = 0
    for row in rows:
        stack[y:y + row.shape[0], :row.shape[1]] = row
        y += row.shape[0] + 4
    rgb = np.where((stack == 0)[..., None], np.array([58, 92, 56], np.uint8),
                   PAL[stack].astype(np.uint8))
    image = Image.fromarray(rgb)
    image = image.resize((image.width * 5, image.height * 5), Image.NEAREST)
    image.save(os.path.join(OUT, "reassembled.png"))

    print("\nwrote", os.path.relpath(OUT, HERE))
    print("  full sprite and reassembled pieces are identical in all "
          "eight directions")
    return 0


if __name__ == "__main__":
    sys.exit(main())
