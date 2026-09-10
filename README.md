# newGRFengine

An OpenTTD sprite renderer for building NewGRFs.

Vehicles are written as small 3D models — boxes, lofted noses, faceted prisms,
thin leaning slabs, and flat decals for windows, doors and liveries — and
projected into OpenTTD's own isometric view for all eight directions. Because
every direction comes off the same geometry, consists line up on straight track
and stay consistent through curves, and a repaint is a dictionary rather than a
day's work in a pixel editor.

The renderer's output is not only pixels. It knows where each sprite sits
relative to the vehicle's reference point, so it writes its own NML sprite
templates — offsets included. That is the part of building a set which is pure
arithmetic and completely unforgiving, and it is the part this engine exists to
take away.

```sh
pip install -r requirements.txt
make demo      # renders six vehicles, writes the NML, compiles demo.grf
make test
```

---

## The shortest useful example

```python
from newgrfengine import *

body  = box(-7, 7, -1.75, 1.75, 3.0, 9.0, (206, 212, 218))
body += box(-6.7, 6.7, -1.5, 1.5, 9.0, 9.9, (112, 118, 124))
body += window_row(-6, 6, 6.2, 8.0, 1.75, 7, (48, 60, 74))
body += bogies(14, 1.75) + pantograph(0, 1.75, 9.9)

model, drawn = RAIL.fit(body, length_ft=85, slot=8)
sprites = render_model(model)          # eight directions, cropped, offsets set

sheet = SpriteSheet("myset")
sheet.add("railcar", sprites, purchase=render_purchase(model))
sheet.save("sprites/myset.png")
print(sheet.nml_templates())           # ready to paste, or to generate around
```

