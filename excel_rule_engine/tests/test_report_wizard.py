"""UI smoke tests without starting the private FastAPI server."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from streamlit.testing.v1 import AppTest


class TestReportWizard(unittest.TestCase):
    def test_no_upload_does_not_require_api(self):
        app = AppTest.from_string(
            'from app.ui.report_wizard import render_report_wizard\nrender_report_wizard()'
        ).run(timeout=20)
        self.assertEqual(len(app.exception), 0)
        self.assertEqual(len(app.get('file_uploader')), 1)

    def test_invalid_upload_shows_error(self):
        script = '''
from unittest.mock import patch
from app.ui.report_wizard import render_report_wizard
class Uploaded:
    name = 'broken.xlsx'
    def getvalue(self):
        return b'not-an-excel-file'
with patch('app.ui.report_wizard.st.file_uploader', return_value=Uploaded()):
    render_report_wizard()
'''
        app = AppTest.from_string(script).run(timeout=20)
        self.assertEqual(len(app.exception), 0)
        self.assertEqual(len(app.error), 1)
        self.assertEqual(len(app.get('download_button')), 0)

    def test_preview_generate_and_invalidate(self):
        script = '''
import streamlit as st
from unittest.mock import patch
from app.ui.report_wizard import render_report_wizard
class Uploaded:
    name = 'employees.csv'
    def getvalue(self):
        return b'department,salary\\nIT,100\\nHR,200\\n'
with patch('app.ui.report_wizard.st.file_uploader', return_value=Uploaded()):
    render_report_wizard()
'''
        app = AppTest.from_string(script).run(timeout=20)
        self.assertEqual(len(app.exception), 0)
        self.assertEqual(len(app.dataframe), 1)
        app.button(key='create_uploaded_report').click().run(timeout=20)
        self.assertEqual(len(app.exception), 0)
        self.assertEqual(len(app.get('download_button')), 1)
        self.assertTrue(app.session_state['uploaded_report_result']['data'].startswith(b'PK'))
        app.text_input(key='report_company').set_value('Another company').run(timeout=20)
        self.assertEqual(len(app.exception), 0)
        self.assertEqual(len(app.get('download_button')), 0)


if __name__ == '__main__':
    unittest.main()
