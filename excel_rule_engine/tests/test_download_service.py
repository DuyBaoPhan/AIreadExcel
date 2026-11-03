"""Tests for server-side cloud downloads and Streamlit rendering."""
import ast
import sys
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import requests
from app.services.download_service import EXCEL_MIME, fetch_output_file


class TestDownloadService(unittest.TestCase):
    @patch('app.services.download_service.requests.get')
    def test_fetches_bytes_and_encodes_names(self, get):
        get.return_value.content = b'xlsx-content'
        result = fetch_output_file('http://localhost:8000/', 'demo project', 'report #1.xlsx')
        self.assertEqual(result, b'xlsx-content')
        get.assert_called_once_with(
            'http://localhost:8000/api/download/demo%20project/report%20%231.xlsx', timeout=30)
        get.return_value.raise_for_status.assert_called_once()

    @patch('app.services.download_service.requests.get')
    def test_http_errors_propagate(self, get):
        get.return_value.raise_for_status.side_effect = requests.HTTPError('404')
        with self.assertRaises(requests.HTTPError):
            fetch_output_file('http://localhost:8000', 'demo', 'missing.xlsx')

    def renderer(self, loader):
        # Load only this UI helper without executing the full interactive app.
        source = Path(__file__).resolve().parents[1] / 'app' / 'chatbot.py'
        tree = ast.parse(source.read_text(encoding='utf-8'))
        node = next(n for n in tree.body if isinstance(n, ast.FunctionDef)
                    and n.name == '_render_download_button')
        st = Mock()
        env = {'st': st, 'Path': Path, 'requests': requests,
               '_load_download_data': loader, 'EXCEL_MIME': EXCEL_MIME}
        exec(compile(ast.Module(body=[node], type_ignores=[]), str(source), 'exec'), env)
        return st, env['_render_download_button']

    def test_ui_uses_native_download_not_localhost_link(self):
        loader = Mock(return_value=b'xlsx')
        st, render = self.renderer(loader)
        render('/output/report.xlsx', project='demo', key='chat_1')
        loader.assert_called_once_with('demo', 'report.xlsx')
        args = st.download_button.call_args.kwargs
        self.assertEqual(args['data'], b'xlsx')
        self.assertEqual(args['file_name'], 'report.xlsx')
        self.assertEqual(args['mime'], EXCEL_MIME)
        self.assertEqual(args['key'], 'chat_1')
        st.markdown.assert_not_called()

    def test_missing_file_shows_warning(self):
        st, render = self.renderer(Mock(side_effect=requests.HTTPError('404')))
        render('missing.xlsx', project='demo', key='missing')
        st.warning.assert_called_once()
        st.download_button.assert_not_called()
