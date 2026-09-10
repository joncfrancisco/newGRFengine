"""
Tests for the parts of the engine where being wrong is silent.

Almost everything here is about arithmetic that produces a picture. A sprite
that is one pixel out, or a length calibration off by a factor of two, does not
raise anything - it compiles, it loads, and it looks slightly wrong in a way
that is hard to attribute. These pin down the properties that would otherwise
only be checked by eye.
"""

import math
import os
import subprocess
import sys

import numpy as np
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from newgrfengine import (COMPANY, GRID, RAIL, ROAD, TIGHT, Lighting, Model,
                          SpriteSheet, Vehicle, box, direction_angle, loft,
                          prism, project, render_model, render_purchase,
                          section, window_row)
from newgrfengine.geometry import TILE_PX, TILE_UNITS, VEHICLE_LENGTH
from newgrfengine.longsprite import (clip_x, render_long, split_overhang,
                                     step_vector)
from newgrfengine.palette import CC1_RAMP, PAL, SAFE, SAFE_2CC, Quantiser
from newgrfengine.parts import bogies
from newgrfengine.render import SIDE_ON


# ------------------------------------------------------------- projection --

def test_projection_matches_openttd_tile():
    """One tile must project to 64 x 32 px, or nothing lines up with the map."""
    corner_x = project((TILE_UNITS, 0.0, 0.0))
    corner_y = project((0.0, TILE_UNITS, 0.0))
    assert corner_y[0] - corner_x[0] == TILE_PX[0]
    assert (corner_x[1] + corner_y[1]) == TILE_PX[1]


def test_height_projects_straight_up():
    assert project((0, 0, 1)) == (0.0, -1.0)


def test_direction_two_is_exactly_broadside():
    """Purchase sprites depend on this: direction 2 must be pure horizontal."""
    angle = direction_angle(SIDE_ON)
    from newgrfengine.geometry import rotate_z
    dx, dy = project(rotate_z((1.0, 0.0, 0.0), math.cos(angle), math.sin(angle)))
    assert dy == pytest.approx(0.0, abs=1e-9)
    assert dx > 0, "the nose should point right in the purchase window"


def test_diagonal_step_is_the_tile_diagonal():
    dx, dy = step_vector(1)
    assert (dx, dy) == pytest.approx((2.0, -1.0))


# ------------------------------------------------------------------ scale --

def test_a_full_length_vehicle_is_half_a_tile():
    """The unit trap: VEHICLE_LENGTH is 8 against a tile's 16."""
    assert VEHICLE_LENGTH * 2 == TILE_UNITS


def test_reference_prototype_fills_its_slot():
    assert RAIL.drawn_length(85, 8) == pytest.approx(8 - RAIL.coupling_gap)


def test_shorter_prototype_draws_shorter_in_the_same_slot():
    """The coarseness trap: two sizes in one slot must not draw the same."""
    short = RAIL.drawn_length(65, 8)
    long = RAIL.drawn_length(85, 8)
    assert short < long
    assert short / long == pytest.approx(65.0 / 85.0, rel=1e-6)


def test_a_generous_estimate_cannot_overrun_the_slot():
    assert RAIL.drawn_length(200, 4) == pytest.approx(4 - RAIL.coupling_gap)
    assert RAIL.is_capped(200, 4)


def test_overhang_lets_a_sprite_past_its_slot_deliberately():
    assert RAIL.drawn_length(120, 8, overhang=0.25) > 8


def test_road_scale_is_larger_than_rail():
    assert ROAD.units_per_foot > RAIL.units_per_foot
    assert ROAD.drawn_length(45, 8) == pytest.approx(RAIL.drawn_length(85, 8))


def test_fit_centres_and_scales():
    model = box(2, 10, -1, 1, 0, 4, (1, 2, 3))
    fitted, drawn = RAIL.fit(model, 85, 8)
    (x0, x1), _, _ = fitted.bbox()
    assert x0 == pytest.approx(-x1)
    assert fitted.length == pytest.approx(drawn)


def test_slot_for_picks_the_smallest_slot_that_does_not_cap():
    for ft in (30, 51, 65, 85):
        slot = RAIL.slot_for(ft)
        assert not RAIL.is_capped(ft, slot)
        assert slot == 1 or RAIL.is_capped(ft, slot - 1)


# --------------------------------------------------------------- palette --

def test_safe_indices_avoid_every_reserved_range():
    from newgrfengine.palette import ANIMATED, CC1_RAMP, PURE_WHITE
    for index in (0, PURE_WHITE):
        assert index not in SAFE
    assert not set(SAFE) & set(CC1_RAMP)
    assert not set(SAFE) & set(ANIMATED)


