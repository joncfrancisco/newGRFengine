"""
Tying it together: models in, a NewGRF out.

(The module is `builder`, not `project`, so that `newgrfengine.project` stays
the isometric projection function - importing a submodule of that name would
quietly shadow it.)

A vehicle set has a shape that barely varies between projects. Every vehicle
has an identifier, a name, a model, a prototype length, a slot, some
properties, and a line of purchase text; every set has a sheet, a .pnml, a
language file, and a call to nmlc at the end. This module holds that shape so
a project can be a table of vehicles and a build script of about ten lines.

Nothing here is required to use the renderer. Everything below is written in
terms of the public pieces - render, sheet, nmlwrite - and a project with its
own ideas about NML can use those directly and skip this.

The one opinion worth stating: `length_ft` and `slot` are separate fields and
both are required. Together they are what stops a set drawing a switcher the
same length as a diner, and the build report prints how much of its slot each
vehicle actually filled so a wrong figure is visible immediately rather than
three days later in a screenshot.
"""

from __future__ import annotations

import os
import subprocess

from . import nmlwrite as nw
from .model import Model
from .preview import consist, contact_sheet
from .render import DEFAULT, render_model, render_purchase
from .scale import RAIL
from .sheet import TIGHT, SpriteSheet

TRAIN = "FEAT_TRAINS"
ROADVEH = "FEAT_ROADVEHS"

#: Setting this is what tells OpenTTD the item carries its own graphics.
SPRITE_ID = {TRAIN: "SPRITE_ID_NEW_TRAIN", ROADVEH: "SPRITE_ID_NEW_ROADVEH"}


class Vehicle:
    """One buyable vehicle: what it looks like, how long it is, what it does."""

    def __init__(self, ident, name, model, length_ft, slot, feature=TRAIN,
                 scale=RAIL, properties=None, graphics=None, purchase=None,
                 overhang=0.0, buy_sprite=True, **meta):
        self.ident = ident
        self.name = name
        self._model = model
        self.length_ft = float(length_ft)
        if not 1 <= int(slot) <= 8:
            raise ValueError(
                "slot must be 1..8 - it is the NML `length` property, in "
                "eighths of a tile; got {!r}".format(slot))
        self.slot = int(slot)
        self.feature = feature
        self.scale = scale
        self.properties = dict(properties or {})
        self.graphics = dict(graphics or {})
        self.purchase = purchase
        self.overhang = float(overhang)
        self.buy_sprite = buy_sprite
        self.drawn = None
        #: Columns the fleet table carries that the engine itself does not
        #: model (kind, balanced_speed, ...) - kept here so the table stays
        #: the single source of truth instead of a parallel dict at the call
        #: site. See issue #7.
        self.meta = meta

    def build_model(self):
        """The model, fitted to its prototype length and its slot."""
        model = self._model() if callable(self._model) else self._model
        fitted, drawn = self.scale.fit(Model(model), self.length_ft, self.slot,
                                       self.overhang)
        self.drawn = drawn
        return fitted

    @property
    def capped(self):
        return self.scale.is_capped(self.length_ft, self.slot, self.overhang)

    @property
    def name_key(self):
        return "STR_NAME_{}".format(self.ident.upper())

    @property
    def purchase_key(self):
        return "STR_PURCHASE_{}".format(self.ident.upper())

    def __repr__(self):
        return "Vehicle({!r}, {:.0f} ft in {}/8)".format(
            self.ident, self.length_ft, self.slot)


