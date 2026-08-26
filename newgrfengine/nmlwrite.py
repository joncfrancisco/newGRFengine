"""
Writing the NML a rendered sheet needs to become a NewGRF.

These are text builders, not a model of NML. NML is a perfectly good language
and there is nothing to gain from wrapping every property in an object; what
is worth automating is the part that has to agree with the renderer - sprite
templates, spriteset names, sprite offsets - and the part that is pure
bookkeeping, like keeping a language file in step with the items that
reference its strings.

Values are written through verbatim, so anything NML accepts can be passed as
a string. The small helpers below exist because `speed: 100 mph;` and
`introduction_date: date(1968, 4, 1);` are easy to typo and annoying to debug
once nmlc has stopped talking to you.
"""

from __future__ import annotations

import os
from collections import OrderedDict

# ------------------------------------------------------------- value helpers --


def string(key):
    return "string({})".format(key)


def mph(value):
    return "{} mph".format(value)


def kmh(value):
    return "{} km/h".format(value)


def hp(value):
    return "{} hp".format(value)


def tons(value):
    return "{} ton".format(value)


def date(year, month=1, day=1):
    return "date({}, {}, {})".format(year, month, day)


def bitmask(*flags):
    return "bitmask({})".format(", ".join(flags))


# ------------------------------------------------------------------ blocks --


def _props(properties, indent=8, pad=32):
    out = []
    for key, value in properties.items():
        if value is None:
            continue
        out.append("{}{}{};".format(" " * indent, (key + ":").ljust(pad), value))
    return "\n".join(out)


def grf_block(grfid, name, desc, version, min_compatible_version=1,
              params=(), url=None):
    """The grf{} block. `params` are pre-rendered parameter blocks."""
    lines = ["grf {",
             "    grfid:                  \"{}\";".format(grfid),
             "    name:                   {};".format(name),
             "    desc:                   {};".format(desc)]
    if url:
        lines.append("    url:                    {};".format(url))
    lines += ["    version:                {};".format(version),
              "    min_compatible_version: {};".format(min_compatible_version)]
    for block in params:
        lines.append(_indent(block, 4))
    lines.append("}")
    return "\n".join(lines) + "\n"


def int_param(number, name, label, desc, values, default=0):
    """An integer NewGRF parameter with named values.

    A parameter is resolved while the GRF loads, so a set can carry two whole
    variants of its numbers - realistic and game-balanced, say - behind an
    `if` and let the player pick between them, at the cost of the choice only
    taking effect on a new game.
    """
    lines = ["param {} {{".format(number),
             "    {} {{".format(name),
             "        type:      int;",
             "        name:      {};".format(label),
             "        desc:      {};".format(desc),
             "        min_value: {};".format(min(values)),
             "        max_value: {};".format(max(values)),
             "        def_value: {};".format(default),
             "        names: {"]
    for value in sorted(values):
        lines.append("            {}: {};".format(value, values[value]))
    lines += ["        };", "    }", "}"]
    return "\n".join(lines)


def table(kind, entries):
    return "{} {{ {} }}\n".format(kind, ", ".join(entries))


def spriteset(name, filename, template_call, zoom=None, depth=None):
    args = [name]
    if zoom:
        args.append(zoom)
    if depth:
        args.append(depth)
    args.append('"{}"'.format(filename))
    return "spriteset({}) {{ {} }}".format(", ".join(args), template_call)


def switch(feature, scope, name, expression, cases=(), default=None):
    """A switch block. `cases` is a sequence of (match, result) pairs."""
    body = ["    {}: {};".format(match, result) for match, result in cases]
    if default is not None:
        body.append("    {};".format(default))
    return "switch ({}, {}, {}, {}) {{\n{}\n}}".format(
        feature, scope, name, expression, "\n".join(body))


def item(feature, nml_id, properties, graphics=None, numeric_id=None,
         comment=None):
    """One item{} block: properties, then the graphics callbacks that vary them."""
    head = "item({}, {}{}) {{".format(
        feature, nml_id, ", {}".format(numeric_id) if numeric_id is not None else "")
    parts = []
    if comment:
        parts.append("/* {} */".format(comment))
    parts.append(head)
    parts.append("    property {\n" + _props(properties) + "\n    }")
    if graphics:
        parts.append("    graphics {\n" + _props(graphics) + "\n    }")
    parts.append("}")
    return "\n".join(parts)


def _indent(text, spaces):
    pad = " " * spaces
    return "\n".join(pad + line if line.strip() else line
                     for line in text.splitlines())


# ------------------------------------------------------------------ output --


class NML:
    """A .pnml file being assembled, section by section."""

    def __init__(self, header=None):
        self.sections = []
        if header:
            self.sections.append(_comment_block(header))

    def add(self, text, heading=None):
        if heading:
            self.sections.append("/* {} {}*/".format(
                heading + " ", "-" * max(2, 68 - len(heading))))
        self.sections.append(text.rstrip("\n"))
        return self

    def text(self):
        return "\n\n".join(s for s in self.sections if s.strip()) + "\n"

    def write(self, path):
        directory = os.path.dirname(os.path.abspath(path))
        if directory:
            os.makedirs(directory, exist_ok=True)
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(self.text())
        return path


def _comment_block(text):
    lines = ["/*"]
    lines += [" * " + line if line else " *" for line in text.splitlines()]
    lines.append(" */")
    return "\n".join(lines)


class Lang:
    """A language file, kept in step with the items that name its strings."""

    def __init__(self, grflangid="0x01", name="English (US)"):
        self.grflangid = grflangid
        self.name = name
        self.strings = OrderedDict()

    def add(self, key, text):
        self.strings[key] = text
        return key

    def named(self, prefix, ident, text):
        """Add a string under a generated key and return the key."""
        return self.add("{}_{}".format(prefix, ident.upper()), text)

    def text(self):
        lines = ["##grflangid {}".format(self.grflangid),
                 "# {}".format(self.name), ""]
        for key, value in self.strings.items():
            lines.append("{:<28}:{}".format(key, value))
        return "\n".join(lines) + "\n"

    def write(self, path):
        directory = os.path.dirname(os.path.abspath(path))
        if directory:
            os.makedirs(directory, exist_ok=True)
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(self.text())
        return path