def test_2cc_safe_indices_also_avoid_the_second_ramp():
    from newgrfengine.palette import CC2_RAMP
    assert set(SAFE_2CC) & set(CC2_RAMP) == set()
    assert set(SAFE) & set(CC2_RAMP), "SAFE keeps the green ramp; SAFE_2CC drops it"


def test_quantiser_returns_only_allowed_indices():
    q = Quantiser(SAFE)
    rgb = np.random.RandomState(0).randint(0, 256, (16, 16, 3)).astype(float)
    out = q(rgb)
    assert set(np.unique(out)).issubset(set(SAFE))


def test_quantiser_is_exact_on_palette_colours():
    q = Quantiser(SAFE)
    for index in (1, 40, 100, 197):
        assert q.index_of(tuple(PAL[index])) == index


# ------------------------------------------------------------- rendering --

def _railcar(length=14.0, half_w=1.75):
    model = box(-length / 2, length / 2, -half_w, half_w, 3.0, 9.0, (206, 212, 218))
    model += bogies(length, half_w)
    model += window_row(-length / 2 + 1, length / 2 - 1, 6.2, 8.0, half_w, 6,
                        (48, 60, 74))
    return RAIL.fit(model, 85, 8)[0]


def test_renders_eight_directions_none_empty():
    sprites = render_model(_railcar())
    assert len(sprites) == 8
    assert all(not s.is_empty() for s in sprites)


def test_sprites_are_cropped_tight():
    for sprite in render_model(_railcar()):
        assert sprite.indices[0].any() and sprite.indices[-1].any()
        assert sprite.indices[:, 0].any() and sprite.indices[:, -1].any()


def test_opposite_directions_are_mirror_images_in_width():
    sprites = render_model(_railcar())
    for a, b in ((0, 4), (1, 5), (2, 6), (3, 7)):
        assert sprites[a].width == sprites[b].width


def test_broadside_width_follows_the_projection():
    """A vehicle 7.7 units long, seen square, must be 7.7 * 2*sqrt(2) px wide."""
    model = _railcar()
    sprite = render_model(model)[SIDE_ON]
    expected = model.length * 2.0 * math.sqrt(2.0)
    assert abs(sprite.width - expected) <= 2


def test_company_colour_lands_on_the_ramp_and_nowhere_near_it():
    model = box(-6, 6, -1.5, 1.5, 3, 8, COMPANY)
    used = set(int(i) for i in np.unique(render_model(model)[SIDE_ON].indices))
    used.discard(0)
    assert used, "the model should have painted something"
    assert used.issubset(set(CC1_RAMP)), (
        "a wholly company-coloured model must quantise entirely onto the ramp, "
        "or it comes out of the depot half repainted")


def test_company_colour_keeps_its_shading():
    """A CC body must use several ramp entries, or it reads as a silhouette."""
    model = box(-6, 6, -1.5, 1.5, 3, 8, COMPANY)
    used = set(int(i) for i in np.unique(render_model(model)[1].indices))
    used.discard(0)
    assert len(used) >= 2


def test_purchase_sprite_is_the_broadside_view():
    model = _railcar()
    assert (render_purchase(model).indices ==
            render_model(model)[SIDE_ON].indices).all()


def test_unlit_material_is_not_shaded():
    from newgrfengine.materials import Material
    lamp = Material((250, 246, 210), unlit=True)
    lighting = Lighting()
    from newgrfengine.geometry import Quad
    quad = Quad([(0, 0, 0)] * 4, lamp, (0, 1, 0))
    assert lighting.factor(quad, (0, 1, 0)) == 1.0
    assert lighting.factor(quad, (1, 0, 0)) == 1.0


def test_layers_beat_depth():
    """A decal must win against the face it decorates from every direction."""
    from newgrfengine.materials import L_WINDOW
    from newgrfengine.primitives import side_decal
    body = box(-6, 6, -1.5, 1.5, 3, 8, (200, 200, 200))
    glass = side_decal(-4, 4, 5, 7, 1.5, (20, 30, 40), layer=L_WINDOW)
    glass_index = Quantiser(SAFE).index_of((20, 30, 40))
    for direction in range(8):
        sprite = render_model(body + glass)[direction]
        if direction in (0, 4):
            continue                      # end-on: the flanks are edge-on
        assert glass_index in set(int(i) for i in np.unique(sprite.indices))


# ----------------------------------------------------------- long sprites --

def _long_model():
    hw = 1.6
    nose = [section(-6, hw, 3, 9), section(2.0, hw, 3, 9),
            section(4.2, hw * 0.86, 3, 8.4, half_w_top=hw * 0.5),
            section(5.6, hw * 0.55, 3.1, 7.4, half_w_top=hw * 0.22),
            section(6.4, hw * 0.22, 3.4, 6.4, half_w_top=hw * 0.08)]
    model = loft(nose, (226, 230, 236), top_mat=(120, 126, 132))
    model += bogies(12, hw, inset=2.2)
    return RAIL.fit(model, 106, 8, overhang=0.25)[0]


