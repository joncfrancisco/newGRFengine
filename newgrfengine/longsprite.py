"""
Drawing a vehicle longer than the slot it occupies.

OpenTTD reserves a train vehicle `length` eighths of a tile and expects its
sprite to stay inside that. A cab car with a real nose does not want to: the
nose is the whole character of the vehicle, and cropping it to the slot throws
that character away. JPplusShinkansen solves it by building each unit as three
articulated parts in a 1-8-1 length pattern, and drawing cab art that runs
about 25% past the middle part's reserved length - the overhang is carried by
the near-zero-length parts either side, which contribute no length of their own.

This module does the rendering half of that, exactly rather than by eye.

The model is cut **in model space**, on planes square across the vehicle at the
edges of its slot, so each piece is a true section of the same geometry - no
pixel slicing, no guessing where a diagonal view's cut line falls. Each piece
then goes through the ordinary pipeline, which crops it and works out its
offsets against the vehicle's own reference point.

The last step is the one that is tedious by hand: an overhang piece is drawn
not by this vehicle but by its neighbour, so its offsets have to be rebased
onto *that* vehicle's reference point. The neighbour sits one slot along the
vehicle's x axis, and that vector projects differently in every direction -
2 px across and 1 down per world unit on a diagonal, 2.83 px across and none
on a straight. Those eight corrections are exactly what a hand-built set's
front and back templates encode as eight sets of hand-tuned offsets.

What this module does not do is decide *when* the game should draw the long
sprite instead of the three pieces. That depends on the consist logic of the
set it is going into - whether the neighbours are straight, level, and the
parts they are meant to be - so `nml_switches` emits the scaffolding with the
predicate left as an expression you supply, rather than pretending to know.
"""

from __future__ import annotations

import math

import numpy as np

from .geometry import Quad, direction_angle, project, rotate_z
from .model import Model
from .render import DEFAULT, Sprite, render_model

FULL, FRONT, BODY, BACK = "full", "front", "body", "back"


def _clip_polygon(pts, plane, keep_greater):
    """Sutherland-Hodgman against the plane x = `plane`."""
    if not pts:
        return []
    out = []
    n = len(pts)
    for i in range(n):
        a = pts[i]
        b = pts[(i + 1) % n]
        a_in = (a[0] >= plane) if keep_greater else (a[0] <= plane)
        b_in = (b[0] >= plane) if keep_greater else (b[0] <= plane)
        if a_in:
            out.append(a)
        if a_in != b_in:
            span = b[0] - a[0]
            t = 0.0 if span == 0 else (plane - a[0]) / span
            out.append((plane,
                        a[1] + (b[1] - a[1]) * t,
                        a[2] + (b[2] - a[2]) * t))
    return out


def clip_x(model, x_min=None, x_max=None, tol=1e-9):
    """A copy of the model with every face cut to the slab x_min <= x <= x_max.

    Faces are clipped, not culled: a carbody straddling the cut comes back as
    two pieces that together are exactly the original, which is what makes the
    seam between an overhang and its body invisible.
    """
    quads = []
    for q in model:
        pts = list(q.pts)
        if x_min is not None:
            pts = _clip_polygon(pts, x_min, True)
        if x_max is not None:
            pts = _clip_polygon(pts, x_max, False)
        if len(pts) < 3 or _extent(pts) < tol:
            continue
        nq = Quad.__new__(Quad)
        nq.pts = pts
        nq.material = q.material
        nq.normal = q.normal
        nq.top = q.top
        nq.layer = q.layer
        nq.tag = q.tag
        quads.append(nq)
    return Model(quads)


def _extent(pts):
    """A cheap "is there anything left of this face" test."""
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    zs = [p[2] for p in pts]
    return max(max(xs) - min(xs), max(ys) - min(ys), max(zs) - min(zs))


def split_overhang(model, slot):
    """Cut a model into back, body and front at the edges of its slot."""
    half = slot / 2.0
    return {
        BACK: clip_x(model, None, -half),
        BODY: clip_x(model, -half, half),
        FRONT: clip_x(model, half, None),
    }


def step_vector(direction):
    """Screen displacement in pixels per world unit along the vehicle's x axis."""
    angle = direction_angle(direction)
    return project(rotate_z((1.0, 0.0, 0.0), math.cos(angle), math.sin(angle)))


