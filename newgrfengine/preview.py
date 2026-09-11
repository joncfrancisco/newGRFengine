"""
Looking at what you just rendered, before OpenTTD does.

Two views, and the second one is the one that catches real mistakes.

`contact_sheet` is the obvious one: every vehicle, every direction, blown up
so individual pixels are visible.

`consist` lays vehicles end to end at exactly the spacing the game will use -
the NML `length` slot in world units, projected through the same isometric
mapping - so a coupling gap that is too wide, a sprite that overruns into its
neighbour, or a set whose vehicles are all the same drawn size regardless of
prototype shows up here rather than in a screenshot three days later. It draws
a diagonal as readily as a straight, because a set that lines up on straight
track can still come apart on a curve.
"""

from __future__ import annotations

from functools import lru_cache

import numpy as np
from PIL import Image, ImageDraw

from .geometry import direction_angle, project, rotate_z
from .palette import PAL
from .render import SIDE_ON, render_model

GRASS = (58, 92, 56)
GRASS_ALT = (52, 84, 50)
INK = (232, 236, 232)


@lru_cache(maxsize=None)
def _builtin_reference(name):
    """Return (label, sprites, slot) for a scale-calibration silhouette."""
    if name != "rail_coach":
        raise ValueError(
            "unknown preview reference {!r}; available: rail_coach".format(name))

    # Kept here as geometry rather than as borrowed base-set artwork: it is an
    # unbranded 85 ft / 8-of-8 measuring stick, and rendering it through the
    # same pipeline makes its scale independent of a bundled bitmap.
    from .parts import bogies, underframe
    from .primitives import box, window_row
    from .scale import RAIL

    half_w = 1.75
    model = bogies(14.5, half_w, top=2.55, inset=2.3)
    model += underframe(14.5, half_w, 2.3, 3.35)
    model += box(-7.25, 7.25, -half_w, half_w, 3.15, 8.7,
                 (176, 180, 184))
    model += window_row(-6.2, 6.2, 5.95, 7.95, half_w, 7,
                        (48, 60, 74))
    model, _ = RAIL.fit(model, 85, 8)
    return "reference: 85 ft rail coach", render_model(model), 8


def _contact_reference(reference):
    if isinstance(reference, str):
        name, sprites, _ = _builtin_reference(reference)
        return name, sprites
    try:
        name, sprites = reference
    except (TypeError, ValueError):
        raise ValueError(
            "contact-sheet reference must be 'rail_coach' or (name, sprites)")
    return name, sprites


def _consist_reference(reference):
    if isinstance(reference, str):
        _, sprites, slot = _builtin_reference(reference)
        return sprites, slot
    try:
        sprites, slot = reference
    except (TypeError, ValueError):
        raise ValueError(
            "consist reference must be 'rail_coach' or (sprites, slot)")
    return sprites, slot


def to_rgb(sprite, background=GRASS):
    """One sprite as an RGB array, transparent pixels filled with background."""
    if sprite.is_empty():
        return np.zeros((1, 1, 3), dtype=np.uint8)
    rgb = PAL[sprite.indices].astype(np.uint8)
    flat = np.zeros_like(rgb)
    flat[:, :] = background
    return np.where((sprite.indices == 0)[..., None], flat, rgb)


def _font():
    from PIL import ImageFont
    try:
        return ImageFont.load_default()
    except Exception:
        return None


def contact_sheet(entries, scale=4, label=True, background=GRASS,
                  alt=GRASS_ALT, pad=2, reference=None):
    """Every direction of every vehicle on one grid.

    `entries` is a sequence of (name, sprites). ``reference="rail_coach"``
    prepends a neutral 85 ft coach, so the set is judged against a stable
    scale rather than only against itself. A custom ``(name, sprites)`` pair
    may be supplied instead.
    """
    entries = list(entries)
    if not entries:
        raise ValueError("nothing to preview")
    if reference is not None:
        entries.insert(0, _contact_reference(reference))
    cell_w = max(s.width for _, sprites in entries for s in sprites) + pad * 2
    cell_h = max(s.height for _, sprites in entries for s in sprites) + pad * 2
    cols = max(len(sprites) for _, sprites in entries)
    label_w = 96 if label else 0

    width = label_w + cols * cell_w
    height = len(entries) * cell_h
    canvas = np.zeros((height, width, 3), dtype=np.uint8)
    canvas[:, :] = background

    for r, (_, sprites) in enumerate(entries):
        for c, sprite in enumerate(sprites):
            x0 = label_w + c * cell_w
            y0 = r * cell_h
            canvas[y0:y0 + cell_h, x0:x0 + cell_w] = alt if (c % 2) else background
            if sprite.is_empty():
                continue
            # Sit each sprite on a common baseline so a row reads as one vehicle
            # turning, not as eight unrelated cut-outs.
            ox = x0 + pad + (cell_w - 2 * pad - sprite.width) // 2
            oy = y0 + cell_h - pad - sprite.height
            canvas[oy:oy + sprite.height, ox:ox + sprite.width] = to_rgb(
                sprite, alt if (c % 2) else background)

    img = Image.fromarray(canvas)
    img = img.resize((img.width * scale, img.height * scale), Image.NEAREST)
    if label:
        draw = ImageDraw.Draw(img)
        font = _font()
        for r, (name, _) in enumerate(entries):
            draw.text((6 * scale, (r * cell_h + cell_h // 2 - 4) * scale),
                      name, fill=INK, font=font)
    return img


def consist(items, direction=SIDE_ON, scale=4, background=GRASS, margin=8,
            reference=None):
    """Vehicles coupled up, spaced exactly as OpenTTD will space them.

    `items` is a sequence of (sprites, slot), where `slot` is the NML `length`
    property in world units. ``reference="rail_coach"`` places a neutral
    85 ft / 8-of-8 coach at the head as a scale check; a custom
    ``(sprites, slot)`` pair may be supplied instead. The game advances by the
    slot along the vehicle's own x axis, so the step on screen is that vector
    projected - which for a diagonal is 2 px across and 1 px down per world
    unit, and for a straight is 2.83 px across and none down.
    """
    items = list(items)
    if not items:
        raise ValueError("nothing to preview")
    if reference is not None:
        items.insert(0, _consist_reference(reference))
    angle = direction_angle(direction)
    step_x, step_y = project(rotate_z((1.0, 0.0, 0.0), np.cos(angle),
                                      np.sin(angle)))

    placed = []
    cursor = 0.0
    for sprites, slot in items:
        sprite = sprites[direction]
        px = cursor * step_x
        py = cursor * step_y
        placed.append((sprite, px + sprite.offset_x, py + sprite.offset_y))
        cursor += float(slot)

    xs = [x for _, x, _ in placed] + [x + s.width for s, x, _ in placed]
    ys = [y for _, _, y in placed] + [y + s.height for s, _, y in placed]
    x0, y0 = min(xs) - margin, min(ys) - margin
    width = int(max(xs) - x0 + margin)
    height = int(max(ys) - y0 + margin)

    canvas = np.zeros((height, width, 3), dtype=np.uint8)
    canvas[:, :] = background
    for sprite, px, py in placed:
        if sprite.is_empty():
            continue
        left, top = int(round(px - x0)), int(round(py - y0))
        patch = to_rgb(sprite, background)
        mask = sprite.indices != 0
        region = canvas[top:top + sprite.height, left:left + sprite.width]
        region[mask] = patch[mask]

    img = Image.fromarray(canvas)
    return img.resize((img.width * scale, img.height * scale), Image.NEAREST)
