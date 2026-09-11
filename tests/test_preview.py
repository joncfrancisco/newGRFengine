"""Tests for preview spacing, bounds, and scale references."""

import numpy as np
import pytest

from newgrfengine.geometry import direction_angle, project, rotate_z
from newgrfengine.palette import rgb_of
from newgrfengine.preview import consist, contact_sheet
from newgrfengine.render import SIDE_ON, Sprite


def _dot(index=100):
    return Sprite(np.array([[index]], dtype=np.uint8), 0, 0, SIDE_ON)


def test_contact_sheet_raises_on_empty_input():
    with pytest.raises(ValueError):
        contact_sheet([])


def test_consist_raises_on_empty_input():
    with pytest.raises(ValueError):
        consist([])


def test_consist_steps_by_exactly_slot_times_step_vector():
    sprite = _dot(100)
    slot = 8
    direction = 1
    items = [([sprite] * 8, slot), ([sprite] * 8, slot)]

    canvas = np.asarray(consist(
        items, direction=direction, scale=1, background=(0, 0, 0)))
    ys, xs = np.where((canvas == rgb_of(100)).all(axis=-1))
    assert len(xs) == 2

    order = np.argsort(xs)
    dx = int(xs[order[1]]) - int(xs[order[0]])
    dy = int(ys[order[1]]) - int(ys[order[0]])
    angle = direction_angle(direction)
    step_x, step_y = project(rotate_z(
        (1.0, 0.0, 0.0), np.cos(angle), np.sin(angle)))
    assert dx == pytest.approx(round(slot * step_x), abs=1)
    assert dy == pytest.approx(round(slot * step_y), abs=1)


def test_consist_never_writes_outside_canvas_for_large_negative_offset():
    sprite = Sprite(np.array([[100]], dtype=np.uint8),
                    -1000, -1000, SIDE_ON)
    canvas = np.asarray(consist(
        [([sprite] * 8, 8)], direction=SIDE_ON, scale=1,
        background=(0, 0, 0)))
    assert (canvas == rgb_of(100)).all(axis=-1).any()


def test_contact_sheet_handles_a_large_negative_offset():
    sprite = Sprite(np.array([[100]], dtype=np.uint8),
                    -1000, -1000, SIDE_ON)
    canvas = np.asarray(contact_sheet(
        [("test", [sprite] * 8)], scale=1, label=False,
        background=(0, 0, 0), alt=(0, 0, 0)))
    assert (canvas == rgb_of(100)).all(axis=-1).any()


def test_contact_sheet_accepts_the_builtin_rail_reference():
    sprite = _dot()
    without = contact_sheet([("test", [sprite] * 8)], scale=1)
    with_reference = contact_sheet(
        [("test", [sprite] * 8)], scale=1, reference="rail_coach")
    assert with_reference.height > without.height


def test_consist_accepts_the_builtin_rail_reference():
    sprite = _dot()
    without = consist([([sprite] * 8, 8)], scale=1)
    with_reference = consist(
        [([sprite] * 8, 8)], scale=1, reference="rail_coach")
    assert with_reference.width > without.width


@pytest.mark.parametrize("function,args", [
    (contact_sheet, [("test", [_dot()] * 8)]),
    (consist, [([_dot()] * 8, 8)]),
])
def test_unknown_builtin_reference_is_rejected(function, args):
    with pytest.raises(ValueError, match="available: rail_coach"):
        function(args, reference="ship")


@pytest.mark.parametrize('direction', range(8))
@pytest.mark.parametrize('slots,distance', [
    ((8, 4), 6), ((4, 8), 6), ((8, 8), 8), ((5, 5), 5),
    ((5, 4), 5), ((4, 5), 4), ((1, 2), 2), ((2, 1), 1),
])
def test_consist_center_offsets_follow_openttd_in_rear_to_front_order(direction, slots, distance):
    image = np.asarray(consist(
        [([_dot(1)] * 8, slots[0]), ([_dot(2)] * 8, slots[1])],
        direction=direction, scale=1, background=(255, 0, 255)))
    centers = [np.argwhere((image == rgb_of(i)).all(axis=-1))[0][::-1]
               for i in (1, 2)]
    angle = direction_angle(direction)
    step = project(rotate_z((1, 0, 0), np.cos(angle), np.sin(angle)))
    np.testing.assert_array_equal(centers[1] - centers[0],
                                   np.rint(np.array(step) * distance).astype(int))


def test_consist_accumulates_adjacent_distances_with_a_reference():
    image = np.asarray(consist(
        [([_dot(2)] * 8, 4), ([_dot(3)] * 8, 7)],
        reference=([_dot(1)] * 8, 5), direction=1, scale=1,
        background=(255, 0, 255)))
    centers = [np.argwhere((image == rgb_of(i)).all(axis=-1))[0][::-1]
               for i in (1, 2, 3)]
    np.testing.assert_array_equal(centers[1] - centers[0], (10, -5))
    np.testing.assert_array_equal(centers[2] - centers[1], (10, -5))
