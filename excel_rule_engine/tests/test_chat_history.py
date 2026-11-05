from app.services.chat.chat_history import save_current,switch_chat


def test_switch_restores_messages_and_context_not_approvals():
    state={'messages':[{'role':'user','content':'First conversation'}], 'session_id':'one',
           'agent_session_id':'agent-one','pending_update':{'token':'secret'}}
    save_current(state);first=state['active_chat_id']
    switch_chat(state)
    assert state['messages']==[]
    assert state['pending_update'] is None
    state['messages']=[{'role':'user','content':'Second conversation'}]
    state['agent_session_id']='agent-two'
    switch_chat(state,first)
    assert state['messages'][0]['content']=='First conversation'
    assert state['agent_session_id']=='agent-one'
    assert len(state['chat_threads'])==2
    state['messages'][0]['content']='changed'
    assert state['chat_threads'][first]['messages'][0]['content']=='First conversation'


def test_empty_threads_not_archived_and_titles_bounded():
    state={'messages':[]}
    switch_chat(state);switch_chat(state)
    assert not state['chat_threads']
    state['messages']=[{'role':'user','content':'a '*100}]
    save_current(state)
    assert len(next(iter(state['chat_threads'].values()))['title'])<=64
