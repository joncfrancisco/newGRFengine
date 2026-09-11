"""
The primitives every model is built from.

Five shapes cover almost everything a vehicle needs:

    box     an axis-aligned block: carbodies, roofs, bogies, hoods, roof pods
    loft    a block whose rectangular cross-section changes along its length:
            tapered noses, cab fronts that pinch in, streamlined skirts
    prism   a faceted cylinder along x: boilers, tanks, arched clerestory roofs
    strut   a thin slab that can lean, which box() cannot: trolley poles,
            pantograph arms, ladders, handrails
    decals  zero-thickness colour laid a hair above a face: windows, doors,
            stripes, corrugation, grilles, lights

The bottom face is skipped everywhere by default. Nothing in an isometric view
from above ever sees the underside of a vehicle, and every quad that is never
drawn is one more for the depth sort to carry.

Decals do not model thickness; they sit EPS above the face they decorate and
win the paint order by layer rather than by depth. Trying to give a window
real depth at this scale costs four more quads and gains nothing: 52 px across
a whole vehicle leaves a window about two pixels wide.
"""

from __future__ import annotations

import math

from .geometry import EPS, Quad
from .materials import L_DECAL, L_SOLID, L_TEXTURE, L_WINDOW, shade
from .model import Model


def quad_normal(pts):
    """Newell's method: an outward normal for any planar-ish quad."""
    nx = ny = nz = 0.0
    n = len(pts)
    for i in range(n):
        x0, y0, z0 = pts[i]
        x1, y1, z1 = pts[(i + 1) % n]
        nx += (y0 - y1) * (z0 + z1)
        ny += (z0 - z1) * (x0 + x1)
        nz += (x0 - x1) * (y0 + y1)
    length = math.sqrt(nx * nx + ny * ny + nz * nz) or 1.0
    return (nx / length, ny / length, nz / length)


def plate(pts, mat, normal=None, top=False, layer=L_SOLID):
    """One free quad, for the shapes no primitive covers."""
    return Model([Quad(pts, mat, normal or quad_normal(pts), top=top, layer=layer)])


# ------------------------------------------------------------------ solids --

def box(x0, x1, y0, y1, z0, z1, mat, top_mat=None, skip=(), layer=L_SOLID):
    """An axis-aligned block. `skip` may name 'top', 'y+', 'y-', 'x+', 'x-'."""
    q = []
    if "top" not in skip:
        q.append(Quad([(x0, y0, z1), (x1, y0, z1), (x1, y1, z1), (x0, y1, z1)],
                      top_mat if top_mat is not None else mat, (0, 0, 1),
                      top=True, layer=layer))
    if "y+" not in skip:
        q.append(Quad([(x0, y1, z0), (x1, y1, z0), (x1, y1, z1), (x0, y1, z1)],
                      mat, (0, 1, 0), layer=layer))
    if "y-" not in skip:
        q.append(Quad([(x0, y0, z0), (x1, y0, z0), (x1, y0, z1), (x0, y0, z1)],
                      mat, (0, -1, 0), layer=layer))
    if "x+" not in skip:
        q.append(Quad([(x1, y0, z0), (x1, y1, z0), (x1, y1, z1), (x1, y0, z1)],
                      mat, (1, 0, 0), layer=layer))
    if "x-" not in skip:
        q.append(Quad([(x0, y0, z0), (x0, y1, z0), (x0, y1, z1), (x0, y0, z1)],
                      mat, (-1, 0, 0), layer=layer))
    return Model(q)


def section(x, half_w, z0, z1, half_w_top=None):
    """One station of a loft: a rectangular cross-section at position x.

    `half_w_top` tapers the section in plan at roof height, which is what
    gives a carbody tumblehome or a nose that narrows as it rises.
    """
    return (float(x), float(half_w), float(z0), float(z1),
            float(half_w if half_w_top is None else half_w_top))


def loft(sections, mat, top_mat=None, caps=True, layer=L_SOLID):
    """A body whose rectangular cross-section changes from station to station.

    This is the primitive a streamlined nose needs. A box can only be as long
    as it is blunt; four or five stations pulling the width and the roof line
    down towards a point draw a cab front that actually tapers, and the same
    call with two identical stations is just a box.

    Each section comes from section(): (x, half_w, z0, z1, half_w_top).
    """
    sections = [tuple(float(v) for v in s) for s in sections]
    if len(sections) < 2:
        raise ValueError("loft needs at least two sections")
    top_mat = mat if top_mat is None else top_mat
    q = []

    def corners(s):
        x, hw, z0, z1, hwt = s
        return {
            "bl": (x, -hw, z0), "br": (x, hw, z0),
            "tl": (x, -hwt, z1), "tr": (x, hwt, z1),
        }

    for a, b in zip(sections, sections[1:]):
        ca, cb = corners(a), corners(b)
        faces = [
            (top_mat, [ca["tl"], cb["tl"], cb["tr"], ca["tr"]], True, 1), # roof
            (mat, [ca["br"], cb["br"], cb["tr"], ca["tr"]], False, 1),    # y+
            (mat, [ca["bl"], cb["bl"], cb["tl"], ca["tl"]], False, -1),   # y-
        ]
        for face_mat, pts, is_top, sign in faces:
            if _degenerate(pts):
                continue
            n = quad_normal(pts)
            # Orient each flank toward its own side, preserving the x/z
            # components from tapering and tumblehome.
            if n[2 if is_top else 1] * sign < 0:
                n = (-n[0], -n[1], -n[2])
            q.append(Quad(pts, face_mat, n, top=is_top, layer=layer))

    if caps:
        for s, sign in ((sections[-1], 1), (sections[0], -1)):
            c = corners(s)
            pts = [c["bl"], c["br"], c["tr"], c["tl"]]
            if not _degenerate(pts):
                q.append(Quad(pts, mat, (sign, 0, 0), layer=layer))
    return Model(q)


