# Repository Guidelines

## Project Structure & Module Organization

`newgrfengine/` is the Python package for rendering OpenTTD sprites and building NewGRFs. Geometry, models, primitives, and materials define vehicles; `render.py`, `palette.py`, and `sheet.py` produce sprite sheets; `builder.py` and `nmlwrite.py` assemble projects and NML. Public exports live in `__init__.py`, and CLI entry points are in `cli.py` and `__main__.py`.

`newgrfengine/data/ttd-newgrf-dos.gpl` contains the bundled DOS palette. `examples/demo/` and `examples/bilevel/` contain runnable model/build scripts. Tests live in `tests/`; `.github/workflows/ci.yml` defines CI. Generated sprites, previews, language files, NML, and GRFs belong in the example output directories and are ignored by Git.

## Build, Test, and Development Commands

Run commands from the repository root:

- `python3 -m pip install -r requirements.txt`: install renderer, NML compiler, and test dependencies.
- `make test`: run the pytest suite (`python3 -m pytest tests -q`).
- `make demo` or `make bilevel`: render an example, write NML/language files, and compile its `.grf`.
- `make check`: build both examples and audit their sprite sheets.
- `make longsprite`: render the overhang splitting/reassembly demonstration.
- `make palette`: generate `palette_key.png` with reserved ranges marked.
- `make clean`: remove generated example outputs and Python caches.

The renderer requires NumPy and Pillow; `.grf` compilation additionally requires `nml`/`nmlc`. Override the Makefile interpreter with `make test PYTHON=python` when needed.

## Coding Style & Naming Conventions

Maintain Python 3.8 compatibility. Use four-space indentation, `snake_case` functions/modules, `PascalCase` classes, and `UPPER_SNAKE_CASE` constants. Follow neighboring code and use docstrings to explain coordinate, palette, and rendering constraints. No formatter or linter is configured; avoid unrelated formatting changes.

## Testing Guidelines

Use pytest files named `tests/test_*.py` and functions named `test_<behavior>`. Use `tmp_path` for generated files and `capsys` for CLI output. Add regression assertions for geometry, palette indices, pixel alignment, or NML ordering as appropriate. No numeric coverage threshold is configured. Before submitting, run `make test` and `make check`; CI tests Python 3.8, 3.9, 3.11, and 3.13.

## Commit & Pull Request Guidelines

History uses short, imperative subjects such as `Fix palette quantisation workflow` and `Add a double-decker passenger carriage example`. Keep commits focused. In PRs, describe the behavior changed, link relevant issues, and report validation commands/results. Include before/after sprite previews for visual changes, and update README examples when public behavior changes.
