"""Exact user screenshot requests: routing, source choice and numeric results."""
import pandas as pd
import pytest

from app.core.analytical_request import is_analytical_request
from app.core.report_planner import plan_report
from app.services.reports.report_engine import run_report


@pytest.mark.parametrize('text,source,expected', [
    ('s\u1ea3n ph\u1ea9m n\u00e0o c\u00f3 doanh thu nh\u1ecf nh\u1ea5t', 'sales.xlsx', ['C']),
    ('nh\u00e2n vi\u00ean n\u00e0o c\u00f3 l\u01b0\u01a1ng cao nh\u1ea5t', 'hr.xlsx', ['Chi']),
    ('L\u1ecdc nh\u00e2n vi\u00ean c\u00f3 l\u01b0\u01a1ng tr\u00ean 10 tri\u1ec7u', 'hr.xlsx', ['Binh', 'Chi']),
    ('s\u1ea3n ph\u1ea9m c\u00f3 doanh thu \u0111\u1ee9ng top 2 l\u00e0', 'sales.xlsx', ['B', 'A']),
])
def test_exact_screenshot_requests(text, source, expected):
    sources = {
        'sales.xlsx': pd.DataFrame({'product': ['A', 'B', 'C'], 'revenue': [20, 30, 10]}),
        'hr.xlsx': pd.DataFrame({'employee_id': ['E1', 'E2', 'E3'],
                                'name': ['An', 'Binh', 'Chi'],
                                'salary': [10_000_000, 20_000_000, 30_000_000]}),
    }
    assert is_analytical_request(text)
    plan = plan_report(text, sources)
    assert plan['status'] == 'ready', plan
    assert plan['source'] == source
    result = run_report(sources[source], plan['config'])
    if text.startswith('L'):
        assert result['data']['name'].tolist() == expected
        assert result['summary'].empty
    else:
        column = 'product' if source == 'sales.xlsx' else 'name'
        assert result['summary'][column].tolist() == expected
