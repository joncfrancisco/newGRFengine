"""
Models: a bag of quads that can be transformed, combined and repainted.

Primitives return Models and Models add together, so a vehicle is written as
an expression rather than as a running list. That matters most for the things
a single box cannot describe - an articulated tram is three body sections and
three trucks placed along x, a married pair is one carbody built once and
mirrored - and it is what lets the same shape be issued in half a dozen
liveries without rebuilding it.
"""

from __future__ import annotations

import math

from .materials import material


class Model:
    """A group of quads in vehicle-local coordinates."""

    __slots__ = ("quads",)

    def __init__(self, quads=()):
        if isinstance(quads, Model):
            quads = quads.quads
        self.quads = list(quads)

    # -- composition ---------------------------------------------------------

    def __iter__(self):
        return iter(self.quads)

    def __len__(self):
        return len(self.quads)

    def __add__(self, other):
        return Model(self.quads + list(_quads_of(other)))

    def __radd__(self, other):
        if other == 0:          # so sum() works
            return Model(self.quads)
        return Model(list(_quads_of(other)) + self.quads)

    def __iadd__(self, other):
        self.quads.extend(_quads_of(other))
        return self

    def add(self, *others):
        for o in others:
            self.quads.extend(_quads_of(o))
        return self

    def copy(self):
        return Model(q.copy() for q in self.quads)

    # -- transforms; each returns a new model ---------------------------------

    def translated(self, dx=0.0, dy=0.0, dz=0.0):
        return Model(q.translated(dx, dy, dz) for q in self.quads)

    def at(self, x=0.0, y=0.0, z=0.0):
        """Same as translated(); reads better when placing a section."""
        return self.translated(x, y, z)

    def scaled(self, sx=1.0, sy=1.0, sz=1.0, about=(0.0, 0.0, 0.0)):
        return Model(q.scaled(sx, sy, sz, about) for q in self.quads)

    def mirrored_x(self):
        return Model(q.mirrored_x() for q in self.quads)

    def rotated_z(self, degrees):
        r = math.radians(degrees)
        return Model(q.rotated_z(r) for q in self.quads)

    def centred_x(self):
        """Slide the model so its x extent is centred on the reference point."""
        (x0, x1), _, _ = self.bbox()
        return self.translated(dx=-(x0 + x1) / 2.0)

    # -- repainting -----------------------------------------------------------

    def recoloured(self, mapping):
        """A copy with materials substituted.

        `mapping` is keyed by Material or by RGB tuple, so a livery written as
        plain tuples and one written as Materials both work. This is how one
        carbody becomes a dozen paint schemes: build the shape once, then issue
        it per operator, per era, or per cargo subtype.
        """
        table = {}
        for key, value in mapping.items():
            table[material(key)] = material(value)
        out = []
        for q in self.quads:
            replacement = table.get(q.material)
            if replacement is None:
                out.append(q)
            else:
                nq = q.copy()
                nq.material = replacement
                out.append(nq)
        return Model(out)

    def tagged(self, tag):
        """A copy with every quad carrying `tag`, for per-piece pixel maps."""
        out = []
        for q in self.quads:
            nq = q.copy()
            nq.tag = int(tag)
            out.append(nq)
        return Model(out)

    def materials(self):
        """Every distinct material used, in first-seen order."""
        seen, order = set(), []
        for q in self.quads:
            if q.material not in seen:
                seen.add(q.material)
                order.append(q.material)
        return order

    # -- measurement ----------------------------------------------------------

    def bbox(self):
        if not self.quads:
            return ((0.0, 0.0), (0.0, 0.0), (0.0, 0.0))
        xs = [p[0] for q in self.quads for p in q.pts]
        ys = [p[1] for q in self.quads for p in q.pts]
        zs = [p[2] for q in self.quads for p in q.pts]
        return ((min(xs), max(xs)), (min(ys), max(ys)), (min(zs), max(zs)))

    @property
    def length(self):
        (x0, x1), _, _ = self.bbox()
        return x1 - x0

    @property
    def width(self):
        _, (y0, y1), _ = self.bbox()
        return y1 - y0

    @property
    def height(self):
        _, _, (z0, z1) = self.bbox()
        return z1 - z0

    def __repr__(self):
        return "Model({} quads, {:.2f} x {:.2f} x {:.2f})".format(
            len(self.quads), self.length, self.width, self.height)


def _quads_of(other):
    if isinstance(other, Model):
        return other.quads
    if other is None:
        return ()
    return list(other)
