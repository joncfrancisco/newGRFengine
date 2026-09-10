#!/usr/bin/env python3
"""
One double-decker passenger carriage, built to exercise newGRFengine end to
end: model -> render -> sheet -> NML -> compiled .grf.

Run it from this directory:

    python3 build.py            render, write the NML, compile with nmlc
    python3 build.py --no-grf   everything except the nmlc call

Nothing about a double-decker needs a new primitive. Its silhouette comes
entirely from height: the body is the same box() as the single-level `coach`
in examples/demo, but the complete vehicle is about 15% taller, with two
window_row() bands separated by a belt decal marking the floor between levels
and doors tall enough to span both levels at the vestibule.
"""

import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__),
                                                "..", "..")))

from newgrfengine import (COMPANY, GRID, Material, Project, Vehicle, bogies,
                          box, doors, ribs, roof_pod, side_decal, underframe,
                          window_row)
from newgrfengine import nmlwrite as nw
from newgrfengine.materials import shade

HERE = os.path.dirname(os.path.abspath(__file__))

STEEL = Material((208, 213, 219), name="stainless")
ROOF = Material((112, 118, 124), name="roof")
GLASS = Material((48, 60, 74), name="glass")
BELT = Material((150, 154, 160), name="belt rail")

HALF_W = 1.75   # a 10 ft 6 rail car, same width as the demo's single-level coach


def bilevel_coach():
    """A stainless bi-level commuter coach: two full rows of windows.

    Running gear and floor height match the demo `coach` exactly - a
    double-decker still rides on one pair of bogies, and the interesting
    part is entirely what happens above the floor line.
    """
    hw = HALF_W
    model = bogies(14.5, hw, top=2.55, inset=2.3)
    model += underframe(14.5, hw, 2.3, 3.35)
    model += box(-7.25, 7.25, -hw, hw, 3.15, 10.25, STEEL, top_mat=STEEL)
    model += box(-6.95, 6.95, -hw * 0.87, hw * 0.87, 10.25, 10.8, ROOF,
                top_mat=ROOF)
    model += ribs(-7.05, 7.05, 3.6, 10.25, hw, shade(STEEL, 0.86))
    model += window_row(-6.2, 6.2, 4.0, 5.4, hw, 7, GLASS)      # lower level
    model += side_decal(-7.0, 7.0, 5.7, 6.1, hw, BELT)          # inter-level floor
    model += window_row(-6.2, 6.2, 6.35, 8.7, hw, 7, GLASS)     # upper level
    model += doors([-5.25, 5.25], 3.35, 8.9, hw, shade(STEEL, 0.78))
    model += roof_pod(-2.2, 2.2, hw, 10.8)
    model += side_decal(-7.0, 7.0, 9.15, 9.7, hw, COMPANY)
    return model


def make_project():
    project = Project(
        name="bilevel",
        grfid="NGE\\02",
        title="newGRFengine Bi-Level Coach",
        description="One double-decker passenger carriage, rendered by "
                    "newGRFengine to exercise the renderer end to end.",
        version=1,
        out_dir=HERE,
        layout=GRID,
        railtypetable=("RAIL", "ELRL"),
    )
    project.add(Vehicle(
        ident="bilevel", name="Demonstrator Bi-Level Coach",
        model=bilevel_coach, length_ft=85, slot=8,
        properties={
            "introduction_date": nw.date(1990, 1, 1),
            "track_type": "RAIL",
            "running_cost_base": "RUNNING_COST_ELECTRIC",
            "speed": nw.mph(100), "power": nw.hp(0), "weight": nw.tons(48),
            "tractive_effort_coefficient": 0.30,
            "air_drag_coefficient": 0.05,
            "cost_factor": 46, "running_cost_factor": 15,
            "model_life": "VEHICLE_NEVER_EXPIRES", "vehicle_life": 30,
            "reliability_decay": 16,
            "refittable_cargo_classes": nw.bitmask("CC_PASSENGERS"),
            "default_cargo_type": "PASS", "cargo_capacity": 88,
            "loading_speed": 20,
            "misc_flags": nw.bitmask("TRAIN_FLAG_2CC"),
        },
        purchase="{BLACK}Two full rows of windows over one set of bogies.",
    ))
    return project


def main():
    project = make_project()
    paths = project.build(compile_grf="--no-grf" not in sys.argv)
    paths["consist"] = project.write_consist(
        ["bilevel", "bilevel"], direction=1)
    print()
    for key in sorted(paths):
        print("{:<10} {}".format(key, os.path.relpath(paths[key], HERE)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
