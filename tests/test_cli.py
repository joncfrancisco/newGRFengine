"""Tests for the command-line palette tools."""

import os
import sys

from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from newgrfengine.cli import main
from newgrfengine.palette import PAL


def test_quantise_reports_index_rgb_and_distance(capsys):
    wanted = tuple(int(value) for value in PAL[0xD1])
    assert main(["quantise", ",".join(str(value) for value in wanted)]) == 0
    output = capsys.readouterr().out
    assert "index 0xD1" in output
    assert "distance 0.0" in output


def test_quantise_2cc_avoids_second_company_colour(capsys):
    wanted = tuple(int(value) for value in PAL[0x50])
    assert main(["quantise", "--2cc",
                 ",".join(str(value) for value in wanted)]) == 0
    assert "index 0x50" not in capsys.readouterr().out


def test_quantise_can_write_a_swatch(tmp_path, capsys):
    path = tmp_path / "swatches.png"
    assert main(["quantise", "12,34,56", "200,210,220",
                 "--swatch", str(path)]) == 0
    assert path.exists()
    with Image.open(path) as image:
        assert image.mode == "RGB"
        assert image.size == (420, 88)
        assert image.getpixel((20, 20)) == (12, 34, 56)
    assert "wrote {}".format(path) in capsys.readouterr().out
