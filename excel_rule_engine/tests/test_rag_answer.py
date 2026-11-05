"""Grounded answer citations and failures; no live provider calls."""
import json
from unittest.mock import Mock,patch
import pytest
from app.services.rag_answer import answer_from_evidence


@pytest.fixture
def evidence():
    return {'hits':[{'id':'row-1','text':'product=Printer; warranty=24 months','source':'goods.xlsx','sheet':'Policies','row':2}],
            'fingerprint':'test','total_documents':1,'truncated':False}


def response(result):
    r=Mock();r.json.return_value={'choices':[{'finish_reason':'stop','message':{'content':json.dumps(result)}}]};return r


def test_answer_with_valid_citation(monkeypatch,evidence):
    monkeypatch.setenv('OPENAI_API_KEY','test')
    with patch('app.services.rag_answer.requests.post',return_value=response({'claims':[{'text':'Printer có bảo hành 24 tháng.','evidence_ids':['row-1']}],'insufficient':False})) as api:
        result=answer_from_evidence('Bao hanh Printer?',evidence)
    assert result['citations'][0]['row']==2
    assert result['citations'][0]['sheet']=='Policies'
    assert '[1]' in result['reply']
    assert '24 months' in str(api.call_args.kwargs['json'])
    assert not result['insufficient']


@pytest.mark.parametrize('ids',[[],['invented']])
def test_missing_or_invented_citation_rejected(monkeypatch,evidence,ids):
    monkeypatch.setenv('OPENAI_API_KEY','test')
    with patch('app.services.rag_answer.requests.post',return_value=response({'claims':[{'text':'Unsupported claim','evidence_ids':ids}],'insufficient':False})),pytest.raises(ValueError):
        answer_from_evidence('question',evidence)


def test_no_hits_no_provider_call():
    with patch('app.services.rag_answer.requests.post',side_effect=AssertionError('no call')):
        result=answer_from_evidence('question',{'hits':[]})
    assert result['insufficient']
    assert result['citations']==[]


def test_insufficient_evidence_never_promises_completeness(monkeypatch,evidence):
    monkeypatch.setenv('OPENAI_API_KEY','test')
    with patch('app.services.rag_answer.requests.post',return_value=response({'claims':[],'insufficient':True})):
        result=answer_from_evidence('question',evidence)
    assert result['insufficient']
    assert 'Chưa đủ' in result['reply']
