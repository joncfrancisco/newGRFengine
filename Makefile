PYTHON   ?= python3
EXAMPLES := demo bilevel

.PHONY: all check test palette clean longsprite $(EXAMPLES)

all: $(EXAMPLES)

## Build one example set: sprites, NML, language file and .grf
$(EXAMPLES):
	cd examples/$@ && $(PYTHON) build.py

## Render the long-sprite demonstration (overhang, sliced and reassembled)
longsprite:
	cd examples/demo && $(PYTHON) longsprite_demo.py

## Audit every generated sheet for the mistakes that only show up in game
check: $(EXAMPLES)
	$(PYTHON) -m newgrfengine check $(foreach ex,$(EXAMPLES),examples/$(ex)/sprites/*.png)

## Run the test suite
test:
	$(PYTHON) -m pytest tests -q

## Draw a key of the OpenTTD DOS palette, reserved ranges marked
palette:
	$(PYTHON) -m newgrfengine palette palette_key.png

clean:
	for ex in $(EXAMPLES); do \
		rm -rf examples/$$ex/sprites examples/$$ex/lang examples/$$ex/*.pnml \
		       examples/$$ex/*.grf examples/$$ex/*_preview.png \
		       examples/$$ex/*_consist.png examples/$$ex/.nmlcache; \
	done
	rm -rf examples/demo/longsprite palette_key.png
	find . -name __pycache__ -type d -prune -exec rm -rf {} +
