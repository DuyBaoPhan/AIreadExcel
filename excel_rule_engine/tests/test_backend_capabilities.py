"""Reject healthy legacy servers that lack conversational report endpoints."""
from unittest.mock import Mock, patch
import requests
import pytest
from app.services.backend_capabilities import check_report_api


@pytest.mark.parametrize('paths,compatible', [
    ({'/api/report/preview': {'post': {}}, '/api/report/confirm': {'post': {}}, '/api/report/auto': {'post': {}}, '/api/chat': {'post': {}}, '/api/chat/update/confirm': {'post': {}}}, True),
    ({'/health': {'get': {}}}, False),
    ({'/api/report/preview': {'get': {}}, '/api/report/confirm': {'post': {}}}, False),
])
def test_openapi_checks_both_post_routes(paths, compatible):
    response = Mock()
    response.json.return_value = {'paths': paths}
    with patch('app.services.backend_capabilities.requests.get', return_value=response) as get:
        ok, message = check_report_api()
    assert ok is compatible
    assert bool(message) is not compatible
    get.assert_called_once_with('http://127.0.0.1:8000/openapi.json', timeout=3)


def test_unavailable_backend_has_actionable_diagnostic():
    with patch('app.services.backend_capabilities.requests.get', side_effect=requests.ConnectionError('offline')):
        ok, message = check_report_api()
    assert not ok
    assert 'offline' in message


def test_current_fastapi_declares_required_routes():
    from app.main import app
    paths = app.openapi()['paths']
    for route in ('/api/report/preview', '/api/report/confirm'):
        assert 'post' in paths[route]

def test_invalid_openapi_paths_are_incompatible():
    response = Mock()
    response.json.return_value = {'paths': []}
    with patch('app.services.backend_capabilities.requests.get', return_value=response):
        assert check_report_api()[0] is False


def test_launcher_does_not_start_ui_on_occupied_api_port():
    import importlib.util
    from pathlib import Path
    import os
    path = Path(__file__).resolve().parents[1] / 'main.py'
    spec = importlib.util.spec_from_file_location('test_engine_launcher', path)
    launcher = importlib.util.module_from_spec(spec)
    cwd = os.getcwd()
    try:
        spec.loader.exec_module(launcher)
        with patch('socket.socket') as socket, patch('subprocess.Popen') as start, \
             patch('app.services.backend_capabilities.check_report_api', return_value=(False, 'missing preview')):
            socket.return_value.__enter__.return_value.connect_ex.return_value = 0
            launcher.main()
        start.assert_not_called()
    finally:
        os.chdir(cwd)

def test_cloud_bootstrap_stops_on_healthy_incompatible_backend():
    import ast
    from pathlib import Path
    from types import SimpleNamespace
    source = (Path(__file__).resolve().parents[2] / 'streamlit_app.py').read_text(encoding='utf-8')
    node = next(n for n in ast.parse(source).body if isinstance(n, ast.FunctionDef) and n.name == 'start_fastapi')
    response = Mock(status_code=200)
    class StopBootstrap(BaseException):
        pass
    streamlit = SimpleNamespace(error=Mock(), stop=Mock(side_effect=StopBootstrap))
    namespace = {'subprocess': SimpleNamespace(Popen=Mock())}
    exec(compile(ast.Module(body=[node], type_ignores=[]), '<bootstrap>', 'exec'), namespace)
    with patch('requests.get', return_value=response), \
         patch('app.services.backend_capabilities.check_report_api', return_value=(False, 'missing report API')), \
         patch.dict('sys.modules', {'streamlit': streamlit}), pytest.raises(StopBootstrap):
        namespace['start_fastapi']()
    streamlit.error.assert_called_once()
    namespace['subprocess'].Popen.assert_not_called()
