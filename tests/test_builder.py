"""
Tests for Project/Vehicle assembly (builder.py): raw NML placement and the
ordering trap around rendering before writing a preview.
"""

import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from newgrfengine import TIGHT, Project, Vehicle, box


def _project(out_dir):
    return Project("t", "NGE\\99", "Test", "A test project.",
                   out_dir=out_dir, layout=TIGHT)


def _vehicle(ident="a"):
    model = box(-6, 6, -1.5, 1.5, 3, 8, (200, 200, 200))
    return Vehicle(ident, "Test Vehicle", model, 85, 8)


# --------------------------------------------------------------- add_nml --

def test_add_nml_defaults_to_before_the_vehicle_blocks(tmp_path):
    project = _project(str(tmp_path))
    project.add(_vehicle())
    project.add_nml("/* guard */")
    project.render(verbose=False)
    text = project.nml_text()
    assert text.index("/* guard */") < text.index("item(FEAT_TRAINS, a)")


def test_add_nml_after_items_lands_after_the_vehicle_blocks(tmp_path):
    """The parameter-guarded override case from issue #2: NML applies Action 0
    records in file order, so an override emitted before the base item it is
    meant to change is silently discarded by it, not the other way round."""
    project = _project(str(tmp_path))
    project.add(_vehicle())
    project.add_nml("/* guard */", position="after_items")
    project.render(verbose=False)
    text = project.nml_text()
    assert text.index("/* guard */") > text.index("item(FEAT_TRAINS, a)")


def test_add_nml_rejects_an_unknown_position(tmp_path):
    project = _project(str(tmp_path))
    with pytest.raises(ValueError):
        project.add_nml("/* guard */", position="middle")


# ------------------------------------------------------------ .rendered --

def test_write_preview_before_render_raises_a_clear_error(tmp_path):
    project = _project(str(tmp_path))
    project.add(_vehicle())
    with pytest.raises(RuntimeError):
        project.write_preview()


def test_write_consist_before_render_raises_a_clear_error(tmp_path):
    project = _project(str(tmp_path))
    project.add(_vehicle())
    with pytest.raises(RuntimeError):
        project.write_consist(["a"])


def test_write_preview_works_after_render_called_outside_build(tmp_path):
    """The ordering a build script that calls write_consist() outside
    build() needs - see examples/*/build.py:write_consist() calls."""
    project = _project(str(tmp_path))
    project.add(_vehicle())
    project.render(verbose=False)
    path = project.write_preview()
    assert os.path.exists(path)
