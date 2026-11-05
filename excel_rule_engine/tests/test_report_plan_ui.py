"""Approval UI must never execute ambiguous or unapproved plans."""
import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from streamlit.testing.v1 import AppTest

SCRIPT = '''
import streamlit as st
from app.ui.report_plan_ui import render_pending_report
if 'pending_report' not in st.session_state:
    st.session_state.pending_report = {'status': 'ready', 'source': 'sales.csv', 'text': 'revenue',
        'project': 'demo', 'fingerprint': 'abc', 'config': {'version':1}, 'explanation':['Sum revenue']}
if 'calls' not in st.session_state:
    st.session_state.calls = []
def api(endpoint,payload):
    st.session_state.calls.append(endpoint)
    return {'result': {'output_path':'report.xlsx','summary':[{'Revenue':100}]}}
def add(role,content,meta):
    st.session_state['result_meta'] = meta
render_pending_report(api,add)
'''

class TestReportPlanUI(unittest.TestCase):
    def test_requires_explicit_approval(self):
        app = AppTest.from_string(SCRIPT).run(timeout=30)
        self.assertEqual(len(app.exception),0)
        self.assertEqual(app.session_state['calls'],[])
        app.button(key='confirm_report_plan').click().run(timeout=30)
        self.assertEqual(len(app.exception),0)
        self.assertEqual(app.session_state['calls'],['/api/report/confirm'])
        self.assertEqual(app.session_state['result_meta']['summary'],[{'Revenue':100}])
        self.assertIsNone(app.session_state['pending_report'])

    def test_ambiguous_cannot_execute_and_can_cancel(self):
        app = AppTest.from_string(SCRIPT.replace("'status': 'ready'", "'status': 'clarify'")).run(timeout=30)
        self.assertTrue(app.button(key='confirm_report_plan').disabled)
        app.button(key='cancel_report_plan').click().run(timeout=30)
        self.assertIsNone(app.session_state['pending_report'])
        self.assertEqual(app.session_state['calls'],[])
