import copy

import pandas as pd
import pytest

from app.core.report_planner import plan_report
from app.services.reports.report_engine import run_report


@pytest.fixture
def sources():
    return {'sales.xlsx': pd.DataFrame({
        'Ngày': ['2025-01-01', '2025-02-15', '2024-01-01'],
        'Sản phẩm': ['Máy in', 'Bàn phím', 'Máy in'],
        'Khu vực': ['Miền Bắc', 'Miền Nam', 'Miền Bắc'],
        'Trạng thái': ['Hoàn tất', 'Đã hủy', 'Hoàn tất'],
        'Doanh thu': [20_000_000, 30_000_000, 5_000_000],
        'Lợi nhuận': [4_000_000, 6_000_000, 1_000_000],
        'Chi phí': [16_000_000, 24_000_000, 4_000_000],
        'Số lượng': [2, 3, 1], 'Mã đơn hàng': ['A', 'B', 'A'],
    })}


@pytest.mark.parametrize('text,operation,column', [
    ('Tổng doanh thu theo sản phẩm', 'sum', 'Doanh thu'),
    ('Lợi nhuận theo khu vực', 'sum', 'Lợi nhuận'),
    ('Tổng chi phí theo trạng thái', 'sum', 'Chi phí'),
    ('Số lượng theo sản phẩm', 'sum', 'Số lượng'),
    ('Doanh thu trung bình theo sản phẩm', 'mean', 'Doanh thu'),
    ('Đếm doanh thu theo sản phẩm', 'count', 'Doanh thu'),
    ('Đếm dòng theo sản phẩm', 'rows', None),
    ('Bao nhiêu đơn hàng theo sản phẩm', 'nunique', 'Mã đơn hàng'),
    ('Vui lòng giúp tôi tính tổng doanh thu là bao nhiêu?', 'sum', 'Doanh thu'),
])
def test_metrics(sources, text, operation, column):
    plan = plan_report(text, sources)
    assert plan['status'] == 'ready', plan
    assert plan['config']['metrics'][0]['operation'] == operation
    assert plan['config']['metrics'][0].get('column') == column
    run_report(sources['sales.xlsx'], plan['config'])


@pytest.mark.parametrize('text', [
    'Tổng doanh thu sản phẩm Máy in', 'Doanh thu khu vực Miền Bắc',
    'Doanh thu trạng thái Hoàn tất', 'Doanh thu Máy in Miền Bắc',
])
def test_literal_filters(sources, text):
    plan = plan_report(text, sources)
    assert plan['status'] == 'ready', plan
    assert plan['config']['filters']
    assert all(f['value'] in ('Máy in', 'Miền Bắc', 'Hoàn tất') for f in plan['config']['filters'])


@pytest.mark.parametrize('phrase,op,value', [
    ('trên 10 triệu', 'gt', 10e6), ('dưới 2 tỷ', 'lt', 2e9),
    ('>= 2 million', 'ge', 2e6), ('<= 100', 'le', 100),
    ('= 2', 'eq', 2), ('từ 10 đến 30 triệu', 'between', [10e6, 30e6]),
])
def test_numeric(sources, phrase, op, value):
    plan = plan_report('Đếm dòng doanh thu ' + phrase, sources)
    assert plan['status'] == 'ready', plan
    filt = plan['config']['filters'][0]
    assert filt['operator'] == op
    assert filt['value'] == value
    run_report(sources['sales.xlsx'], plan['config'])


@pytest.mark.parametrize('frequency,word', [('month', 'tháng'), ('quarter', 'quý'), ('year', 'năm')])
def test_time_groups(sources, frequency, word):
    plan = plan_report('Doanh thu theo ' + word + ' năm 2025', sources)
    assert plan['status'] == 'ready', plan
    assert plan['config']['date_group']['frequency'] == frequency
    run_report(sources['sales.xlsx'], plan['config'])


def test_month(sources):
    plan = plan_report('Doanh thu tháng 2 năm 2025', sources)
    assert plan['status'] == 'ready', plan
    assert run_report(sources['sales.xlsx'], plan['config'])['summary'].iloc[0, 0] == 30e6


def test_year_month_column():
    data = pd.DataFrame({'Tháng': ['2025-01', '2025-02'], 'Doanh thu': [10, 20]})
    plan = plan_report('Doanh thu tháng 2 năm 2025', {'monthly': data})
    assert plan['status'] == 'ready', plan
    assert plan['config']['filters'][0]['type'] == 'text'
    assert run_report(data, plan['config'])['summary'].iloc[0, 0] == 20


def test_hr():
    df = pd.DataFrame({'employee_id': ['a', 'a', 'b'], 'salary': [10, 20, 30], 'department': ['IT', 'IT', 'HR']})
    plan = plan_report('Lương trung bình theo phòng ban IT', {'hr': df})
    assert plan['status'] == 'ready', plan
    assert plan['config']['filters'][0]['value'] == 'IT'
    assert run_report(df, plan['config'])['summary'].iloc[0, 1] == 15
    assert plan_report('Đếm nhân viên theo phòng ban', {'hr': df})['config']['metrics'][0]['operation'] == 'nunique'