class Project:
    """A whole set: vehicles, a sheet, a .pnml, a language file, a .grf."""

    def __init__(self, name, grfid, title, description, version=1,
                 min_compatible_version=1, out_dir=".", layout=TIGHT,
                 spec=DEFAULT, sprite_dir="sprites", lang_dir="lang",
                 cargotable=("PASS", "MAIL"), railtypetable=("RAIL", "ELRL"),
                 roadtypetable=None, params=(), header=None):
        self.name = name
        self.grfid = grfid
        self.title = title
        self.description = description
        self.version = version
        self.min_compatible_version = min_compatible_version
        self.out_dir = out_dir
        self.layout = layout
        self.spec = spec
        self.sprite_dir = sprite_dir
        self.lang_dir = lang_dir
        self.cargotable = cargotable
        self.railtypetable = railtypetable
        self.roadtypetable = roadtypetable
        self.params = list(params)
        self.header = header
        self.vehicles = []
        self.extra_nml = []
        self.lang = nw.Lang()
        self.sheet = None
        self.rendered = {}

    # -- assembly -------------------------------------------------------------

    def add(self, vehicle):
        self.vehicles.append(vehicle)
        return vehicle

    def vehicle(self, *args, **kwargs):
        return self.add(Vehicle(*args, **kwargs))

    def add_nml(self, text, heading=None, position="before_items"):
        """Raw NML - switches, callbacks, anything this module does not model.

        `position` is where the text lands relative to the generated item()
        blocks: "before_items" (the default - templates, spritesets, switches
        that the properties below reference) or "after_items", which is where
        a parameter-guarded override block belongs. NML applies Action 0
        records in file order, so an override emitted *before* the base
        definition it is meant to change is silently overwritten by it rather
        than the other way around.
        """
        if position not in ("before_items", "after_items"):
            raise ValueError(
                "position must be 'before_items' or 'after_items', got {!r}"
                .format(position))
        self.extra_nml.append((text, heading, position))
        return self

    # -- paths ----------------------------------------------------------------

    def path(self, *parts):
        return os.path.join(self.out_dir, *parts)

    @property
    def sheet_name(self):
        return os.path.join(self.sprite_dir, self.name + ".png")

    # -- rendering ------------------------------------------------------------

    def render(self, verbose=True):
        """Render every vehicle and pack the sheet."""
        self.sheet = SpriteSheet(self.name, layout=self.layout)
        self.rendered = {}
        for vehicle in self.vehicles:
            model = vehicle.build_model()
            sprites = render_model(model, self.spec)
            buy = render_purchase(model, self.spec) if vehicle.buy_sprite else None
            self.sheet.add(vehicle.ident, sprites, purchase=buy)
            self.rendered[vehicle.ident] = sprites
            if verbose:
                print(self._report(vehicle))
        return self.sheet

    def _report(self, v):
        return "{:<20} {:5.2f} of {} units  ({:3.0f}% of slot)  {:>5.0f} ft{}".format(
            v.ident, v.drawn, v.slot, 100.0 * v.drawn / v.slot, v.length_ft,
            "  capped" if v.capped else "")

    # -- output ---------------------------------------------------------------

    def write_sprites(self):
        return self.sheet.save(self.path(self.sheet_name))

    def write_lang(self, filename="english.lng"):
        lang = self.lang
        lang.strings.setdefault("STR_GRF_NAME", self.title)
        lang.strings.setdefault("STR_GRF_DESC", self.description)
        for v in self.vehicles:
            lang.strings.setdefault(v.name_key, v.name)
            if v.purchase:
                lang.strings.setdefault(v.purchase_key, v.purchase)
        return lang.write(self.path(self.lang_dir, filename))

    def nml_text(self):
        doc = nw.NML(self.header or self._default_header())
        doc.add(nw.grf_block(self.grfid, nw.string("STR_GRF_NAME"),
                             nw.string("STR_GRF_DESC"), self.version,
                             self.min_compatible_version, self.params))
        tables = []
        if self.cargotable:
            tables.append(nw.table("cargotable", self.cargotable))
        if self.railtypetable:
            tables.append(nw.table("railtypetable", self.railtypetable))
        if self.roadtypetable:
            tables.append(nw.table("roadtypetable", self.roadtypetable))
        if tables:
            doc.add("".join(tables))
        doc.add(self.sheet.nml_templates(), heading="sprite templates")
        doc.add(self.sheet.nml_spritesets(self.sheet_name), heading="spritesets")
        for text, heading, position in self.extra_nml:
            if position == "before_items":
                doc.add(text, heading=heading)
        doc.add("\n\n".join(self._item(v) for v in self.vehicles),
                heading="vehicles")
        for text, heading, position in self.extra_nml:
            if position == "after_items":
                doc.add(text, heading=heading)
        return doc.text()

    def _item(self, v):
        properties = {"name": nw.string(v.name_key), "length": v.slot}
        properties.update(v.properties)
        properties.setdefault("climates_available", "ALL_CLIMATES")
        properties.setdefault("sprite_id", SPRITE_ID[v.feature])
        graphics = {"default": "ss_" + v.ident}
        if v.buy_sprite:
            graphics["purchase"] = "ss_{}_buy".format(v.ident)
        if v.purchase:
            # NML calls the purchase-window blurb `additional_text`, which is
            # easy to go looking for under the wrong name.
            graphics["additional_text"] = nw.string(v.purchase_key)
        graphics.update(v.graphics)
        return nw.item(v.feature, v.ident, properties, graphics,
                       comment="{} - {:.0f} ft prototype".format(v.name, v.length_ft))

    def write_nml(self, filename=None):
        filename = filename or (self.name + ".pnml")
        path = self.path(filename)
        directory = os.path.dirname(os.path.abspath(path))
        if directory:
            os.makedirs(directory, exist_ok=True)
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(self.nml_text())
        return path

    def _default_header(self):
        return ("{}\n\nGenerated by newGRFengine - edit the project, not this "
                "file.\nEvery sprite here is projected from a 3D model into "
                "OpenTTD's own\nisometric mapping, and every template offset "
                "below was computed from\nthe rendered geometry rather than "
                "measured by hand.".format(self.title))

    # -- previews -------------------------------------------------------------

    def _require_rendered(self):
        if not self.rendered:
            raise RuntimeError(
                "call render() or build() before writing a preview")

    def write_preview(self, filename=None, scale=4):
        self._require_rendered()
        filename = filename or (self.name + "_preview.png")
        entries = [(v.ident, self.rendered[v.ident]) for v in self.vehicles]
        path = self.path(filename)
        contact_sheet(entries, scale=scale).save(path)
        return path

    def write_consist(self, idents, filename=None, direction=1, scale=4):
        """A preview of the named vehicles coupled up, at the game's spacing."""
        self._require_rendered()
        filename = filename or (self.name + "_consist.png")
        by_id = {v.ident: v for v in self.vehicles}
        items = [(self.rendered[i], by_id[i].slot) for i in idents]
        path = self.path(filename)
        consist(items, direction=direction, scale=scale).save(path)
        return path

    # -- compiling ------------------------------------------------------------

    def compile(self, grf=None, nmlc="nmlc", extra_args=()):
        """Run nmlc over the generated .pnml.

        nmlc resolves the sprite filenames inside a spriteset against its own
        working directory, so it is run from the project directory with
        everything named relatively - which is also what keeps the generated
        .pnml portable between machines.
        """
        grf = grf or (self.name + ".grf")
        cmd = [nmlc, "--grf", grf, "--lang-dir", self.lang_dir,
               self.name + ".pnml"] + list(extra_args)
        result = subprocess.run(cmd, cwd=self.out_dir or ".",
                                capture_output=True, text=True)
        return result, self.path(grf)

    def build(self, verbose=True, preview=True, compile_grf=False):
        """Render, write everything, and optionally call nmlc."""
        self.render(verbose=verbose)
        paths = {"sprites": self.write_sprites(),
                 "lang": self.write_lang(),
                 "nml": self.write_nml()}
        if preview:
            paths["preview"] = self.write_preview()
        if compile_grf:
            result, grf = self.compile()
            if result.returncode != 0:
                raise RuntimeError("nmlc failed:\n{}\n{}".format(
                    result.stdout, result.stderr))
            paths["grf"] = grf
        return paths
