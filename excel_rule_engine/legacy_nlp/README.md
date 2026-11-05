# Legacy NLP archive

> **Historical regression code only ? not part of the production runtime.**

These modules preserve the retired keyword/regex intent router, command parser,
entity extraction, analytical-request classifier, deterministic report planner,
response templates, and source-policy heuristic for offline regression tests.
The active application uses the AI provider; it must never import this package
or fall back to these rules when AI is unavailable. Old `app.core` and
`app.services.sources.source_policy` import paths are intentionally not supported.

`scripts/run_test_cases.py` is a historical, direct-module demonstration of the
retired parser, not an acceptance test of the current AI application.
