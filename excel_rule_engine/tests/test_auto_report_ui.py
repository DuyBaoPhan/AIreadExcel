"""Automatic reporting UX: clear requests execute, ambiguous ones ask only once."""
import ast
from contextlib import nullcontext
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from streamlit.testing.v1 import AppTest


def command_harness(response, automatic=True):
    class State:
        project = 'demo_project'
        pending_report = None
        def get(self, key, default=None):
            return automatic if key == 'auto_reports' else default
    path = Path(__file__).resolve().parents[1] / 'app' / 'chatbot.py'
    node = next(n for n in ast.parse(path.read_text(encoding='utf-8')).body if isinstance(n, ast.FunctionDef) and n.name == 'process_command')
    namespace = {'st': SimpleNamespace(session_state=State(), spinner=lambda *a: nullcontext()),
                 'call_api': Mock(return_value=response), 'add_message': Mock(),
                 '_handle_requires_input': Mock(), '_handle_success_result': Mock()}
    exec(compile(ast.Module(body=[node], type_ignores=[]), str(path), 'exec'), namespace)
    namespace['process_command']('top 2 san pham doanh thu cao nhat')
    return namespace


def test_clear_request_auto_executes_without_preview_or_confirm():
    state = command_harness({'status': 'ready', 'result': {'report_type': 'planned', 'output_path': 'x.xlsx'}})
    assert state['call_api'].call_count == 1
    assert state['call_api'].call_args.args[0] == '/api/report/auto'
    state['_handle_requires_input'].assert_not_called()
    state['_handle_success_result'].assert_called_once()


def test_ambiguous_request_retains_clarification_not_generic_export():
    plan = {'status': 'clarify', 'candidate_sources': ['hr.csv', 'pay.csv'], 'config': None}
    state = command_harness({'status': 'requires_input', 'report_plan': plan})
    state['_handle_success_result'].assert_not_called()
    assert state['_handle_requires_input'].call_args.args[0]['status'] == 'clarify'
    assert state['call_api'].call_count == 1


def test_manual_mode_preserves_explicit_approval():
    state = command_harness({'status': 'ready', 'config': {}}, automatic=False)
    assert state['call_api'].call_args.args[0] == '/api/report/preview'
    state['_handle_requires_input'].assert_called_once()


def test_old_backend_404_does_not_fall_back():
    state = command_harness({'error': '404 Not Found'})
    assert state['call_api'].call_count == 1
    state['_handle_success_result'].assert_not_called()
    state['_handle_requires_input'].assert_not_called()


SCRIPT = '''
import streamlit as st
from app.report_plan_ui import render_pending_report
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
