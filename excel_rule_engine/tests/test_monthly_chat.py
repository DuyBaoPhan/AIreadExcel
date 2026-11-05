"""Monthly source descriptors and the screenshot's October request."""
from pathlib import Path
from unittest.mock import patch
import pandas as pd
from app.services.sources.column_metadata import describe_column
from app.services.chat import chat_conversation as chat
from .test_openai_planner import mock_response


def monthly_plan(source, year):
    """Explicit provider fixture keeps date conversion and aggregation in real Python."""
    return {"status": "ready", "source": source, "config": {
        "version": 1, "filters": [{"column": "month", "operator": "between",
             "type": "date", "value": [f"{year}-10-01", f"{year}-10-31"]}],
        "filter_logic": "and", "group_by": [],
        "metrics": [{"column": "revenue", "operation": "sum", "alias": "RevenueSum"}],
        "date_group": None, "top_n": None},
        "explanation": [], "questions": [], "unsupported": []}


def test_month_descriptor_no_values():
    result=describe_column(pd.Series(['2024-10','2024-11'],name='month'))
    assert result['format']=='YYYY-MM'
    assert '2024' not in str(result)
    assert 'format' not in describe_column(pd.Series(['other'],name='note'))


def test_october_export_real_demo(tmp_path,monkeypatch):
    source=Path(__file__).resolve().parents[1]/'projects/demo_project/input'
    monkeypatch.setenv('REPORT_PLANNER','openai')
    monkeypatch.setattr(chat.reports,'safe_output_path',lambda p,n:tmp_path/n)
    mock_response(monkeypatch, monthly_plan('Sales_Data.xlsx', 2024))
    chat._SESSIONS.clear()
    with patch.object(chat,'route_turn',return_value={'action':'export','request':'doanh thu thang 10 nam 2024','reply':'','update':None}):
        response=chat.chat(source,'demo_project','ban co the xuat bao cao doanh thu thang 10/2024 khong')
    assert response['action']=='export'
    assert response['result']['total_rows']==5
    assert Path(response['result']['output_path']).exists()
    expected=pd.read_excel(source/'Sales_Data.xlsx')
    expected=expected.loc[expected['month']=='2024-10','revenue'].sum()
    assert sum(r['RevenueSum'] for r in response['result']['summary'])==expected


def test_no_matches_preserves_conversation_without_export(tmp_path,monkeypatch):
    source=tmp_path/'input';source.mkdir()
    (source/'sales.csv').write_text('month,revenue\n2024-10,100\n')
    monkeypatch.setenv('REPORT_PLANNER','openai')
    mock_response(monkeypatch, monthly_plan('sales.csv', 2030))
    chat._SESSIONS.clear()
    with patch.object(chat,'route_turn',return_value={'action':'export','request':'doanh thu thang 10 nam 2030','reply':'','update':None}):
        response=chat.chat(source,'demo','export October 2030')
    assert response['action']=='no_matches'
    assert response['result']['total_rows']==0
    assert response['result']['output_path'] is None
    assert response['result']['applied_filters']
    assert response['session_id'] in chat._SESSIONS
    assert not (tmp_path/'output').exists()
