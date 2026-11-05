"""Employee exports retain detail rows instead of per-column counts (mocked AI)."""
from pathlib import Path
from unittest.mock import patch
import pandas as pd
from app.services.ai import chat_agent, openai_planner
from app.services.chat import chat_conversation as chat
from .test_openai_planner import mock_response


def test_prompts_distinguish_detail_and_export_followup():
    assert 'metrics=[], group_by=[]' in openai_planner._PROMPT
    assert 'never count every' in openai_planner._PROMPT
    assert 'It changes delivery to export only' in chat_agent._PROMPT


def test_employee_query_then_export_keeps_rows_and_strict_bounds(tmp_path, monkeypatch):
    source=tmp_path/'input';source.mkdir()
    output=tmp_path/'output';output.mkdir()
    frame=pd.DataFrame({'employee_id':['A','B','C','D'], 'name':['An','Binh','Chi','Dung'],
        'department':['IT','IT','IT','HR'], 'salary':[15000000,19999999,20000000,10000000]})
    frame.to_csv(source/'staff.csv',index=False)
    plan={'status':'ready','source':'staff.csv','config':{'version':1,
        'filters':[{'column':'salary','operator':'lt','type':'number','value':20000000},
                   {'column':'department','operator':'eq','type':'text','value':'IT'}],
        'filter_logic':'and','group_by':[],'metrics':[],'date_group':None,'top_n':None},
        'explanation':[],'questions':[],'unsupported':[]}
    mock_response(monkeypatch,plan)
    monkeypatch.setattr(chat.reports,'safe_output_path',lambda p,n:output/n)
    request='Danh sach nhan vien phong IT co luong duoi 20000000'
    actions=[{'action':action,'reply':'','request':request,'update':None} for action in ['query','export']]
    with patch.object(chat,'route_turn',side_effect=actions) as router:
        first=chat.chat(source,'demo','xem nhan vien IT luong duoi 20tr')
        assert not list(output.iterdir())
        second=chat.chat(source,'demo','xuat file ra cho toi di',first['session_id'])
    for result in [first['result'],second['result']]:
        assert result['summary']==[]
        assert [r['employee_id'] for r in result['detail_preview']]==['A','B']
        assert result['total_rows']==2
    book=pd.read_excel(second['result']['output_path'],sheet_name='Data')
    assert book['employee_id'].tolist()==['A','B']
    assert book['salary'].tolist()==[15000000,19999999]
    assert second['result']['output_filename']=='Nhan_vien_IT.xlsx'
    assert router.call_args.args[1]  # Follow-up receives prior resolved task.
