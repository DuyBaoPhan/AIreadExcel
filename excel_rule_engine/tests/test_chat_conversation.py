"""Conversation behavior tested without live model calls."""
from pathlib import Path
from unittest.mock import patch
import pytest
from app.services import chat_conversation as chat


@pytest.fixture
def workspace(tmp_path,monkeypatch):
    source=tmp_path/'input';source.mkdir()
    (source/'staff.csv').write_text('name,salary\nAn,10\nBinh,20\n')
    monkeypatch.setenv('REPORT_PLANNER','rules')
    chat._SESSIONS.clear()
    return source


def turn(action,request='',reply='Xin chao'):
    return {'action':action,'request':request,'reply':reply,'update':None}


def test_greeting_does_not_plan_export_or_write(workspace):
    with patch.object(chat,'route_turn',return_value=turn('chat')), \
         patch.object(chat.reports,'_preview',side_effect=AssertionError('no report')):
        result=chat.chat(workspace,'demo','hello')
    assert result['reply']=='Xin chao'
    assert 'result' not in result
    assert list(workspace.parent.iterdir())==[workspace]


def test_data_question_returns_rows_without_output(workspace):
    with patch.object(chat,'route_turn',return_value=turn('query','danh sach nhan vien')):
        # Dataset has names only; explicit detail config simulates validated planner.
        with patch.object(chat.reports,'_preview',return_value=(
            {'status':'ready','source':'staff.csv','warnings':[], 'available_sources':['staff.csv'],
             'fingerprint':'test','config':{'version':1,'metrics':[],'group_by':[]}},
            {'staff.csv':__import__('pandas').read_csv(workspace/'staff.csv')})):
            response=chat.chat(workspace,'demo','cho xem danh sach')
    assert response['result']['output_path'] is None
    assert response['result']['total_rows']==2
    assert not (workspace.parent/'output').exists()


def test_followup_receives_history_but_not_result_cells(workspace):
    with patch.object(chat,'route_turn',side_effect=[turn('chat',reply='hello'),turn('clarify',reply='which source?')]) as route:
        first=chat.chat(workspace,'demo','hello')
        chat.chat(workspace,'demo','con IT?',first['session_id'])
    history=route.call_args.args[1]
    assert history[0]['content']=='hello'
    assert 'An' not in str(history)


def test_session_cannot_cross_projects(workspace,tmp_path):
    with patch.object(chat,'route_turn',return_value=turn('chat')):
        first=chat.chat(workspace,'demo','hello')
    with pytest.raises(ValueError):
        chat.chat(tmp_path/'other','other','hi',first['session_id'])


def test_confirmation_requires_pending_session_token(workspace):
    with pytest.raises(ValueError):
        chat.confirm(workspace,'missing','fake')


def test_explicit_export_creates_one_workbook(workspace,monkeypatch):
    import pandas as pd
    output=workspace.parent/'output';output.mkdir()
    monkeypatch.setattr(chat.reports,'safe_output_path',lambda p,n:output/n)
    plan={'status':'ready','source':'staff.csv','warnings':[],'available_sources':['staff.csv'],
          'fingerprint':'test','config':{'version':1,'metrics':[],'group_by':[]}}
    with patch.object(chat,'route_turn',return_value=turn('export','list staff')), \
         patch.object(chat.reports,'_preview',return_value=(plan,{'staff.csv':pd.read_csv(workspace/'staff.csv')})):
        response=chat.chat(workspace,'demo','xuat ra Excel')
    assert Path(response['result']['output_path']).exists()
    assert len(list(output.iterdir()))==1


def test_update_requires_button_confirmation_and_cannot_replay(workspace):
    from app.services.source_updates import _PENDING
    _PENDING.clear()
    action=turn('update')
    action['update']={'source':'staff.csv','key_column':'name','key_value':'An','column':'salary','value':'30'}
    original=(workspace/'staff.csv').read_bytes()
    with patch.object(chat,'route_turn',return_value=action):
        response=chat.chat(workspace,'demo','doi luong An thanh 30')
    assert (workspace/'staff.csv').read_bytes()==original
    token=response['update_proposal']['token']
    result=chat.confirm(workspace,response['session_id'],token)
    assert result['action']=='updated'
    assert 'An,30' in (workspace/'staff.csv').read_text()
    with pytest.raises(ValueError): chat.confirm(workspace,response['session_id'],token)


def test_cancel_invalidates_write_at_session_layer(workspace):
    action=turn('update')
    action['update']={'source':'staff.csv','key_column':'name','key_value':'An','column':'salary','value':'30'}
    with patch.object(chat,'route_turn',return_value=action):
        response=chat.chat(workspace,'demo','doi luong')
    chat.cancel(workspace,response['session_id'])
    with pytest.raises(ValueError):
        chat.confirm(workspace,response['session_id'],response['update_proposal']['token'])
    assert 'An,10' in (workspace/'staff.csv').read_text()


def test_retrieval_turn_uses_cited_answer_without_export(workspace):
    hits={'hits':[{'id':'r1','text':'name=An; note=remote','source':'staff.csv','sheet':'CSV','row':2}],
          'fingerprint':'v1','total_documents':2,'truncated':True}
    with patch.object(chat,'route_turn',return_value=turn('retrieve','An lam viec o dau?')), \
         patch('app.services.rag_index.search',return_value=hits), \
         patch('app.services.rag_answer.answer_from_evidence',return_value={'reply':'An works remotely [1]',
             'citations':[{'number':1,**hits['hits'][0]}],'insufficient':False}), \
         patch.object(chat.reports,'_preview',side_effect=AssertionError('no report')):
        response=chat.chat(workspace,'demo','An lam viec o dau?')
    assert response['action']=='retrieve'
    assert response['citations'][0]['row']==2
    assert response['retrieval']['fingerprint']=='v1'
    assert 'result' not in response
    assert not (workspace.parent/'output').exists()
