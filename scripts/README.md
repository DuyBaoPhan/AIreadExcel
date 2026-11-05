# Development utilities

Run these commands from the repository root using the installed project environment.

| Command | Purpose | Side effects |
| --- | --- | --- |
| `python scripts/create_sample_data.py` | Regenerate demonstration Excel inputs | Writes demo input files; may replace demo data. Do not run against user-owned files. |
| `python scripts/create_advanced_reports.py` | Generate example advanced reports | Writes demonstration report outputs. |
| `python scripts/rag_live_smoke.py` | Opt-in real E5/FAISS recall check | May download a large model; does not call OpenAI. |

The normal offline test suite is `python -m pytest -q`. Current test fixtures remain under `excel_rule_engine/tests/`, separate from these explicitly invoked utilities.

## Supabase migration

`python scripts/migrate_supabase_storage.py --project demo_project` previews files without network calls. Add `--apply` to upload and verify without overwriting existing remote objects. Run `supabase_storage_setup.sql` in Supabase SQL Editor first for confirmed source edits. See [the full setup guide](../docs/supabase_storage.md).
