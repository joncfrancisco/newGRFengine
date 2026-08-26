"""
The OpenTTD (DOS) palette, and quantisation into it.

An 8bpp NewGRF sprite is a paletted image: every pixel is an index into the
game's own 256-colour table, not an RGB value. Index 0 is transparent, and a
handful of the other 255 are not ordinary colours at all - the game rewrites
them at draw time:

    0x00        transparent
    0x50-0x57   the second company colour, when a vehicle sets its 2CC flag
    0xC6-0xCD   the (first) company colour, always
    0xF5-0xFE   the animated ranges: fire, water sparkle, the fizzy-drink glow
    0xFF        pure white, used as a marker in several places

Anything a model paints into one of those ranges stops being the colour it
was drawn in. A Tuscan-red locomotive that quantises into 0xC6-0xCD comes out
of the depot painted in the company's colours instead, and changes colour when
the player changes theirs. So quantisation here works against an explicit
allow-list rather than the whole 256, and the default list is the safe middle
of the palette.

The table itself is read from the bundled GIMP palette file, so the engine has
no import-time dependency on nml; if nml *is* installed its copy is preferred,
since that is the table nmlc will encode against.
"""

from __future__ import annotations

import os

import numpy as np

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")

TRANSPARENT = 0
CC1_RAMP = tuple(range(0xC6, 0xCE))      # 198-205, company colour 1
CC2_RAMP = tuple(range(0x50, 0x58))      # 80-87, company colour 2 under 2CC
ANIMATED = tuple(range(0xF5, 0xFF))      # 245-254, cycled by the game
PURE_WHITE = 0xFF

#: Indices safe for ordinary painted colour in any set.
SAFE = tuple(range(1, 198))
#: Indices safe for a set that sets a 2CC flag: 0x50-0x57 becomes a company
#: colour there, so the green ramp in the middle of SAFE has to go.
SAFE_2CC = tuple(i for i in SAFE if i not in CC2_RAMP)


def _load_gpl(path):
    """Read a GIMP palette file into a (256, 3) int array."""
    rows = []
    with open(path, "r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line or line.startswith("#") or ":" in line:
                continue
            parts = line.split()
            if len(parts) < 3:
                continue
            try:
                rows.append([int(parts[0]), int(parts[1]), int(parts[2])])
            except ValueError:
                continue
    if len(rows) != 256:
        raise ValueError("{}: expected 256 entries, found {}".format(path, len(rows)))
    return np.array(rows, dtype=np.int16)


def _load_from_nml():
    from nml import palette as nmlpal          # noqa: WPS433 (optional dependency)
    raw = list(nmlpal.raw_palette_data[0])     # index 0 is DEFAULT == DOS
    return np.array(raw, dtype=np.int16).reshape(256, 3)


def load_palette():
    """The DOS palette as a (256, 3) int16 array, nml's copy for preference."""
    try:
        return _load_from_nml()
    except Exception:                          # nml missing, or its layout moved
        return _load_gpl(os.path.join(DATA_DIR, "ttd-newgrf-dos.gpl"))


PAL = load_palette()
#: Flat bytes, in the form ``PIL.Image.putpalette`` wants.
PAL_BYTES = [int(v) for v in PAL.reshape(-1)]


class Quantiser:
    """Maps RGB to palette indices, restricted to an allow-list.

    The distance metric is a weighted Euclidean one in RGB. Weighting green up
    and blue down tracks how the eye reads error: a few points of blue drift in
    a grey roof is invisible, the same drift in green is not.
    """

    WEIGHTS = np.array([0.9, 1.1, 0.8], dtype=np.float32)

    def __init__(self, allowed=SAFE, palette=None):
        self.palette = PAL if palette is None else palette
        self.allowed = np.asarray(allowed, dtype=np.int32)
        self.allowed_rgb = self.palette[self.allowed].astype(np.float32)

    def __call__(self, rgb):
        """rgb: float array (..., 3) -> uint8 index array of the same shape[:-1]."""
        rgb = np.asarray(rgb, dtype=np.float32)
        shape = rgb.shape[:-1]
        flat = rgb.reshape(-1, 1, 3)
        d = (((flat - self.allowed_rgb[None, :, :]) * self.WEIGHTS) ** 2).sum(axis=2)
        return self.allowed[np.argmin(d, axis=1)].reshape(shape).astype(np.uint8)

    def index_of(self, rgb):
        """Quantise a single colour."""
        return int(self(np.array([[rgb]], dtype=np.float32))[0, 0])


def ramp_index(ramp, level):
    """Pick a shade out of a company-colour ramp.

    `level` runs 0.0 (darkest) to 1.0 (lightest). Company-colour ramps are 8
    entries dark-to-light, so a face's shading factor maps straight onto them:
    that is how a model painted in company colour keeps its 3D reading instead
    of coming out as one flat area of blue.
    """
    n = len(ramp)
    i = int(round(level * (n - 1)))
    return ramp[max(0, min(n - 1, i))]


def rgb_of(index):
    return tuple(int(v) for v in PAL[index])
