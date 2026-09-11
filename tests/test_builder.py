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


@pytest.mark.parametrize('second', ['coach', 'COACH'])
@pytest.mark.parametrize('purchase', [None, 'Purchase details'])
def test_project_rejects_duplicate_identifiers_and_generated_keys(tmp_path, second, purchase):
    project = _project(str(tmp_path))
    first = _vehicle('coach')
    first.purchase = purchase
    project.add(first)
    other = _vehicle(second)
    other.purchase = 'Other details' if purchase else None
    with pytest.raises(ValueError) as error:
        project.add(other)
    assert 'coach' in str(error.value) and second in str(error.value)
    assert project.vehicles == [first]
    assert project.sheet is None


@pytest.mark.parametrize('output', ['render', 'write_lang', 'nml_text'])
def test_identity_validation_rechecks_mutable_fleets_before_output(tmp_path, output):
    project = _project(str(tmp_path))
    first = project.add(_vehicle('coach'))
    second = project.add(_vehicle('bus'))
    project.render(verbose=False)
    second.ident = first.ident.upper()
    with pytest.raises(ValueError, match='share generated language key'):
        getattr(project, output)()


def _numbered_vehicle(ident='coach', numeric_id=None, **kwargs):
    return Vehicle(ident, ident.title(),
                   box(-6, 6, -1.5, 1.5, 3, 8, (200, 200, 200)),
                   85, 8, numeric_id=numeric_id, **kwargs)


@pytest.mark.parametrize('numeric_id', [-1, 65536, 1.5, '42', True, False])
def test_vehicle_rejects_invalid_numeric_ids(numeric_id):
    with pytest.raises(ValueError, match='numeric_id must be an integer in 0..65535'):
        _numbered_vehicle(numeric_id=numeric_id)


@pytest.mark.parametrize('numeric_id', [0, 42, 65535])
def test_vehicle_exposes_and_emits_explicit_numeric_id(tmp_path, numeric_id):
    project = _project(str(tmp_path))
    vehicle = project.add(_numbered_vehicle(numeric_id=numeric_id))
    assert vehicle.numeric_id == numeric_id
    assert 'numeric_id' not in vehicle.meta
    project.render(verbose=False)
    assert 'item(FEAT_TRAINS, coach, {})'.format(numeric_id) in project.nml_text()


def test_project_rejects_duplicate_ids_within_a_feature(tmp_path):
    project = _project(str(tmp_path))
    project.add(_numbered_vehicle('coach', 42))
    with pytest.raises(ValueError, match="'coach' and 'loco' share numeric_id 42"):
        project.add(_numbered_vehicle('loco', 42))


def test_project_allows_same_numeric_id_in_different_features(tmp_path):
    from newgrfengine.builder import ROADVEH
    project = _project(str(tmp_path))
    project.add(_numbered_vehicle('coach', 42))
    project.add(_numbered_vehicle('bus', 42, feature=ROADVEH))
    project.render(verbose=False)
    text = project.nml_text()
    assert 'item(FEAT_TRAINS, coach, 42)' in text
    assert 'item(FEAT_ROADVEHS, bus, 42)' in text


def test_explicit_ids_survive_insertion_reordering_and_removal(tmp_path):
    project = _project(str(tmp_path))
    coach = project.add(_numbered_vehicle('coach', 42))
    loco = project.add(_numbered_vehicle('loco', 116))
    for vehicles in ([coach, loco], [_numbered_vehicle('auto'), loco, coach],
                     [loco, coach]):
        project.vehicles[:] = vehicles
        project.render(verbose=False)
        text = project.nml_text()
        assert 'item(FEAT_TRAINS, coach, 42)' in text
        assert 'item(FEAT_TRAINS, loco, 116)' in text
        if len(vehicles) == 3:
            assert text.index('item(FEAT_TRAINS, loco, 116)') < text.index('item(FEAT_TRAINS, auto)')


@pytest.mark.parametrize('output', ['render', 'write_lang', 'nml_text'])
@pytest.mark.parametrize('numeric_id', [42, -1])
def test_numeric_id_validation_rechecks_mutable_fleets(tmp_path, output, numeric_id):
    project = _project(str(tmp_path))
    project.add(_numbered_vehicle('coach', 42))
    other = project.add(_numbered_vehicle('loco', 43))
    project.render(verbose=False)
    other.numeric_id = numeric_id
    with pytest.raises(ValueError, match='numeric_id'):
        getattr(project, output)()


def test_explicit_ids_and_distinct_language_strings_compile(tmp_path):
    import shutil
    if shutil.which('nmlc') is None:
        pytest.skip('nmlc not installed')
    from newgrfengine.builder import ROADVEH
    project = _variant_project(str(tmp_path))
    # Train auto-allocation starts at 116; explicitly reserving that ID after
    # an automatic item would otherwise silently give them the same number.
    first = project.vehicles[0]
    first.name = 'Automatic Engine'
    first.purchase = 'Automatic purchase details'
    for ident, numeric_id in [('coach', 42), ('loco', 116), ('upper', 65535), ('lower', 0)]:
        vehicle = project.add(_numbered_vehicle(ident, numeric_id,
                                               properties=first.properties))
        vehicle.purchase = ident + ' purchase details'
    project.add(_numbered_vehicle('bus', 42, feature=ROADVEH,
                                  properties={'speed': '50 mph', 'power': '100 hp',
                                              'weight': '10 ton', 'cargo_capacity': 0}))
    project.vehicles[1].variants = {'balanced': {'speed': '80 mph'}}
    project.build(verbose=False, preview=False)
    text = project.nml_text()
    language = dict((key.strip(), value) for line in project.lang.text().splitlines()
                    if ':' in line for key, value in [line.split(':', 1)])
    for vehicle in project.vehicles:
        assert language[vehicle.name_key] == vehicle.name
        assert 'string({})'.format(vehicle.name_key) in text
        if vehicle.purchase:
            assert language[vehicle.purchase_key] == vehicle.purchase
            assert 'string({})'.format(vehicle.purchase_key) in text
    result, grf = project.compile(extra_args=['--nfo', 't.nfo'])
    assert result.returncode == 0, result.stdout + result.stderr
    assert os.path.getsize(grf) > 0
    # nmlc's decoded name records pair each name with its actual ID. The
    # automatically allocated train must use 117, not explicit 116.
    nfo = (tmp_path / 't.nfo').read_text()
    for vehicle in project.vehicles:
        numeric_id = 117 if vehicle.numeric_id is None else vehicle.numeric_id
        assert (r'FF \wx{:04X} "{}"'.format(numeric_id, vehicle.name)) in nfo
