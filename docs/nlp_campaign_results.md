# Vietnamese NLP regression campaign

## Scope and measurement

- No LLM or external service added. Deterministic schema-aware finance/HR requests.
- Expanded corpus: 596 request/source/routing cases, 572 distinct sentences. Accent/no-accent pairs are explicit normalization checks, not independent semantic features.
- Same corrected expanded corpus: before planner/classifier revision `39a8b66e6e533e38fe09d5f26d4aa9b81828b35a` 482/596; after first integrated run 596/596. Final verification recorded below when complete.
- Executable reports: 416/514 before -> 514/514 after; clarification 14/26 ->26/26; unsupported safety30/30; API preview routing22/26 ->26/26.
- Before/after JSON record every sentence, expected config and independent result, actual config/result and failures. Compare the same corpus, not the smaller original denominator.
- Original baseline464 cases retained immutably. Repeated salary ID ranking expectation corrected to explicit total; bare salary asks clarification. Six ambiguous bare personnel-department phrasings made explicit. See baseline notes.

## Fixed families

1. Vietnamese amounts: `1.000`, `10.000.000`, `1,5 tri?u`, grouped decimals; >=/<= Vietnamese comparisons.
2. Quantity phrase no longer becomes a second salary filter (`s? l??ng` vs `l??ng`).
3. Polite requests and schema synonyms (`doanh s?`, `b? ph?n`), coordinated dimensions.
4. Calendar quarters including Roman numerals and absolute dd/mm/yyyy inclusive ranges.
5. Identity-aware employee/order counts and classifier routing.
6. Explicit scalar min/max distinct from entity rankings.
7. Same-metric mixed operators no longer silently lose requested calculations: clarify unsupported operator scope.
8. Employee repeated salary records require explicit sum/mean scope; names cannot merge distinct IDs.
9. Source labels cannot silently consume a matching data constraint.
10. Period+entity ranking and grouped aggregate thresholds ask scope instead of guessing global ranking or row-level filtering.
11. Partial-day date intervals on monthly-only sources now ask for daily detail rather than include whole months.
12. Scaled mean calculation avoids overflowing an intermediate sum even when the true mean is finite.
13. Integer sum wraparound and nonfinite float totals fail explicitly. Integer SUM limited to absolute999,999,999,999,999 for conservative Excel15-digit output; rescale larger totals.

## Reproduce (repository root, PowerShell)

```powershell
$env:PYTHONIOENCODING='utf-8'
.\excel_rule_engine\venv\Scripts\python.exe excel_rule_engine/tests/test_nlp_benchmark.py --audit docs/nlp_benchmark_current.json
.\excel_rule_engine\venv\Scripts\python.exe excel_rule_engine/tests/test_nlp_benchmark.py --audit docs/nlp_benchmark_expanded_before.json --baseline-ref 39a8b66e6e533e38fe09d5f26d4aa9b81828b35a
.\excel_rule_engine\venv\Scripts\python.exe -m pytest -q
```

Audit mode saves failures and exits zero intentionally; pytest is the strict acceptance gate. Baseline-ref executes only a trusted local project revision; use known reviewed revisions.

## Limits and honest behavior

This finite corpus is not a guarantee of arbitrary Vietnamese understanding. Forecasts, general free-form formulas, arbitrary joins, OR/exclusion logic, relative dates, group-level HAVING and per-period top-N remain unsupported or require clarification. Multi-operator requests can need splitting or the advanced report UI. Unknown constraints are not discarded. New reports still require explicit approval; no fallback to generic merge.

Natural-language fixture tests are automated, not manual browser validation. Workbook tests exercise actual CSV/XLSX snapshot loading, planner, approval fingerprint, engine, and openpyxl-readable output. Only output paths are redirected to test temporary directories.

## Verification

Final full regression: **956 passed, 56 subtests passed**, with 2 pre-existing FastAPI startup deprecation warnings (36.27 seconds). Real planner-to-workbook tests:14 passed. Independent adversarial safety includes partial-month granularity checks and finite extreme means. Compileall and git diff --check passed. No deployment, commit, or push performed.

## Actual demo source smoke checks

Executed without writing project outputs: top3 product revenues selected Sales_Data.xlsx only; Laptop Pro X70,075,000,000; Màn Hình4K32,688,000,000; Tai Nghe ANC12,062,400,000. Lowest product Chuột Không Dây4,125,600,000. Laptop Pro X year2024 total70,075,000,000. Quarter1 year2024 total25,125,200,000. Employee salary >=10,000,000 asks source selection across five HR files rather than concatenate them. Amount units are source-defined, not inferred currency.
