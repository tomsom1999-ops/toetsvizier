# Copilot instructions for this repository

## Build and test commands

This repository is primarily a **Python desktop application**.

```powershell
python -m pip install -r requirements.txt
python -m playwright install chromium
python main.py
```

The automated test suite uses the standard library `unittest` runner, not `pytest`.

```powershell
python -m unittest discover -s tests -v
python -m unittest tests.test_results -v
python -m unittest tests.test_results.ResultsEntryTests.test_only_students_from_test_groups_are_available_for_entry -v
```

There is also a separate frontend build in `dashboard\`:

```powershell
Set-Location dashboard
npm run build
```

That build writes to `toetsanalyse\dashboard_dist`, but the in-app analysis and norming dashboards currently come from Python-generated HTML in `toetsanalyse\analysis_dashboard.py` and `toetsanalyse\norming_dashboard.py`, not from the Vite app.

## High-level architecture

- `main.py` and `toetsanalyse\__main__.py` both start `toetsanalyse.app.run()`.
- `toetsanalyse\app.py` is the main application module and contains most of the Qt UI, navigation, dialogs, and workspace flow. Expect many features to be implemented here rather than split into smaller UI modules.
- Data is stored in a **separate SQLite database per subject**. `toetsanalyse\database.py` owns the schema, lightweight migrations, default taxonomy seeding, backup support, and the `SubjectDatabase` wrapper used throughout the app.
- Runtime folders are centralized in `toetsanalyse\paths.py`. The app creates `data`, `backups`, `exports`, `logs`, and `config` on startup.
- Core feature logic is split by domain:
  - `importers.py` handles Magister student imports and score import parsing/mapping.
  - `results.py` handles result validation, status changes, score persistence, and multiple-choice regrading.
  - `norming.py` calculates grades and stores the active normalization configuration.
  - `analysis.py` computes test-quality, item-analysis, group, and student metrics from stored scores.
  - `reports.py` builds the HTML for the matrix report.
  - `student_reports.py` builds the HTML for leerlingniveau reports.
  - `norming_exports.py` builds XLSX and HTML participant overviews for norming.
  - `pdf_export.py` renders report HTML to PDF through Playwright Chromium.
- The rich dashboards are not server-backed web apps. `analysis_dashboard.py` and `norming_dashboard.py` generate full HTML documents as strings, which `app.py` loads into `QWebEngineView` and connects to Qt via `QWebChannel`.

## Key conventions

- **Keep domain language and UI copy in Dutch.** Code can use English helper names, but user-facing labels, messages, report text, and workflow terminology are Dutch throughout the app and tests.
- **Use `SubjectDatabase` instead of ad hoc sqlite access patterns** when adding features. Schema changes, default data, and compatibility logic live in `database.py`; changes usually need both schema updates and migration handling in `_migrate_schema()` or related seed/migration helpers.
- **Preserve the per-subject database model.** Features should work against one selected `.db` file, with `QSettings` only storing app-level state such as window geometry and the last opened database path.
- **Do not treat `dashboard\` as the source of truth for the current in-app dashboards.** The shipped analysis/norming views are Python-built HTML documents embedded in Qt. If a dashboard change affects the running app, check `analysis_dashboard.py`, `norming_dashboard.py`, and the `QWebEngineView` wiring in `app.py` first.
- **Reports are HTML-first.** Preview and export paths share the same generated HTML; Qt preview uses transformed page-break markers, and PDF export uses Playwright in `pdf_export.py`.
- **Tests usually build realistic temporary subject databases.** Follow the existing pattern in `tests\`: create a temp DB with `SubjectDatabase.create(...)`, seed only the rows needed for the scenario, and use helper functions like `save_score()` where the behavior under test depends on application rules.
- **Defaults matter.** New databases are expected to contain standard taxonomies (`RTTI`, `OBIT`, `Bloom`) and default properties (`Domein`, `Leerdoel`, `Vraagtype`), and many features/tests assume those seeds exist.
- **Backups are part of normal flow.** The app automatically backs up the current subject database when returning to the start screen or closing the app, and restore creates a copied database instead of overwriting the original.
