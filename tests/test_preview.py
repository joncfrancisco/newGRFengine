"""
Tests for preview.py. `consist()` is the check that catches a real mistake -
a coupling gap that is too wide, a sprite overrunning its neighbour - so its
spacing arithmetic is worth pinning exactly rather than trusting by eye.
See issue #17.
"""

import numpy as np
import pytest

from newgrfengine.geometry import direction_angle, project, rotate_z
from newgrfengine.palette import rgb_of
from newgrfengine.preview import consist, contact_sheet
from newgrfengine.render import SIDE_ON, Sprite


def _dot(index=100):
    """A single opaque 1x1 pixel sprite, for exact pixel-position assertions."""
    return Sprite(np.array([[index]], dtype=np.uint8), 0, 0, SIDE_ON)


# ------------------------------------------------------------------ empty --

def test_contact_sheet_raises_on_empty_input():
    with pytest.raises(ValueError):
        contact_sheet([])


def test_consist_raises_on_empty_input():
    with pytest.raises(ValueError):
        consist([])


# ---------------------------------------------------------------- consist --

def test_consist_steps_by_exactly_slot_times_step_vector():
    """The check that would catch the unit trap regressing: consist() must
    advance each vehicle by `slot` world units along x, projected - not by
    the sprite's own width or some other spacing."""
    sprite = _dot(100)
    slot = 8
    direction = 1                                # a diagonal: dx and dy both move
    items = [([sprite] * 8, slot), ([sprite] * 8, slot)]

    img = consist(items, direction=direction, scale=1, background=(0, 0, 0))
    canvas = np.asarray(img)
    color = rgb_of(100)
    ys, xs = np.where((canvas == color).all(axis=-1))
    assert len(xs) == 2, "expected exactly one pixel per vehicle"

    order = np.argsort(xs)
    dx = int(xs[order[1]]) - int(xs[order[0]])
    dy = int(ys[order[1]]) - int(ys[order[0]])

    angle = direction_angle(direction)
    step_x, step_y = project(rotate_z((1.0, 0.0, 0.0), np.cos(angle), np.sin(angle)))
    assert dx == pytest.approx(round(slot * step_x), abs=1)
    assert dy == pytest.approx(round(slot * step_y), abs=1)


def test_consist_never_writes_outside_the_canvas_for_a_large_negative_offset():
    """The canvas is sized from the actual placed positions, offsets
    included, so an extreme offset must still land inside it rather than
    wrapping through numpy's negative-index slicing or being dropped."""
    sprite = Sprite(np.array([[100]], dtype=np.uint8), -1000, -1000, SIDE_ON)
    items = [([sprite] * 8, 8)]
    img = consist(items, direction=SIDE_ON, scale=1, background=(0, 0, 0))
    canvas = np.asarray(img)
    color = rgb_of(100)
    assert (canvas == color).all(axis=-1).any(), "the sprite must still be drawn"
