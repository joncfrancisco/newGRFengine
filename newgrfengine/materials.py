"""
Materials: a colour, plus what the renderer is allowed to do with it.

Three things separate a material from a bare RGB triple.

`cc` marks a surface as company-coloured. OpenTTD reserves two palette ramps
for that (see `palette`), and a face painted into one of them is repainted by
the game in the player's colours. The renderer resolves such a face to a ramp
index directly rather than quantising it, so the shading it would have got as
paint becomes a position in the ramp instead - which is what keeps a company-
coloured body reading as a 3D shape rather than a flat silhouette.

`unlit` opts a surface out of shading altogether. Headlights and marker lights
want the same value on every face of the vehicle whichever way it is pointing;
shading them makes the light on the shadowed side look switched off.

`layer` is paint order. Every decal in a vehicle model sits a hair above the
face it decorates, and floating-point depth sorting alone will not reliably
keep a window in front of the body it is cut into. An explicit layer settles
it: solids, then texture, then doors, then stripes, then glass, then lights.
"""

from __future__ import annotations

# Paint layers, low to high. A quad is sorted by (layer, depth), so anything
# in a higher layer wins against anything below it regardless of depth.
L_SOLID = 0
L_TEXTURE = 1
L_DOOR = 2
L_STRIPE = 3
L_WINDOW = 4
L_LIGHT = 5

#: What a decal lands on when nothing says otherwise.
L_DECAL = L_STRIPE

LAYER_NAMES = {
    L_SOLID: "solid", L_TEXTURE: "texture", L_DOOR: "door",
    L_STRIPE: "stripe", L_WINDOW: "window", L_LIGHT: "light",
}


class Material:
    """A paintable surface colour."""

    __slots__ = ("rgb", "cc", "unlit", "name")

    def __init__(self, rgb, cc=None, unlit=False, name=None):
        if cc not in (None, 1, 2):
            raise ValueError("cc must be None, 1 or 2, not {!r}".format(cc))
        self.rgb = tuple(int(v) for v in rgb)
        self.cc = cc
        self.unlit = bool(unlit)
        self.name = name

    def shade(self, factor):
        """A darker or lighter copy, keeping every other property."""
        rgb = tuple(max(0, min(255, int(round(v * factor)))) for v in self.rgb)
        return Material(rgb, cc=self.cc, unlit=self.unlit, name=self.name)

    def mix(self, other, t):
        other = material(other)
        rgb = tuple(int(round(a + (b - a) * t))
                    for a, b in zip(self.rgb, other.rgb))
        return Material(rgb, cc=self.cc, unlit=self.unlit, name=self.name)

    def __eq__(self, other):
        return (isinstance(other, Material) and self.rgb == other.rgb
                and self.cc == other.cc and self.unlit == other.unlit)

    def __hash__(self):
        return hash((self.rgb, self.cc, self.unlit))

    def __repr__(self):
        extra = ""
        if self.cc:
            extra += ", cc={}".format(self.cc)
        if self.unlit:
            extra += ", unlit=True"
        return "Material({}{}{})".format(
            self.rgb, extra, ", name={!r}".format(self.name) if self.name else "")


def material(value):
    """Coerce an RGB tuple, or a Material, to a Material."""
    if isinstance(value, Material):
        return value
    return Material(value)


def shade(value, factor):
    """Shade an RGB tuple or Material, returning the same kind of thing.

    Model code reaches for this constantly - a door leaf is the body colour at
    0.8, a corrugation line is the body colour at 0.86 - and wants back what it
    passed in, so a livery written as plain tuples stays plain tuples.
    """
    if isinstance(value, Material):
        return value.shade(factor)
    return tuple(max(0, min(255, int(round(v * factor)))) for v in value)


#: Company colour 1, used for a body that should follow the player's livery.
COMPANY = Material((110, 130, 180), cc=1, name="company")
#: Company colour 2, painted by the game only when the vehicle sets a 2CC flag.
COMPANY2 = Material((150, 120, 150), cc=2, name="company2")
