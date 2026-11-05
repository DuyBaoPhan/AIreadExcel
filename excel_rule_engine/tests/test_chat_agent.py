"""Conversation router contract and privacy; provider mocked."""
import json
from unittest.mock import Mock,patch
import pytest
from app.services.ai.chat_agent import route_turn


def test_chat_router_strict_schema_and_metadata_only(monkeypatch):
    monkeypatch.setenv('OPENAI_API_KEY','test-private')
    response=Mock()
    response.json.return_value={'choices':[{'finish_reason':'stop','message':{'content':json.dumps({
        'action':'chat','reply':'Xin chao','request':'','update':None})}}]}
    with patch('app.services.ai.chat_agent.requests.post',return_value=response) as post:
        result=route_turn('hello',[],[{'name':'staff.csv','columns':['name','salary']}])
    assert result['action']=='chat'
    assert post.call_args.kwargs['json']['response_format']['json_schema']['strict'] is True
    assert 'test-private' not in json.dumps(post.call_args.kwargs['json'])


@pytest.mark.parametrize('action', ['delete','execute_code','confirm_update'])
def test_model_cannot_invent_write_actions(monkeypatch,action):
    monkeypatch.setenv('OPENAI_API_KEY','test')
    response=Mock()
    response.json.return_value={'choices':[{'finish_reason':'stop','message':{'content':json.dumps({
        'action':action,'reply':'done','request':'','update':None})}}]}
    with patch('app.services.ai.chat_agent.requests.post',return_value=response),pytest.raises(ValueError):
        route_turn('yes',[],[])
