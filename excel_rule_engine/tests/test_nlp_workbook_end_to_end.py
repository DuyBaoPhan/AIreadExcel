"""Fixed OpenAI responses -> real validation -> snapshots -> approval -> XLSX."""
from io import BytesIO
from pathlib import Path
from unittest.mock import Mock, patch
import json

import pandas as pd
import pytest
from openpyxl import load_workbook
from app.services.reports import conversation_reporting as service


def fixture_config(groups=(), metric='revenue', operation='sum', alias='RevenueSum', filters=(), top=None):
    """Finite hand-authored plans, never a text/keyword translator."""
    return {'version': 1, 'filters': list(filters), 'filter_logic': 'and',
            'group_by': list(groups), 'metrics': [{'column': metric, 'operation': operation, 'alias': alias}],
            'date_group': None, 'top_n': top}


def date_filter(start, end):
    return {'column': 'month', 'operator': 'between', 'type': 'date', 'value': [start, end]}


YEAR = date_filter('2024-01-01', '2024-12-31')
PLANS = {
    'doanh thu Laptop Pro X nam 2024': ('sales.xlsx', fixture_config(filters=[YEAR,
        {'column': 'product', 'operator': 'eq', 'type': 'text', 'value': 'Laptop Pro X'}])),
    'top 1 san pham doanh thu cao nhat nam 2024': ('sales.xlsx', fixture_config(['product'], filters=[YEAR],
        top={'column': 'RevenueSum', 'n': 1, 'ascending': False, 'offset': 0, 'scope': 'summary'})),
    'san pham nao doanh thu nho nhat nam 2024': ('sales.xlsx', fixture_config(['product'], filters=[YEAR],
        top={'column': 'RevenueSum', 'n': 1, 'ascending': True, 'offset': 0, 'scope': 'summary'})),
    'luong trung binh theo phong ban': ('hr.csv', fixture_config(['department'], 'salary', 'mean', 'SalaryMean')),
    'nhan vien nao luong cao nhat': ('hr.csv', fixture_config(['employee_id', 'name'], 'salary', 'sum', 'SalarySum',
        top={'column': 'SalarySum', 'n': 1, 'ascending': False, 'offset': 0, 'scope': 'summary'})),
    'dem nhan vien theo phong ban': ('hr.csv', fixture_config(['department'], None, 'rows', 'Employees')),
    'doanh thu quy 1 nam 2024': ('sales.xlsx', fixture_config(filters=[date_filter('2024-01-01', '2024-03-31')])),
    'doanh thu tu ngay 01/01/2024 den ngay 31/01/2024': ('sales.xlsx', fixture_config(filters=[date_filter('2024-01-01', '2024-01-31')])),
    'dem nhan vien luong lon hon hoac bang 20.000.000': ('hr.csv', fixture_config(metric=None, operation='rows', alias='Employees', filters=[
        {'column': 'salary', 'operator': 'ge', 'type': 'number', 'value': 20_000_000}])),
}
UNSUPPORTED = {'du bao doanh thu nam 2027', 'doanh thu sau thue theo san pham',
               'doanh thu khong tinh Phone', 'so sanh doanh thu 2024 voi 2025'}


@pytest.fixture(autouse=True)
def fixed_openai_responses(monkeypatch):
    monkeypatch.setenv('OPENAI_API_KEY', 'offline-fixture-key')
    def respond(*args, **kwargs):
        text = json.loads(kwargs['json']['messages'][-1]['content'])['request']
        if text in PLANS:
            source, config = PLANS[text]
            plan = {'status': 'ready', 'source': source, 'config': config,
                    'explanation': ['Ke hoach kiem thu co dinh.'], 'questions': [], 'unsupported': []}
        else:
            assert text in UNSUPPORTED, text
            plan = {'status': 'unsupported', 'source': None, 'config': None,
                    'explanation': [], 'questions': [], 'unsupported': ['Chua ho tro yeu cau nay.']}
        return Mock(json=lambda: {'choices': [{'finish_reason': 'stop', 'message': {'content': json.dumps(plan)}}]})
    with patch('app.services.ai.openai_planner.requests.post', side_effect=respond):
        yield


