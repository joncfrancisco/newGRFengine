"""
newGRFengine - an OpenTTD sprite renderer for building NewGRFs.

Vehicles are described as small 3D models - boxes, lofted noses, faceted
prisms, thin leaning slabs, and flat decals for windows, doors and liveries -
and projected into OpenTTD's own isometric mapping for all eight directions.
Because every direction comes off the same geometry, consists line up on
straight track and stay consistent through curves, and a livery change is a
dictionary rather than a repainting job.

The renderer's output is not just pixels. It knows where each sprite sits
relative to the vehicle's reference point, so it writes its own NML sprite
templates, offsets included - the part of building a set that is pure
arithmetic and entirely unforgiving.

    from newgrfengine import *

    body = box(-7, 7, -1.75, 1.75, 3.0, 9.0, (206, 212, 218))
    body += bogies(14, 1.75) + pantograph(0, 1.75, 9.0)

    model, drawn = RAIL.fit(body, length_ft=85, slot=8)
    sprites = render_model(model)

See `builder.Project` for the full render-to-.grf path, and the demo under
examples/ for a set that compiles.
"""

from .geometry import (DIRECTIONS, EPS, NUM_DIRS, TILE_UNITS, VEHICLE_LENGTH,
                       Lighting, Quad, direction_angle, project)
from .longsprite import render_long, split_overhang
from .materials import (COMPANY, COMPANY2, L_DECAL, L_DOOR, L_LIGHT, L_SOLID,
                        L_STRIPE, L_TEXTURE, L_WINDOW, Material, material,
                        shade)
from .model import Model
from .palette import PAL, SAFE, SAFE_2CC, Quantiser
from .parts import (LIGHT, PANTO, UNDER, WHEEL, axles, bellows, bogies,
                    cab_glass, doors, headlights, pantograph, roof_pod, skirt,
                    trolley_poles, truck, underframe)
from .preview import consist, contact_sheet
from .primitives import (box, end_decal, loft, plate, prism, ribs, section,
                         side_decal, strut, top_decal, window_row)
from .builder import ROADVEH, TRAIN, Project, Vehicle
from .render import (DEFAULT, RenderSpec, Sprite, render_direction,
                     render_model, render_purchase)
from .scale import RAIL, ROAD, TRAM, LengthScale
from .sheet import GRID, TIGHT, SpriteSheet

__version__ = "0.1.0"

__all__ = [
    "DIRECTIONS", "EPS", "NUM_DIRS", "TILE_UNITS", "VEHICLE_LENGTH",
    "Lighting", "Quad", "direction_angle", "project",
    "render_long", "split_overhang",
    "COMPANY", "COMPANY2", "L_DECAL", "L_DOOR", "L_LIGHT", "L_SOLID",
    "L_STRIPE", "L_TEXTURE", "L_WINDOW", "Material", "material", "shade",
    "Model", "PAL", "SAFE", "SAFE_2CC", "Quantiser",
    "LIGHT", "PANTO", "UNDER", "WHEEL", "axles", "bellows", "bogies",
    "cab_glass", "doors", "headlights", "pantograph", "roof_pod", "skirt",
    "trolley_poles", "truck", "underframe",
    "consist", "contact_sheet",
    "box", "end_decal", "loft", "plate", "prism", "ribs", "section",
    "side_decal", "strut", "top_decal", "window_row",
    "ROADVEH", "TRAIN", "Project", "Vehicle",
    "DEFAULT", "RenderSpec", "Sprite", "render_direction", "render_model",
    "render_purchase",
    "RAIL", "ROAD", "TRAM", "LengthScale",
    "GRID", "TIGHT", "SpriteSheet",
    "__version__",
]
