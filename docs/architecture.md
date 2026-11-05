# Repository architecture

## Repository roots

Run installation, `python main.py`, and `python -m pytest` from the repository root. The root launcher starts the application; `streamlit_app.py` is the Streamlit deployment entrypoint. Root requirements files define shared dependencies, and `docs/` holds project documentation and evaluation results.

Application code remains in `excel_rule_engine/app/`; this is not a move to a top-level `app/`. Project inputs and generated outputs remain under `excel_rule_engine/projects/`. Root `scripts/` is the home for repository-level utility scripts, separate from application runtime code.

## Application layers

| Layer | Responsibility |
| --- | --- |
| `app/main.py` | FastAPI entrypoint and API integration. |
| `app/services/reports/schema_matching.py` | Column aliases/normalization for validated references; no intent classification. |
| `app/ui/` | Streamlit presentation: `chatbot.py`, `report_wizard.py`, `advanced_report_wizard.py`, `report_plan_ui.py`, and `ui_theme.py`. |
| `app/services/ai/` | AI-provider integration, structured planning and retrieval integration. |
| `app/services/chat/` | Conversation orchestration, context and pending interactions. |
| `app/services/excel/` | Workbook reading, writing and safe spreadsheet operations. |
| `app/services/reports/` | Validated report execution, exports and report naming. |
| `app/services/sources/` | Source discovery, project file management and source policies. |
| `app/services/runtime/` | Runtime configuration, provider setup and process-local infrastructure. |
| `app/database/` | SQLite setup and persistence repositories. |
| `app/workflows/` | Deterministic aggregation, filtering, comparison and report-export workflows. |

Presentation modules live under `app/ui/`; service modules have been extracted into the six subpackages above. `app/paths.py` defines stable filesystem locations, independent of service nesting or the working directory. Keep computation and file operations in validated backend services/workflows rather than duplicating them in UI or AI-provider code.

## Tests and utilities

Tests remain under `excel_rule_engine/tests/`; root `pytest.ini` supplies the import path and test discovery configuration. Data generation, manual scenario checks and the opt-in live RAG smoke test live in root `scripts/`. The benchmark case catalog remains with tests because it is a test fixture.

Repository reorganization does not change data-retention, authorization or AI-provider privacy boundaries; see the README for those operational constraints.

## Layout

```text
AIreadExcel/
|-- README.md
|-- main.py                       # Local combined launcher
|-- streamlit_app.py              # Streamlit Cloud entrypoint
|-- requirements*.txt
|-- pytest.ini
|-- .streamlit/                   # Cloud UI configuration (no secrets in Git)
|-- docs/                         # Guides, implementation notes and evaluations
|-- scripts/                      # Explicit development/demo commands
`-- excel_rule_engine/
    |-- main.py                   # Local process lifecycle
    |-- requirements.txt          # Forwards to root dependencies
    |-- start.bat / start.sh      # Existing platform launchers
    |-- app/
    |   |-- main.py               # HTTP API
    |   |-- paths.py              # Stable filesystem locations
    |   |-- ui/
    |   |-- services/
    |   |   |-- ai/
    |   |   |-- chat/
    |   |   |-- excel/
    |   |   |-- reports/
    |   |   |-- sources/
    |   |   `-- runtime/
    |   |-- database/
    |   `-- workflows/
    |-- legacy_nlp/              # Historical offline benchmark code, never imported by app
    |-- tests/
    |-- examples/                 # Sample report configurations
    `-- projects/                 # Existing inputs, policies and generated outputs
```

The existing local virtual environment and SQLite database stay in place and are ignored by Git. Do not move a running database or a virtual environment as part of housekeeping. Both Streamlit configuration files remain because root Cloud and engine-local launches have different working directories.

## Commands from repository root

```bash
python main.py
python -m pytest -q
python scripts/run_test_cases.py
# These create demo workbooks; do not run against user-owned input files:
python scripts/create_sample_data.py
python scripts/create_advanced_reports.py
# Opt-in only: loads/downloads the real embedding model:
python scripts/rag_live_smoke.py
```

Existing root launch commands and the Cloud entrypoint are unchanged. Internal Python imports now use functional packages (for example `app.services.reports.report_engine` and `app.ui.ui_theme`); external scripts importing the old flat service paths must update their imports. No old-path module aliases are installed, avoiding two module instances and split in-memory approval/session state.

## Natural-language routing (OpenAI only)

The chatbot and conversational report endpoints use OpenAI structured outputs. `REPORT_PLANNER` defaults to `openai`; `auto` remains an alias with identical behavior. `rules` is rejected. Missing API credentials and provider errors fail explicitly, with no regex, fuzzy intent or rule-planner fallback. Python still validates sources, columns, types, operations, write proposals and approval tokens; these safety checks are independent of language understanding and are retained. Manual report wizards may execute explicit configurations without asking a language model.

Legacy offline NLP benchmarks are historical regression material, not evidence of current OpenAI semantic accuracy.
