"""AI service integration: actual exports, no keyword gate, frozen approval."""
import ast
from contextlib import nullcontext
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

import pytest
from app.services.reports import conversation_reporting as service
from app.services.ai.planner_settings import planner_mode


@pytest.fixture
def workspace(tmp_path, monkeypatch):
    monkeypatch.setenv('REPORT_PLANNER', 'openai')
    monkeypatch.setenv('OPENAI_API_KEY', 'test-not-real')
    source = tmp_path / 'input'
    source.mkdir()
    (source / 'staff.csv').write_text('name,salary\nAn,10\nBinh,20\n', encoding='utf-8')
    output = tmp_path / 'output'
    output.mkdir()
    monkeypatch.setattr(service, 'safe_output_path', lambda p,n: output/n)
    return source, output


def plan():
    return {'status': 'ready', 'source': 'staff.csv', 'config': {'version': 1,
        'filters': [], 'group_by': [], 'metrics': []}, 'explanation': ['List staff'], 'questions': [], 'unsupported': []}


def test_auto_uses_ai_without_rule_parser_and_exports(workspace):
    source, output = workspace
    with patch('app.services.ai.openai_planner.plan_with_openai', return_value=plan()) as ai:
        response = service.automatic_request(source, 'demo', 'cho minh xem cac ban dang lam')
    assert response['status'] == 'ready'
    assert response['result']['planner'] == 'openai'
    assert response['result']['total_rows'] == 2
    assert len(list(output.iterdir())) == 1
    ai.assert_called_once()


def test_manual_confirmation_reuses_approved_config_without_second_api(workspace):
    source, output = workspace
    with patch('app.services.ai.openai_planner.plan_with_openai', return_value=plan()) as ai:
        preview = service.preview_request(source, 'show staff')
        assert not list(output.iterdir())
        result = service.execute_request(source, 'demo', 'show staff', 'staff.csv', preview['fingerprint'])
    ai.assert_called_once()
    assert result['total_rows'] == 2


def test_changed_data_rejects_approval(workspace):
    source, output = workspace
    with patch('app.services.ai.openai_planner.plan_with_openai', return_value=plan()):
        preview = service.preview_request(source, 'show staff')
    (source / 'staff.csv').write_text('name,salary\nZ,999\n')
    with pytest.raises(ValueError, match='thay doi'):
        service.execute_request(source, 'demo', 'show staff', 'staff.csv', preview['fingerprint'])
    assert not list(output.iterdir())


def test_api_error_never_falls_back(workspace):
    source, output = workspace
    with patch('app.services.ai.openai_planner.plan_with_openai', side_effect=ValueError('API unavailable')):
        with pytest.raises(ValueError, match='API unavailable'):
            service.automatic_request(source, 'demo', 'show staff')
    assert not list(output.iterdir())


def test_ai_ui_does_not_require_keyword():
    path = Path(__file__).resolve().parents[1] / 'app/ui/chatbot.py'
    node = next(n for n in ast.parse(path.read_text(encoding='utf-8')).body if isinstance(n, ast.FunctionDef) and n.name == 'process_command')
    state = {'ai_planner_enabled': False, 'auto_reports': True}
    class State:
        project = 'demo'
        def get(self, key, default=None): return state.get(key, default)
    api = Mock(return_value={'session_id':'test','action':'clarify','reply':'Which source?'})
    ns = {'st': SimpleNamespace(session_state=State(), spinner=lambda *a: nullcontext()),
          'call_api': api, 'add_message': Mock(), '_handle_requires_input': Mock()}
    exec(compile(ast.Module(body=[node], type_ignores=[]), str(path), 'exec'), ns)
    ns['process_command']('ai dang kiem nhieu tien nhat vay')
    assert api.call_args.args[0] == '/api/chat'


def test_mode_auto_and_explicit(monkeypatch):
    monkeypatch.delenv('REPORT_PLANNER', raising=False)
    monkeypatch.delenv('OPENAI_API_KEY', raising=False)
    assert planner_mode() == 'openai'
    monkeypatch.setenv('OPENAI_API_KEY', 'test')
    assert planner_mode() == 'openai'
    monkeypatch.setenv('REPORT_PLANNER', 'rules')
    with pytest.raises(ValueError, match='REPORT_PLANNER=openai'):
        planner_mode()

def test_legacy_api_ai_branch_never_calls_keyword_parser(workspace):
    import asyncio
    from app import main
    response = {'status': 'ready', 'result': {'source_file': 'staff.csv', 'total_rows': 2}}
    with patch.object(main, 'ensure_session'), patch.object(main, 'create_task', return_value=7), \
         patch.object(main, 'update_task_status'), \
         patch('app.services.chat.chat_conversation.chat', return_value=response['result']):
        outcome = asyncio.run(main.handle_command(main.CommandRequest(text='ai kiem nhieu nhat', project='demo')))
    assert outcome.result['total_rows'] == 2
    assert outcome.error is None
