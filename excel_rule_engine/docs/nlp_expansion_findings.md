# NLP expansion baseline exploration

48 realistic requests, evaluated against untouched HEAD before changes. Accent-insensitive Vietnamese is used for reproducible command-line encoding. Ready is not proof of correct semantics.

## Polite and synonyms

| Request | Baseline status | Detail |
|---|---|---|
| Ban hay tinh tong doanh so giup toi nhe | unsupported | Chưa hiểu đầy đủ điều kiện: ban doanh so nhe. |
| Cho minh xem doanh thu theo san pham | unsupported | Chưa hiểu đầy đủ điều kiện: minh xem. |
| Thong ke tong doanh thu theo tung khu vuc | unsupported | Chưa hiểu đầy đủ điều kiện: theo tung. |
| Tinh tong tien luong theo bo phan | unsupported | Chưa hiểu đầy đủ điều kiện: theo bo phan. |
| Tong doanh thu va loi nhuan theo san pham | ready | {'version': 1, 'filters': [], 'filter_logic': 'and', 'group_by': ['product'], 'metrics': [{'column': 'revenue', 'operation': 'sum', 'alias': 'RevenueSum'}, {'column': 'profit', 'operation': 'sum', 'alias': 'ProfitSum'}]} |
| Cho biet doanh thu theo san pham | unsupported | Chưa hiểu đầy đủ điều kiện: biet. |
| Toi can bao cao doanh thu nam 2025 | unsupported | Chưa hiểu đầy đủ điều kiện: toi can. |
| Vui long cho toi tong doanh thu | ready | {'version': 1, 'filters': [], 'filter_logic': 'and', 'group_by': [], 'metrics': [{'column': 'revenue', 'operation': 'sum', 'alias': 'RevenueSum'}]} |

## HR counts

| Request | Baseline status | Detail |
|---|---|---|
| Co bao nhieu nhan vien | ready | {'version': 1, 'filters': [], 'filter_logic': 'and', 'group_by': [], 'metrics': [{'column': 'employee_id', 'operation': 'nunique', 'alias': 'Employees'}]} |
| Dem so nhan vien theo phong ban | ready | {'version': 1, 'filters': [], 'filter_logic': 'and', 'group_by': ['department'], 'metrics': [{'column': 'employee_id', 'operation': 'nunique', 'alias': 'Employees'}]} |
| So luong nhan su theo phong ban | unsupported | Chưa hiểu đầy đủ điều kiện: nhan su. |
| Tong so nhan vien | ready | {'version': 1, 'filters': [], 'filter_logic': 'and', 'group_by': [], 'metrics': [{'column': 'employee_id', 'operation': 'nunique', 'alias': 'Employees'}]} |
| Dem nhan vien co luong tren 10 trieu | ready | {'version': 1, 'filters': [{'column': 'salary', 'operator': 'gt', 'value': 10000000.0, 'type': 'number'}], 'filter_logic': 'and', 'group_by': [], 'metrics': [{'column': 'employee_id', 'operation': 'nunique', 'alias': 'Employees'}]} |
| Co bao nhieu nhan vien luong lon hon hoac bang 10 trieu | unsupported | Chưa hỗ trợ điều kiện: hoac. |
| Nhan vien nao co luong cao nhat | ready | {'version': 1, 'filters': [], 'filter_logic': 'and', 'group_by': ['employee_id', 'employee_name'], 'metrics': [{'column': 'salary', 'operation': 'sum', 'alias': 'SalarySum'}], 'top_n': {'column': 'SalarySum', 'n': 1, 'ascending': False}} |
| Top 2 nhan vien co tong luong cao nhat | ready | {'version': 1, 'filters': [], 'filter_logic': 'and', 'group_by': ['employee_id', 'employee_name'], 'metrics': [{'column': 'salary', 'operation': 'sum', 'alias': 'SalarySum'}], 'top_n': {'column': 'SalarySum', 'n': 2, 'ascending': False}} |

