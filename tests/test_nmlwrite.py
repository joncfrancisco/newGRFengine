"""
Tests for nmlwrite.py - the NML text builders. These are pure string
builders, so the tests are cheap and exact rather than approximate. See
issue #17: this module was previously reached only indirectly, through
Project.nml_text() in the demo test.
"""

import os

from newgrfengine import nmlwrite as nw


# ---------------------------------------------------------------- values --

def test_value_helpers_format_units():
    assert nw.string("STR_FOO") == "string(STR_FOO)"
    assert nw.mph(100) == "100 mph"
    assert nw.kmh(160) == "160 km/h"
    assert nw.hp(1200) == "1200 hp"
    assert nw.tons(56) == "56 ton"
    assert nw.date(1968, 4, 1) == "date(1968, 4, 1)"
    assert nw.date(1968) == "date(1968, 1, 1)"
    assert nw.bitmask("A", "B") == "bitmask(A, B)"


# ---------------------------------------------------------------- _props --

def test_props_skips_none_values():
    """None is how a caller leaves a property out - see Vehicle.properties
    and Project._item(), which relies on this to omit unset fields."""
    text = nw._props({"speed": "100 mph", "power": None, "weight": "56 ton"})
    assert "speed" in text and "weight" in text
    assert "power" not in text


def test_props_indents_and_pads_the_key():
    text = nw._props({"speed": "100 mph"}, indent=4, pad=10)
    assert text.startswith("    speed:    100 mph;")


# ----------------------------------------------------------------- item --

def test_item_omits_the_graphics_block_when_none_given():
    text = nw.item("FEAT_TRAINS", "a", {"length": 8})
    assert "graphics" not in text
    assert "property {" in text


def test_item_includes_the_graphics_block_when_given():
    text = nw.item("FEAT_TRAINS", "a", {"length": 8}, {"default": "ss_a"})
    assert "graphics {" in text
    assert "default:" in text


def test_item_includes_a_comment_when_given():
    text = nw.item("FEAT_TRAINS", "a", {"length": 8}, comment="a note")
    assert "/* a note */" in text


def test_item_includes_a_numeric_id_when_given():
    text = nw.item("FEAT_TRAINS", "a", {"length": 8}, numeric_id=3)
    assert "item(FEAT_TRAINS, a, 3)" in text


# ------------------------------------------------------------- int_param --

def test_int_param_derives_min_and_max_from_the_values_dict():
    text = nw.int_param(0, "stats", "Stats", "Which stats",
                        {0: "Realistic", 1: "Balanced"})
    assert "min_value: 0;" in text
    assert "max_value: 1;" in text
    assert "0: Realistic;" in text
    assert "1: Balanced;" in text


def test_int_param_uses_the_given_default():
    text = nw.int_param(0, "stats", "Stats", "desc", {0: "A", 1: "B"},
                        default=1)
    assert "def_value: 1;" in text


# -------------------------------------------------------------- grf_block --

def test_grf_block_includes_url_only_when_given():
    without = nw.grf_block("NGE\\01", "string(N)", "string(D)", 1)
    with_url = nw.grf_block("NGE\\01", "string(N)", "string(D)", 1,
                            url="string(URL)")
    assert "url:" not in without
    assert "url:" in with_url


def test_grf_block_indents_param_blocks():
    param = nw.int_param(0, "stats", "Stats", "desc", {0: "A"})
    text = nw.grf_block("NGE\\01", "string(N)", "string(D)", 1, params=[param])
    assert "    param 0 {" in text


# ------------------------------------------------------------------ table --

def test_table_joins_entries():
    assert nw.table("cargotable", ("PASS", "MAIL")) == "cargotable { PASS, MAIL }\n"


# -------------------------------------------------------------- spriteset --

def test_spriteset_includes_zoom_and_depth_only_when_given():
    plain = nw.spriteset("ss_a", "sheet.png", "tmpl_a()")
    full = nw.spriteset("ss_a", "sheet.png", "tmpl_a()", zoom="ZOOM_NORMAL",
                        depth="8bpp")
    assert "ZOOM_NORMAL" not in plain
    assert "ZOOM_NORMAL" in full and "8bpp" in full


# ---------------------------------------------------------------- switch --

def test_switch_includes_a_default_only_when_given():
    without = nw.switch("FEAT_TRAINS", "SELF", "sw", "expr", [("1", "a")])
    with_default = nw.switch("FEAT_TRAINS", "SELF", "sw", "expr", [("1", "a")],
                             default="b")
    assert without.count(";") == 1
    assert with_default.count(";") == 2
    assert "b;" in with_default


# ------------------------------------------------------------------- NML --

def test_nml_drops_empty_sections():
    doc = nw.NML()
    doc.add("")
    doc.add("real content")
    assert doc.text().strip() == "real content"


def test_nml_wraps_the_header_as_a_comment_block():
    doc = nw.NML(header="line one\nline two")
    text = doc.text()
    assert text.startswith("/*")
    assert " * line one" in text and " * line two" in text


def test_nml_write_creates_directories(tmp_path):
    doc = nw.NML()
    doc.add("content")
    path = doc.write(str(tmp_path / "nested" / "out.pnml"))
    assert os.path.exists(path)
    with open(path) as fh:
        assert "content" in fh.read()


# ------------------------------------------------------------------ Lang --

def test_lang_text_round_trips_through_the_grflangid_header():
    """The ##grflangid header format is a fixed contract nmlc parses - a
    typo here breaks every string in the language file at once."""
    lang = nw.Lang(grflangid="0x01", name="English (US)")
    lang.add("STR_FOO", "Foo")
    lines = lang.text().splitlines()
    assert lines[0] == "##grflangid 0x01"
    assert lines[1] == "# English (US)"
    assert any(line.startswith("STR_FOO") and line.rstrip().endswith(":Foo")
              for line in lines)


def test_lang_named_builds_a_prefixed_uppercase_key():
    lang = nw.Lang()
    key = lang.named("STR_NAME", "railcar", "Demonstrator EMU")
    assert key == "STR_NAME_RAILCAR"
    assert lang.strings[key] == "Demonstrator EMU"


def test_lang_write_creates_directories(tmp_path):
    lang = nw.Lang()
    lang.add("STR_FOO", "Foo")
    path = lang.write(str(tmp_path / "lang" / "english.lng"))
    assert os.path.exists(path)
