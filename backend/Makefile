# Call Desk developer shortcuts (from backend/)
PY := uv run --python 3.12 --with-requirements requirements.txt

.PHONY: test e2e e2e-install run-local seed-local

test:            ## unit + API suite (pytest.ini demands coverage flags; override)
	$(PY) --with pytest --with pytest-mock python -m pytest -o addopts="" -p no:cacheprovider tests -q --deselect tests/test_portal

e2e-install:     ## one-time: Chromium for Playwright
	$(PY) --with pytest --with pytest-playwright python -m playwright install chromium

e2e:             ## browser suite against a scratch server (never run alongside a local dev server)
	$(PY) --with pytest --with pytest-playwright python -m pytest -o addopts="" -p no:cacheprovider tests/e2e -q --browser chromium
	@rm -f instance/umuve.db umuve.db
