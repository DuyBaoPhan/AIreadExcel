"""Session-only advanced wizard integration tests without a chatbot server."""
import sys
from datetime import date
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from streamlit.testing.v1 import AppTest


SCRIPT = '''
from unittest.mock import patch
from app.advanced_report_wizard import render_advanced_report_wizard
class Uploaded:
    name = 'sales.csv'
    def getvalue(self):
        return b'department,salary\\nIT,100\\nHR,200\\n'
def upload(label, **kwargs):
    return Uploaded() if kwargs.get('key') == 'advanced_primary' else None
with patch('app.advanced_report_wizard.st.file_uploader', side_effect=upload):
    render_advanced_report_wizard()
'''


class TestAdvancedReportWizard(unittest.TestCase):
    def test_no_upload_without_api(self):
        app = AppTest.from_string(
            'from app.advanced_report_wizard import render_advanced_report_wizard\nrender_advanced_report_wizard()'
        ).run(timeout=60)
        self.assertEqual(len(app.exception), 0)
        self.assertEqual(len(app.get('file_uploader')), 1)
        self.assertEqual(len(app.get('download_button')), 0)

    def test_preview_generate_and_invalidate(self):
        app = AppTest.from_string(SCRIPT).run(timeout=60)
        self.assertEqual(len(app.exception), 0)
        self.assertEqual(len(app.get('download_button')), 1)  # Config needs no pipeline execution.
        app.button(key='advanced_generate').click().run(timeout=60)
        self.assertEqual(len(app.exception), 0)
        self.assertEqual(len(app.error), 0)
        self.assertEqual(len(app.get('download_button')), 2)
        self.assertTrue(app.session_state['advanced_report_result']['data'].startswith(b'PK'))
        app.text_input(key='advanced_company').set_value('New company').run(timeout=60)
        self.assertEqual(len(app.get('download_button')), 1)
        self.assertNotIn('advanced_report_result', app.session_state)

    def test_pivot_generate_uses_real_pipeline(self):
        app = AppTest.from_string(SCRIPT).run(timeout=60)
        app.checkbox(key='advanced_pivot_enabled').check().run(timeout=60)
        app.multiselect(key='advanced_pivot_index').set_value(['department'])
        app.selectbox(key='advanced_pivot_columns').set_value('department')
        app.selectbox(key='advanced_pivot_values').set_value('salary').run(timeout=60)
        # Keep the index distinct from the column axis.
        app.multiselect(key='advanced_pivot_index').set_value([]).run(timeout=60)
        app.button(key='advanced_generate').click().run(timeout=60)
        self.assertEqual(len(app.exception), 0)
        self.assertEqual(len(app.error), 0)
        self.assertEqual(len(app.get('download_button')), 2)
        self.assertTrue(app.session_state['advanced_report_result']['data'].startswith(b'PK'))
        self.assertFalse(app.session_state['advanced_report_result']['report']['summary'].empty)

    def test_comparison_defaults_and_inclusive_end_day(self):
        today = date.today()
        csv = (f'department,salary,date\nIT,100,{today.isoformat()} 18:00:00\n'
               f'HR,200,{today.year - 1}-01-01 18:00:00\n')
        script = SCRIPT.replace("b'department,salary\\nIT,100\\nHR,200\\n'", repr(csv.encode()))
        app = AppTest.from_string(script).run(timeout=60)
        app.checkbox(key='advanced_comparison_enabled').check().run(timeout=60)
        app.selectbox(key='advanced_comparison_column').set_value('date').run(timeout=60)
        app.button(key='advanced_generate').click().run(timeout=60)
        self.assertEqual(len(app.exception), 0)
        self.assertEqual(len(app.error), 0)
        summary = app.session_state['advanced_report_result']['report']['summary']
        self.assertEqual(summary['row_count_current'].iloc[0], 1)
        self.assertEqual(summary['row_count_previous'].iloc[0], 1)
        # A checked comparison from the preceding run must not leak into pivot.
        app.checkbox(key='advanced_pivot_enabled').check().run(timeout=60)
        app.selectbox(key='advanced_pivot_values').set_value('salary').run(timeout=60)
        app.button(key='advanced_generate').click().run(timeout=60)
        self.assertEqual(len(app.error), 0)

    def test_imported_config_generate_uses_real_pipeline(self):
        script = SCRIPT.replace(
            "return Uploaded() if kwargs.get('key') == 'advanced_primary' else None",
            """if kwargs.get('key') == 'advanced_primary':
        return Uploaded()
    class Config:
        def getvalue(self):
            return b'{"version":1,"filter_logic":"and","filters":[{"column":"salary","operator":"ge","type":"number","value":100}],"group_by":["department"],"metrics":[{"operation":"sum","column":"salary","alias":"total"}]}'
    return Config()""",
        )
        app = AppTest.from_string(script).run(timeout=60)
        app.checkbox(key='advanced_use_imported').check().run(timeout=60)
        app.button(key='advanced_generate').click().run(timeout=60)
        self.assertEqual(len(app.exception), 0)
        self.assertEqual(len(app.error), 0)
        self.assertEqual(len(app.get('download_button')), 2)
        self.assertTrue(app.session_state['advanced_report_result']['data'].startswith(b'PK'))

    def test_imported_invalid_column_reports_error(self):
        script = SCRIPT.replace(
            "return Uploaded() if kwargs.get('key') == 'advanced_primary' else None",
            """if kwargs.get('key') == 'advanced_primary':
        return Uploaded()
    class Config:
        def getvalue(self):
            return b'{"version":1,"group_by":["missing"],"metrics":[{"operation":"rows","alias":"rows"}]}'
    return Config()""",
        )
        app = AppTest.from_string(script).run(timeout=60)
        app.checkbox(key='advanced_use_imported').check().run(timeout=60)
        self.assertEqual(len(app.exception), 0)
        if not app.error:
            app.button(key='advanced_generate').click().run(timeout=60)
        self.assertEqual(len(app.exception), 0)
        self.assertGreater(len(app.error), 0)
        self.assertNotIn('advanced_report_result', app.session_state)

    def test_bad_upload_reports_error(self):
        script = SCRIPT.replace("return b'department,salary\\nIT,100\\nHR,200\\n'", "return b''")
        app = AppTest.from_string(script).run(timeout=60)
        self.assertEqual(len(app.exception), 0)
        self.assertGreater(len(app.error), 0)
        self.assertEqual(len(app.get('download_button')), 0)


if __name__ == '__main__':
    unittest.main()

