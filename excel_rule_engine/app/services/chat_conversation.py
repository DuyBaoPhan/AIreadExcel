"""Bounded server-side conversation context; computed rows never sent to the model."""
from collections import OrderedDict
from threading import RLock
from time import monotonic
from uuid import uuid4
import json
from pathlib import Path
from app.services import conversation_reporting as reports
from app.services.chat_agent import route_turn
from app.services.column_metadata import describe_column

_SESSIONS=OrderedDict()
_LOCK=RLock()


def chat(input_dir, project, text, session_id=None):
    with _LOCK:
        return _chat(input_dir,project,text,session_id)


def _chat(input_dir,project,text,session_id):
    root=str(Path(input_dir).resolve())
    now=monotonic()
    for key in list(_SESSIONS):
        if now-_SESSIONS[key]['time']>3600: del _SESSIONS[key]
    if session_id is not None and session_id not in _SESSIONS:
        raise ValueError('Phien da het han; hay bat dau hoi thoai moi.')
    sid=session_id or uuid4().hex
    state=_SESSIONS.get(sid,{'root':root,'history':[],'pending':None,'time':now})
    if state['root']!=root: raise ValueError('Phien khong thuoc du an nay.')
    sources, snapshots, names, warnings=reports._load_sources(input_dir,None)
    catalog=[{'name':name,'columns':[describe_column(df[c]) for c in df.columns]} for name,df in sources.items()]
    policy_path=Path(input_dir).parent/'source_policy.json'
    policy=None
    if policy_path.exists():
        if policy_path.stat().st_size>65536: raise ValueError('Cau hinh nguon qua lon.')
        try: policy=json.loads(policy_path.read_text(encoding='utf-8-sig'))
        except (OSError,ValueError): raise ValueError('Cau hinh nguon khong hop le.') from None
    # Invalidate the previous write even if the new provider request fails.
    state['pending']=None
    turn=route_turn(text,state['history'],catalog,policy)
    response={'session_id':sid,'action':turn['action'],'reply':turn['reply']}
    if turn['action'] in {'query','export'}:
        plan, frames=reports._preview(input_dir,turn['request'],None)
        if plan['status']!='ready':
            response['action']='clarify'
            response['reply']='\n'.join(plan.get('questions',[])+plan.get('unsupported',[])) or 'Vui long lam ro yeu cau.'
        else:
            # An empty selection is a normal conversational outcome, not HTTP failure.
            inspected = reports.run_report(frames[plan['source']].copy(deep=True), plan['config'])
            if inspected['data'].empty:
                response['action'] = 'no_matches'
                response['reply'] = ('Kh\u00f4ng t\u00ecm th\u1ea5y b\u1ea3n ghi kh\u1edbp b\u1ed9 l\u1ecdc trong '
                    + plan['source'] + '. Ch\u01b0a t\u1ea1o file v\u00e0 kh\u00f4ng t\u1ef1 \u0111\u1ed5i \u0111i\u1ec1u ki\u1ec7n. '
                    'B\u1ea1n c\u00f3 th\u1ec3 ki\u1ec3m tra b\u1ed9 l\u1ecdc b\u00ean d\u01b0\u1edbi ho\u1eb7c ch\u1ec9 r\u00f5 ngu\u1ed3n kh\u00e1c.')
                response['result'] = {'source_file': plan['source'], 'total_rows': 0,
                    'applied_filters': plan['config'].get('filters', []), 'output_path': None}
            else:
                result=reports._render_report(plan,frames,project,None,export=turn['action']=='export')
                result['summary']=result['summary'][:100]
                result['applied_filters']=plan['config'].get('filters', [])
                response['result']=result
                response['reply']=f"Nguon: {result['source_file']}. {result['total_rows']} dong phu hop. Ket qua duoc Python tinh toan."
    elif turn['action']=='retrieve':
        from app.services.rag_index import search
        from app.services.rag_answer import answer_from_evidence
        retrieval = search(input_dir, turn['request'], top_k=10)
        answer = answer_from_evidence(turn['request'], retrieval)
        response.update(answer)
        response['retrieval'] = {k: retrieval.get(k) for k in ('fingerprint', 'total_documents', 'truncated')}
    elif turn['action']=='update':
        from app.services.source_updates import propose_update
        u=turn['update']
        try:
            proposal=propose_update(input_dir,u['source'],u['key_column'],u['key_value'],u['column'],u['value'])
        except OSError:
            raise ValueError('Khong the doc tep nguon; vui long kiem tra tep va quyen truy cap.') from None
        state['pending']=proposal['token']
        response['update_proposal']=proposal
        response['reply']='De xuat thay doi duoi day chua duoc ghi. Kiem tra gia tri cu/moi va bam Xac nhan neu dung.'
    # Store user text + resolved task only, never results or source cell values.
    state['history']=(state['history']+[{'role':'user','content':text},
        {'role':'assistant','content':json.dumps({'action':response['action'],'resolved_request':turn['request'],
            'reply':turn['reply'] if turn['action'] in {'chat','clarify'} else ''},ensure_ascii=False)}])[-12:]
    state['time']=now
    _SESSIONS[sid]=state
    _SESSIONS.move_to_end(sid)
    while len(_SESSIONS)>128: _SESSIONS.popitem(last=False)
    return response


def confirm(input_dir,session_id,token):
    with _LOCK:
        state=_SESSIONS.get(session_id)
        if (not state or state['root']!=str(Path(input_dir).resolve()) or
                not isinstance(token,str) or state['pending']!=token or monotonic()-state['time']>3600):
            raise ValueError('De xuat khong con hieu luc trong phien nay.')
        from app.services.source_updates import confirm_update
        try:
            result=confirm_update(input_dir,token)
        except OSError:
            raise ValueError('Khong the ghi tep nguon; kiem tra quyen truy cap va dong tep Excel dang mo.') from None
        state['pending']=None
        return {'action':'updated','reply':'Da cap nhat tep nguon va luu ban sao luu.','result':result}


def cancel(input_dir, session_id):
    with _LOCK:
        state = _SESSIONS.get(session_id)
        if not state or state['root'] != str(Path(input_dir).resolve()):
            raise ValueError('Phien khong hop le.')
        state['pending'] = None
        return {'reply': 'Da huy de xuat; khong thay doi tep nguon.'}
