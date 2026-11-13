# Contributing to Queryopsy

Thanks for helping! Bug reports, UI polish, new levels and whole new cases are all welcome.

## Setup

```bash
git clone https://github.com/Himanshu-5680/queryopsy.git && cd queryopsy
python -m venv .venv && source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements-dev.txt
python -m playwright install chromium
python tools/serve.py                                  # http://localhost:8000
```

## Ground rules

* **Python first.** App logic lives in `src/` and runs in Pyodide; `src/boot.js` is the only JavaScript and should stay tiny.
* **Offline only.** No CDNs, analytics or network calls. The e2e suite fails on any external request.
* **No answers in the site.** Solutions go in the pipeline (they are hashed) and in `tests/fixtures/solutions.json`.
* **Original content.** Write your own stories; do not copy text, data or branding from other SQL games.

## Adding a level or a case

1. Edit or add an adapter in `pipeline/datasets/` (see `funding.py` for the pattern): tables, cleaning, planted anomalies and `levels()` with the task, three hints and the solution SQL.
2. Register it in `pipeline/datasets/__init__.py`.
3. `python -m pipeline.build` (fails if a solution returns no rows).
4. `python -m pytest` (every solution must pass, wrong answers must fail, the final hint must solve the level).
5. Commit the regenerated `data/`, `docs/PLANTED.md`, `docs/DATA-INPUTS.md` and `index.html`.

## Pull requests

* One topic per PR, with a clear description and screenshots for UI changes (light, dark and mobile).
* Keep `python -m pytest` green; CI runs unit tests, e2e tests and CodeQL.
* Update `CHANGELOG.md` under *Unreleased*.

By contributing you agree that your work is released under the MIT License and you follow our [Code of Conduct](CODE_OF_CONDUCT.md).
