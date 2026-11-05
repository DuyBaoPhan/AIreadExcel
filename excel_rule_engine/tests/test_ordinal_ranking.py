"""Ranking positions are independently verified, including stable tie handling."""
import copy

import pandas as pd
import pytest

from legacy_nlp.report_planner import plan_report
from app.services.reports.report_engine import MAX_ROWS, load_config, run_report, serialize_config


@pytest.fixture
def frame():
    # First-seen group order is Z, B, A, C; B and A tie for the lead.
    return pd.DataFrame({'Product': ['Z', 'B', 'A', 'C', 'Z'],
                         'Revenue': [10, 90, 90, 5, 20]})


@pytest.mark.parametrize('text', [
    'san pham co doanh thu dung top 2 la',
    'san pham co doanh thu xep top 2',
    'san pham co doanh thu nam trong top 2',
    'san pham co doanh thu thuoc top 2',
    'top 2 san pham doanh thu cao nhat',
])
def test_top_two_returns_two_leaders(frame, text):
    plan = plan_report(text, {'sales.xlsx': frame})
    assert plan['status'] == 'ready', plan
    assert plan['config']['top_n'] == {'column': 'RevenueSum', 'n': 2, 'ascending': False}
    result = run_report(frame, plan['config'])
    assert result['summary'].to_dict('records') == [
        {'Product': 'B', 'RevenueSum': 90}, {'Product': 'A', 'RevenueSum': 90}]
    pd.testing.assert_frame_equal(result['data'], frame)


@pytest.mark.parametrize('text,expected,ascending', [
    ('san pham dung thu 2 ve doanh thu', 'A', False),
    ('san pham xep hang thu 2 ve doanh thu', 'A', False),
    ('san pham co doanh thu cao thu 2', 'A', False),
    ('san pham co doanh thu thap thu 2', 'Z', True),
    ('san pham co doanh thu nho thu 2', 'Z', True),
])
def test_second_position_is_one_row_not_dense_rank(frame, text, expected, ascending):
    original = frame.copy(deep=True)
    plan = plan_report(text, {'sales.xlsx': frame})
    assert plan['status'] == 'ready', plan
    assert plan['config']['top_n'] == {
        'column': 'RevenueSum', 'n': 1, 'ascending': ascending, 'offset': 1}
    assert any('dense rank' in item for item in plan['explanation'])
    restored = load_config(serialize_config(plan['config']))
    assert restored == plan['config']
    result = run_report(frame, restored)
    assert result['summary']['Product'].tolist() == [expected]
    pd.testing.assert_frame_equal(result['data'], original)
    pd.testing.assert_frame_equal(frame, original)


@pytest.mark.parametrize('text', [
    'san pham doanh thu dung yen top 2',
    'san pham doanh thu thu khac top 2',
    'san pham doanh thu cao thu 2 theo mau sac',
    'san pham doanh thu dung thu 0',
    'san pham doanh thu dung thu 10001',
])
def test_unknown_and_invalid_clauses_do_not_disappear(frame, text):
    assert plan_report(text, {'sales.xlsx': frame})['status'] != 'ready'


@pytest.mark.parametrize('text', [
    'top 2 san pham doanh thu cao thu 2',
    'san pham doanh thu cao thu 2 thap nhat',
    'san pham doanh thu cao thu 2 thap thu 3',
    'top 2 top 3 san pham doanh thu',
])
def test_conflicting_rankings_require_clarification(frame, text):
    assert plan_report(text, {'sales.xlsx': frame})['status'] == 'clarify'


@pytest.mark.parametrize('top', [
    {'column': 'Revenue', 'n': 1, 'offset': True},
    {'column': 'Revenue', 'n': 1, 'offset': -1},
    {'column': 'Revenue', 'n': 1, 'offset': MAX_ROWS},
    {'column': 'Revenue', 'n': 2, 'offset': MAX_ROWS - 1},
    {'column': 'Revenue', 'offset': 1},
    {'column': 'Revenue', 'n': True, 'offset': 1},
    {'column': 'Revenue', 'n': 0, 'offset': 1},
])
def test_invalid_offset_configs_are_rejected(frame, top):
    config = {'version': 1, 'top_n': top}
    with pytest.raises(ValueError):
        serialize_config(config)
    with pytest.raises(ValueError):
        run_report(frame, config)


def test_detail_offset_and_missing_position(frame):
    original = copy.deepcopy(frame)
    result = run_report(frame, {'version': 1, 'top_n': {
        'column': 'Revenue', 'n': 1, 'offset': 1}})
    assert result['data'].to_dict('records') == [{'Product': 'A', 'Revenue': 90}]
    assert result['summary'].empty
    result = run_report(frame, {'version': 1, 'top_n': {
        'column': 'Revenue', 'n': 1, 'offset': 99}})
    assert result['data'].empty
    pd.testing.assert_frame_equal(frame, original)


def test_accented_screenshot_request(frame):
    text = 's\u1ea3n ph\u1ea9m c\u00f3 doanh thu \u0111\u1ee9ng top 2 l\u00e0'
    plan = plan_report(text, {'sales.xlsx': frame})
    assert plan['status'] == 'ready', plan
    assert run_report(frame, plan['config'])['summary']['Product'].tolist() == ['B', 'A']


def test_export_preserves_ordinal_config_and_evidence(frame):
    from io import BytesIO
    import json
    from openpyxl import load_workbook
    from app.services.reports.advanced_report_export import build_advanced_report_bytes

    plan = plan_report('san pham co doanh thu cao thu 2', {'sales.xlsx': frame})
    result = run_report(frame, plan['config'])
    blob = build_advanced_report_bytes(result, plan['config'])
    workbook = load_workbook(BytesIO(blob))
    try:
        text = ''.join(row[0] for row in workbook['Configuration'].iter_rows(min_row=2, values_only=True))
        assert json.loads(text) == plan['config']
        assert workbook['Summary']['A2'].value == 'A'
        assert workbook['Summary'].max_row == 2
        assert workbook['Data'].max_row == len(frame) + 1
    finally:
        workbook.close()
