"""
Turning a real vehicle's length into the length it is drawn at.

Two different things get called "length" in a NewGRF, and getting either one
wrong shows up immediately as sprites that overlap their neighbours, or as a
train in which every vehicle looks the same size.

**The unit trap.** A tile is 16 world units, but a train vehicle is not.
OpenTTD's VEHICLE_LENGTH is 8 against a tile's TILE_SIZE of 16, so a
full-length 8/8 vehicle is *half a tile*, and the game spaces consecutive
vehicles by exactly the NML `length` property in world units - not twice that.
A sprite drawn to fill a whole tile overlaps the vehicle behind it by about
45%.

**The coarseness trap.** `length` is an integer from 1 to 8, so prototypes of
quite different size land in the same bucket: a 65 ft locomotive and an 85 ft
coach are both 8/8 vehicles. Scaling every model to fill its bucket draws them
the same length, and a roster where a switcher is as long as a diner is a
roster that has only fixed the first trap.

So a model carries its prototype length in feet as well as its NML slot, and
gets drawn to the first, capped by the second. A short engine in a slot sized
for something longer simply shows more coupling gap around it, which is the
correct read: it *is* a short engine sharing a slot built for something bigger.

**Road vehicles need their own calibration, and this is not a fudge.** At the
rail scale a 40 ft bus comes out about seven pixels long - too few to carry a
windscreen, a door and three window bays, and dwarfed by the body height those
details need. OpenTTD's own artwork makes exactly the same concession: a
vanilla bus is drawn very nearly as long as a vanilla wagon. Calibrating the
road fleet against itself keeps every road length honest relative to the other
road vehicles, which is the comparison a player can actually make on screen.
"""

from __future__ import annotations

from .model import Model


class LengthScale:
    """A feet-to-world-units calibration for one family of vehicles.

    `reference_ft` is the prototype length that should fill `reference_slot`
    eighths, minus a fixed visible coupling gap.
    """

    __slots__ = ("reference_ft", "reference_slot", "coupling_gap", "name")

    def __init__(self, reference_ft, reference_slot=8, coupling_gap=0.3,
                 name=None):
        if reference_ft <= 0:
            raise ValueError("reference_ft must be positive")
        if not 1 <= reference_slot <= 8:
            raise ValueError("reference_slot must be 1..8")
        self.reference_ft = float(reference_ft)
        self.reference_slot = int(reference_slot)
        self.coupling_gap = float(coupling_gap)
        self.name = name

    @property
    def units_per_foot(self):
        return (self.reference_slot - self.coupling_gap) / self.reference_ft

    def drawn_length(self, length_ft, slot, overhang=0.0):
        """World units to draw, honouring the prototype but capped by the slot.

        `overhang` is the fraction of the slot the sprite is allowed to run
        past, for a set that carries the overflow on neighbouring near-zero-
        length articulated parts - see the longsprite module. It is 0 by
        default, because a sprite that overruns its slot in a set with nowhere
        to put the overhang simply draws over the next vehicle.
        """
        if slot <= self.coupling_gap:
            raise ValueError(
                "length {} leaves no room for a {} unit coupling gap"
                .format(slot, self.coupling_gap))
        limit = slot * (1.0 + overhang) - self.coupling_gap
        return min(length_ft * self.units_per_foot, limit)

    def is_capped(self, length_ft, slot, overhang=0.0):
        return (length_ft * self.units_per_foot
                > self.drawn_length(length_ft, slot, overhang) + 1e-6)

    def slot_for(self, length_ft):
        """The smallest NML `length` that fits this prototype without capping."""
        need = length_ft * self.units_per_foot + self.coupling_gap
        for slot in range(1, 9):
            if slot >= need - 1e-9:
                return slot
        return 8

    def fit(self, model, length_ft, slot, overhang=0.0):
        """Scale a model along x to its prototype length, centred on the origin.

        Returns (model, drawn_length). Models are usually laid out at roughly
        twice final scale, where a bogie is more than one unit long and the
        detail work - door pitch, cab fractions, bogie inset - is easier to
        reason about; this brings them down at the end.
        """
        model = Model(model)
        raw = model.length
        if raw <= 0:
            raise ValueError("model has no extent along x")
        (x0, x1), _, _ = model.bbox()
        mid = (x0 + x1) / 2.0
        drawn = self.drawn_length(length_ft, slot, overhang)
        return (model.translated(dx=-mid).scaled(sx=drawn / raw), drawn)

    def __repr__(self):
        return "LengthScale({} ft fills {}/8{})".format(
            self.reference_ft, self.reference_slot,
            ", {!r}".format(self.name) if self.name else "")


#: Mainline rail: an 85 ft coach fills an 8/8 slot.
RAIL = LengthScale(85.0, name="rail")
#: Road: a 45 ft highway coach fills an 8/8 slot, because a bus at the rail
#: scale is seven pixels long and cannot carry any detail at all.
ROAD = LengthScale(45.0, name="road")
#: Narrow gauge and tram stock, drawn a little more generously than mainline.
TRAM = LengthScale(70.0, name="tram")