`contact_sheet` and `consist` will show you what you just built before OpenTTD
does — see [Looking at it first](#looking-at-it-first).

---

## The projection, and why it has to be this one

```
screen_x = (wy - wx) * 2
screen_y = (wy + wx) - wz
```

This is OpenTTD's own `RemapCoords`. Any other isometric mapping produces
sprites that line up with each other but not with the track under them, the
platform beside them or the ground they stand on. One tile is 16 world units
and covers 64 × 32 pixels; the eight directions come from rotating the single
model about z by `225° − 45° × direction`, in the game's sprite order N, NE, E,
SE, S, SW, W, NW.

Direction 2 is the one rotation where the projection collapses to pure
horizontal — the vehicle exactly broadside with its nose to the right — which
is why `render_purchase()` is a one-line function and not a second model.

Faces are back-face culled against the view direction `(1, 1, 2)`, sorted by
paint layer and then depth, rasterised at 4×, downsampled with a mask-weighted
filter so edges do not bleed the background, and quantised to the DOS palette.

**Sorting is by layer first, depth second.** A painter's algorithm on depth
alone cannot be trusted to keep a window in front of the body it is cut into:
the decal sits a hundredth of a unit proud, and at some rotations that is inside
the noise. Layers — `L_SOLID`, `L_TEXTURE`, `L_DOOR`, `L_STRIPE`, `L_WINDOW`,
`L_LIGHT` — make the ordering a statement about what the surfaces *are*.

**Downsampling is mask-weighted.** Averaging a 4×4 block that is half vehicle
and half background pulls the edge towards the background colour, and since the
background is nothing at all that reads as a dark fringe all round the sprite.
Weighting by coverage and dividing by it averages only the pixels that are
actually vehicle, and coverage doubles as the alpha the transparency threshold
works on.

---

## Two things are called "length", and both matter

Getting either wrong shows up as sprites that overlap their neighbours, or as a
roster in which every vehicle is the same size.

**The unit trap.** A tile is 16 world units, but a train vehicle is not.
OpenTTD's `VEHICLE_LENGTH` is 8 against a tile's `TILE_SIZE` of 16, so a
full-length 8/8 vehicle is **half a tile**, and the game spaces consecutive
vehicles by exactly the NML `length` property in world units — not twice that.
A sprite drawn to fill a whole tile overlaps the vehicle behind it by about 45%.

**The coarseness trap.** `length` is an integer from 1 to 8, so prototypes of
quite different size land in the same bucket: a 65 ft locomotive and an 85 ft
coach are both 8/8 vehicles. Scaling every model to fill its bucket draws them
the same length, which is what a set that has only fixed the first trap looks
like.

So a vehicle carries both figures, and `LengthScale` reconciles them:

```python
model, drawn = RAIL.fit(model, length_ft=65, slot=8)   # 5.9 units in an 8-unit slot
RAIL.slot_for(65)                                      # 7 - the slot it really needs
RAIL.is_capped(90, 8)                                  # True: longer than the reference
```

A short engine in a slot sized for something longer simply shows more coupling
gap, which is the correct read: it *is* a short engine sharing a slot built for
something bigger. A `length_ft` estimate that runs long is capped at the slot,
so a generous guess can never make a sprite overrun into the next vehicle.

**Road vehicles get their own calibration, and this is not a fudge.** At the
rail scale a 40 ft bus comes out about seven pixels long — too few to carry a
windscreen, a door and three window bays, and dwarfed by the body height those
details need. OpenTTD's own artwork makes exactly the same concession: a vanilla
bus is drawn very nearly as long as a vanilla wagon. `ROAD` calibrates the road
fleet against itself, so every road length is honest relative to the other road
vehicles — the comparison a player can actually make on screen.

| Scale | Reference | A 40 ft vehicle draws |
| --- | --- | --- |
| `RAIL` | 85 ft fills 8/8 | 3.6 units |
| `ROAD` | 45 ft fills 8/8 | 6.8 units |
| `TRAM` | 70 ft fills 8/8 | 4.4 units |

---

## The palette, and the colours that are not colours

An 8bpp NewGRF sprite is a paletted image, and several entries in that palette
are not paint — the game rewrites them at draw time:

| Range | What the game does with it |
| --- | --- |
| `0x00` | transparent |
| `0x50–0x57` | the second company colour, in a set that sets a 2CC flag |
| `0xC6–0xCD` | the company colour, always |
| `0xE3–0xFE` | animated: fire, water sparkle, the fizzy-drink glow |
| `0xFF` | pure white, used as a marker in several places |

Quantisation therefore works against an allow-list, not the whole 256. `SAFE`
is the middle of the palette; `SAFE_2CC` also drops the green ramp that a 2CC
set loses. A locomotive whose Tuscan red quantises into `0xC6–0xCD` comes out of
the depot in the player's colours instead, and changes colour when they change
theirs.

Company colour is available deliberately as a material:

```python
model += side_decal(-6.9, 5.6, 4.4, 5.6, 1.75, COMPANY)   # COMPANY2 for 2CC
```

A company-coloured face resolves to a palette **index** in the reserved ramp
rather than being quantised, with the face's shading choosing a position in the
ramp — which is what keeps a company-coloured body reading as a 3D shape
instead of a flat silhouette. Those pixels are then settled by majority vote per
output pixel, because blending two ramp indices gives a third that is not in the
ramp, and the face would come out of the depot half painted. The cost is that
the boundary between a company-coloured panel and a fixed-colour one is not
antialiased. That is a constraint of the palette, not of this renderer.

`python -m newgrfengine palette` draws a key of the whole table with the
reserved ranges crossed out.

---

## Primitives

Five shapes cover nearly everything.

| | |
| --- | --- |
| `box(x0, x1, y0, y1, z0, z1, mat)` | carbodies, roofs, bogies, hoods, roof pods |
| `loft(sections, mat)` | a body whose cross-section changes along its length |
| `prism(x0, x1, cy, cz, ry, rz, mat, facets=8)` | boilers, tanks, arched clerestory roofs |
| `strut(x0, z0, x1, z1, y, thick, mat)` | anything diagonal — `box` is axis-aligned and cannot lean |
| `side_decal` / `end_decal` / `top_decal` | windows, doors, stripes, corrugation, grilles, lights |

`loft` is the one worth knowing about. A box can only be as long as it is blunt;
four or five `section()` stations pulling the width and the roof line down
towards a point draw a cab front that genuinely tapers, and the same call with
two identical stations is just a box:

```python
nose = loft([
    section(-7.0, 1.75, 3.0, 9.0),
    section( 3.2, 1.75, 3.0, 9.0),
    section( 5.0, 1.54, 3.0, 8.5, half_w_top=1.02),
    section( 6.4, 1.05, 3.1, 7.6, half_w_top=0.46),
    section( 7.2, 0.46, 3.4, 6.6, half_w_top=0.18),
], STEEL, top_mat=ROOF)
```

On top of those sit the sub-assemblies in `parts`: `bogies`, `truck`, `axles`,
`underframe`, `pantograph`, `trolley_poles`, `roof_pod`, `headlights`,
`cab_glass`, `bellows`, `doors`, `skirt`, `window_row`, `ribs`. What is
*underneath* a body is most of what tells the eye which kind of vehicle it is
looking at, before any livery goes on: a pair of bogies inset from the ends
reads as a rail car, two plain axles read as a bus, three trucks with a bellows
between the sections read as an articulated tram.

Models compose and repaint:

```python
pair = cab.at(-8) + cab.mirrored_x().at(8)
red  = cab.recoloured({STEEL: (188, 46, 44)})
```

---

## Sheets that write their own NML

A NewGRF loads rectangles out of a sheet, each named by a template line of
`[left_x, upper_y, width, height, offset_x, offset_y]`. Getting those six
numbers right by hand is most of the tedium of building a set, and getting the
last two wrong is why some sets' consists sit half a pixel apart or ride above
the rails. The renderer already knows all six.

```python
sheet = SpriteSheet("myset", layout=GRID)      # or TIGHT
sheet.add("railcar", sprites, purchase=buy_sprite)
sheet.save("sprites/myset.png")
sheet.nml_templates()                          # template tmpl_myset(row) { ... }
sheet.nml_spritesets("sprites/myset.png")      # spriteset(ss_railcar, ...) { ... }
```

**`TIGHT`** crops every sprite to its own bounding box and writes one template
per vehicle. Nothing is wasted and a vehicle may be any size at all, which is
what long sprites need.

**`GRID`** derives one cell size and one reference point for the whole sheet and
writes a single shared template — the form a hand-written set uses. The file is
bigger, but the sheet can be opened in a pixel editor and touched up by hand
without any offset moving, which is how most published sets are actually
finished. The cell size is computed from the sprites, not chosen in advance.

The eight direction sprites and the purchase sprite are kept in separate
templates, because a train's `default` graphics wants a spriteset of exactly
eight sprites and handing it a ninth is a compile error.

---

## Long sprites: drawing past the slot

OpenTTD expects a vehicle's sprite to stay inside its reserved `length`. A cab
car with a real nose does not want to. [JPplusShinkansen][jp] solves this by
building each unit as three articulated parts in a 1-8-1 length pattern and
drawing cab art about 25% past the middle part's length, carried on the two
near-zero-length parts either side.

`longsprite` does the rendering half of that exactly rather than by eye:

```python
model, drawn = RAIL.fit(cab, length_ft=106, slot=8, overhang=0.25)
parts = render_long(model, slot=8)     # 'full', 'back', 'body', 'front'
```

The model is cut **in model space**, on planes square across the vehicle at the
edges of its slot — no pixel slicing, no guessing where a diagonal view's cut
line falls. The pieces are then extracted from the *finished* sprite by a
per-pixel tag map, so every pixel belongs to exactly one piece and the occlusion
between them is the occlusion the whole model had. Rendering three models
independently would give each piece its own antialiased edge along the cut and
its own idea of what hides what, and the three would not add back up to the one.
These do, in all eight directions — the test suite asserts it pixel for pixel.

The last step is the one nobody wants to do by hand: an overhang is drawn not by
this vehicle but by its neighbour, so its offsets are rebased onto *that*
vehicle's reference point. The neighbour sits one slot along the vehicle's x
axis, and that vector projects differently in every direction — 2 px across and
1 down per world unit on a diagonal, 2.83 px across and none on a straight.
Those eight corrections are precisely what a hand-built set's front and back
templates encode as eight sets of hand-tuned numbers.

What the engine will not do is decide *when* the game should draw the long
sprite instead of the three pieces; that depends on the consist logic of the set
it is going into. `nml_switches()` emits the scaffolding with the predicate left
as an expression you supply, and states its polarity in the generated comment
rather than burying it.

`make longsprite` renders the whole thing, including a side-by-side proof.

---

## Looking at it first

```python
contact_sheet([("railcar", sprites), ("coach", coach_sprites)]).save("preview.png")
consist([(loco, 7), (coach, 8), (coach, 8)], direction=1).save("consist.png")
```

`consist` is the one that catches real mistakes. It lays vehicles end to end at
exactly the spacing the game will use — the NML `length` slot in world units,
projected through the same mapping — so a coupling gap that is too wide, a
sprite that overruns its neighbour, or a set whose vehicles are all the same
drawn size shows up here rather than in a screenshot three days later. It draws
a diagonal as readily as a straight, because a set that lines up on straight
track can still come apart on a curve.

---

## From models to a .grf

`builder.Project` holds the shape every vehicle set has, so a project can be a
table of vehicles and a build script of about ten lines:

```python
project = Project(name="myset", grfid="ABC\\01", title="My Set",
                  description="...", layout=GRID)
project.add(Vehicle(ident="railcar", name="Railcar", model=models.railcar,
                    length_ft=85, slot=8, properties={...}))
project.build(compile_grf=True)
```

It renders every vehicle, packs the sheet, writes the templates, spritesets and
item blocks, keeps the language file in step with the strings the items
reference, and calls `nmlc`. The build report prints how much of its slot each
vehicle actually filled, so a wrong `length_ft` is visible immediately:

```
railcar               7.70 of 8 units  ( 96% of slot)     85 ft
steam                 6.34 of 7 units  ( 91% of slot)     70 ft
tram                  7.70 of 8 units  ( 96% of slot)     90 ft  capped
bus                   6.84 of 8 units  ( 86% of slot)     40 ft
```

Nothing in the renderer requires this layer. A project with its own ideas about
NML can use `render`, `sheet` and `nmlwrite` directly and skip it.

---

## Command line

```
python -m newgrfengine palette [out.png]     draw a key of the DOS palette
python -m newgrfengine check <sheet.png>...  audit a sheet
python -m newgrfengine build <module>        build a project module
```

`check` is the one worth putting in a Makefile. A sheet is an ordinary PNG and
anything can produce one — this renderer, a pixel editor, a hand touch-up — and
the failures it catches are all silent: a sprite saved as RGB instead of
paletted, a palette that is nearly but not quite the game's, a highlight that
landed in the company-colour ramp and will repaint itself blue in one player's
hands and red in another's. Company colour that is *meant* to be there is
reported as information, not as a problem, since telling those two apart is the
entire job.

---

## The demo set

`examples/demo` is six vehicles chosen so that between them they use every
primitive, and it compiles to a real GRF with no nmlc errors or warnings:

| | |
| --- | --- |
| railcar | `loft()` — a cab front that actually tapers |
| coach | `ribs()` and `window_row()` — what makes a flank read as a coach |
| steam | `prism()` — a boiler is the one shape a box cannot fake |
| tram | `bellows()` and `truck()` — three sections over three trucks |
| bus | `axles()` at the road scale — no bogie frame, low floor |
| trolleybus | `strut()` — poles laid back along a roof have to lean |

The liveries are deliberately plain. The interesting question about the output
is whether the shapes read at 24 pixels, not whether the stripes are pretty.

---

## Layout

```
newgrfengine/
  palette.py      the DOS palette, the reserved ranges, quantisation
  geometry.py     Quad, the isometric projection, lighting
  materials.py    Material, company colour, paint layers
  model.py        Model: compose, transform, repaint, measure
  primitives.py   box, loft, prism, strut, decals, window_row, ribs
  parts.py        bogies, axles, pantograph, bellows, headlights, ...
  scale.py        LengthScale: prototype feet to world units
  render.py       cull, shade, sort, rasterise, downsample, quantise, crop
  sheet.py        packing, and the NML templates that read it back
  longsprite.py   drawing past the slot: clip, tag, split, rebase
  nmlwrite.py     NML text builders and the language file
  preview.py      contact sheets and consists
  builder.py      Project: models in, .grf out
  cli.py          palette / check / build
  data/           the DOS palette, so nml is not needed to render
examples/demo/    six vehicles, one compiled GRF, the long-sprite demo
tests/            the arithmetic that is otherwise only checked by eye
```

---

## Credits

The renderer's approach — vehicles as boxes and surface decals, projected
through OpenTTD's own mapping, quantised to the DOS palette — is generalised
from the sprite generator in **[njtransit][njt]**, along with its length
calibration and the reasoning about why road vehicles need a second one.

The long-sprite technique, the purchase sprite cropped from the set's own
artwork, and the bundled DOS palette file come from
**[JPplusShinkansen][jp]**, whose 1-8-1 articulated units and hand-tuned
front/middle/back templates are what this engine's `longsprite` module computes
instead of measuring.

Built for NML 0.9. Not affiliated with OpenTTD.

[njt]: https://github.com/joncfrancisco/njtransit
[jp]: https://github.com/OpenTTD-JPplus/JPplusShinkansen