## Numeric

| Request | Baseline status | Detail |
|---|---|---|
| Dem dong doanh thu lon hon hoac bang 10 trieu | unsupported | Chưa hỗ trợ điều kiện: hoac. |
| Dem dong doanh thu nho hon hoac bang 20 trieu | unsupported | Chưa hỗ trợ điều kiện: hoac. |
| Dem dong doanh thu tren 10.000.000 | unsupported | Chưa hiểu đầy đủ điều kiện: 000. |
| Dem dong doanh thu tren 1,5 trieu | ready | {'version': 1, 'filters': [{'column': 'revenue', 'operator': 'gt', 'value': 1500000.0, 'type': 'number'}], 'filter_logic': 'and', 'group_by': [], 'metrics': [{'operation': 'rows', 'alias': 'Rows'}]} |
| Dem dong doanh thu tu 10.000.000 den 20.000.000 | unsupported | Chưa hiểu đầy đủ điều kiện: tu 10 000 000 den 20 000 000. |
| Tong doanh thu tren 10 trieu theo san pham | ready | {'version': 1, 'filters': [{'column': 'revenue', 'operator': 'gt', 'value': 10000000.0, 'type': 'number'}], 'filter_logic': 'and', 'group_by': ['product'], 'metrics': [{'column': 'revenue', 'operation': 'sum', 'alias': 'RevenueSum'}]} |
| Dem dong luong toi thieu 10 trieu | unsupported | Chưa hiểu đầy đủ điều kiện: toi thieu 10 trieu. |
| Dem dong luong toi da 20 trieu | ready | {'version': 1, 'filters': [{'column': 'salary', 'operator': 'le', 'value': 20000000.0, 'type': 'number'}], 'filter_logic': 'and', 'group_by': [], 'metrics': [{'operation': 'rows', 'alias': 'Rows'}]} |

## Dates

| Request | Baseline status | Detail |
|---|---|---|
| Doanh thu quy 1 nam 2025 | unsupported | Chưa hiểu đầy đủ điều kiện: quy 1. |
| Doanh thu quy II nam 2025 | unsupported | Chưa hiểu đầy đủ điều kiện: quy ii. |
| Doanh thu trong nam 2025 | ready | {'version': 1, 'filters': [{'column': 'date', 'operator': 'between', 'value': ['2025-01-01', '2025-12-31 23:59:59.999999999'], 'type': 'date'}], 'filter_logic': 'and', 'group_by': [], 'metrics': [{'column': 'revenue', 'operation': 'sum', 'alias': 'RevenueSum'}]} |
| Doanh thu thang 1 nam 2025 | ready | {'version': 1, 'filters': [{'column': 'date', 'operator': 'between', 'value': ['2025-01-01', '2025-01-31 23:59:59.999999999'], 'type': 'date'}], 'filter_logic': 'and', 'group_by': [], 'metrics': [{'column': 'revenue', 'operation': 'sum', 'alias': 'RevenueSum'}]} |
| Doanh thu tu ngay 01/01/2025 den ngay 31/03/2025 | unsupported | Chưa hỗ trợ nhiều khoảng thời gian trong một yêu cầu.; Chưa hiểu đầy đủ điều kiện: tu ngay 01/01/ den ngay 31/03/. |
| Doanh thu tu thang 1 den thang 3 nam 2025 | unsupported | Chưa hỗ trợ nhiều khoảng thời gian trong một yêu cầu.; Chưa hiểu đầy đủ điều kiện: tu den. |
| Doanh thu ca nam 2025 | unsupported | Chưa hiểu đầy đủ điều kiện: ca. |
| Doanh thu quy 5 nam 2025 | unsupported | Chưa hiểu đầy đủ điều kiện: quy 5. |

## Groups and scalar aggregates

