"""Scoped deterministic Vietnamese NLP expansion and safety regressions."""
import pandas as pd
import pytest

from legacy_nlp.analytical_request import is_analytical_request
from legacy_nlp.report_planner import plan_report
from app.services.reports.report_engine import run_report


@pytest.fixture
def sales():
    return pd.DataFrame({'date': ['2025-01-01', '2025-03-31', '2025-04-01'],
                         'product': ['A', 'A', 'B'], 'region': ['North', 'South', 'North'],
                         'revenue': [10_000_000, 20_000_000, 30_000_000],
                         'profit': [1, 2, 3], 'order_id': ['a', 'b', 'c']})


@pytest.fixture
def hr():
    return pd.DataFrame({'employee_id': ['e1', 'e2'], 'employee_name': ['An', 'Binh'],
                         'department': ['IT', 'HR'], 'salary': [10_000_000, 20_000_000]})


@pytest.mark.parametrize('text', [
    'Ban hay tinh tong doanh so giup toi nhe',
    'Cho minh xem doanh thu theo san pham',
    'Thong ke tong doanh thu theo tung khu vuc',
    'Cho biet doanh thu theo san pham',
    'Toi can bao cao doanh thu nam 2025',
    'Vui long cho toi tong doanh thu',
])
def test_polite_and_synonym_requests(sales, text):
    plan = plan_report(text, {'sales': sales})
    assert plan['status'] == 'ready', plan
    run_report(sales, plan['config'])


@pytest.mark.parametrize('text', ['Co bao nhieu nhan vien', 'Dem so nhan vien theo phong ban',
    'So luong nhan su theo phong ban', 'Tong so nhan vien',
    'Dem nhan vien co luong tren 10 trieu',
    'Co bao nhieu nhan vien luong lon hon hoac bang 10 trieu'])
def test_identity_counts(hr, text):
    plan = plan_report(text, {'hr': hr})
    assert plan['status'] == 'ready', plan
    assert plan['config']['metrics'] == [{'column': 'employee_id', 'operation': 'nunique', 'alias': 'Employees'}]
    run_report(hr, plan['config'])


@pytest.mark.parametrize('phrase,operator,value', [
    ('lon hon hoac bang 10 trieu', 'ge', 10e6),
    ('nho hon hoac bang 20 trieu', 'le', 20e6),
    ('tren 10.000.000', 'gt', 10e6),
    ('tren 1,5 trieu', 'gt', 1.5e6),
    ('tren 1.500.000,5', 'gt', 1500000.5),
    ('tu 10.000.000 den 20.000.000', 'between', [10e6, 20e6]),
    ('toi thieu 10 trieu', 'ge', 10e6), ('toi da 20 trieu', 'le', 20e6),
])
def test_number_formats(sales, phrase, operator, value):
    plan = plan_report('Dem dong doanh thu ' + phrase, {'sales': sales})
    assert plan['status'] == 'ready', plan
    assert plan['config']['filters'][0]['operator'] == operator
    assert plan['config']['filters'][0]['value'] == value
    run_report(sales, plan['config'])


@pytest.mark.parametrize('text,groups', [
    ('Doanh thu theo san pham va khu vuc', ['product', 'region']),
    ('Doanh thu theo san pham, khu vuc', ['product', 'region']),
    ('Doanh thu theo tung san pham va tung khu vuc', ['product', 'region']),
    ('Doanh thu theo thang va san pham', ['Month', 'product']),
])
def test_coordinated_explicit_groups(sales, text, groups):
    plan = plan_report(text, {'sales': sales})
    assert plan['status'] == 'ready', plan
    assert plan['config']['group_by'] == groups
    run_report(sales, plan['config'])


@pytest.mark.parametrize('text,total', [
    ('Doanh thu quy 1 nam 2025', 30e6),
    ('Doanh thu quy II nam 2025', 30e6),
    ('Doanh thu quy 1', 30e6),
    ('Doanh thu tu ngay 01/01/2025 den ngay 31/03/2025', 30e6),
    ('Doanh thu ca nam 2025', 60e6),
])
def test_absolute_date_intervals(sales, text, total):
    plan = plan_report(text, {'sales': sales})
    assert plan['status'] == 'ready', plan
    assert run_report(sales, plan['config'])['summary'].iloc[0, 0] == total


@pytest.mark.parametrize('text,op', [
    ('Gia tri lon nhat cua doanh thu', 'max'),
    ('Gia tri nho nhat cua doanh thu', 'min'),
    ('Max doanh thu', 'max'), ('Minimum doanh thu', 'min'),
])
def test_explicit_scalar_aggregate(sales, text, op):
    plan = plan_report(text, {'sales': sales})
    assert plan['status'] == 'ready', plan
    assert plan['config']['metrics'][0]['operation'] == op
    assert 'top_n' not in plan['config']
    run_report(sales, plan['config'])


