# OpenAI integration verification

## Architecture

AI is the planner, not the calculator. Production now always uses OpenAI for natural-language requests. `REPORT_PLANNER` defaults to `openai`; `auto` is an alias, and `rules` is rejected. Missing credentials and API errors never activate a keyword fallback. UI and the command compatibility API bypass keyword intent routing. Existing read-only reporting executor, snapshot limits and unique outputs are retained.

Only current user request, filenames, row counts, column names/dtypes and configured department priorities are transmitted. No cell values or sample rows are sent. User-entered text and metadata may themselves be sensitive. Credentials are backend-only environment variables / Streamlit Secrets; no key was requested in chat or used for these tests.

Structured output is validated locally: exact shape, available source/column references, supported operations, finite bounded configuration, ranking scope and unresolved conditions. Schema-equivalent sources require clarification unless an explicit filename or configured department policy establishes the source. No arbitrary Python/SQL generation or execution is allowed.

## Execution and approval

Automatic reports run on the same snapshots used for planning. Manual preview stores the validated plan for up to 15 minutes in a bounded server cache; confirmation checks the source bytes and executes the same config without asking the model again. Backend restart requires a new preview. This cache is a consistency check, not authentication or authorization.

Provider errors and refusals stop safely. There is no hidden fallback after an OpenAI error. One API call per plan, no retries, 45-second provider timeout, 4,000 output token cap. Model defaults to gpt-4.1-mini and is configurable; chosen model/account must support strict structured outputs.

## Validation limits

Provider tests use mocked HTTP responses; integration tests exercise actual report execution with a mocked planner. They cover metadata privacy, invalid schemas/columns/configs, ambiguous sources, explicit-source precedence, timeouts/API errors, refusal, ranking, no keyword routing, exact approval reuse, changed-data rejection and real XLSX export.

No live provider evaluation or Streamlit Cloud deployment has been performed. Mock tests establish contracts, not actual language accuracy. Before production, evaluate your configured model on representative paraphrases, compare source/filters/aggregates and computed results against independently reviewed expectations. Semantic misunderstandings remain possible even when a plan passes structural validation. This version has no conversation history, joins, forecasts or unrestricted formulas; unsupported tasks must not be silently approximated.

## Activation

See the OpenAI agent section of [README](../README.md). Put OPENAI_API_KEY, OPENAI_MODEL and REPORT_PLANNER in Streamlit Cloud Secrets, publish the whole change set and reboot the app. Do not commit real credentials. The repository-root .env is now loaded automatically at startup; existing environment variables take precedence.

## Final local verification

1,089 tests passed; 56 subtests passed. The 33 provider/integration tests use mocks, not live OpenAI. Compilation and git diff --check succeeded. Two existing FastAPI startup deprecation warnings and a non-failing Git line-ending notice remain. No live API call, push or Cloud deployment performed.

## Conversational follow-up implementation

The main AI chatbot now separates chat/query/export/update. Queries run validated Python reports without output files. Explicit exports create files. Bounded server context supports follow-up conditions without sending computed cell values to the router. Each data turn can require two provider calls. One-cell direct updates require a server proposal, old/new UI preview and explicit confirmation; normal text cannot confirm writes. Original bytes are backed up before atomic replacement; stale data, unsupported formats, formulas and duplicate keys are rejected. This is not authentication or authorization. Production write access requires a separate security layer, backup retention and durable storage; Streamlit Cloud local files are ephemeral.

Earlier one-call/no-history statements describe the legacy reporting endpoint, not the newer conversational path. Live language quality remains unmeasured; mocked tests cannot establish semantic accuracy.

Final conversational verification: **1,109 tests passed; 73 subtests passed**. Focused chat/source-update rerun after final error-handling adjustment: **15 passed; 17 subtests passed**. Compile and diff checks succeeded. Provider responses were mocked for AI tests; no live semantic-quality evaluation or Cloud deployment performed.

## AI-only migration

Production no longer imports keyword intent routing, entity extraction, analytical-request regex gates or the deterministic natural-language planner. The old implementation is isolated in `excel_rule_engine/legacy_nlp/` solely for historical regression evaluation. Existing historical test totals above do not establish current OpenAI language accuracy.

Chat UI always calls `/api/chat`; `/api/command` is an AI compatibility adapter. Conversational report preview/auto use the OpenAI structured planner and confirmation executes the frozen approved config without re-planning. `REPORT_PLANNER=openai` is the default; `auto` is an alias; `rules` fails explicitly. Missing credentials/API failure never activate local keyword routing. Column aliases/normalization now live in `app/services/reports/schema_matching.py`; these validate references/name outputs, not classify user intent. Explicit source ambiguity and configured source-authority checks remain protective vetoes, not alternative language planners.

All migration provider tests mock HTTP; no live OpenAI evaluation or Cloud deployment is implied. Schema-valid plans can still misunderstand user meaning, so production model evaluation remains necessary.
