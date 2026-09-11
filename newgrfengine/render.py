"""
Projecting a model into OpenTTD sprites.

The pipeline for one direction is:

    rotate -> cull -> shade -> sort -> rasterise at 4x -> downsample -> quantise

and then crop to the tight bounding box, which is what lets the sheet writer
pack sprites and emit exact NML offsets rather than making every vehicle sit
in one generously sized cell.

Two details are worth knowing about.

**Sorting is by layer first, depth second.** A painter's algorithm on depth
alone cannot be trusted to keep a window in front of the body it is cut into:
the decal sits a hundredth of a unit proud, and at some rotations that is
inside the noise. Layers make the ordering a statement about what the surfaces
*are* rather than about where they happened to land.

**Downsampling is mask-weighted.** Averaging a 4x4 block that is half vehicle
and half background pulls the edge pixels towards the background colour, and
since the background is nothing at all, that reads as a dark fringe all round
the sprite. Weighting by coverage and dividing by it averages only the pixels
that are actually vehicle, so the edge keeps the colour of the thing it is the
edge of, and coverage becomes the alpha the transparency threshold works on.

Company colour is the one thing that cannot go through that averaging. A
company-coloured face resolves to a palette *index* in a reserved ramp, and
blending two ramp indices gives a third index that is not in the ramp - so the
face would come out of the depot half painted. Those pixels are carried in a
separate index buffer and decided by majority vote per output pixel: a pixel
that is mostly company colour stays exactly on the ramp, a pixel on the border
falls through to ordinary quantisation. The cost is that the boundary between
a company-coloured panel and a fixed-colour one is not antialiased, which is
a constraint of the palette rather than of this renderer.
"""

from __future__ import annotations

import math

import numpy as np
from PIL import Image, ImageDraw

from .geometry import (NUM_DIRS, VIEW, Lighting, depth, direction_angle,
                       facing_camera, project, rotate_z)
from .model import Model
from .palette import (CC1_RAMP, CC2_RAMP, PAL, PAL_BYTES, SAFE, Quantiser,
                      ramp_index)

#: Direction index that projects a vehicle exactly broadside, nose to the
#: right - the view a purchase-menu sprite wants.
SIDE_ON = 2


class Sprite:
    """One rendered direction: palette indices plus where to draw them.

    `offset_x` / `offset_y` are the NML sprite offsets: the position of the
    sprite's top-left corner relative to the vehicle's reference point, which
    is what makes consecutive vehicles in a consist line up.
    """

    __slots__ = ("indices", "offset_x", "offset_y", "direction")

    def __init__(self, indices, offset_x, offset_y, direction=None):
        self.indices = indices
        self.offset_x = int(offset_x)
        self.offset_y = int(offset_y)
        self.direction = direction

    @property
    def height(self):
        return int(self.indices.shape[0])

    @property
    def width(self):
        return int(self.indices.shape[1])

    def is_empty(self):
        return self.width == 0 or self.height == 0

    def to_image(self):
        img = Image.frombytes("P", (self.width, self.height),
                              np.ascontiguousarray(self.indices).tobytes())
        img.putpalette(PAL_BYTES)
        return img

    def __repr__(self):
        return "Sprite({}x{} at {},{}{})".format(
            self.width, self.height, self.offset_x, self.offset_y,
            ", dir={}".format(self.direction) if self.direction is not None else "")


class RenderSpec:
    """Everything about how a model becomes pixels, in one place."""

    __slots__ = ("supersample", "lighting", "quantiser", "view", "alpha",
                 "pad", "directions", "cc1", "cc2")

    def __init__(self, supersample=4, lighting=None, quantiser=None, view=VIEW,
                 alpha=0.42, pad=1, directions=NUM_DIRS, cc1=CC1_RAMP,
                 cc2=CC2_RAMP):
        self.supersample = int(supersample)
        self.lighting = lighting or Lighting()
        self.quantiser = quantiser or Quantiser(SAFE)
        self.view = view
        self.alpha = float(alpha)
        self.pad = int(pad)
        self.directions = int(directions)
        self.cc1 = tuple(cc1)
        self.cc2 = tuple(cc2)

    def ramp(self, cc):
        return self.cc1 if cc == 1 else self.cc2


DEFAULT = RenderSpec()


def _prepare(model, angle, spec):
    """Cull, shade and project one rotation. Returns a paint list."""
    c, s = math.cos(angle), math.sin(angle)
    out = []
    for q in model:
        normal = rotate_z(q.normal, c, s)
        if not facing_camera(normal, spec.view):
            continue
        pts = [rotate_z(p, c, s) for p in q.pts]
        poly = [project(p) for p in pts]
        mat = q.material
        if mat.cc:
            level = spec.lighting.level(q, normal)
            index = ramp_index(spec.ramp(mat.cc), level)
            rgb = tuple(int(v) for v in PAL[index])
        else:
            index = 0
            rgb = mat.shade(spec.lighting.factor(q, normal)).rgb
        out.append((q.layer, depth(pts), poly, rgb, index, q.tag))
    out.sort(key=lambda item: (item[0], item[1]))
    return out


