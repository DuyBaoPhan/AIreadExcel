"""Employee listings remain filtered detail rows through approved workbook export."""
from io import BytesIO
from pathlib import Path
from unittest.mock import patch

import pandas as pd
import pytest
from openpyxl import load_workbook

from .test_openai_planner import mock_response
from app.services.reports import conversation_reporting as service


@pytest.fixture
def employees():
    return pd.DataFrame({
        'employee_id': ['E1', 'E2', 'E3', 'E2'],
        'name': ['An', 'Binh', 'Chi', 'Binh'],
        'department': ['IT', 'IT', 'HR', 'IT'],
        'salary': [10_000_000, 20_000_000, 30_000_000, 9_000_000],
    })


def test_approved_detail_workbook_contains_only_matching_source_rows(tmp_path, employees, monkeypatch):
    monkeypatch.setenv("REPORT_PLANNER", "openai")
    calls = mock_response(monkeypatch, {"status": "ready", "source": "hr.csv", "config": {
        "version": 1, "filters": [{"column": "salary", "operator": "gt",
                                  "value": 10_000_000, "type": "number"}],
        "filter_logic": "and", "group_by": [], "metrics": [],
        "date_group": None, "top_n": None},
        "explanation": [], "questions": [], "unsupported": []})
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
    assert len(calls) == 1  # Execute consumes the approved snapshot, not another AI plan.
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
