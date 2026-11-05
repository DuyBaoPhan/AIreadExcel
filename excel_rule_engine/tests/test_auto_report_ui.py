"""Chat UX delegates every message to AI; unavailable APIs never fall back."""
import ast
from contextlib import nullcontext
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from streamlit.testing.v1 import AppTest


def command_harness(response, text='top 2 san pham doanh thu cao nhat', automatic=True):
    class State:
        project = 'demo_project'
        pending_report = {'stale': True}
        pending_update = {'stale': True}
        agent_session_id = 'previous-session'
        def get(self, key, default=None):
            return getattr(self, key, automatic if key == 'auto_reports' else default)
    state = State()
    path = Path(__file__).resolve().parents[1] / 'app' / 'ui' / 'chatbot.py'
    node = next(n for n in ast.parse(path.read_text(encoding='utf-8')).body if isinstance(n, ast.FunctionDef) and n.name == 'process_command')
    namespace = {'st': SimpleNamespace(session_state=state, spinner=lambda *a: nullcontext()),
                 'call_api': Mock(return_value=response), 'add_message': Mock(),
                 '_handle_requires_input': Mock(), '_handle_success_result': Mock()}
    exec(compile(ast.Module(body=[node], type_ignores=[]), str(path), 'exec'), namespace)
    namespace['process_command'](text)
    return namespace


@pytest.mark.parametrize('text', ['xin chao', 'doanh thu theo san pham', 'xuat bao cao Excel'])
@pytest.mark.parametrize('automatic', [True, False])
def test_every_message_uses_chat_without_keyword_or_approval_branches(text, automatic):
    state = command_harness({'session_id': 'new-session', 'reply': 'AI response', 'citations': []}, text, automatic)
    state['call_api'].assert_called_once_with('/api/chat', {
        'text': text, 'project': 'demo_project', 'session_id': 'previous-session'})
    assert state['st'].session_state.agent_session_id == 'new-session'
    assert state['st'].session_state.pending_report is None
    assert state['st'].session_state.pending_update is None
    state['_handle_requires_input'].assert_not_called()
    state['_handle_success_result'].assert_not_called()
    assert state['add_message'].call_args.args[:2] == ('assistant', 'AI response')


def test_query_result_and_export_metadata_are_rendered_from_ai_response():
    result = {'summary': [{'RevenueSum': 30}], 'detail_preview': [{'product': 'A'}],
              'total_rows': 2, 'warnings': ['sum not count'], 'output_path': 'x.xlsx'}
    state = command_harness({'session_id': 'new-session', 'reply': 'Report ready',
                             'result': result, 'citations': [{'source': 'sales.csv'}]})
    meta = state['add_message'].call_args.args[2]
    for key, value in result.items():
        assert meta[key] == value
    assert meta['citations'] == [{'source': 'sales.csv'}]
    assert state['call_api'].call_count == 1


def test_ai_clarification_remains_conversational_without_generic_export():
    state = command_harness({'session_id': 'new-session', 'reply': 'Which source should I use?',
                             'citations': [], 'result': None})
    assert state['add_message'].call_args.args[1] == 'Which source should I use?'
    assert state['add_message'].call_args.args[2]['output_path'] is None
    assert state['call_api'].call_count == 1
    assert state['st'].session_state.pending_report is None


@pytest.mark.parametrize('response', [None, {}, {'error': '404 Not Found'}, {'error': 'OPENAI_UNAVAILABLE'}])
def test_unavailable_chat_api_does_not_fall_back(response):
    state = command_harness(response)
    assert state['call_api'].call_count == 1
    assert state['call_api'].call_args.args[0] == '/api/chat'
    assert state['st'].session_state.agent_session_id == 'previous-session'
    state['_handle_success_result'].assert_not_called()
    state['_handle_requires_input'].assert_not_called()
    assert state['add_message'].call_args.args[0] == 'assistant'


def test_update_proposal_is_retained_without_automatic_execution():
    proposal = {'token': 'approval-required', 'summary': 'Change one cell'}
    state = command_harness({'session_id': 'new-session', 'reply': 'Please confirm',
                             'update_proposal': proposal})
    assert state['st'].session_state.pending_update == proposal
    assert state['call_api'].call_count == 1


SCRIPT = '''
import streamlit as st
from app.ui.report_plan_ui import render_pending_report
st.session_state.auto_reports = True
if 'pending_report' not in st.session_state:
    st.session_state.pending_report = {'status':'clarify', 'text':'salary', 'project':'demo',
        'candidate_sources':['hr.csv','pay.csv'], 'available_sources':['sales.csv','hr.csv','pay.csv']}
if 'calls' not in st.session_state: st.session_state.calls = []
def api(endpoint,payload):
    st.session_state.calls.append((endpoint,payload))
    return {'status':'ready','result':{'output_path':'x.xlsx','source_file':'pay.csv','summary':[{'SalarySum':30}], 'explanation':['sum salary']}}
def add(role, content, meta):
    st.session_state.output = meta
render_pending_report(api, add)
'''


def test_relevant_source_choice_executes_once_without_second_confirmation():
    app = AppTest.from_string(SCRIPT).run(timeout=30)
    assert len(app.exception) == 0
    assert app.selectbox(key='plan_source_choice').options == ['hr.csv', 'pay.csv']
    app.selectbox(key='plan_source_choice').select('pay.csv').run(timeout=30)
    app.button(key='replan_source').click().run(timeout=30)
    assert len(app.exception) == 0
    assert app.session_state['calls'][0][0] == '/api/report/auto'
    assert app.session_state['calls'][0][1]['source_name'] == 'pay.csv'
    assert len(app.session_state['calls']) == 1
    assert app.session_state['pending_report'] is None
    assert app.session_state['output']['summary'] == [{'SalarySum': 30}]


def test_unsupported_grammar_does_not_offer_irrelevant_source_dropdown():
    app = AppTest.from_string(SCRIPT.replace("'status':'clarify'", "'status':'unsupported'")).run(timeout=30)
    assert len(app.exception) == 0
    assert len(app.selectbox) == 0
    assert app.button(key='confirm_report_plan').disabled
