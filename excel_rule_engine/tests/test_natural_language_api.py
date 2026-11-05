"""Legacy command clients run the AI conversation, never the local NLP router."""
import asyncio
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.main import handle_command, CommandRequest, confirm_conversation_report, ConfirmReportRequest
from app.services.reports import conversation_reporting as reports


@pytest.fixture
def command_workspace(tmp_path, monkeypatch):
    source, output = tmp_path / 'input', tmp_path / 'output'
    source.mkdir()
    output.mkdir()
    (source / 'sales.csv').write_text('product,revenue\nA,10\nB,20\n', encoding='utf-8')
    monkeypatch.setenv('REPORT_PLANNER', 'openai')
    monkeypatch.setattr(reports, 'safe_output_path', lambda project, name: output / name)
    with patch('app.main.get_input_dir', return_value=source), \
         patch('app.main.ensure_session'), patch('app.main.create_task', return_value=1), \
         patch('app.main.update_task_status') as status, \
         patch('app.workflows.report_export.run_export_report', side_effect=AssertionError('generic fallback')) as generic, \
         patch('requests.post', side_effect=AssertionError('live HTTP forbidden')):
        yield source, output, status, generic


@pytest.mark.parametrize('action', ['query', 'export'])
def test_legacy_command_uses_ai_plan_and_returns_computed_outcome(command_workspace, action):
    source, output, status, generic = command_workspace
    plan = {'status': 'ready', 'source': 'sales.csv', 'config': {
        'version': 1, 'filters': [], 'group_by': ['product'],
        'metrics': [{'column': 'revenue', 'operation': 'sum', 'alias': 'Total'}]}}
    with patch('app.services.chat.chat_conversation.route_turn', return_value={
            'action': action, 'reply': '', 'request': 'revenue by product'}) as route, \
         patch('app.services.ai.openai_planner.plan_with_openai', return_value=plan) as planner:
        result = asyncio.run(handle_command(CommandRequest(text='doanh thu theo san pham')))
    assert result.error is None
    assert result.requires_input is None
    assert result.parsed['intent'] == 'CHAT'
    assert result.session_id == result.result['session_id']
    assert result.result['action'] == action
    assert sum(row['Total'] for row in result.result['result']['summary']) == 30
    assert bool(result.result['result']['output_path']) == (action == 'export')
    assert len(list(output.iterdir())) == (1 if action == 'export' else 0)
    route.assert_called_once()
    planner.assert_called_once()
    generic.assert_not_called()
    status.assert_called_once_with(1, 'done')


def test_unrecognized_constraint_remains_ai_clarification_without_export(command_workspace):
    source, output, status, generic = command_workspace
    with patch('app.services.chat.chat_conversation.route_turn', return_value={
            'action': 'clarify', 'reply': 'Which forecast period?', 'request': ''}), \
         patch('app.services.ai.openai_planner.plan_with_openai') as planner:
        result = asyncio.run(handle_command(CommandRequest(text='du bao doanh thu')))
    assert result.result['action'] == 'clarify'
    assert result.result['reply'] == 'Which forecast period?'
    assert result.requires_input is None
    assert 'result' not in result.result
    planner.assert_not_called()
    generic.assert_not_called()
    assert not list(output.iterdir())


def test_provider_failure_is_safe_error_not_preview_or_generic_export(command_workspace):
    source, output, status, generic = command_workspace
    with patch('app.services.chat.chat_conversation.route_turn', side_effect=ValueError('OPENAI_UNAVAILABLE')), \
         patch.object(reports, 'preview_request') as preview:
        result = asyncio.run(handle_command(CommandRequest(text='doanh thu')))
    assert result.error == 'OPENAI_UNAVAILABLE'
    assert result.result is None
    assert result.requires_input is None
    status.assert_called_once_with(1, 'failed', error_msg='OPENAI_UNAVAILABLE')
    preview.assert_not_called()
    generic.assert_not_called()
    assert not list(output.iterdir())


def test_confirm_executes_only_explicit_endpoint():
    with patch.object(reports, 'execute_request', return_value={'output_path': 'x.xlsx'}) as execute:
        result = asyncio.run(confirm_conversation_report(ConfirmReportRequest(
            text='doanh thu', source_name='sales.csv', fingerprint='abc')))
    assert result['result']['output_path'] == 'x.xlsx'
    execute.assert_called_once()
