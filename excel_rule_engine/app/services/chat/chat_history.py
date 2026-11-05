"""Per-browser-session conversation archive; never restore write approvals."""
from copy import deepcopy
from datetime import datetime, timezone
from uuid import uuid4


def save_current(state):
    threads=state.setdefault('chat_threads',{})
    current=state.setdefault('active_chat_id',uuid4().hex)
    messages=state.get('messages',[])
    if messages:
        title=next((m['content'] for m in messages if m.get('role')=='user'),'Conversation')
        title=' '.join(title.split())[:64]
        existing=threads.get(current)
        if existing and existing['messages']==messages and existing.get('agent_session_id')==state.get('agent_session_id'):
            return
        threads[current]={'title':title,'messages':deepcopy(messages),
            'agent_session_id':state.get('agent_session_id'),
            'session_id':state.get('session_id'), 'project':state.get('project','demo_project'),
            'updated':datetime.now(timezone.utc).isoformat()}


def switch_chat(state,chat_id=None):
    save_current(state)
    threads=state['chat_threads']
    if chat_id is not None and chat_id not in threads:
        raise ValueError('Unknown conversation')
    entry=threads.get(chat_id,{})
    state['active_chat_id']=chat_id or uuid4().hex
    state['messages']=deepcopy(entry.get('messages',[]))
    state['agent_session_id']=entry.get('agent_session_id')
    state['session_id']=entry.get('session_id') or str(uuid4())
    state['project']=entry.get('project',state.get('project','demo_project'))
    for key in ('pending_update','pending_report','pending_comparison'):
        state[key]=None
