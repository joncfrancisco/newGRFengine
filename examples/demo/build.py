#!/usr/bin/env python3
"""
Build the demonstration set: models in, demo.grf out.

Run it from this directory:

    python3 build.py            render, write the NML, compile with nmlc
    python3 build.py --no-grf   everything except the nmlc call

The fleet table below is the only place any number about a vehicle lives. The
sprite sheet, the sprite templates, the spritesets, the item blocks and the
language file are all generated from it, so changing a figure means editing
one line and rebuilding - never editing the .pnml, which is overwritten.
"""

import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__),
                                                "..", "..")))

from newgrfengine import GRID, ROAD, ROADVEH, TRAIN, Project, Vehicle  # noqa: E402
from newgrfengine import nmlwrite as nw                                # noqa: E402

import models                                                          # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))

# ---------------------------------------------------------------- the fleet --
#
# length_ft is the prototype length over couplers; slot is the NML `length`
# property, in eighths of a tile. Both are needed and they are not the same
# thing: two prototypes of quite different size routinely land in the same
# slot, and drawing each to fill its slot is what makes every vehicle in a set
# come out the same length. See newgrfengine/scale.py.

FLEET = [
    dict(
        ident="railcar", name="Demonstrator EMU", model=models.railcar,
        length_ft=85, slot=8,
        properties={
            "introduction_date": nw.date(1968, 4, 1),
            "track_type": "ELRL",
            "engine_class": "ENGINE_CLASS_ELECTRIC",
            "running_cost_base": "RUNNING_COST_ELECTRIC",
            "speed": nw.mph(100), "power": nw.hp(1200), "weight": nw.tons(56),
            "tractive_effort_coefficient": 0.30,
            "air_drag_coefficient": 0.06,
            "cost_factor": 110, "running_cost_factor": 52,
            "model_life": "VEHICLE_NEVER_EXPIRES", "vehicle_life": 30,
            "reliability_decay": 20,
            "refittable_cargo_classes": nw.bitmask("CC_PASSENGERS"),
            "default_cargo_type": "PASS", "cargo_capacity": 44,
            "loading_speed": 20,
            "misc_flags": nw.bitmask("TRAIN_FLAG_MU", "TRAIN_FLAG_2CC"),
            "visual_effect_and_powered":
                "visual_effect_and_powered(VISUAL_EFFECT_ELECTRIC, 0, "
                "DISABLE_WAGON_POWER)",
        },
        purchase="{BLACK}A lofted cab front, five stations deep.{}"
                 "{GOLD}Electrified track only.",
    ),
    dict(
        ident="coach", name="Demonstrator Coach", model=models.coach,
        length_ft=85, slot=8,
        properties={
            "introduction_date": nw.date(1968, 4, 1),
            "track_type": "RAIL",
            "running_cost_base": "RUNNING_COST_ELECTRIC",
            "speed": nw.mph(100), "power": nw.hp(0), "weight": nw.tons(30),
            "tractive_effort_coefficient": 0.30,
            "air_drag_coefficient": 0.05,
            "cost_factor": 34, "running_cost_factor": 13,
            "model_life": "VEHICLE_NEVER_EXPIRES", "vehicle_life": 30,
            "reliability_decay": 16,
            "refittable_cargo_classes": nw.bitmask("CC_PASSENGERS"),
            "default_cargo_type": "PASS", "cargo_capacity": 40,
            "loading_speed": 20,
            "misc_flags": nw.bitmask("TRAIN_FLAG_2CC"),
        },
        purchase="{BLACK}Corrugated flanks and a row of seven bays.",
    ),
    dict(
        ident="steam", name="Demonstrator Pacific", model=models.steam,
        length_ft=70, slot=7,
        properties={
            "introduction_date": nw.date(1925, 1, 1),
            "track_type": "RAIL",
            "engine_class": "ENGINE_CLASS_STEAM",
            "running_cost_base": "RUNNING_COST_STEAM",
            "speed": nw.mph(80), "power": nw.hp(1600), "weight": nw.tons(130),
            "tractive_effort_coefficient": 0.20,
            "air_drag_coefficient": 0.09,
            "cost_factor": 80, "running_cost_factor": 90,
            "model_life": 40, "vehicle_life": 30, "reliability_decay": 26,
            "cargo_capacity": 0,
            "misc_flags": nw.bitmask("TRAIN_FLAG_2CC"),
            "visual_effect_and_powered":
                "visual_effect_and_powered(VISUAL_EFFECT_STEAM, 0, "
                "DISABLE_WAGON_POWER)",
        },
        purchase="{BLACK}A ten-facet prism for a boiler.",
    ),
    dict(
        ident="tram", name="Demonstrator LRV", model=models.tram,
        length_ft=90, slot=8,
        properties={
            "introduction_date": nw.date(2000, 4, 1),
            "track_type": "ELRL",
            "engine_class": "ENGINE_CLASS_ELECTRIC",
            "running_cost_base": "RUNNING_COST_ELECTRIC",
            "speed": nw.mph(55), "power": nw.hp(670), "weight": nw.tons(45),
            "tractive_effort_coefficient": 0.30,
            "air_drag_coefficient": 0.06,
            "cost_factor": 70, "running_cost_factor": 20,
            "model_life": "VEHICLE_NEVER_EXPIRES", "vehicle_life": 30,
            "reliability_decay": 14,
            "refittable_cargo_classes": nw.bitmask("CC_PASSENGERS"),
            "default_cargo_type": "PASS", "cargo_capacity": 70,
            "loading_speed": 40,
            "misc_flags": nw.bitmask("TRAIN_FLAG_MU", "TRAIN_FLAG_2CC"),
            "visual_effect_and_powered":
                "visual_effect_and_powered(VISUAL_EFFECT_ELECTRIC, 0, "
                "DISABLE_WAGON_POWER)",
        },
        purchase="{BLACK}Three sections over three trucks, with a bellows "
                 "at each joint.",
    ),
    dict(
        ident="bus", name="Demonstrator Bus", model=models.bus,
        length_ft=40, slot=8, feature=ROADVEH, scale=ROAD,
        properties={
            "introduction_date": nw.date(1960, 1, 1),
            "road_type": "ROAD",
            "running_cost_base": "RUNNING_COST_ROADVEH",
            "speed": nw.mph(55), "power": nw.hp(210), "weight": nw.tons(11),
            "tractive_effort_coefficient": 0.30,
            "air_drag_coefficient": 0.50,
            "cost_factor": 26, "running_cost_factor": 70,
            "model_life": "VEHICLE_NEVER_EXPIRES", "vehicle_life": 20,
            "reliability_decay": 20,
            "refittable_cargo_classes": nw.bitmask("CC_PASSENGERS"),
            "default_cargo_type": "PASS", "cargo_capacity": 34,
            "loading_speed": 20,
            "misc_flags": nw.bitmask("ROADVEH_FLAG_2CC"),
            "visual_effect": "VISUAL_EFFECT_DIESEL",
        },
        purchase="{BLACK}Drawn on the road scale, which is not the rail one.",
    ),
    dict(
        ident="trolleybus", name="Demonstrator Trolleybus",
        model=models.trolleybus, length_ft=36, slot=7,
        feature=ROADVEH, scale=ROAD,
        properties={
            "introduction_date": nw.date(1935, 1, 1),
            "road_type": "ROAD",
            "running_cost_base": "RUNNING_COST_ROADVEH",
            "speed": nw.mph(35), "power": nw.hp(150), "weight": nw.tons(10),
            "tractive_effort_coefficient": 0.30,
            "air_drag_coefficient": 0.50,
            "cost_factor": 22, "running_cost_factor": 60,
            "model_life": 40, "vehicle_life": 20, "reliability_decay": 24,
            "refittable_cargo_classes": nw.bitmask("CC_PASSENGERS"),
            "default_cargo_type": "PASS", "cargo_capacity": 26,
            "loading_speed": 20,
            "misc_flags": nw.bitmask("ROADVEH_FLAG_2CC"),
            "visual_effect": "VISUAL_EFFECT_ELECTRIC",
        },
        purchase="{BLACK}Poles laid back along the roof, because a box "
                 "cannot lean.",
    ),
]


def make_project():
    project = Project(
        name="demo",
        grfid="NGE\\01",
        title="newGRFengine Demonstration Set",
        description="Six vehicles rendered from 3D models by newGRFengine. "
                    "Every sprite offset in this GRF was computed from the "
                    "geometry rather than measured by hand.",
        version=1,
        out_dir=HERE,
        # GRID keeps one shared template and one cell size for the whole sheet,
        # so the PNG can be opened in a pixel editor and touched up by hand
        # without any offset moving. TIGHT packs harder and writes a template
        # per vehicle; it is what a set with long sprites wants.
        layout=GRID,
        railtypetable=("RAIL", "ELRL"),
        roadtypetable=("ROAD",),
    )
    for entry in FLEET:
        project.add(Vehicle(**entry))
    return project


def main():
    project = make_project()
    paths = project.build(compile_grf="--no-grf" not in sys.argv)
    paths["consist"] = project.write_consist(
        ["railcar", "coach", "coach"], direction=1)
    print()
    for key in sorted(paths):
        print("{:<10} {}".format(key, os.path.relpath(paths[key], HERE)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