@pytest.fixture
def workspace(tmp_path):
    inputs = tmp_path / 'input'
    inputs.mkdir()
    outputs = tmp_path / 'output'
    outputs.mkdir()
    pd.DataFrame({
        'product': ['Laptop Pro X', 'Laptop Pro X', 'Phone', 'Phone'],
        'region': ['North', 'South', 'North', 'South'],
        'month': ['2024-01', '2024-02', '2024-01', '2025-01'],
        'revenue': [100, 200, 50, 900],
        'profit': [20, 40, 5, 100],
    }).to_excel(inputs / 'sales.xlsx', index=False)
    pd.DataFrame({
        'employee_id': ['E1', 'E2', 'E3'], 'name': ['An', 'Binh', 'Chi'],
        'department': ['IT', 'IT', 'HR'], 'salary': [10_000_000, 20_000_000, 30_000_000],
    }).to_csv(inputs / 'hr.csv', index=False)
    with patch.object(service, 'safe_output_path', side_effect=lambda project, name: outputs / name):
        yield inputs, outputs


@pytest.mark.parametrize('text,column,expected', [
    ('doanh thu Laptop Pro X nam 2024', 'RevenueSum', [300]),
    ('top 1 san pham doanh thu cao nhat nam 2024', 'RevenueSum', [300]),
    ('san pham nao doanh thu nho nhat nam 2024', 'RevenueSum', [50]),
    ('luong trung binh theo phong ban', 'SalaryMean', [15_000_000, 30_000_000]),
    ('nhan vien nao luong cao nhat', 'SalarySum', [30_000_000]),
    ('dem nhan vien theo phong ban', 'Employees', [2, 1]),
    ('doanh thu quy 1 nam 2024', 'RevenueSum', [350]),
    ('doanh thu tu ngay 01/01/2024 den ngay 31/01/2024', 'RevenueSum', [150]),
    ('dem nhan vien luong lon hon hoac bang 20.000.000', 'Employees', [2]),
])
def test_real_approved_report_has_correct_workbook(workspace, text, column, expected):
    inputs, outputs = workspace
    preview = service.preview_request(inputs, text)
    assert preview['status'] == 'ready', preview
    assert list(outputs.iterdir()) == []
    result = service.execute_request(inputs, 'demo', text, preview['source'], preview['fingerprint'])
    assert [row[column] for row in result['summary']] == expected
    assert result['files_included'] == 1
    book = load_workbook(BytesIO(Path(result['output_path']).read_bytes()), data_only=True)
    assert {'Report', 'Summary', 'Data', 'Quality', 'Configuration'} <= set(book.sheetnames)
    rows = list(book['Summary'].values)
    # The export must retain the computed value, not just return it in chat.
    assert any(any(value == expected[0] for value in row) for row in rows)
    book.close()
    assert len(list(outputs.iterdir())) == 1


@pytest.mark.parametrize('text', [
    'du bao doanh thu nam 2027',
    'doanh thu sau thue theo san pham',
    'doanh thu khong tinh Phone',
    'so sanh doanh thu 2024 voi 2025',
])
def test_unsupported_real_requests_never_write(workspace, text):
    inputs, outputs = workspace
    plan = service.preview_request(inputs, text)
    assert plan['status'] != 'ready', plan
    assert 'fingerprint' not in plan
    with pytest.raises(ValueError):
        service.execute_request(inputs, 'demo', text, None, 'fake')
    assert list(outputs.iterdir()) == []


def test_two_actual_hr_sources_require_selection(workspace):
    inputs, outputs = workspace
    (inputs / 'hr2.csv').write_bytes((inputs / 'hr.csv').read_bytes())
    text = 'nhan vien nao luong cao nhat'
    plan = service.preview_request(inputs, text)
    assert plan['status'] == 'clarify'
    assert list(outputs.iterdir()) == []
    selected = service.preview_request(inputs, text, 'hr.csv')
    assert selected['status'] == 'ready'
    assert selected['source'] == 'hr.csv'
