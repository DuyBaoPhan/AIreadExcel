"""Employee listings remain filtered detail rows through approved workbook export."""
from io import BytesIO
from pathlib import Path
from unittest.mock import patch

import pandas as pd
import pytest
from openpyxl import load_workbook

from app.core.report_planner import plan_report
from app.services.reports import conversation_reporting as service
from app.services.reports.report_engine import run_report


@pytest.fixture
def employees():
    return pd.DataFrame({
        'employee_id': ['E1', 'E2', 'E3', 'E2'],
        'name': ['An', 'Binh', 'Chi', 'Binh'],
        'department': ['IT', 'IT', 'HR', 'IT'],
        'salary': [10_000_000, 20_000_000, 30_000_000, 9_000_000],
    })


@pytest.mark.parametrize('text,expected', [
    ('Lọc nhân viên có lương trên 10 triệu', ['E2', 'E3']),
    ('liet ke nhan vien luong >= 20 trieu', ['E2', 'E3']),
    ('danh sach nhan vien phong ban IT luong tren 10 trieu', ['E2']),
    ('loc nhan vien phong ban IT', ['E1', 'E2', 'E2']),
    ('danh sach nhan vien', ['E1', 'E2', 'E3', 'E2']),
])
def test_employee_detail_preserves_rows_and_columns(employees, text, expected):
    before = employees.copy(deep=True)
    plan = plan_report(text, {'hr.csv': employees})
    assert plan['status'] == 'ready', plan
    assert plan['config']['metrics'] == []
    assert plan['config']['group_by'] == []
    result = run_report(employees, plan['config'])
    assert result['summary'].empty
    assert list(result['data'].columns) == list(employees.columns)
    assert result['data']['employee_id'].tolist() == expected
    pd.testing.assert_frame_equal(employees, before)


def test_exact_accented_salary_condition(employees):
    plan = plan_report('Lọc nhân viên có lương trên 10 triệu', {'hr.csv': employees})
    assert plan['status'] == 'ready', plan
    assert plan['config']['filters'] == [
        {'column': 'salary', 'operator': 'gt', 'value': 10_000_000, 'type': 'number'}]


@pytest.mark.parametrize('text', [
    'loc nhan vien luong tren 10 trieu sau thue',
    'danh sach nhan vien phong ban Marketing',
    'liet ke nhan vien luong tren 10 trieu khong tinh HR',
    'loc nhan vien theo phong ban',
    'loc nhan vien va dem dong',
    'danh sach nhan vien luong cao nhat',
    'danh sach nhan vien luong trung binh',
])
def test_unsupported_detail_constraints_never_become_generic_report(employees, text):
    plan = plan_report(text, {'hr.csv': employees})
    assert plan['status'] != 'ready', plan
    assert plan['config'] is None


def test_employee_source_ambiguity_requires_selection(employees):
    text = 'loc nhan vien luong tren 10 trieu'
    assert plan_report(text, {'a.csv': employees, 'b.csv': employees})['status'] == 'clarify'
    selected = plan_report(text + ' file b.csv', {'a.csv': employees, 'b.csv': employees})
    assert selected['status'] == 'ready', selected
    assert selected['source'] == 'b.csv'


def test_salary_column_alone_does_not_establish_employee_source(employees):
    plan = plan_report('loc nhan vien luong tren 10 trieu',
                       {'pay.csv': employees[['salary', 'department']]})
    assert plan['status'] != 'ready', plan


def test_existing_employee_aggregate_is_unchanged(employees):
    plan = plan_report('dem nhan vien luong tren 10 trieu', {'hr.csv': employees})
    assert plan['status'] == 'ready', plan
    assert plan['config']['metrics'][0]['operation'] == 'nunique'
    assert run_report(employees, plan['config'])['summary'].iloc[0, 0] == 2


def test_approved_detail_workbook_contains_only_matching_source_rows(tmp_path, employees):
    inputs, outputs = tmp_path / 'input', tmp_path / 'output'
    inputs.mkdir()
    outputs.mkdir()
    employees.to_csv(inputs / 'hr.csv', index=False)
    pd.DataFrame({'product': ['A'], 'revenue': [100]}).to_csv(inputs / 'sales.csv', index=False)
    text = 'Lọc nhân viên có lương trên 10 triệu'
    with patch.object(service, 'safe_output_path', side_effect=lambda project, name: outputs / name):
        preview = service.preview_request(inputs, text)
        assert preview['status'] == 'ready', preview
        assert preview['source'] == 'hr.csv'
        assert list(outputs.iterdir()) == []
        result = service.execute_request(inputs, 'demo', text, preview['source'], preview['fingerprint'])
    assert result['summary'] == []
    assert result['total_rows'] == 2
    assert [row['employee_id'] for row in result['detail_preview']] == ['E2', 'E3']
    book = load_workbook(BytesIO(Path(result['output_path']).read_bytes()), data_only=True)
    rows = list(book['Data'].values)
    assert rows[0] == tuple(employees.columns)
    assert rows[1:] == [('E2', 'Binh', 'IT', 20_000_000), ('E3', 'Chi', 'HR', 30_000_000)]
    assert not any('SalarySum' in str(cell) for row in book['Summary'].values for cell in row)
    book.close()
    assert len(list(outputs.iterdir())) == 1
