"""Ranking positions are independently verified, including stable tie handling."""
import copy

import pandas as pd
import pytest

from app.services.reports.report_engine import MAX_ROWS, run_report, serialize_config


@pytest.fixture
def frame():
    # First-seen group order is Z, B, A, C; B and A tie for the lead.
    return pd.DataFrame({'Product': ['Z', 'B', 'A', 'C', 'Z'],
                         'Revenue': [10, 90, 90, 5, 20]})


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


def test_export_preserves_ordinal_config_and_evidence(frame):
    from io import BytesIO
    import json
    from openpyxl import load_workbook
    from app.services.reports.advanced_report_export import build_advanced_report_bytes

    plan = {'config': {'version': 1, 'group_by': ['Product'],
        'metrics': [{'column': 'Revenue', 'operation': 'sum', 'alias': 'RevenueSum'}],
        'top_n': {'column': 'RevenueSum', 'n': 1, 'ascending': False, 'offset': 1}}}
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
