# Development utilities

Run these commands from the repository root using the installed project environment.

| Command | Purpose | Side effects |
| --- | --- | --- |
| `python scripts/run_test_cases.py` | Historical offline parser/workflow scenarios (not current AI acceptance) | Uses temporary test workspaces. |
| `python scripts/create_sample_data.py` | Regenerate demonstration Excel inputs | Writes demo input files; may replace demo data. Do not run against user-owned files. |
| `python scripts/create_advanced_reports.py` | Generate example advanced reports | Writes demonstration report outputs. |
| `python scripts/rag_live_smoke.py` | Opt-in real E5/FAISS recall check | May download a large model; does not call OpenAI. |

The normal offline test suite is `python -m pytest -q`. Test fixtures and benchmark case catalogs remain under `excel_rule_engine/tests/`, separate from these explicitly invoked utilities.
