"""
Six vehicles, chosen so that between them they use every primitive.

    railcar      loft() - a cab front that actually tapers
    coach        ribs() and window_row() - what makes a flank read as a coach
    steam        prism() - a boiler is the one shape a box cannot fake
    tram         bellows() and truck() - three sections over three trucks
    bus          axles() at the road scale - no bogie frame, low floor
    trolleybus   strut() - poles laid back along a roof have to lean

The liveries are deliberately plain. This is a demonstration of a renderer,
not of a paint shop, and the interesting thing to look at in the output is
whether the shapes read at 24 pixels - not whether the stripes are pretty.

Everything is modelled at roughly twice final scale, where a bogie is more
than one world unit long and door pitch and cab fractions are easy to reason
about. LengthScale.fit() brings each model down to its prototype length at the
end, so these numbers never have to be thought about in final pixels.
"""

from newgrfengine import (COMPANY, Material, axles, bellows, bogies, box,
                          cab_glass, doors, end_decal, headlights, loft,
                          pantograph, prism, ribs, roof_pod, section,
                          side_decal, skirt, strut, top_decal, truck,
                          underframe, window_row)
from newgrfengine.materials import L_LIGHT, L_TEXTURE, L_WINDOW, shade

# ------------------------------------------------------------------ liveries --

STEEL = Material((208, 213, 219), name="stainless")
CREAM = Material((226, 222, 206), name="cream")
ROOF = Material((112, 118, 124), name="roof")
DARK_ROOF = Material((74, 78, 84), name="dark roof")
GLASS = Material((48, 60, 74), name="glass")
GLASS_PALE = Material((92, 116, 142), name="pale glass")
BOILER = Material((48, 50, 54), name="boiler")
BRASS = Material((176, 146, 68), name="brass")
BELLOWS = Material((56, 58, 62), name="bellows")
BUS_BODY = Material((214, 218, 222), name="bus body")
TROLLEY_BODY = Material((150, 156, 164), name="trolleybus body")

HALF_W = 1.75          # a 10 ft 6 rail car, in model units
BUS_HALF_W = 1.42      # an 8 ft 6 bus is visibly narrower, and should be


# -------------------------------------------------------------------- trains --

def railcar():
    """An electric railcar with a tapered cab front.

    The nose is five lofted stations rather than a box with a decal on it. At
    this size that is worth the trouble in exactly one way: the roof line comes
    down as the width pulls in, and the silhouette from the three-quarter views
    stops being a brick.
    """
    hw = HALF_W
    body = loft([
        section(-7.0, hw, 3.0, 9.0),
        section(3.2, hw, 3.0, 9.0),
        section(5.0, hw * 0.88, 3.0, 8.5, half_w_top=hw * 0.58),
        section(6.4, hw * 0.60, 3.1, 7.6, half_w_top=hw * 0.26),
        section(7.2, hw * 0.26, 3.4, 6.6, half_w_top=hw * 0.10),
    ], STEEL, top_mat=ROOF)

    model = bogies(14, hw, top=2.55, inset=2.3)
    model += underframe(14, hw, 2.3, 3.35)
    model += body
    model += box(-6.7, 3.0, -hw * 0.87, hw * 0.87, 9.0, 9.9, ROOF, top_mat=ROOF)
    model += window_row(-6.0, 2.4, 6.3, 8.1, hw, 6, GLASS)
    model += cab_glass(6.2, 1, hw * 0.62, 6.4, 7.6, GLASS)
    model += headlights(7.2, 1, hw * 0.26, 5.4, 5.9)
    model += doors([-5.0, 1.4], 3.2, 8.5, hw, shade(STEEL, 0.78))
    # A band in company colour, so a player's fleet reads as theirs. Company
    # colour resolves to a reserved palette ramp, and the renderer shades it by
    # picking a position in that ramp rather than by mixing paint.
    model += side_decal(-6.9, 5.6, 4.4, 5.6, hw, COMPANY)
    model += end_decal(7.2, 1, -hw * 0.24, hw * 0.24, 4.6, 5.6, COMPANY)
    model += pantograph(-3.4, hw, 9.9, up=1.3)
    return model


def coach():
    """A stainless trailer coach: the plainest thing in the set, on purpose."""
    hw = HALF_W
    model = bogies(14.5, hw, top=2.55, inset=2.3)
    model += underframe(14.5, hw, 2.3, 3.35)
    model += box(-7.25, 7.25, -hw, hw, 3.15, 8.7, STEEL, top_mat=STEEL)
    model += box(-6.95, 6.95, -hw * 0.87, hw * 0.87, 8.7, 9.7, ROOF, top_mat=ROOF)
    model += ribs(-7.05, 7.05, 3.6, 8.3, hw, shade(STEEL, 0.86))
    model += window_row(-6.2, 6.2, 5.95, 7.95, hw, 7, GLASS)
    model += doors([-5.25, 5.25], 3.35, 8.35, hw, shade(STEEL, 0.78))
    model += side_decal(-7.0, 7.0, 4.3, 5.0, hw, COMPANY)
    return model


