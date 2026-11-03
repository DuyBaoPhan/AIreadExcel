"""Full chatbot navigation smoke tests with deterministic backend responses."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from streamlit.testing.v1 import AppTest

SCRIPT = '''
from pathlib import Path
from unittest.mock import patch, Mock
response = Mock(status_code=200)
response.json.return_value = {'files': []}
response.content = b'example'
with patch('requests.get', return_value=response):
    path = Path(%r)
    exec(compile(path.read_text(encoding='utf-8'), str(path), 'exec'), globals())
''' % str(Path(__file__).resolve().parents[1] / 'app' / 'chatbot.py')


class TestChatbotWorkspace(unittest.TestCase):
    def test_navigation_only_renders_selected_tool(self):
        app = AppTest.from_string(SCRIPT).run(timeout=30)
        self.assertEqual(len(app.exception), 0)
        self.assertEqual(len(app.get('chat_input')), 1)
        self.assertEqual(len(app.get('file_uploader')), 0)
        app.radio(key='workspace_section').set_value('Tạo báo cáo').run(timeout=30)
        self.assertEqual(len(app.exception), 0)
        self.assertEqual(len(app.get('file_uploader')), 1)
        self.assertEqual(len(app.get('chat_input')), 0)
        app.radio(key='workspace_section').set_value('Báo cáo nâng cao').run(timeout=30)
        self.assertEqual(len(app.exception), 0)
        self.assertEqual(len(app.get('file_uploader')), 1)
        app.radio(key='workspace_section').set_value('Chatbot').run(timeout=30)
        self.assertEqual(len(app.exception), 0)
        self.assertEqual(len(app.get('chat_input')), 1)

    def test_offline_reports_still_available(self):
        script = SCRIPT.replace("return_value=response", "side_effect=__import__('requests').ConnectionError('offline')")
        app = AppTest.from_string(script).run(timeout=30)
        self.assertEqual(len(app.exception), 0)
        self.assertTrue(app.get('chat_input')[0].disabled)
        self.assertTrue(app.warning)
        app.radio(key='workspace_section').set_value('Tạo báo cáo').run(timeout=30)
        self.assertEqual(len(app.exception), 0)
        self.assertEqual(len(app.get('file_uploader')), 1)

    def test_history_survives_navigation_and_pending_cancel(self):
        app = AppTest.from_string(SCRIPT).run(timeout=30)
        app.session_state['messages'] = [{'role': 'user', 'content': 'Test history', 'metadata': {}}]
        app.session_state['pending_comparison'] = {'suggestions': ['id']}
        app.run(timeout=30)
        self.assertEqual(len(app.exception), 0)
        self.assertTrue(app.button(key='quick_0').disabled)
        app.button(key='cancel_comparison').click().run(timeout=30)
        self.assertIsNone(app.session_state['pending_comparison'])
        app.radio(key='workspace_section').set_value('Tạo báo cáo').run(timeout=30)
        app.radio(key='workspace_section').set_value('Chatbot').run(timeout=30)
        self.assertEqual(app.session_state['messages'][0]['content'], 'Test history')
        self.assertTrue(app.button(key='clear_chat').disabled)
        app.checkbox(key='confirm_clear_chat').check().run(timeout=30)
        app.button(key='clear_chat').click().run(timeout=30)
        self.assertEqual(app.session_state['messages'], [])
