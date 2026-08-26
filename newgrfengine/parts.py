"""
Vehicle vocabulary: the sub-assemblies almost every model wants.

These are not primitives - each one is a handful of boxes and decals in an
arrangement that says something specific about the vehicle. What is under a
body is most of what tells the eye which kind of vehicle it is looking at,
before any livery goes on: a pair of bogies inset from the ends reads as a
rail car, two or three plain axles read as a bus, three trucks with a bellows
between the sections read as an articulated tram.
"""

from __future__ import annotations

from .materials import L_LIGHT, L_TEXTURE, L_WINDOW, Material
from .model import Model
from .primitives import box, end_decal, side_decal, strut, top_decal

# Default greys for running gear. Liveries override the body; almost nobody
# overrides what is under it, so these carry sensible values.
BOGIE = Material((38, 40, 44), name="bogie")
WHEEL = Material((24, 25, 27), name="wheel")
UNDER = Material((46, 48, 52), name="underframe")
PANTO = Material((58, 60, 64), name="pantograph")
ROOF_POD = Material((78, 84, 90), name="roof pod")
LIGHT = Material((250, 246, 210), unlit=True, name="headlight")
TAIL = Material((210, 46, 40), unlit=True, name="tail light")


def bogies(length, half_w, top=2.45, inset=2.2, frame=1.55, wheel_h=1.35,
           bogie_mat=BOGIE, wheel_mat=WHEEL, axles=2, spacing=1.3):
    """A pair of bogies inset from each end - the rail-vehicle signature."""
    q = Model()
    bw = half_w * 0.80
    for sign in (-1, 1):
        cx = sign * (length / 2.0 - inset)
        q += box(cx - frame, cx + frame, -bw, bw, 0.85, top, bogie_mat)
        first = cx - spacing * (axles - 1) / 2.0
        for i in range(axles):
            wx = first + i * spacing - 0.5
            q += box(wx, wx + 1.0, -bw - 0.18, bw + 0.18, 0.0, wheel_h, wheel_mat)
    return q


def truck(cx, half_w, top=2.0, frame=1.5, wheel_h=1.35, bogie_mat=BOGIE,
          wheel_mat=WHEEL):
    """One bogie at an arbitrary position: centre trucks on articulated cars."""
    bw = half_w * 0.80
    q = box(cx - frame, cx + frame, -bw, bw, 0.85, top, bogie_mat)
    for wx in (cx - 1.15, cx + 0.15):
        q += box(wx, wx + 1.0, -bw - 0.18, bw + 0.18, 0.0, wheel_h, wheel_mat)
    return q


def axles(xs, half_w, top=1.45, width=1.0, mat=WHEEL):
    """Plain axles under a road vehicle: no bogie frame, wheels at the body edge.

    This one difference does most of the work of making a bus look like a bus
    rather than a short coach. A rail bogie is a visible box between the wheels;
    a bus has nothing there at all.
    """
    q = Model()
    for x in xs:
        q += box(x - width / 2.0, x + width / 2.0, -half_w - 0.12, half_w + 0.12,
                 0.0, top, mat)
    return q


def underframe(length, half_w, z0, z1, mat=UNDER, inset=1.2):
    """The dark mass of equipment between the floor and the running gear."""
    return box(-length / 2.0 + inset, length / 2.0 - inset,
               -half_w * 0.9, half_w * 0.9, z0, z1, mat)


def pantograph(cx, half_w, z_roof, up=1.35, mat=PANTO):
    """A folded pantograph.

    Drawn as three slabs rather than as arms. At this size a correctly modelled
    pantograph is one or two grey pixels either way, and the slab version reads
    as "there is something on the roof here" more reliably than the truth does.
    """
    q = box(cx - 1.5, cx + 1.5, -half_w * 0.62, half_w * 0.62,
            z_roof, z_roof + 0.30, mat)
    q += box(cx - 0.35, cx + 0.35, -half_w * 0.30, half_w * 0.30,
             z_roof + 0.30, z_roof + up - 0.28, mat)
    q += box(cx - 1.7, cx + 1.7, -half_w * 0.55, half_w * 0.55,
             z_roof + up - 0.28, z_roof + up, mat)
    return q


def trolley_poles(x0, x1, z0, z1, half_w, mat=PANTO, spread=0.5, thick=0.16):
    """Two poles laid back along a roof. Needs strut(): these lean."""
    q = Model()
    for sign in (-1, 1):
        q += strut(x0, z0, x1, z1, sign * half_w * spread, thick, mat)
    return q


def roof_pod(x0, x1, half_w, z_roof, height=0.35, mat=ROOF_POD, span=0.46):
    """Air conditioning, battery packs, resistor banks: a low box on the roof."""
    return box(x0, x1, -half_w * span, half_w * span, z_roof, z_roof + height, mat)


def headlights(x, sign, half_w, z0, z1, mat=LIGHT, inner=0.36, outer=0.72):
    """A pair of lights on an end face, unlit so they read from every angle."""
    q = end_decal(x, sign, -half_w * outer, -half_w * inner, z0, z1, mat,
                  layer=L_LIGHT)
    q += end_decal(x, sign, half_w * inner, half_w * outer, z0, z1, mat,
                   layer=L_LIGHT)
    return q


def cab_glass(x_end, sign, half_w, z0, z1, mat, depth=2.4, layer=L_WINDOW):
    """A windscreen wrapping from the end face round onto both flanks."""
    x_in = x_end - sign * depth
    lo, hi = min(x_end, x_in), max(x_end, x_in)
    q = side_decal(lo + 0.4, hi - 0.4, z0, z1, half_w, mat, layer=layer)
    q += end_decal(x_end, sign, -half_w * 0.76, half_w * 0.76, z0, z1, mat,
                   layer=layer)
    return q


def bellows(x, half_w, z0, z1, z_roof, mat, width=0.26):
    """The concertina at an articulation, carried up over the roof.

    Taking it onto the roof is what makes the joint read from above, which in
    an isometric view is most of what you see of it.
    """
    q = side_decal(x - width, x + width, z0, z1, half_w, mat, layer=L_WINDOW)
    q += top_decal(x - width, x + width, -half_w * 0.86, half_w * 0.86,
                   z_roof, mat)
    return q


def doors(xs, z0, z1, half_w, mat, width=0.55, layer=None):
    """Door leaves down both flanks, at the given x positions."""
    from .materials import L_DOOR
    q = Model()
    for x in xs:
        q += side_decal(x - width, x + width, z0, z1, half_w, mat,
                        layer=L_DOOR if layer is None else layer)
    return q


def skirt(length, half_w, z0, z1, mat, inset=0.0):
    """A valance closing in the space between the floor and the rail."""
    return side_decal(-length / 2.0 + inset, length / 2.0 - inset, z0, z1,
                      half_w, mat, layer=L_TEXTURE)