def test_top(sources):
    plan = plan_report('Top 2 sản phẩm doanh thu cao nhất theo sản phẩm', sources)
    assert plan['status'] == 'ready', plan
    assert plan['config']['top_n']['n'] == 2


@pytest.mark.parametrize('text', [
    'Doanh thu trừ đơn đã hủy', 'Doanh thu không bao gồm Đã hủy',
    'Doanh thu sản phẩm Sao Hỏa', 'Doanh thu theo khách hàng',
    'Dự báo doanh thu năm 2026', 'So sánh doanh thu năm 2024 và 2025',
    'Doanh thu tăng trưởng', 'Doanh thu ghép nhân viên',
    'Doanh thu trên 20 triệu hoặc dưới 10 triệu', 'Doanh thu hôm qua',
    'Doanh thu giảm 10 phần trăm', 'Doanh thu tháng 13 năm 2025',
])
def test_never_drop_constraints(sources, text):
    plan = plan_report(text, sources)
    assert plan['status'] == 'unsupported', plan
    assert plan['config'] is None


def test_source_ambiguity_and_explicit(sources):
    sources['other.xlsx'] = sources['sales.xlsx'].copy()
    assert plan_report('Doanh thu theo sản phẩm', sources)['status'] == 'clarify'
    plan = plan_report('Doanh thu theo sản phẩm file sales.xlsx', sources)
    assert plan['status'] == 'ready', plan
    assert plan['source'] == 'sales.xlsx'


def test_schema_and_values_unchanged(sources):
    before = copy.deepcopy(sources['sales.xlsx'])
    a = plan_report('tong DOANH THU san pham may in nam 2025', sources)
    b = plan_report('Tổng doanh thu sản phẩm Máy in năm 2025', sources)
    assert a == b
    pd.testing.assert_frame_equal(before, sources['sales.xlsx'])


def test_missing_data():
    assert plan_report('', {})['status'] == 'clarify'
    assert plan_report('Doanh thu', {})['status'] == 'clarify'
    assert plan_report('Doanh thu', {'x': pd.DataFrame({'foo': [1]})})['status'] == 'clarify'


def test_natural_top_dimension(sources):
    plan = plan_report('Top 2 sản phẩm doanh thu cao nhất', sources)
    assert plan['status'] == 'ready', plan
    assert plan['config']['group_by'] == ['Sản phẩm']
    assert plan['config']['top_n']['n'] == 2


def test_numeric_metric_without_repeated_column(sources):
    plan = plan_report('Doanh thu trên 10 triệu theo sản phẩm', sources)
    assert plan['status'] == 'ready', plan
    assert plan['config']['metrics'][0]['column'] == 'Doanh thu'


def test_unknown_product_and_multiple_literal_values(sources):
    assert plan_report('Doanh thu Máy in và Bàn phím', sources)['status'] == 'unsupported'
    assert plan_report('Doanh thu cao nhất', sources)['status'] == 'unsupported'
    assert plan_report('Doanh thu sản phẩm', sources)['status'] == 'clarify'


def test_employee_quantity_phrase():
    df = pd.DataFrame({'employee_id': ['a', 'a'], 'salary': [10, 20], 'department': ['IT', 'IT']})
    plan = plan_report('Số lượng nhân viên theo phòng ban', {'hr': df})
    assert plan['status'] == 'ready', plan
    assert plan['config']['metrics'] == [{'column': 'employee_id', 'operation': 'nunique', 'alias': 'Employees'}]

@pytest.mark.parametrize('text', ['Tổng doanh thu và chi phí trung bình', 'Đếm doanh thu và tổng chi phí'])
def test_mixed_operation_scope_needs_clarification(sources, text):
    plan = plan_report(text, sources)
    assert plan['status'] != 'ready'
    assert plan['config'] is None

def test_mean_and_row_count_are_independent(sources):
    plan = plan_report('Doanh thu trung bình và đếm dòng', sources)
    assert plan['status'] == 'ready', plan
    assert [m['operation'] for m in plan['config']['metrics']] == ['mean', 'rows']


def test_reserved_negation_cannot_be_product_value(sources):
    sources['sales.xlsx'].loc[0, 'Sản phẩm'] = 'không'
    plan = plan_report('Doanh thu không theo khu vực', sources)
    assert plan['status'] != 'ready'

@pytest.mark.parametrize('literal,text', [('tổng', 'Tổng doanh thu'), ('trung bình', 'Doanh thu trung bình')])
def test_metric_words_are_not_implicit_product_filters(sources, literal, text):
    sources['sales.xlsx'].loc[0, 'Sản phẩm'] = literal
    plan = plan_report(text, sources)
    assert plan['status'] == 'ready', plan
    assert plan['config']['filters'] == []
