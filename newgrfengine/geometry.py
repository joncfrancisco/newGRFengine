"""
Geometry and the isometric projection OpenTTD draws vehicles in.

Everything in this engine is a quad: four points in a right-handed vehicle-
local frame where +x runs forward along the vehicle, +y across it to the left,
and +z up. World units are OpenTTD's, in which one map tile is 16 units and
covers 64 x 32 screen pixels. The projection is the game's own RemapCoords:

    screen_x = (wy - wx) * 2
    screen_y = (wy + wx) - wz

Matching it exactly is the whole point: sprites drawn under any other
projection line up with each other but not with the track, the platforms or
the ground the vehicle stands on.

A vehicle is drawn in eight directions, and rather than rendering eight models
the one model is rotated about z by

    phi = 225 deg - 45 deg * direction

for direction 0..7 in OpenTTD's sprite order N, NE, E, SE, S, SW, W, NW. Every
direction therefore comes off the same geometry, which is what makes a consist
line up on straight track and stay consistent through curves.
"""

from __future__ import annotations

import math

from .materials import L_SOLID, material

#: OpenTTD sprite order for a vehicle's eight directions.
DIRECTIONS = ("N", "NE", "E", "SE", "S", "SW", "W", "NW")
NUM_DIRS = len(DIRECTIONS)

#: One tile is 16 world units...
TILE_UNITS = 16.0
#: ...but a train vehicle is 8, so a full-length 8/8 vehicle is half a tile.
#: (OpenTTD src/vehicle_type.h VEHICLE_LENGTH against src/map_type.h TILE_SIZE.)
VEHICLE_LENGTH = 8.0
#: A tile projects to this many pixels.
TILE_PX = (64.0, 32.0)

#: The direction the camera looks from, in world units. Used for back-face
#: culling: 2 in z because the view is twice as steep as it is wide.
VIEW = (1.0, 1.0, 2.0)

#: How far above the face it decorates a decal sits, in world units. Enough to
#: win the depth sort at any rotation, small enough never to show as a lip.
EPS = 0.06


class Quad:
    """Four points, one colour, one outward normal."""

    __slots__ = ("pts", "material", "normal", "top", "layer", "tag")

    def __init__(self, pts, mat, normal, top=False, layer=L_SOLID, tag=0):
        self.pts = [tuple(float(c) for c in p) for p in pts]
        self.material = material(mat)
        self.normal = tuple(float(c) for c in normal)
        self.top = top          # horizontal surface: lit as a roof, not a flank
        self.layer = layer
        # An arbitrary small integer the renderer can carry through to a
        # per-pixel map, so a caller can ask which part of the model painted
        # each pixel. Used to cut a long sprite into pieces that reassemble
        # exactly; ignored otherwise.
        self.tag = int(tag)

    def copy(self):
        q = Quad.__new__(Quad)
        q.pts = list(self.pts)
        q.material = self.material
        q.normal = self.normal
        q.top = self.top
        q.layer = self.layer
        q.tag = self.tag
        return q

    # -- transforms; each returns a new quad, leaving this one alone ----------

    def translated(self, dx=0.0, dy=0.0, dz=0.0):
        q = self.copy()
        q.pts = [(x + dx, y + dy, z + dz) for x, y, z in q.pts]
        return q

    def scaled(self, sx=1.0, sy=1.0, sz=1.0, about=(0.0, 0.0, 0.0)):
        ax, ay, az = about
        q = self.copy()
        q.pts = [(ax + (x - ax) * sx, ay + (y - ay) * sy, az + (z - az) * sz)
                 for x, y, z in q.pts]
        # A non-uniform scale tilts normals. Rescaling by the reciprocals and
        # renormalising is the correct correction, and for the axis-aligned
        # normals almost everything here uses it is a no-op.
        nx, ny, nz = q.normal
        nx, ny, nz = (nx / sx if sx else 0.0,
                      ny / sy if sy else 0.0,
                      nz / sz if sz else 0.0)
        n = math.sqrt(nx * nx + ny * ny + nz * nz) or 1.0
        q.normal = (nx / n, ny / n, nz / n)
        return q

    def mirrored_x(self):
        """Reflect through x = 0, reversing the winding so the face still faces out."""
        q = self.copy()
        q.pts = [(-x, y, z) for x, y, z in reversed(q.pts)]
        nx, ny, nz = q.normal
        q.normal = (-nx, ny, nz)
        return q

    def rotated_z(self, radians):
        c, s = math.cos(radians), math.sin(radians)
        q = self.copy()
        q.pts = [rotate_z(p, c, s) for p in q.pts]
        q.normal = rotate_z(q.normal, c, s)
        return q

    def __repr__(self):
        return "Quad({} pts, {}, layer={})".format(
            len(self.pts), self.material, self.layer)


def rotate_z(p, c, s):
    """Rotate a point or vector about the z axis, given cos and sin."""
    x, y, z = p
    return (x * c - y * s, x * s + y * c, z)


def project(p):
    """World point -> (screen_x, screen_y) in final pixels, before any origin."""
    x, y, z = p
    return ((y - x) * 2.0, (y + x) - z)


def direction_angle(direction):
    """Rotation in radians that turns the model to face `direction` (0..7)."""
    return math.radians(225.0 - 45.0 * direction)


def facing_camera(normal, view=VIEW, bias=0.02):
    """Back-face cull test for an already-rotated normal."""
    return normal[0] * view[0] + normal[1] * view[1] + normal[2] * view[2] > bias


def depth(points):
    """Painter's-algorithm depth of an already-rotated quad: nearer is larger."""
    return sum(p[0] + p[1] + p[2] for p in points) / float(len(points))


class Lighting:
    """How a face's brightness follows the direction it points.

    Only the horizontal component matters: a flank is lit by how far it turns
    towards `light`, a roof takes `top` flat. The default is deliberately a
    narrow range - at 52 px across, a vehicle whose two visible flanks differ
    by more than about 15% stops reading as one object and starts reading as
    two, and the sprite loses its shape.
    """

    __slots__ = ("base", "spread", "top", "light")

    def __init__(self, base=0.82, spread=0.13, top=1.0, light=(1.0, -1.0)):
        self.base = base
        self.spread = spread
        self.top = top
        n = math.hypot(*light) or 1.0
        self.light = (light[0] / n, light[1] / n)

    def factor(self, quad, normal):
        if quad.material.unlit:
            return 1.0
        if quad.top:
            return self.top
        nx, ny, _ = normal
        n = math.hypot(nx, ny)
        if not n:
            return self.top
        t = (nx * self.light[0] + ny * self.light[1]) / n
        return self.base + self.spread * t

    def level(self, quad, normal):
        """The same brightness, remapped to 0..1 for company-colour ramps."""
        f = self.factor(quad, normal)
        lo = self.base - self.spread
        hi = max(self.top, self.base + self.spread)
        if hi <= lo:
            return 1.0
        return max(0.0, min(1.0, (f - lo) / (hi - lo)))
