# Independent correctness audit ? initial findings

These findings were reproduced before campaign fixes (2026-11-03). Do not treat safe rejection as successful execution.

1. Vietnamese thousands: `Tong doanh thu tren 1.000` interpreted threshold 1 not 1000; `tu 1.000 den 2.000` likewise.
2. Same-column operation loss: `Tong va trung binh doanh thu` only mean; `Dem va tong doanh thu` only count. Must implement both or clarify.
3. Repeated salary records: E1 salaries100+100 and E2 salary150, highest-paid employee incorrectly E1 sum200. Need explicit aggregation scope or clarify.
4. Source/literal collision: filename `A`, product A/B revenues100/200; `Tong doanh thu theo san pham A` consumes product A as filename and returns both. Only explicit source markers should disambiguate ambiguous names.
5. Sum overflow: int64 [2**62,2**62] wraps negative; [1e308,1e308] produces infinity.
6. `Top 1 san pham doanh thu theo thang` ranks month-product tuples globally; scope ambiguous versus per-month winners. Ask rather than silently choose.
7. `Tong doanh thu theo san pham doanh thu tren 10 trieu`: row vs aggregate threshold ambiguity. Do not silently apply HAVING-like phrase to raw rows.
8. Routing `So nhan vien theo phong ban` / `So don hang theo san pham` must preview planner.

Initial fixed corpus: see nlp_benchmark_baseline.json (464 cases; 458 passed, 6 failed). Independent exploratory findings above extend beyond corpus and need regressions.
