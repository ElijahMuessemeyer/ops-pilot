.PHONY: run demo review-demo test compile clean

PYTHON ?= python3
export PYTHONPATH := src

run:
	$(PYTHON) run_server.py --port 8000

demo:
	$(PYTHON) run_demo.py

review-demo:
	$(PYTHON) run_review_demo.py

test:
	$(PYTHON) -m unittest discover -s tests -v

compile:
	$(PYTHON) -m compileall src tests run_demo.py run_review_demo.py run_server.py

clean:
	find . -name '__pycache__' -type d -prune -exec rm -rf {} +
	find . -name '*.pyc' -delete
