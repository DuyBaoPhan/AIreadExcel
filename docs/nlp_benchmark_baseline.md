# Vietnamese NLP benchmark: initial baseline

Captured on 2026-11-03 before production fixes. The immutable detailed snapshot is [nlp_benchmark_baseline.json](nlp_benchmark_baseline.json): each of 464 requests records its sentence, category, expected status/config/result, actual plan/result and failure reasons.

## Reproduce

Run from repository root using the existing project virtual environment (system Python lacks pytest):

```powershell
$env:PYTHONIOENCODING='utf-8'
excel_rule_engine\venv\Scripts\python.exe excel_rule_engine/tests/test_nlp_benchmark.py --audit docs/nlp_benchmark_current.json
excel_rule_engine\venv\Scripts\python.exe -m pytest excel_rule_engine/tests/test_nlp_benchmark.py -q
```

The audit deliberately exits zero and preserves real failures in JSON. Pytest strictly asserts all expectations. Do not overwrite the initial baseline when evaluating fixes.

## Initial results

| Expected behavior | Passed | Failed | Total |
|---|---:|---:|---:|
| Supported executable report | 398 | 6 | 404 |
| Ask clarification | 14 | 0 | 14 |
| Unsupported safety | 30 | 0 | 30 |
| Command routes to preview, never export | 16 | 0 | 16 |
| All | 458 | 6 | 464 |

Safety/clarification are not counted as supported analytical successes. Accent and accent-free pairs are intentional normalization checks; 464 is the number of distinct request/source/routing tuples, not a claim of 464 independent semantic capabilities.

## Failures

Each row represents both an accented request and its accent-free equivalent (six failing requests total).

| Category | Request | Expected | Actual |
|---|---|---|---|
| Numeric filter | Đếm dòng số lượng từ 0 đến 20 triệu | Ready; sales source; quantity between 0 and 20,000,000; 9 rows | Clarify: missing salary column |
| HR ranking | Nhân viên nào có lương cao nhất | Ready; HR source; group by employee ID and display name; E03, Trần Bình, 45,000,000 | Clarify: missing salary/identity on sales source |
| HR ranking | Nhân viên nào có lương thấp nhất | Ready; HR source; E05, Đỗ Dũng, 0 | Clarify: missing salary/identity on sales source |

All finance aggregates (128), calendar groups (24), calendar boundaries (48), product rankings (48), literal filters (48), HR aggregates (12), HR literal filters (36), identity counts (6), explicit-source selection (2), clarification (14), unsupported conditions (30), and routing (16) passed initially. Numeric filters passed 46/48; HR ranking passed 0/4.

## Method and fixture

Expected configurations are hand-authored from the corpus, never obtained from planner output. A separate pandas oracle implements filtering, grouping, null-aware aggregations and stable ranking without importing engine conversion/filtering helpers. Every ready case compares exact source/configuration and full summary values, not merely ready status. Non-ready cases assert no executable config. Routing mocks the preview and legacy export boundaries and asserts preview exactly once and export never, without filesystem exports, database writes, UI, or network.

The fixed finance and HR fixtures include four products, three regions/statuses/departments, Vietnamese column names and values, repeated order and employee IDs, two different employees sharing a display name, null amounts/IDs, zero and negative values, leap day, month-end timestamps, year-end timestamps, and adjacent-year records. Category coverage is enforced by a separate test.

## Acceptance correction after independent review

The immutable baseline retains its original 464 expectations. Four HR ranking expectations assumed an implicit salary sum despite repeated employee IDs across dates. That assumption was not justified. Current executable ranking cases explicitly ask **tổng lương**; four new bare-salary cases require clarification. This is a documented oracle correction, not a claim those four requests became supported. The corrected corpus has 468 cases before further additions. Initial JSON must not be overwritten; comparisons account for this semantic correction.

Six original bare `lương Nhân sự` cases now state `phòng ban Nhân sự`: the token also means personnel generally, so it must not silently become a department filter without context. The original snapshot remains unchanged. Explicit department expectations are unchanged.