def _degenerate(pts, tol=1e-9):
    n = quad_normal(pts)
    return abs(n[0]) + abs(n[1]) + abs(n[2]) < tol


def prism(x0, x1, cy, cz, ry, rz, mat, facets=8, a0=-180.0, a1=180.0,
          top_mat=None, caps=True, layer=L_SOLID):
    """A faceted cylinder along x: boilers, tanks, arched clerestory roofs.

    `facets` is the whole point of the shape at this scale. Eight is enough to
    read as round on a boiler four pixels across, and cheap; going higher buys
    nothing the palette can show. `a0`/`a1` cut an arc rather than a full tube,
    which is how a roof gets its camber without a cylinder buried in the body.
    """
    q = []
    n = max(3, facets)
    step = math.radians(a1 - a0) / n
    a = math.radians(a0)
    pts = [(cy + ry * math.sin(a + step * i), cz + rz * math.cos(a + step * i))
           for i in range(n + 1)]
    for i in range(n):
        y0, z0 = pts[i]
        y1, z1 = pts[i + 1]
        my, mz = (y0 + y1) / 2 - cy, (z0 + z1) / 2 - cz
        norm = math.hypot(my, mz) or 1.0
        nz = mz / norm
        face_mat = top_mat if (top_mat is not None and nz > 0.72) else mat
        q.append(Quad([(x0, y0, z0), (x1, y0, z0), (x1, y1, z1), (x0, y1, z1)],
                      face_mat, (0, my / norm, nz), top=(nz > 0.85), layer=layer))
    if caps:
        for x, sign in ((x1, 1), (x0, -1)):
            for i in range(n):
                y0, z0 = pts[i]
                y1, z1 = pts[i + 1]
                q.append(Quad([(x, cy, cz), (x, y0, z0), (x, y1, z1), (x, cy, cz)],
                              shade(mat, 0.82), (sign, 0, 0), layer=layer))
    return Model(q)


def strut(x0, z0, x1, z1, y, thick, mat, layer=L_WINDOW):
    """A thin sloping slab in the x-z plane at a fixed y, faced both ways.

    box() is axis-aligned and cannot lean, so anything diagonal - a trolley
    pole laid back along a roof, a pantograph arm, a ladder - needs this. Both
    faces are emitted so it stays visible whichever side the camera is on.
    """
    pts = [(x0, y, z0), (x1, y, z1), (x1, y, z1 + thick), (x0, y, z0 + thick)]
    return Model([Quad(pts, mat, (0, 1, 0), layer=layer),
                  Quad(list(reversed(pts)), mat, (0, -1, 0), layer=layer)])


# ------------------------------------------------------------------ decals --

def side_decal(x0, x1, z0, z1, half_w, mat, layer=L_DECAL):
    """Colour laid on both flanks at once - which is what a livery wants."""
    y = half_w + EPS
    return Model([
        Quad([(x0, y, z0), (x1, y, z0), (x1, y, z1), (x0, y, z1)],
             mat, (0, 1, 0), layer=layer),
        Quad([(x0, -y, z0), (x1, -y, z0), (x1, -y, z1), (x0, -y, z1)],
             mat, (0, -1, 0), layer=layer),
    ])


def end_decal(x, sign, y0, y1, z0, z1, mat, layer=L_DECAL):
    """Colour on one end face; sign is +1 for the front, -1 for the rear."""
    xx = x + sign * EPS
    return Model([Quad([(xx, y0, z0), (xx, y1, z0), (xx, y1, z1), (xx, y0, z1)],
                       mat, (sign, 0, 0), layer=layer)])


def top_decal(x0, x1, y0, y1, z, mat, layer=L_DECAL):
    zz = z + EPS
    return Model([Quad([(x0, y0, zz), (x1, y0, zz), (x1, y1, zz), (x0, y1, zz)],
                       mat, (0, 0, 1), top=True, layer=layer)])


def window_row(x0, x1, z0, z1, half_w, count, mat, pillar=0.42, layer=L_WINDOW):
    """A run of separate windows down both flanks.

    Drawing them individually rather than as one long band is what makes a
    coach read as a coach: the pillars between them are the only cue at this
    size that says "this is a row of bays", and a single band says "this is a
    slot".
    """
    q = Model()
    unit = (x1 - x0) / float(max(1, count))
    for i in range(count):
        a = x0 + i * unit + pillar * 0.5
        b = x0 + (i + 1) * unit - pillar * 0.5
        if b > a:
            q += side_decal(a, b, z0, z1, half_w, mat, layer=layer)
    return q


def ribs(x0, x1, z0, z1, half_w, mat, pitch=0.85, thick=0.16, layer=L_TEXTURE):
    """Horizontal corrugation down both flanks: stainless-steel car sides."""
    q = Model()
    z = z0
    while z < z1 - thick:
        q += side_decal(x0, x1, z, z + thick, half_w, mat, layer=layer)
        z += pitch
    return q
