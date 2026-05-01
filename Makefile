.PHONY: help install test eval sweep dashboard clean lint

PY=PYTHONPATH=src python
PIP=pip install --break-system-packages

help:
	@echo "Common commands:"
	@echo "  make install    - install runtime + dev dependencies"
	@echo "  make test       - run pytest"
	@echo "  make eval       - run the headline experiment (clean/attacked/defended)"
	@echo "  make sweep      - run the full attack-budget sweep, write CSV"
	@echo "  make dashboard  - launch Streamlit dashboard"
	@echo "  make clean      - remove caches and build artefacts"

install:
	$(PIP) -r requirements.txt

test:
	$(PY) -m pytest tests/ -v

eval:
	$(PY) -m scs.evaluation.run_experiment \
	    --budget 10 --vector press_release \
	    --out data/results/main_experiment.json

sweep:
	$(PY) -m scs.evaluation.run_budget_sweep

dashboard:
	$(PY) -m streamlit run src/scs/dashboard/app.py

clean:
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .pytest_cache -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true
