"""
Packing rendered sprites into a PNG, and writing the NML that reads it back.

A NewGRF does not load sprites one file at a time; it loads rectangles out of
a sheet, each one named by a template line of

    [left_x, upper_y, width, height, offset_x, offset_y]

Getting those six numbers right by hand is most of the tedium of building a
vehicle set, and getting the last two wrong is why a set's consists sit half a
pixel apart or ride above the rails. The renderer already knows all six - it
cropped the sprite and it knows where the crop sits relative to the vehicle's
reference point - so the sheet writes its own templates.

Two layouts, because they suit different workflows:

TIGHT   every sprite cropped to its own bounding box, packed left to right,
        one generated template per vehicle. Nothing is wasted, and a vehicle
        may be any size at all - which is what long sprites need.

GRID    one cell size for the whole sheet, one shared template, every sprite
        drawn around a common reference point. Bigger file, but the sheet can
        be opened in a pixel editor and touched up by hand without any of the
        offsets moving, which is how most published sets are actually finished.
"""

from __future__ import annotations

import os

import numpy as np
from PIL import Image

from .geometry import DIRECTIONS
from .palette import PAL_BYTES

TIGHT = "tight"
GRID = "grid"


class Row:
    """One vehicle's sprites on the sheet, and the templates that name them.

    The eight direction sprites and the purchase-menu sprite are kept apart
    because they are used apart: a train's `default` graphics wants a spriteset
    of exactly eight sprites, and handing it a ninth is a compile error. They
    still share a row, because they belong to the same vehicle and packing them
    together is what keeps a sheet readable.
    """

    __slots__ = ("name", "sprites", "purchase", "boxes", "purchase_box",
                 "top", "height", "template")

    def __init__(self, name, sprites, purchase=None):
        self.name = name
        self.sprites = list(sprites)
        self.purchase = purchase
        self.boxes = []       # (left, top, width, height) within the sheet
        self.purchase_box = None
        self.top = 0
        self.height = 0
        self.template = "tmpl_" + name

    @property
    def all_sprites(self):
        return self.sprites + ([self.purchase] if self.purchase else [])

    @staticmethod
    def _line(box, sprite):
        left, top, w, h = box
        if w == 0 or h == 0:
            return "    []"
        return "    [{:4d}, {:4d}, {:3d}, {:3d}, {:4d}, {:4d}]".format(
            left, top, w, h, sprite.offset_x, sprite.offset_y)

    def template_lines(self):
        return [self._line(box, sprite)
                for box, sprite in zip(self.boxes, self.sprites)]

    def purchase_template_lines(self):
        if not self.purchase:
            return []
        return [self._line(self.purchase_box, self.purchase)]


