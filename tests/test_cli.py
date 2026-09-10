"""
Tests for cli.py - the project's own safety net, and therefore the module
where a mistake is most worth catching in a test rather than by eye. See
issue #17: this module had no coverage at all, and the two crashes filed as
#11 and #13 both lived in this untested territory.
"""

import os

import numpy as np
import pytest
from PIL import Image

from newgrfengine import cli
from newgrfengine.palette import CC1_RAMP, PAL_BYTES, ANIMATED


def _paletted(pixels):
    """A small paletted PNG from a 2D array of DOS palette indices."""
    img = Image.frombytes("P", (pixels.shape[1], pixels.shape[0]),
                          pixels.astype(np.uint8).tobytes())
    img.putpalette(PAL_BYTES)
    return img


# ------------------------------------------------------------------ check --

def test_check_reports_no_problems_on_a_clean_sheet(tmp_path, capsys):
    path = str(tmp_path / "clean.png")
    _paletted(np.full((4, 4), 40, dtype=np.uint8)).save(path)
    assert cli.main(["check", path]) == 0
    assert "no problems found" in capsys.readouterr().out


def test_check_reports_an_rgb_image_instead_of_crashing(tmp_path, capsys):
    path = str(tmp_path / "rgb.png")
    Image.new("RGB", (4, 4), (200, 0, 0)).save(path)
    code = cli.main(["check", path])
    out = capsys.readouterr().out
    assert code == 1
    assert "mode is RGB, not P" in out


def test_check_reports_a_short_palette_instead_of_crashing(tmp_path, capsys):
    """The exact reproduction from issue #11: a PNG whose palette was
    trimmed to the colours actually used, which most indexed-mode exporters
    do, used to crash `check` with a ValueError instead of reporting it."""
    path = str(tmp_path / "tiny.png")
    Image.new("RGB", (8, 8), (200, 0, 0)).convert(
        "P", palette=Image.ADAPTIVE, colors=4).save(path)
    code = cli.main(["check", path])
    out = capsys.readouterr().out
    assert code == 1
    assert "palette holds" in out and "not 256" in out


def test_check_flags_pixels_in_the_animated_range(tmp_path, capsys):
    path = str(tmp_path / "animated.png")
    _paletted(np.full((4, 4), ANIMATED[0], dtype=np.uint8)).save(path)
    code = cli.main(["check", path])
    out = capsys.readouterr().out
    assert code == 1
    assert "WARN" in out and "animated" in out


def test_check_reports_company_colour_as_info_not_a_problem(tmp_path, capsys):
    """Telling a hazard from a feature is "the entire job" per the module
    docstring - company colour that is meant to be there must not fail the
    exit code the way an animated or mismatched pixel does."""
    path = str(tmp_path / "cc.png")
    _paletted(np.full((4, 4), CC1_RAMP[0], dtype=np.uint8)).save(path)
    code = cli.main(["check", path])
    out = capsys.readouterr().out
    assert code == 0
    assert "info" in out and "company colour 1" in out


def test_check_audits_every_sheet_even_if_an_earlier_one_fails(tmp_path, capsys):
    bad = str(tmp_path / "bad.png")
    Image.new("RGB", (4, 4), (0, 0, 0)).save(bad)
    good = str(tmp_path / "good.png")
    _paletted(np.full((4, 4), 40, dtype=np.uint8)).save(good)
    code = cli.main(["check", bad, good])
    out = capsys.readouterr().out
    assert bad in out and good in out
    assert "no problems found" not in out
    assert code == 1


def test_check_reports_unreadable_files_without_crashing(tmp_path, capsys):
    path = str(tmp_path / "not_an_image.png")
    (tmp_path / "not_an_image.png").write_text("not a png")
    code = cli.main(["check", path])
    out = capsys.readouterr().out
    assert code == 1
    assert "cannot read" in out


# ------------------------------------------------------------------ build --

def test_cmd_build_reports_a_module_with_neither_main_nor_project(
        tmp_path, capsys, monkeypatch):
    (tmp_path / "empty_module.py").write_text("x = 1\n")
    monkeypatch.chdir(str(tmp_path))
    code = cli.main(["build", "empty_module"])
    err = capsys.readouterr().err
    assert code == 2
    assert "no main()" in err


def test_cmd_build_calls_main_when_the_module_defines_one(
        tmp_path, capsys, monkeypatch):
    (tmp_path / "has_main.py").write_text(
        "def main():\n    print('built')\n    return 0\n")
    monkeypatch.chdir(str(tmp_path))
    code = cli.main(["build", "has_main"])
    assert code == 0
    assert "built" in capsys.readouterr().out


# --------------------------------------------------------------- palette --

def test_cmd_palette_writes_a_key_and_prints_the_reserved_ranges(
        tmp_path, capsys, monkeypatch):
    monkeypatch.chdir(str(tmp_path))
    code = cli.main(["palette", "key.png"])
    assert code == 0
    assert os.path.exists(str(tmp_path / "key.png"))
    out = capsys.readouterr().out
    assert "company colour 1" in out
    assert "0x{:02X}-0x{:02X}".format(min(ANIMATED), max(ANIMATED)) in out
