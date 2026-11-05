import sys
import unittest
import tempfile
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.services.sources.file_manager import list_excel_files
from app.core.analytical_request import is_analytical_request
from app.core.report_planner import plan_report
import pandas as pd

class TestRankingRegression(unittest.TestCase):
    def test_exact_screenshot_request(self):
        text = 'top 3 sản phẩm có doanh thu cao nhất'
        self.assertTrue(is_analytical_request(text))
        frame = pd.DataFrame({'product':['A','A','B','C','D'], 'revenue':[10,20,50,40,1]})
        plan = plan_report(text, {'sales.xlsx':frame})
        self.assertEqual(plan['status'],'ready',plan)
        from app.services.reports.report_engine import run_report
        result = run_report(frame,plan['config'])
        self.assertEqual(result['summary']['product'].tolist(),['B','C','A'])

    def test_excel_lock_files_excluded(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            (root/'sales.xlsx').touch()
            (root/'~$sales.xlsx').touch()
            self.assertEqual([p.name for p in list_excel_files(root)],['sales.xlsx'])

class TestChatRoutingRegression(unittest.TestCase):
    def run_command_with_response(self, response):
        import ast
        from contextlib import nullcontext
        from types import SimpleNamespace
        from unittest.mock import Mock
        path = Path(__file__).resolve().parents[1] / 'app' / 'ui' / 'chatbot.py'
        tree = ast.parse(path.read_text(encoding='utf-8'))
        function = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == 'process_command')
        api = Mock(return_value=response)
        messages = Mock()
        handle = Mock()
        namespace = {
            'st': SimpleNamespace(session_state=type('State', (), {'project': 'demo_project', 'pending_report': None, 'get': lambda self, key, default=None: default})(), spinner=lambda *args: nullcontext()),
            'call_api': api, 'add_message': messages, '_handle_requires_input': handle,
        }
        exec(compile(ast.Module(body=[function], type_ignores=[]), str(path), 'exec'), namespace)
        namespace['process_command']('top 3 san pham co doanh thu cao nhat')
        self.assertEqual(api.call_count, 1)
        self.assertEqual(api.call_args.args[0], '/api/report/auto')
        return messages, handle

    def test_analytical_request_goes_directly_to_planner(self):
        _, handle = self.run_command_with_response({'status': 'ready', 'config': {}})
        self.assertEqual(handle.call_count, 1)

    def test_missing_planner_does_not_fall_back_to_merge(self):
        messages, handle = self.run_command_with_response({'error': '404 Not Found'})
        handle.assert_not_called()
        self.assertEqual(messages.call_args.args[0], 'assistant')
        self.assertIn('404 Not Found', messages.call_args.args[1])
