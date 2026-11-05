# Shared private Excel storage (Supabase)

## Before switching

Stop both local and deployed writers during the first migration. Back up existing Excel files.
Create a **private** bucket named `excel-files`. Never add public read/write policies.
This implementation shares file objects only, not chat history, SQLite tasks, or pending confirmation tokens.

## 1. Install SQL lock functions

Open Supabase **SQL Editor**, create a query, paste the entire contents of
`scripts/supabase_storage_setup.sql`, and run it once. The SQL creates a lock table
and two RPC functions restricted to the `service_role`. It does not import Excel data.
Re-running is supported. Storage uploads/listing do not need public policies with the server secret.

## 2. Configure server settings

Local `.env` (keep existing OpenAI settings):

```dotenv
FILE_STORAGE_BACKEND=supabase
SUPABASE_URL=https://YOUR_PROJECT.supabase.co
SUPABASE_SECRET_KEY=YOUR_SERVER_SECRET
SUPABASE_STORAGE_BUCKET=excel-files
```

Use a backend `sb_secret_...` key or legacy `service_role` key, never publishable/anon.
Legacy `SUPABASE_SERVICE_ROLE_KEY` is also supported if `SUPABASE_SECRET_KEY` is unset.
Never commit credentials or paste them into chat. Restrict app access to trusted users:
the application currently has no authenticated per-user project authorization. Private
Storage alone does not prevent an app visitor from invoking exposed app operations.
Do not expose the FastAPI port publicly. Deploy the UI privately before allowing edits.

Streamlit Community Cloud **Settings > Secrets** uses TOML, not dotenv:

```toml
FILE_STORAGE_BACKEND = "supabase"
SUPABASE_URL = "https://YOUR_PROJECT.supabase.co"
SUPABASE_SECRET_KEY = "YOUR_SERVER_SECRET"
SUPABASE_STORAGE_BUCKET = "excel-files"
```

Preserve OpenAI secrets. Deploy the updated code, configure these values, then reboot.
The Cloud launcher forwards documented settings to its backend process.

## 3. Migrate originals explicitly (Windows, repository root)

Keep the app stopped until upload verification completes. First preview (no network):

```powershell
.\venv\Scripts\python.exe scripts/migrate_supabase_storage.py --project demo_project
```

Then upload and verify hashes:

```powershell
.\venv\Scripts\python.exe scripts/migrate_supabase_storage.py --project demo_project --apply
```

Repeat with `--project NAME` for each project. This includes direct XLSX/XLS/CSV files
in input/output/backups plus existing `name.xlsx.backup-*` backups from input (relocated
to backups). Nested directories, temporary lockfiles, databases, and chat messages are not migrated.
Existing identical remote objects are verified and left unchanged. Different objects
are reported as CONFLICT and never overwritten; exit code is nonzero. Resolve conflicts
manually using your intended authoritative version. Do not delete remote objects blindly.
The tool never deletes or rewrites original local files. Partial migrations can be resumed.

## 4. Storage layout and runtime

```text
projects/PROJECT/input/FILE.xlsx
projects/PROJECT/output/REPORT.xlsx
projects/PROJECT/backups/FILE.xlsx.backup-UNIQUE
```

In shared mode the local working cache is `excel_rule_engine/projects/.shared-cache/`.
The original `projects/PROJECT/input/` files remain unchanged; they are not live mirrors.
An empty remote input folder means no available files, not a fallback to bundled samples.
Remote errors fail closed rather than using stale local data. Sources refresh on access;
reports are uploaded before success/download. Chatbot uploads and confirmed edits are
persistent. Wizard report outputs are persisted in shared mode; wizard source uploads
are session inputs (upload them through the chatbot source uploader to make them shared).
No OpenAI settings or chat behavior is replaced by Supabase.
Project-specific JSON configuration such as source_policy.json is not migrated by this
Excel-only utility. If used, provision it consistently in the shared cache project
directory on each runtime; a durable shared configuration store is outside this change.

## 5. Verify with a disposable source

1. Start local app; check Storage input names match the app source list.
2. Upload a small test workbook through the chatbot uploader.
3. Open deploy with the same configuration; check that test workbook appears.
4. Propose one test-cell update, review it, and explicitly confirm.
5. Re-read it from local; check new data and the backup object in Storage.
6. Export a report and verify its object under output.
7. Reboot deploy and confirm the source still contains the edit.

Mocked automated tests do not validate a real project's permissions or configuration.
A live end-to-end check must be performed after setup; no automatic live migration is run.

## Concurrent edits and recovery

All application source overwrites use a durable database lock per object, re-read the
source under that lock, compare the approved digest, back up, upload, then verify bytes.
A stale proposal fails and requires a new preview. Locks do not expire automatically:
an uncertain upload or process crash can leave a lock held to prevent a late write
from overwriting a newer one. A blocked edit needs administrator recovery; do not just
retry forever or delete lock rows while writers are active. Follow SQL file recovery
comments: stop all writers, ensure no requests remain in flight, inspect/reconcile source
and backups, then remove only the intended lock using the Supabase SQL editor.
Direct dashboard edits or other clients bypass the application's cooperative lock.
Do not edit shared source objects externally while app writes are active.

## Rollback

Stop writers before changing storage configuration. `FILE_STORAGE_BACKEND=local` returns
to original local files; it does **not** download or merge remote changes. Back up/export
the remote latest files first if returning to local mode. Never treat a backend switch
as automatic two-way synchronization.