def steam():
    """A 4-6-2 in outline: a boiler, a firebox, a cab and a stack.

    prism() is the whole reason this vehicle is in the demo. A boiler drawn as
    a box reads as a tank wagon from every angle; eight facets is enough to
    round it off, and the top facets take a lighter material so the barrel
    catches light the way a cylinder should.
    """
    hw = 1.55
    model = bogies(13.0, hw * 0.9, top=2.2, inset=2.6, wheel_h=2.0, frame=1.3)
    model += box(-6.5, 5.6, -hw * 0.86, hw * 0.86, 2.0, 3.4, shade(BOILER, 0.8))
    # barrel, smokebox, firebox
    model += prism(-2.4, 4.6, 0.0, 5.1, hw * 0.82, 1.85, BOILER,
                   facets=10, top_mat=shade(BOILER, 1.25))
    model += prism(4.6, 5.9, 0.0, 5.1, hw * 0.86, 1.9, shade(BOILER, 0.85),
                   facets=10)
    model += box(-4.4, -2.2, -hw * 0.94, hw * 0.94, 3.2, 6.4, BOILER)
    # cab
    model += box(-6.6, -4.2, -hw, hw, 3.4, 8.1, BOILER, top_mat=DARK_ROOF)
    model += side_decal(-6.0, -4.6, 6.1, 7.5, hw, GLASS, layer=L_WINDOW)
    model += end_decal(-6.6, -1, -hw * 0.7, hw * 0.7, 6.1, 7.5, GLASS,
                       layer=L_WINDOW)
    # chimney, dome, headlamp
    model += box(4.0, 4.9, -0.5, 0.5, 6.9, 8.0, BOILER)
    model += box(1.0, 2.0, -0.55, 0.55, 6.9, 7.6, BRASS)
    model += end_decal(5.9, 1, -0.45, 0.45, 5.4, 6.1,
                       Material((250, 246, 210), unlit=True), layer=L_LIGHT)
    model += side_decal(-6.5, 5.8, 3.4, 3.9, hw, BRASS, layer=L_TEXTURE)
    return model


def tram():
    """A double-articulated low-floor tram: three sections, three trucks.

    What separates this from a rail car is not the livery, it is the running
    gear and the height. There is a truck under the middle, a bellows at each
    joint carried up over the roof, and the whole body sits about a foot lower
    than a mainline car - which is most of what makes it read as street
    running rather than as a short EMU.
    """
    hw = 1.45
    length, joint = 15.4, 15.4 * 0.092
    model = bogies(length, hw, top=2.0, inset=2.9)
    model += truck(0.0, hw, top=2.0)
    model += underframe(length, hw, 1.75, 2.4, inset=1.0)
    model += box(-7.7, 7.7, -hw, hw, 2.2, 7.35, CREAM, top_mat=CREAM)
    model += box(-7.4, 7.4, -hw * 0.86, hw * 0.86, 7.35, 8.0, ROOF, top_mat=ROOF)
    model += roof_pod(2.0, 5.5, hw, 8.0)
    model += side_decal(-7.5, 7.5, 5.25, 6.93, hw, Material((40, 44, 50)),
                        layer=L_TEXTURE)
    for x in (-4.6, -1.4, 1.4, 4.6):
        model += doors([x], 2.35, 6.93, hw, shade(CREAM, 0.72), width=0.42)
        model += side_decal(x - 0.32, x + 0.32, 5.45, 6.73, hw, GLASS_PALE,
                            layer=L_WINDOW)
    for a, b in ((-7.0, -5.4), (-3.6, -2.2), (2.2, 3.6), (5.4, 7.0)):
        model += window_row(a, b, 5.45, 6.73, hw, 1, GLASS_PALE)
    for j in (-joint, joint):
        model += bellows(j, hw, 2.2, 7.35, 8.0, BELLOWS)
    for sign in (1, -1):
        model += cab_glass(sign * 7.7, sign, hw * 0.8, 5.4, 6.9, GLASS,
                           depth=2.2)
        model += headlights(sign * 7.7, sign, hw, 2.75, 3.25)
    model += side_decal(-7.5, 7.5, 3.0, 4.0, hw, COMPANY)
    model += pantograph(-4.6, hw, 8.0, up=1.25)
    return model


# ---------------------------------------------------------------- road stock --

def _bus_body(mat, roof_mat, poles=False, windscreen_wrap=True):
    """The shape both road vehicles share, so the livery is the only difference."""
    hw = BUS_HALF_W
    model = axles([-4.6, 4.2], hw, top=1.45)
    model += box(-6.4, 6.4, -hw, hw, 1.0, 6.4, mat, top_mat=roof_mat)
    model += box(-6.1, 6.1, -hw * 0.9, hw * 0.9, 6.4, 6.8, roof_mat,
                 top_mat=roof_mat)
    model += skirt(12.8, hw, 1.0, 1.9, shade(mat, 0.7))
    model += window_row(-5.6, 3.4, 4.3, 5.9, hw, 5, GLASS)
    model += doors([4.6], 1.3, 6.1, hw, shade(mat, 0.74), width=0.5)
    if windscreen_wrap:
        model += cab_glass(6.4, 1, hw * 0.9, 4.2, 6.0, GLASS, depth=1.6)
    model += headlights(6.4, 1, hw, 2.1, 2.7)
    model += side_decal(-6.3, 6.3, 3.2, 4.0, hw, COMPANY)
    model += end_decal(6.4, 1, -hw * 0.9, hw * 0.9, 6.05, 6.4,
                       Material((26, 28, 32)), layer=L_TEXTURE)   # destination sign
    if poles:
        # Two poles laid back along the roof. box() is axis-aligned and cannot
        # lean, which is the entire reason strut() exists.
        for sign in (-1, 1):
            model += strut(-1.0, 6.9, 5.6, 8.6, sign * hw * 0.45, 0.16,
                           Material((58, 60, 64)))
        model += box(-1.8, -0.6, -hw * 0.5, hw * 0.5, 6.8, 7.1,
                     Material((58, 60, 64)))
    return model


def bus():
    return _bus_body(BUS_BODY, Material((186, 190, 196)))


def trolleybus():
    return _bus_body(TROLLEY_BODY, Material((132, 138, 146)), poles=True)


MODELS = {
    "railcar": railcar,
    "coach": coach,
    "steam": steam,
    "tram": tram,
    "bus": bus,
    "trolleybus": trolleybus,
}