def rebase(sprites, distance):
    """Re-express offsets against a reference point `distance` units along x.

    Positive `distance` moves the reference point forward, which is the front
    overhang's case: it is drawn by the vehicle ahead, so relative to that
    vehicle everything shifts back.
    """
    out = []
    for d, sprite in enumerate(sprites):
        if sprite.is_empty():
            out.append(sprite)
            continue
        sx, sy = step_vector(d)
        out.append(Sprite(sprite.indices,
                          int(round(sprite.offset_x - distance * sx)),
                          int(round(sprite.offset_y - distance * sy)),
                          sprite.direction))
    return out


TAGS = {BACK: 1, BODY: 2, FRONT: 3}


def extract(sprite, tagmap, tag):
    """The part of a rendered sprite that one tag painted, cropped tight."""
    if sprite.is_empty():
        return sprite
    mask = (tagmap == tag) & (sprite.indices != 0)
    if not mask.any():
        return Sprite(np.zeros((0, 0), dtype=np.uint8), 0, 0, sprite.direction)
    rows = np.flatnonzero(mask.any(axis=1))
    cols = np.flatnonzero(mask.any(axis=0))
    top, bottom = int(rows[0]), int(rows[-1]) + 1
    left, right = int(cols[0]), int(cols[-1]) + 1
    piece = np.where(mask, sprite.indices, 0)[top:bottom, left:right]
    return Sprite(piece.astype(np.uint8),
                  sprite.offset_x + left, sprite.offset_y + top,
                  sprite.direction)


def render_long(model, slot, spec=DEFAULT):
    """Render a model that overruns its slot, in all four forms.

    Returns 'full', 'front', 'body' and 'back' sprite lists. The full sprite is
    what to draw when the vehicle and its neighbours are in a line; the three
    pieces are what to draw when they are not, one on each articulated part.

    The pieces are cut out of the *finished* sprite rather than rendered
    separately. That matters: rendering three models independently gives each
    piece its own antialiased edge along the cut and its own idea of what
    occludes what, so the three do not add back up to the one. Tagging the
    geometry and splitting the pixels afterwards means every pixel belongs to
    exactly one piece, and laying the three back down reproduces the full
    sprite exactly.

    Rebasing rounds to whole pixels, because a sprite offset is an integer. On
    a straight, one world unit is 2.83 px, so an 8-unit slot rebases by 22.6 px
    and loses a third of a pixel - less than the game's own per-vehicle
    rounding already moves the same consist.
    """
    model = Model(model)
    parts = split_overhang(model, slot)
    tagged = (parts[BACK].tagged(TAGS[BACK])
              + parts[BODY].tagged(TAGS[BODY])
              + parts[FRONT].tagged(TAGS[FRONT]))
    sprites, tagmaps = render_model(tagged, spec, tags=True)

    out = {FULL: sprites, BACK: [], BODY: [], FRONT: []}
    for sprite, tagmap in zip(sprites, tagmaps):
        for key in (BACK, BODY, FRONT):
            out[key].append(extract(sprite, tagmap, TAGS[key]))
    out[FRONT] = rebase(out[FRONT], slot)
    out[BACK] = rebase(out[BACK], -slot)
    return out


def nml_switches(name, straight, feature="FEAT_TRAINS", prefix="ss_"):
    """Scaffolding that picks the long sprite on a straight and the pieces off it.

    `straight` is an expression that is 1 when this vehicle and its neighbours
    are in a line and level - for an articulated set that is usually built out
    of other_veh_curv_info() and other_veh_z_offset() over the neighbouring
    parts. It is left to the caller because the answer depends on how the set
    lays its articulation out, and getting it wrong is a visual bug rather than
    a compile error.

    The polarity is spelled out here rather than buried in a helper: on a
    straight the middle part draws the whole vehicle and the end parts draw
    nothing; otherwise each part draws its own third.
    """
    p = prefix + name
    return (
        "/* {name}: one long sprite on a straight, three pieces otherwise. */\n"
        "switch ({feat}, SELF, sw_{name}_straight, {straight}) {{ return; }}\n"
        "\n"
        "switch ({feat}, SELF, sw_{name}_body, sw_{name}_straight()) {{\n"
        "    1: {p}_full;\n"
        "    {p}_body;\n"
        "}}\n"
        "switch ({feat}, SELF, sw_{name}_front, sw_{name}_straight()) {{\n"
        "    1: {p}_empty;\n"
        "    {p}_front;\n"
        "}}\n"
        "switch ({feat}, SELF, sw_{name}_back, sw_{name}_straight()) {{\n"
        "    1: {p}_empty;\n"
        "    {p}_back;\n"
        "}}\n"
    ).format(name=name, feat=feature, straight=straight, p=p)