@pytest.mark.parametrize('text', [
    'Tong doanh thu tren 10 trieu theo san pham',
    'Doanh thu theo san pham co tong doanh thu tren 10 trieu',
    'Doanh thu va trung binh loi nhuan',
    'Doanh thu khong bao gom South', 'Doanh thu theo khach hang',
    'Doanh thu sau thue', 'Doanh thu tren 10 hoac duoi 2 trieu',
    'Doanh thu thang truoc', 'Doanh thu quy 5 nam 2025',
    'Doanh thu tu ngay 31/03/2025 den ngay 01/01/2025',
    'Doanh thu tu ngay 31/02/2025 den ngay 01/03/2025',
    'Doanh thu theo san pham va khach hang',
    'Doanh thu tu 20 den 10 trieu',
    'Gia tri lon nhat cua doanh thu va loi nhuan',
    'Gia tri lon nhat cua doanh thu trung binh',
    'Doanh thu quy 1 nam 2025 thang 1 nam 2025',
])
def test_unsupported_or_ambiguous_scope_never_ready(sales, text):
    plan = plan_report(text, {'sales': sales})
    assert plan['status'] != 'ready', plan
    assert plan['config'] is None


def test_repeated_employee_salary_requires_explicit_aggregate(hr):
    hr = pd.concat([hr, hr.iloc[[0]]], ignore_index=True)
    assert plan_report('Nhan vien nao luong cao nhat', {'hr': hr})['status'] == 'clarify'
    plan = plan_report('Nhan vien nao tong luong cao nhat', {'hr': hr})
    assert plan['status'] == 'ready', plan


@pytest.mark.parametrize('text', ['\u0110\u1ebfm nhan vien', '\u0110\u1ebfm dong',
    'So luong theo san pham', 'So nhan su theo phong ban', 'Doanh so theo khu vuc',
    'Max quantity', 'Gia tri nho nhat cua quantity'])
def test_classifier_uses_shared_vietnamese_normalization(text):
    assert is_analytical_request(text)


@pytest.mark.parametrize('literal', ['cao nhat', 'trung binh', 'luong', 'nhan vien', 'hay', 'cho toi'])
def test_grammar_literals_cannot_become_hidden_filters(sales, literal):
    sales['product'] = literal
    plan = plan_report('San pham nao doanh thu cao nhat', {'sales': sales})
    assert plan['status'] == 'ready', plan
    assert not plan['config']['filters']


@pytest.mark.parametrize('text', ['So luong tu 2 den 5', 'Tong so luong tu 2 den 5'])
def test_quantity_between_does_not_also_filter_salary(text):
    frame = pd.DataFrame({'quantity': [1, 3, 6], 'salary': [100, 200, 300]})
    plan = plan_report(text, {'data.xlsx': frame})
    assert plan['status'] == 'ready', plan
    assert plan['config']['filters'] == [{'column': 'quantity', 'operator': 'between', 'value': [2, 5], 'type': 'number'}]


@pytest.mark.parametrize('prefix', ['Tong luong phong ban ', 'Tong luong ', 'Dem luong '])
def test_reserved_hr_literal_does_not_swallow_identity_count(prefix):
    frame = pd.DataFrame({'employee_id': ['e1', 'e2'], 'department': ['Nh\u00e2n s\u1ef1', 'IT'], 'salary': [100, 200]})
    plan = plan_report(prefix + 'Nh\u00e2n s\u1ef1', {'hr.xlsx': frame})
    assert plan['status'] == 'ready', plan
    assert plan['config']['filters'][0]['value'] == 'Nh\u00e2n s\u1ef1'
    count = plan_report('So luong nhan su theo phong ban', {'hr.xlsx': frame})
    assert count['status'] == 'ready', count
    assert count['config']['filters'] == []
    assert count['config']['metrics'][0]['operation'] == 'nunique'


@pytest.mark.parametrize('source,marker', [('A', 'file A'), ('sales', 'nguon sales'), ('sales.xlsx', 'sales.xlsx')])
def test_explicit_source_names_remain_supported(source, marker):
    frame = pd.DataFrame({'product': ['A', 'B'], 'revenue': [100, 200]})
    plan = plan_report('Tong doanh thu theo san pham ' + marker, {source: frame})
    assert plan['status'] == 'ready', plan
    assert plan['source'] == source
    assert not plan['config']['filters']
