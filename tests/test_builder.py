"""
Tests for Project/Vehicle assembly (builder.py): raw NML placement and the
ordering trap around rendering before writing a preview.
"""

import os
import subprocess

import pytest

from newgrfengine import IntParam, TIGHT, Project, Vehicle, box


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


# ------------------------------------------------------- property variants --

def _variant_project(out_dir):
    parameter = IntParam(
        0, "stats", values={0: "Realistic", 1: "Game-balanced"},
        default=0)
    project = Project("t", "NGE\\99", "Test", "A test project.",
                      out_dir=out_dir, layout=TIGHT,
                      variant_param=parameter)
    project.add(Vehicle(
        "a", "Test Vehicle", box(-6, 6, -1.5, 1.5, 3, 8,
                                  (200, 200, 200)), 85, 8,
        properties={"speed": "125 mph", "power": "3200 hp",
                    "weight": "50 ton", "cargo_capacity": 0},
        variants={"balanced": {"speed": "110 mph",
                                "power": "3200 hp"}}))
    return project


def test_variants_emit_parameter_and_changed_properties_after_items(tmp_path):
    project = _variant_project(str(tmp_path))
    project.render(verbose=False)
    text = project.nml_text()
    assert "param 0" in text and "stats" in text
    guard = text.index("if (stats == 1)")
    assert guard > text.index("item(FEAT_TRAINS, a)")
    override = text[guard:]
    assert "speed:" in override and "110 mph" in override
    assert "power:" not in override, "unchanged values should be omitted"


def test_variant_language_strings_are_generated(tmp_path):
    project = _variant_project(str(tmp_path))
    path = project.write_lang()
    with open(path) as handle:
        text = handle.read()
    assert "STR_PARAM_STATS_NAME" in text
    assert "Game-balanced" in text


def test_variant_report_is_a_markdown_comparison(tmp_path):
    report = _variant_project(str(tmp_path)).variant_report()
    assert "| Vehicle | Property | Realistic | Game-balanced |" in report
    assert "| a | speed | 125 mph | 110 mph |" in report
    assert "power" not in report, "unchanged values should be omitted"


def test_variant_project_compiles_if_nmlc_is_available(tmp_path):
    try:
        subprocess.run(["nmlc", "--version"], capture_output=True)
    except (OSError, FileNotFoundError):
        pytest.skip("nmlc not installed")
    project = _variant_project(str(tmp_path))
    paths = project.build(verbose=False, preview=False, compile_grf=True)
    assert os.path.exists(paths["grf"])


def test_vehicle_variants_require_a_project_parameter(tmp_path):
    project = _project(str(tmp_path))
    project.add(Vehicle(
        "a", "Test Vehicle", box(-6, 6, -1.5, 1.5, 3, 8,
                                  (200, 200, 200)), 85, 8,
        variants={"balanced": {"speed": "110 mph"}}))
    project.render(verbose=False)
    with pytest.raises(ValueError, match="no variant_param"):
        project.nml_text()


# ---------------------------------------------------------- build report --

def test_build_report_includes_fitted_dimensions_and_aspect_warning(tmp_path):
    project = _project(str(tmp_path))
    vehicle = Vehicle("tower", "Tower",
                      box(-6, 6, -1.5, 1.5, 0, 12, (200, 200, 200)),
                      85, 8)
    project.add(vehicle)
    vehicle.build_model()
    report = project._report(vehicle)
    assert "7.7 x  3.0 x 12.0" in report
    assert "WARN taller than long" in report
