PYTHON ?= python3
DEMO   := examples/demo

.PHONY: all demo check test preview palette clean

all: demo

## Build the demonstration set: sprites, NML, language file and .grf
demo:
	cd $(DEMO) && $(PYTHON) build.py

## Render the long-sprite demonstration (overhang, sliced and reassembled)
longsprite:
	cd $(DEMO) && $(PYTHON) longsprite_demo.py

## Audit every generated sheet for the mistakes that only show up in game
check: demo
	$(PYTHON) -m newgrfengine check $(DEMO)/sprites/*.png

## Run the test suite
test:
	$(PYTHON) -m pytest tests -q

## Draw a key of the OpenTTD DOS palette, reserved ranges marked
palette:
	$(PYTHON) -m newgrfengine palette palette_key.png

clean:
	rm -rf $(DEMO)/sprites $(DEMO)/lang $(DEMO)/demo.pnml $(DEMO)/demo.grf \
	       $(DEMO)/demo_preview.png $(DEMO)/demo_consist.png \
	       $(DEMO)/longsprite $(DEMO)/.nmlcache palette_key.png
	find . -name __pycache__ -type d -prune -exec rm -rf {} +
