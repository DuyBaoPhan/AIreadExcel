"""Independent adversarial cases discovered during the broad NLP campaign."""
import pandas as pd
import pytest
from legacy_nlp.report_planner import plan_report
from legacy_nlp.analytical_request import is_analytical_request
from app.services.reports.report_engine import run_report


@pytest.mark.parametrize('text', [
    'Tong va trung binh doanh thu',
    'Dem va tong doanh thu',
    'Tong doanh thu va doanh thu trung binh',
])
def test_same_column_multiple_operations_not_silently_collapsed(text):
    plan = plan_report(text, {'sales.xlsx': pd.DataFrame({'revenue': [6, 6, 15]})})
    assert plan['status'] != 'ready' or len(plan['config']['metrics']) == 2, plan


@pytest.mark.parametrize('text', ['So nhan vien theo phong ban', 'So don hang theo san pham', 'So luong theo san pham'])
def test_identity_and_quantity_routes_are_analytical(text):
    assert is_analytical_request(text)


@pytest.mark.parametrize('filename,literal', [('A', 'A'), ('sales', 'sales')])
def test_short_source_names_cannot_swallow_literal_filters(filename, literal):
    frame = pd.DataFrame({'product': [literal, 'other'], 'revenue': [100, 200]})
    plan = plan_report('Tong revenue theo product ' + literal, {filename: frame})
    if plan['status'] == 'ready':
        result = run_report(frame, plan['config'])['summary']
        assert result['product'].tolist() == [literal], plan
    else:
        assert plan['config'] is None


def test_period_ranking_does_not_guess_global_tuple_scope():
    frame = pd.DataFrame({'product': ['A', 'B', 'A', 'B'],
                          'month': ['2025-01', '2025-01', '2025-02', '2025-02'],
                          'revenue': [10, 20, 30, 40]})
    plan = plan_report('Top 1 san pham doanh thu theo thang', {'sales.xlsx': frame})
    assert plan['status'] != 'ready', plan
    assert plan['config'] is None


def test_post_group_threshold_not_guessed_as_row_threshold():
    frame = pd.DataFrame({'product': ['A', 'A', 'B'], 'revenue': [6e6, 6e6, 15e6]})
    plan = plan_report('Tong doanh thu theo san pham doanh thu tren 10 trieu', {'sales.xlsx': frame})
    assert plan['status'] != 'ready', plan


def test_employee_repeated_salary_scope_requires_clarification():
    frame = pd.DataFrame({'employee_id': ['e1', 'e1', 'e2'], 'salary': [100, 100, 150]})
    plan = plan_report('Nhan vien nao luong cao nhat', {'hr.xlsx': frame})
    assert plan['status'] != 'ready', plan


@pytest.mark.parametrize('number,expected', [('1.000', 1000), ('1.000.000', 1000000), ('1,5 trieu', 1500000)])
def test_vietnamese_numeric_separators(number, expected):
    frame = pd.DataFrame({'revenue': [500, 1500, 2e6]})
    plan = plan_report('Dem dong doanh thu tren ' + number, {'sales.xlsx': frame})
    assert plan['status'] == 'ready', plan
    assert plan['config']['filters'][0]['value'] == expected, plan

@pytest.mark.parametrize('text', [
    'Doanh thu tu ngay 15/01/2025 den ngay 20/01/2025',
    'Doanh thu tu ngay 02/01/2025 den ngay 28/02/2025',
])
def test_monthly_sources_cannot_answer_partial_day_intervals(text):
    frame = pd.DataFrame({'month': ['2025-01', '2025-02'], 'revenue': [100, 200]})
    plan = plan_report(text, {'sales.xlsx': frame})
    assert plan['status'] == 'clarify', plan
    assert plan['config'] is None


def test_monthly_sources_allow_exact_whole_month_intervals():
    frame = pd.DataFrame({'month': ['2025-01', '2025-02'], 'revenue': [100, 200]})
    plan = plan_report('Doanh thu tu ngay 01/01/2025 den ngay 31/01/2025', {'sales.xlsx': frame})
    assert plan['status'] == 'ready', plan
    assert run_report(frame, plan['config'])['summary']['RevenueSum'].tolist() == [100]