def test_clipping_preserves_the_whole_model():
    model = _long_model()
    parts = split_overhang(model, 8)
    assert len(parts["front"]) and len(parts["back"]) and len(parts["body"])
    total = sum(len(p) for p in parts.values())
    assert total >= len(model), "clipping splits faces, it does not drop them"


def test_clip_respects_the_plane():
    model = box(-6, 6, -1, 1, 0, 4, (1, 2, 3))
    kept = clip_x(model, x_min=2.0)
    xs = [p[0] for q in kept for p in q.pts]
    assert min(xs) >= 2.0 - 1e-9


def _compose(pieces):
    """Lay sprites down at their reference points and return the composite."""
    placed = []
    for sprite, units in pieces:
        if sprite.is_empty():
            continue
        sx, sy = step_vector(sprite.direction)
        placed.append((sprite, int(round(sprite.offset_x + units * sx)),
                       int(round(sprite.offset_y + units * sy))))
    x0 = min(x for _, x, _ in placed)
    y0 = min(y for _, _, y in placed)
    x1 = max(x + s.width for s, x, _ in placed)
    y1 = max(y + s.height for s, _, y in placed)
    canvas = np.zeros((y1 - y0, x1 - x0), dtype=np.uint8)
    for sprite, x, y in placed:
        region = canvas[y - y0:y - y0 + sprite.height,
                        x - x0:x - x0 + sprite.width]
        mask = sprite.indices != 0
        region[mask] = sprite.indices[mask]
    return canvas, x0, y0


def test_long_sprite_pieces_reassemble_exactly():
    """The point of tagging: three pieces on three parts == one full sprite."""
    parts = render_long(_long_model(), 8)
    for d in range(8):
        whole = _compose([(parts["full"][d], 0)])
        pieces = _compose([(parts["back"][d], -8), (parts["body"][d], 0),
                           (parts["front"][d], 8)])
        assert whole[1:] == pieces[1:], "direction {} is misaligned".format(d)
        assert (whole[0] == pieces[0]).all(), "direction {} differs".format(d)


def test_overhang_actually_overhangs():
    parts = render_long(_long_model(), 8)
    assert any(not s.is_empty() for s in parts["front"] + parts["back"])


# ----------------------------------------------------------------- sheets --

def _sheet(layout):
    sheet = SpriteSheet("test", layout=layout)
    for name in ("a", "b"):
        model = _railcar()
        sheet.add(name, render_model(model), purchase=render_purchase(model))
    return sheet


@pytest.mark.parametrize("layout", [TIGHT, GRID])
def test_sheet_places_every_sprite_inside_the_image(layout):
    sheet = _sheet(layout)
    width, height = sheet.layout_sheet()
    for row in sheet.rows:
        boxes = row.boxes + ([row.purchase_box] if row.purchase else [])
        for left, top, w, h in boxes:
            assert 0 <= left and left + w <= width
            assert 0 <= top and top + h <= height


@pytest.mark.parametrize("layout", [TIGHT, GRID])
def test_sheet_template_rectangles_hold_the_right_pixels(layout):
    """The template is only correct if reading it back gives the sprite."""
    sheet = _sheet(layout)
    image = np.asarray(sheet.image())
    for row in sheet.rows:
        for (left, top, w, h), sprite in zip(row.boxes, row.sprites):
            if layout == GRID:
                # In grid layout the cell is padded around the sprite; check
                # the sprite sits where the shared offsets say it does.
                cell_w, cell_h = sheet.cell
                ox, oy = sheet.origin
                column = row.sprites.index(sprite)
                x = column * cell_w + ox + sprite.offset_x
                y = row.top + oy + sprite.offset_y
                assert (image[y:y + sprite.height,
                              x:x + sprite.width] == sprite.indices).all()
            else:
                assert (image[top:top + h, left:left + w] == sprite.indices).all()


def test_grid_layout_rejects_mixed_view_counts():
    sheet = SpriteSheet("mixed", layout=GRID)
    model = _railcar()
    sheet.add("a", render_model(model))
    sheet.add("b", render_model(model)[:4])
    with pytest.raises(ValueError):
        sheet.layout_sheet()


def test_purchase_sprite_gets_its_own_template():
    for layout in (TIGHT, GRID):
        nml = _sheet(layout).nml_templates()
        assert "_buy" in nml
        sets = _sheet(layout).nml_spritesets("sprites/test.png")
        assert "ss_a_buy" in sets and "ss_a," in sets


