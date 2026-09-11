"""Regressions for outward loft normals and company-colour coverage."""

import numpy as np
import pytest

from newgrfengine import (COMPANY, COMPANY2, RenderSpec, box, loft, prism,
                          render_model, section)
from newgrfengine.palette import CC1_RAMP, CC2_RAMP, PAL, SAFE_2CC, Quantiser
from newgrfengine.render import _resolve


def test_rectangular_loft_matches_box_in_every_view():
    paint = (200, 200, 200)
    actual = render_model(loft([section(-6, 1.5, 3, 8),
                                section(6, 1.5, 3, 8)], paint))
    expected = render_model(box(-6, 6, -1.5, 1.5, 3, 8, paint))
    for a, b in zip(actual, expected):
        assert (a.offset_x, a.offset_y) == (b.offset_x, b.offset_y)
        np.testing.assert_array_equal(a.indices, b.indices)


@pytest.mark.parametrize('tapered', [False, True])
def test_loft_normals_point_outward_and_preserve_taper(tapered):
    end = section(6, 1, 4, 7, half_w_top=0.5) if tapered else section(6, 2, 3, 8)
    model = loft([section(-6, 2, 3, 8), end], (200, 200, 200), caps=False)
    roof, positive, negative = model
    assert roof.normal[2] > 0
    assert positive.normal[1] > 0
    assert negative.normal[1] < 0
    for face in model:
        assert np.linalg.norm(face.normal) == pytest.approx(1)
    if tapered:
        assert roof.normal[0] > 0
        for face in (positive, negative):
            assert face.normal[0] > 0
            assert face.normal[2] > 0
        np.testing.assert_allclose(positive.normal,
                                   np.array(negative.normal) * [1, -1, 1])


@pytest.mark.parametrize('material,ramp', [(COMPANY, CC1_RAMP), (COMPANY2, CC2_RAMP)])
@pytest.mark.parametrize('shape', ['box', 'prism'])
def test_company_colour_shapes_stay_on_their_ramp_in_every_view(material, ramp, shape):
    model = (box(-6, 6, -1.5, 1.5, 3, 8, material) if shape == 'box'
             else prism(-6, 6, 0, 6, 1.5, 2, material))
    for sprite in render_model(model):
        painted = sprite.indices[sprite.indices != 0]
        assert painted.size
        assert np.isin(painted, ramp).all()


def _resolve_pixel(forced, covered=None):
    forced = np.array(forced, dtype=np.uint8).reshape(4, 4)
    cover = np.ones((4, 4), dtype=np.float32) if covered is None else np.array(
        covered, dtype=np.float32).reshape(4, 4)
    rgb = PAL[forced].astype(np.float32)
    rgb[forced == 0] = (180, 180, 180)
    spec = RenderSpec(alpha=0.25, quantiser=Quantiser(SAFE_2CC))
    return int(_resolve(rgb, cover, forced, 1, 1, 4, spec)[1][0, 0])


@pytest.mark.parametrize('ramp', [CC1_RAMP, CC2_RAMP])
@pytest.mark.parametrize('counts', [(8, 8), (6, 5, 5), (4, 4), (3, 3, 2)])
def test_ramp_vote_combines_shades_and_breaks_shade_ties_in_ramp_order(ramp, counts):
    forced = [value for value, count in zip(ramp, counts) for _ in range(count)]
    covered = [1] * len(forced) + [0] * (16 - len(forced))
    forced += [0] * (16 - len(forced))
    assert _resolve_pixel(forced, covered) == ramp[0]


@pytest.mark.parametrize('other', [0, CC2_RAMP[0]])
def test_company_ramp_needs_strict_majority_over_fixed_paint_or_other_ramp(other):
    # Neither shade alone has a majority, but their ramp does.
    assert _resolve_pixel([CC1_RAMP[0]] * 5 + [CC1_RAMP[1]] * 4 + [other] * 7) == CC1_RAMP[0]
    tied = _resolve_pixel([CC1_RAMP[0]] * 4 + [CC1_RAMP[1]] * 4 + [other] * 8)
    assert tied in SAFE_2CC
    minority = _resolve_pixel([CC1_RAMP[0]] * 7 + [other] * 9)
    if other:
        assert minority == other
    else:
        assert minority in SAFE_2CC