class SpriteSheet:
    """A sheet under construction."""

    def __init__(self, name, layout=TIGHT, gap=1, background=0):
        if layout not in (TIGHT, GRID):
            raise ValueError("layout must be {!r} or {!r}".format(TIGHT, GRID))
        self.name = name
        self.layout = layout
        self.gap = int(gap)
        self.background = int(background)
        self.rows = []
        self._cell = None
        self._origin = None
        self._views = None

    def add(self, name, sprites, purchase=None):
        """Add one vehicle's sprites, and optionally its purchase-menu sprite."""
        row = Row(name, list(sprites), purchase)
        self.rows.append(row)
        return row

    # -- layout ---------------------------------------------------------------

    def _layout_tight(self):
        y = 0
        width = 0
        for row in self.rows:
            row.top = y
            row.height = max([s.height for s in row.all_sprites] + [1])
            x = 0
            row.boxes = []
            for s in row.sprites:
                row.boxes.append((x, y, s.width, s.height))
                x += s.width + self.gap
            if row.purchase:
                row.purchase_box = (x, y, row.purchase.width, row.purchase.height)
                x += row.purchase.width + self.gap
            width = max(width, x)
            y += row.height + self.gap
        return max(1, width), max(1, y)

    def _layout_grid(self):
        counts = set(len(row.sprites) for row in self.rows)
        if len(counts) > 1:
            raise ValueError(
                "grid layout needs every row to hold the same number of views; "
                "found {}. Use the tight layout for mixed sets.".format(
                    sorted(counts)))
        views = counts.pop() if counts else 0
        self._views = views

        # One origin that every sprite on the sheet can be drawn around. Taking
        # the extremes over the whole sheet is what makes a single shared
        # template legal: every vehicle then sits at the same place in its cell.
        every = [s for row in self.rows for s in row.all_sprites
                 if not s.is_empty()]
        left = max([-s.offset_x for s in every] + [0])
        right = max([s.offset_x + s.width for s in every] + [0])
        top = max([-s.offset_y for s in every] + [0])
        bottom = max([s.offset_y + s.height for s in every] + [0])
        cell_w = left + right + self.gap
        cell_h = top + bottom + self.gap
        self._origin = (left, top)
        self._cell = (cell_w, cell_h)

        def place(sprite, column, y):
            cx = column * cell_w
            if sprite.is_empty():
                return (cx, y, 0, 0)
            return (cx + left + sprite.offset_x, y + top + sprite.offset_y,
                    sprite.width, sprite.height)

        y = 0
        columns = views + (1 if any(r.purchase for r in self.rows) else 0)
        for row in self.rows:
            row.top = y
            row.height = cell_h
            row.boxes = [place(s, i, y) for i, s in enumerate(row.sprites)]
            row.purchase_box = (place(row.purchase, views, y)
                                if row.purchase else None)
            y += cell_h
        return max(1, columns * cell_w), max(1, y)

    def layout_sheet(self):
        if self.layout == GRID:
            return self._layout_grid()
        return self._layout_tight()

    # -- grid geometry ----------------------------------------------------------
    #
    # These three only mean anything in GRID layout, where every vehicle shares
    # one cell size and one reference point; TIGHT packs each sprite to its own
    # bounding box and has no such shared geometry. They run the layout on
    # first access rather than requiring layout_sheet() to have been called
    # already, so touching them before image()/save()/nml_templates() reports
    # the real numbers instead of an AttributeError.

    @property
    def cell(self):
        """The shared (width, height) of one grid cell, or None in TIGHT layout."""
        if self._cell is None and self.layout == GRID:
            self._layout_grid()
        return self._cell

    @property
    def origin(self):
        """The shared reference point within a cell, or None in TIGHT layout."""
        if self._origin is None and self.layout == GRID:
            self._layout_grid()
        return self._origin

    @property
    def views(self):
        """The number of direction views per row, or None in TIGHT layout."""
        if self._views is None and self.layout == GRID:
            self._layout_grid()
        return self._views

    # -- output ---------------------------------------------------------------

    def image(self):
        width, height = self.layout_sheet()
        canvas = np.full((height, width), self.background, dtype=np.uint8)
        for row in self.rows:
            boxes = list(row.boxes)
            sprites = list(row.sprites)
            if row.purchase:
                boxes.append(row.purchase_box)
                sprites.append(row.purchase)
            for (left, top, w, h), sprite in zip(boxes, sprites):
                if w == 0 or h == 0:
                    continue
                canvas[top:top + h, left:left + w] = sprite.indices
        img = Image.frombytes("P", (width, height), canvas.tobytes())
        img.putpalette(PAL_BYTES)
        return img

    def save(self, path):
        directory = os.path.dirname(os.path.abspath(path))
        if directory:
            os.makedirs(directory, exist_ok=True)
        img = self.image()
        img.save(path, optimize=False)
        return path

    # -- NML ------------------------------------------------------------------

    def nml_templates(self):
        """The template block(s) this sheet needs.

        In GRID layout that is a single shared template taking the row's y as
        a parameter, which is the form a hand-written set uses. In TIGHT layout
        each vehicle gets its own, because each vehicle is its own size.
        """
        self.layout_sheet()
        if self.layout == GRID:
            cell_w, cell_h = self.cell
            ox, oy = self.origin
            lines = ["/* {} cells of {}x{} px around a common reference point,".format(
                        self.views, cell_w, cell_h),
                     " * one per direction in the order {}. */".format(
                        ", ".join(DIRECTIONS[:min(self.views, len(DIRECTIONS))])),
                     "template tmpl_{}(row) {{".format(self.name)]
            for i in range(self.views):
                lines.append("    [{:4d}, row, {:3d}, {:3d}, {:4d}, {:4d}]".format(
                    i * cell_w, cell_w, cell_h, -ox, -oy))
            lines.append("}")
            if any(r.purchase for r in self.rows):
                lines += ["",
                          "template tmpl_{}_buy(row) {{".format(self.name),
                          "    [{:4d}, row, {:3d}, {:3d}, {:4d}, {:4d}]".format(
                              self.views * cell_w, cell_w, cell_h, -ox, -oy),
                          "}"]
            return "\n".join(lines) + "\n"

        blocks = []
        for row in self.rows:
            blocks.append("template {}() {{\n{}\n}}".format(
                row.template, "\n".join(row.template_lines())))
            if row.purchase:
                blocks.append("template {}_buy() {{\n{}\n}}".format(
                    row.template, "\n".join(row.purchase_template_lines())))
        return "\n\n".join(blocks) + ("\n" if blocks else "")

    def template_call(self, row, purchase=False):
        suffix = "_buy" if purchase else ""
        if self.layout == GRID:
            return "tmpl_{}{}({})".format(self.name, suffix, row.top)
        return "{}{}()".format(row.template, suffix)

    def nml_spritesets(self, filename, prefix="ss_"):
        """A spriteset per vehicle, pointing at this sheet."""
        self.layout_sheet()
        out = []
        for row in self.rows:
            out.append('spriteset({}{}, "{}") {{ {} }}'.format(
                prefix, row.name, filename, self.template_call(row)))
            if row.purchase:
                out.append('spriteset({}{}_buy, "{}") {{ {} }}'.format(
                    prefix, row.name, filename, self.template_call(row, True)))
        return "\n".join(out) + ("\n" if out else "")

    def __repr__(self):
        return "SpriteSheet({!r}, {}, {} rows)".format(
            self.name, self.layout, len(self.rows))