def test_sheet_image_is_paletted():
    image = _sheet(TIGHT).image()
    assert image.mode == "P"
    assert image.getpalette()[:3] == [0, 0, 255]     # index 0, transparent blue


# ---------------------------------------------------------------- models --

def test_models_add_without_mutating():
    a = box(0, 1, 0, 1, 0, 1, (1, 1, 1))
    b = box(2, 3, 0, 1, 0, 1, (2, 2, 2))
    before = len(a)
    assert len(a + b) == before + len(b)
    assert len(a) == before


def test_transforms_return_copies():
    model = box(0, 2, -1, 1, 0, 1, (1, 1, 1))
    moved = model.translated(dx=5)
    assert model.bbox()[0][0] == 0.0
    assert moved.bbox()[0][0] == 5.0


def test_recolouring_swaps_by_rgb_or_material():
    from newgrfengine.materials import Material
    red = Material((200, 0, 0))
    model = box(0, 1, 0, 1, 0, 1, (1, 2, 3))
    assert model.recoloured({(1, 2, 3): red}).materials() == [red]
    assert model.recoloured({Material((1, 2, 3)): red}).materials() == [red]


def test_mirroring_keeps_faces_outward():
    model = box(1, 3, -1, 1, 0, 2, (1, 1, 1))
    for original, mirrored in zip(model, model.mirrored_x()):
        assert mirrored.normal[0] == pytest.approx(-original.normal[0])


def test_loft_of_two_identical_sections_is_a_box():
    a = loft([section(-2, 1, 0, 2), section(2, 1, 0, 2)], (1, 1, 1))
    b = box(-2, 2, -1, 1, 0, 2, (1, 1, 1))
    assert a.bbox() == b.bbox()


def test_prism_normals_are_unit_length():
    for quad in prism(-2, 2, 0, 3, 1.5, 1.0, (1, 1, 1), facets=12):
        assert sum(c * c for c in quad.normal) == pytest.approx(1.0)


def test_tagged_rejects_a_tag_outside_the_8bpp_label_range():
    """tag ends up in an 8bpp label image (render.py); out of range either
    collides with the untagged value or clamps silently. See issue #18."""
    model = box(0, 1, 0, 1, 0, 1, (1, 1, 1))
    with pytest.raises(ValueError):
        model.tagged(0)
    with pytest.raises(ValueError):
        model.tagged(256)


def test_tagged_accepts_the_full_8bpp_label_range():
    model = box(0, 1, 0, 1, 0, 1, (1, 1, 1))
    assert model.tagged(1).quads[0].tag == 1
    assert model.tagged(255).quads[0].tag == 255


# ------------------------------------------------------------ housekeeping --

def test_running_gear_materials_are_all_exported():
    """`from newgrfengine import *` is the documented entry point (README); a
    material missing from __all__ cannot be reached that way. Issue #18."""
    import newgrfengine as ng
    for name in ("BOGIE", "WHEEL", "UNDER", "PANTO", "ROOF_POD", "LIGHT",
                "TAIL"):
        assert hasattr(ng, name), name
        assert name in ng.__all__, name


def test_vehicle_rejects_a_slot_outside_1_to_8():
    """slot is the NML `length` property, in eighths of a tile. Unchecked, a
    typo like slot=18 used to render happily and only fail much later, inside
    nmlc, with a message that did not point back at the vehicle. Issue #18."""
    model = box(-6, 6, -1.5, 1.5, 3, 8, (200, 200, 200))
    with pytest.raises(ValueError):
        Vehicle("a", "A", model, 85, 18)
    with pytest.raises(ValueError):
        Vehicle("a", "A", model, 85, 0)


# ------------------------------------------------------------------ build --

DEMO = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                    "examples", "demo")


@pytest.mark.skipif(not os.path.isdir(DEMO), reason="demo not present")
def test_demo_project_generates_valid_nml():
    sys.path.insert(0, DEMO)
    import build as demo_build
    project = demo_build.make_project()
    project.render(verbose=False)
    text = project.nml_text()
    assert "grf {" in text and "item(FEAT_TRAINS, railcar)" in text
    assert text.count("template tmpl_") == 2     # grid layout: views and buy
    assert "spriteset(ss_bus_buy," in text


@pytest.mark.skipif(not os.path.isdir(DEMO), reason="demo not present")
def test_demo_compiles_if_nmlc_is_available():
    try:
        subprocess.run(["nmlc", "--version"], capture_output=True)
    except (OSError, FileNotFoundError):
        pytest.skip("nmlc not installed")
    result = subprocess.run([sys.executable, "build.py"], cwd=DEMO,
                            capture_output=True, text=True)
    assert result.returncode == 0, result.stdout + result.stderr
    assert os.path.exists(os.path.join(DEMO, "demo.grf"))
