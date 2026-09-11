"""GRID geometry must track newly added rows."""

import numpy as np
import pytest

from newgrfengine import GRID, TIGHT, Sprite, SpriteSheet


def _sprites(width=3, height=2, x=-1, y=-1):
    return [Sprite(np.ones((height, width), dtype=np.uint8), x, y, d)
            for d in range(8)]


@pytest.mark.parametrize('first_property', ['views', 'cell', 'origin'])
def test_empty_grid_geometry_is_invalidated_when_a_row_is_added(first_property):
    sheet = SpriteSheet('t', layout=GRID)
    getattr(sheet, first_property)
    assert (sheet.views, sheet.cell, sheet.origin) == (0, (1, 1), (0, 0))
    sheet.add('a', _sprites())
    getattr(sheet, first_property)
    assert (sheet.views, sheet.cell, sheet.origin) == (8, (4, 3), (1, 1))


@pytest.mark.parametrize('first_property', ['views', 'cell', 'origin'])
def test_populated_grid_geometry_tracks_larger_offset_sprites(first_property):
    sheet = SpriteSheet('t', layout=GRID)
    sheet.add('a', _sprites())
    getattr(sheet, first_property)
    sheet.add('b', _sprites(12, 10, -5, -7))
    getattr(sheet, first_property)
    assert (sheet.views, sheet.cell, sheet.origin) == (8, (13, 11), (5, 7))


@pytest.mark.parametrize('property_name', ['views', 'cell', 'origin'])
def test_cached_grid_geometry_cannot_hide_incompatible_views(property_name):
    sheet = SpriteSheet('t', layout=GRID)
    sheet.add('a', _sprites())
    getattr(sheet, property_name)
    sheet.add('b', _sprites()[:4])
    with pytest.raises(ValueError, match='same number of views'):
        getattr(sheet, property_name)


def test_tight_geometry_stays_none_after_additions():
    sheet = SpriteSheet('t', layout=TIGHT)
    for name in ('a', 'b'):
        assert (sheet.views, sheet.cell, sheet.origin) == (None, None, None)
        sheet.add(name, _sprites())
    assert (sheet.views, sheet.cell, sheet.origin) == (None, None, None)
