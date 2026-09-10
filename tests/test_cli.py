"""Tests for the command-line palette tools."""

import numpy as np
from PIL import Image

from newgrfengine import cli
from newgrfengine.palette import ANIMATED, CC1_RAMP, PAL, PAL_BYTES


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
    assert cli.main(["check", path]) == 1
    assert "mode is RGB, not P" in capsys.readouterr().out


def test_check_reports_a_short_palette_instead_of_crashing(tmp_path, capsys):
    path = str(tmp_path / "tiny.png")
    Image.new("RGB", (8, 8), (200, 0, 0)).convert(
        "P", palette=Image.ADAPTIVE, colors=4).save(path)
    assert cli.main(["check", path]) == 1
    output = capsys.readouterr().out
    assert "palette holds" in output and "not 256" in output


def test_check_flags_pixels_in_the_animated_range(tmp_path, capsys):
    path = str(tmp_path / "animated.png")
    _paletted(np.full((4, 4), ANIMATED[0], dtype=np.uint8)).save(path)
    assert cli.main(["check", path]) == 1
    output = capsys.readouterr().out
    assert "WARN" in output and "animated" in output


def test_check_reports_company_colour_as_info_not_a_problem(tmp_path, capsys):
    path = str(tmp_path / "cc.png")
    _paletted(np.full((4, 4), CC1_RAMP[0], dtype=np.uint8)).save(path)
    assert cli.main(["check", path]) == 0
    output = capsys.readouterr().out
    assert "info" in output and "company colour 1" in output


def test_check_audits_every_sheet_even_if_an_earlier_one_fails(
        tmp_path, capsys):
    bad = str(tmp_path / "bad.png")
    Image.new("RGB", (4, 4), (0, 0, 0)).save(bad)
    good = str(tmp_path / "good.png")
    _paletted(np.full((4, 4), 40, dtype=np.uint8)).save(good)
    assert cli.main(["check", bad, good]) == 1
    output = capsys.readouterr().out
    assert bad in output and good in output


def test_check_reports_unreadable_files_without_crashing(tmp_path, capsys):
    path = str(tmp_path / "not_an_image.png")
    (tmp_path / "not_an_image.png").write_text("not a png")
    assert cli.main(["check", path]) == 1
    assert "cannot read" in capsys.readouterr().out


# ------------------------------------------------------------------ build --

def test_cmd_build_reports_a_module_with_neither_main_nor_project(
        tmp_path, capsys, monkeypatch):
    (tmp_path / "empty_module.py").write_text("x = 1\n")
    monkeypatch.chdir(str(tmp_path))
    assert cli.main(["build", "empty_module"]) == 2
    assert "no main()" in capsys.readouterr().err


def test_cmd_build_calls_main_when_the_module_defines_one(
        tmp_path, capsys, monkeypatch):
    (tmp_path / "has_main.py").write_text(
        "def main():\n    print('built')\n    return 0\n")
    monkeypatch.chdir(str(tmp_path))
    assert cli.main(["build", "has_main"]) == 0
    assert "built" in capsys.readouterr().out


# --------------------------------------------------------------- palette --

def test_cmd_palette_writes_a_key_and_prints_the_reserved_ranges(
        tmp_path, capsys, monkeypatch):
    monkeypatch.chdir(str(tmp_path))
    assert cli.main(["palette", "key.png"]) == 0
    assert (tmp_path / "key.png").exists()
    output = capsys.readouterr().out
    assert "company colour 1" in output
    assert "0x{:02X}-0x{:02X}".format(min(ANIMATED), max(ANIMATED)) in output


# -------------------------------------------------------------- quantise --


def test_quantise_reports_index_rgb_and_distance(capsys):
    wanted = tuple(int(value) for value in PAL[0xD1])
    assert cli.main(["quantise", ",".join(str(value) for value in wanted)]) == 0
    output = capsys.readouterr().out
    assert "index 0xD1" in output
    assert "distance 0.0" in output


def test_quantise_2cc_avoids_second_company_colour(capsys):
    wanted = tuple(int(value) for value in PAL[0x50])
    assert cli.main(["quantise", "--2cc",
                     ",".join(str(value) for value in wanted)]) == 0
    assert "index 0x50" not in capsys.readouterr().out


def test_quantise_can_write_a_swatch(tmp_path, capsys):
    path = tmp_path / "swatches.png"
    assert cli.main(["quantise", "12,34,56", "200,210,220",
                     "--swatch", str(path)]) == 0
    assert path.exists()
    with Image.open(path) as image:
        assert image.mode == "RGB"
        assert image.size == (420, 88)
        assert image.getpixel((20, 20)) == (12, 34, 56)
    assert "wrote {}".format(path) in capsys.readouterr().out
