"""Real planner -> bounded file snapshots -> approval -> workbook regressions."""
from io import BytesIO
from pathlib import Path
from unittest.mock import patch

import pandas as pd
import pytest
from openpyxl import load_workbook
from app.services.reports import conversation_reporting as service


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
