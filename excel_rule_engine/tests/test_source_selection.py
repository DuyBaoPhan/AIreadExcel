"""Source choice must be justified by request/data evidence, not order."""
import pandas as pd
import pytest

from app.core.report_planner import plan_report


def sales(products=('Printer', 'Keyboard'), dates=('2025-01-01', '2025-02-01')):
    return pd.DataFrame({'product': products, 'date': dates, 'revenue': [10, 20]})


def hr():
    return pd.DataFrame({'employee_id': ['a', 'b'], 'salary': [10, 20], 'department': ['IT', 'HR']})


def test_schema_selects_sales_not_first_hr():
    result = plan_report('Tong doanh thu theo san pham', {'first.xlsx': hr(), 'second.xlsx': sales()})
    assert result['status'] == 'ready', result
    assert result['source'] == 'second.xlsx'
    assert result['relevant_sources'] == ['second.xlsx']
    assert result['selection_reason']


def test_schema_selects_hr_not_misleading_filename():
    result = plan_report('Luong trung binh theo phong ban', {'payroll.xlsx': sales(), 'sales.xlsx': hr()})
    assert result['status'] == 'ready', result
    assert result['source'] == 'sales.xlsx'


@pytest.mark.parametrize('reverse', [False, True])
def test_equivalent_snapshots_remain_ambiguous(reverse):
    sources = {'one.xlsx': sales(), 'two.xlsx': sales()}
    if reverse:
        sources = dict(reversed(list(sources.items())))
    result = plan_report('Tong doanh thu theo san pham', sources)
    assert result['status'] == 'clarify', result
    assert set(result['ambiguity_candidates']) == set(sources)
    assert result['source'] is None and result['config'] is None


def test_literal_evidence_disambiguates():
    result = plan_report('Tong doanh thu san pham Printer', {
        'one.xlsx': sales(), 'two.xlsx': sales(('Desk', 'Chair'))})
    assert result['status'] == 'ready', result
    assert result['source'] == 'one.xlsx'


def test_unknown_literal_does_not_choose_a_snapshot():
    result = plan_report('Tong doanh thu san pham Mars', {
        'one.xlsx': sales(), 'two.xlsx': sales(('Desk', 'Chair'))})
    assert result['status'] == 'unsupported', result
    assert result['relevant_sources'] == ['one.xlsx', 'two.xlsx']
    assert result['source'] is None and result['config'] is None


def test_date_coverage_disambiguates():
    result = plan_report('Tong doanh thu nam 2025', {
        'old.xlsx': sales(dates=('2024-01-01', '2024-02-01')), 'current.xlsx': sales()})
    assert result['status'] == 'ready', result
    assert result['source'] == 'current.xlsx'


def test_no_date_coverage_does_not_choose_snapshot():
    result = plan_report('Tong doanh thu nam 2030', {'one.xlsx': sales(), 'two.xlsx': sales()})
    assert result['status'] == 'clarify', result
    assert set(result['relevant_sources']) == {'one.xlsx', 'two.xlsx'}


def test_explicit_full_filename_overrides_coverage():
    result = plan_report('Tong doanh thu nam 2025 file old.xlsx', {
        'old.xlsx': sales(dates=('2024-01-01', '2024-02-01')), 'current.xlsx': sales()})
    assert result['status'] == 'ready', result
    assert result['source'] == 'old.xlsx'


def test_parse_failure_is_not_source_selection_evidence():
    # Both have the required capabilities; ambiguity in column mapping is a
    # real source issue, not grounds to silently choose the other snapshot.
    duplicate_alias = sales().assign(sales=[30, 40])
    result = plan_report('Tong doanh thu theo san pham', {
        'one.xlsx': sales(), 'two.xlsx': duplicate_alias})
    assert result['status'] == 'clarify', result
    assert set(result['relevant_sources']) == {'one.xlsx', 'two.xlsx'}
    assert result['source'] is None and result['config'] is None


def test_unsupported_sales_request_never_returns_hr_diagnostics():
    result = plan_report('Doanh thu theo san pham tren sao Hoa', {
        'hr.xlsx': hr(), 'sales-a.xlsx': sales(), 'sales-b.xlsx': sales()})
    assert result['status'] == 'unsupported', result
    assert result['relevant_sources'] == ['sales-a.xlsx', 'sales-b.xlsx']
    assert not any('salary' in message or 'employee' in message for message in result['questions'])
    assert result['source'] is None and result['config'] is None


def test_ancillary_date_column_does_not_make_hr_a_sales_candidate():
    personnel = hr().assign(date=['2025-01-01', '2025-02-01'])
    revenue = sales().drop(columns='date')
    result = plan_report('Tong doanh thu nam 2025', {'hr.xlsx': personnel, 'sales.xlsx': revenue})
    assert result['status'] == 'clarify', result
    assert result['relevant_sources'] == ['sales.xlsx']
    assert result['source'] is None and result['config'] is None

@pytest.mark.parametrize('text', ['Tong so luong', 'Dem dong so luong tren 10 trieu',
                                  'So luong theo san pham'])
def test_quantity_phrase_does_not_make_salary_source_relevant(text):
    sale = sales().assign(quantity=[1, 2])
    result = plan_report(text, {'hr.xlsx': hr(), 'sales.xlsx': sale})
    assert result['status'] == 'ready', result
    assert result['source'] == 'sales.xlsx'
    assert result['candidate_sources'] == ['sales.xlsx']