| Request | Baseline status | Detail |
|---|---|---|
| Doanh thu theo san pham va khu vuc | ready | {'version': 1, 'filters': [], 'filter_logic': 'and', 'group_by': ['product', 'region'], 'metrics': [{'column': 'revenue', 'operation': 'sum', 'alias': 'RevenueSum'}]} |
| Doanh thu theo thang va san pham | ready | {'version': 1, 'filters': [], 'filter_logic': 'and', 'group_by': ['Month', 'product'], 'metrics': [{'column': 'revenue', 'operation': 'sum', 'alias': 'RevenueSum'}], 'date_group': {'column': 'date', 'frequency': 'month', 'alias': 'Month'}} |
| Gia tri lon nhat cua doanh thu | unsupported | Cần chỉ rõ nhóm để xếp hạng chỉ tiêu.; Chưa hiểu đầy đủ điều kiện: gia tri. |
| Doanh thu toi da | unsupported | Chưa hiểu đầy đủ điều kiện: toi da. |
| Luong nho nhat | unsupported | Cần chỉ rõ nhóm để xếp hạng chỉ tiêu. |
| Tong doanh thu theo tung san pham va tung khu vuc | unsupported | Chưa hiểu đầy đủ điều kiện: theo tung tung. |
| San pham nao doanh thu cao nhat | ready | {'version': 1, 'filters': [], 'filter_logic': 'and', 'group_by': ['product'], 'metrics': [{'column': 'revenue', 'operation': 'sum', 'alias': 'RevenueSum'}], 'top_n': {'column': 'RevenueSum', 'n': 1, 'ascending': False}} |
| Doanh thu trung binh theo san pham | ready | {'version': 1, 'filters': [], 'filter_logic': 'and', 'group_by': ['product'], 'metrics': [{'column': 'revenue', 'operation': 'mean', 'alias': 'RevenueMean'}]} |

## Safety

| Request | Baseline status | Detail |
|---|---|---|
| Doanh thu khong bao gom Nam | unsupported | Chưa hỗ trợ điều kiện: khong. |
| Doanh thu theo khach hang | unsupported | Chưa hiểu đầy đủ điều kiện: theo khach hang. |
| Doanh thu sau thue | unsupported | Chưa hiểu đầy đủ điều kiện: sau thue. |
| Doanh thu lon hon 10 hoac nho hon 2 trieu | unsupported | Chưa hỗ trợ điều kiện: hoac. |
| Doanh thu thang truoc | unsupported | Chưa hiểu đầy đủ điều kiện: thang truoc. |
| Doanh thu va trung binh loi nhuan | ready | {'version': 1, 'filters': [], 'filter_logic': 'and', 'group_by': [], 'metrics': [{'column': 'revenue', 'operation': 'mean', 'alias': 'RevenueMean'}, {'column': 'profit', 'operation': 'mean', 'alias': 'ProfitMean'}]} |
| Doanh thu theo san pham co tong doanh thu tren 10 trieu | ready | {'version': 1, 'filters': [{'column': 'revenue', 'operator': 'gt', 'value': 10000000.0, 'type': 'number'}], 'filter_logic': 'and', 'group_by': ['product'], 'metrics': [{'column': 'revenue', 'operation': 'sum', 'alias': 'RevenueSum'}]} |
| Doanh thu tu 20 den 10 trieu | unsupported | Cận dưới lớn hơn cận trên. |

## Findings

- Missing common polite wrappers, doanh so/bo phan synonyms and identity count variants.
- Vietnamese >= and <= phrases, grouped thousands, quarters and date ranges rejected.
- Coordinated explicit dimensions and explicit scalar min/max require extension.
- Existing silent risks: aggregate thresholds treated as row conditions, metric-scoped operators applied globally, repeated employee salary rows summed implicitly.
- Keep unknown constraints, negatives, OR, mixed sources and ambiguous scopes non-ready.
- Deferred deliberately: relative dates, arbitrary joins/OR, monthly ranges and implicit aggregate suffixes (e.g. luong nho nhat without explicit scalar grammar).