def render_direction(model, direction, spec=DEFAULT, tags=False):
    """Render one of the eight directions to a tightly cropped Sprite.

    With `tags`, also returns a map of the same shape saying which quad tag
    painted each pixel. That is how a model gets cut into pieces that reassemble
    to exactly the original sprite: the split happens after the depth sort, so
    every pixel belongs to precisely one piece and the occlusion between them is
    the occlusion the whole model had.
    """
    painted = _prepare(model, direction_angle(direction), spec)
    if not painted:
        empty = Sprite(np.zeros((0, 0), dtype=np.uint8), 0, 0, direction)
        return (empty, np.zeros((0, 0), dtype=np.uint8)) if tags else empty

    xs = [p[0] for _, _, poly, _, _, _ in painted for p in poly]
    ys = [p[1] for _, _, poly, _, _, _ in painted for p in poly]
    x0 = int(math.floor(min(xs))) - spec.pad
    y0 = int(math.floor(min(ys))) - spec.pad
    w = int(math.ceil(max(xs))) + spec.pad - x0
    h = int(math.ceil(max(ys))) + spec.pad - y0
    ss = spec.supersample

    img = Image.new("RGB", (w * ss, h * ss), (0, 0, 0))
    cover = Image.new("L", (w * ss, h * ss), 0)
    forced = Image.new("L", (w * ss, h * ss), 0)
    tagmap = Image.new("L", (w * ss, h * ss), 0) if tags else None
    d_img, d_cover, d_forced = (ImageDraw.Draw(im) for im in (img, cover, forced))
    d_tag = ImageDraw.Draw(tagmap) if tags else None

    for _, _, poly, rgb, index, tag in painted:
        screen = [((px - x0) * ss, (py - y0) * ss) for px, py in poly]
        d_img.polygon(screen, fill=rgb)
        d_cover.polygon(screen, fill=255)
        d_forced.polygon(screen, fill=int(index))
        if d_tag is not None:
            d_tag.polygon(screen, fill=int(tag))

    _, indices = _resolve(np.asarray(img, dtype=np.float32),
                          np.asarray(cover, dtype=np.float32) / 255.0,
                          np.asarray(forced), h, w, ss, spec)
    if not tags:
        return _crop(indices, x0, y0, direction)

    flat_tags = _majority(np.asarray(tagmap), h, w, ss)
    sprite, box = _crop(indices, x0, y0, direction, want_box=True)
    if box is None:
        return sprite, np.zeros((0, 0), dtype=np.uint8)
    top, bottom, left, right = box
    return sprite, flat_tags[top:bottom, left:right]


def _resolve(rgb, cover, forced, h, w, ss, spec):
    """Downsample, quantise and settle the company-colour pixels."""
    rgb = rgb.reshape(h, ss, w, ss, 3)
    cover = cover.reshape(h, ss, w, ss)
    weight = cover.sum(axis=(1, 3))
    colour = np.where(weight[..., None] > 0,
                      (rgb * cover[..., None]).sum(axis=(1, 3))
                      / np.maximum(weight, 1e-6)[..., None],
                      0.0)
    alpha = weight / float(ss * ss)

    indices = spec.quantiser(colour)

    if forced.any():
        blocks = forced.reshape(h, ss, w, ss)
        for ramp in (spec.cc1, spec.cc2):
            ramp_count = np.zeros((h, w), dtype=np.float32)
            best_count = np.zeros((h, w), dtype=np.float32)
            best_index = np.zeros((h, w), dtype=np.uint8)
            for value in ramp:
                count = ((blocks == value) * cover).sum(axis=(1, 3))
                ramp_count += count
                better = count > best_count
                best_count = np.where(better, count, best_count)
                best_index = np.where(better, value, best_index)
            # Vote by ramp over covered subpixels before choosing its most
            # frequent shade. Shade ties use the first entry in ramp order;
            # a ramp tied with fixed paint or another ramp does not win.
            wins = ramp_count * 2.0 > np.maximum(weight, 1e-6)
            indices = np.where(wins, best_index, indices).astype(np.uint8)

    indices[alpha < spec.alpha] = 0
    return weight, indices


def _majority(values, h, w, ss):
    """Downsample an integer label map by majority over the covered subpixels."""
    blocks = values.reshape(h, ss, w, ss)
    best_count = np.zeros((h, w), dtype=np.float32)
    best = np.zeros((h, w), dtype=np.uint8)
    for value in np.unique(values):
        if value == 0:
            continue
        count = (blocks == value).sum(axis=(1, 3)).astype(np.float32)
        better = count > best_count
        best_count = np.where(better, count, best_count)
        best = np.where(better, value, best).astype(np.uint8)
    return best


def _crop(indices, x0, y0, direction, want_box=False):
    rows = np.flatnonzero(indices.any(axis=1))
    cols = np.flatnonzero(indices.any(axis=0))
    if rows.size == 0 or cols.size == 0:
        empty = Sprite(np.zeros((0, 0), dtype=np.uint8), 0, 0, direction)
        return (empty, None) if want_box else empty
    top, bottom = int(rows[0]), int(rows[-1]) + 1
    left, right = int(cols[0]), int(cols[-1]) + 1
    sprite = Sprite(indices[top:bottom, left:right],
                    x0 + left, y0 + top, direction)
    return (sprite, (top, bottom, left, right)) if want_box else sprite


def render_model(model, spec=DEFAULT, tags=False):
    """Every direction of one model, in OpenTTD's sprite order."""
    model = Model(model)
    rendered = [render_direction(model, d, spec, tags) for d in range(spec.directions)]
    if tags:
        return [r[0] for r in rendered], [r[1] for r in rendered]
    return rendered


def render_purchase(model, spec=DEFAULT, direction=SIDE_ON):
    """The broadside view a purchase-menu sprite wants.

    Direction 2 is the one rotation where the projection collapses to pure
    horizontal - the vehicle is exactly side-on with its nose to the right -
    so it is the cheapest honest purchase sprite there is: no separate artwork,
    no separate model, just the sheet's own geometry seen square.
    """
    return render_direction(model, direction, spec)
