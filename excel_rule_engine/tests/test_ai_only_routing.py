"""Production NLP must use AI even without credentials or a healthy provider."""
import ast
import asyncio
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from app.services.ai.planner_settings import planner_mode, planner_status
from app.services.reports import conversation_reporting as reports


@pytest.mark.parametrize('mode', [None, 'auto', 'openai', ' AUTO '])
def test_modes_never_select_rules_without_credentials(monkeypatch, mode):
    monkeypatch.delenv('OPENAI_API_KEY', raising=False)
    if mode is None:
        monkeypatch.delenv('REPORT_PLANNER', raising=False)
    else:
        monkeypatch.setenv('REPORT_PLANNER', mode)
    assert planner_mode() == 'openai'
    assert planner_status()['configured'] is False


@pytest.mark.parametrize('mode', ['rules', 'offline', ''])
def test_retired_or_invalid_modes_are_actionable(monkeypatch, mode):
    monkeypatch.setenv('REPORT_PLANNER', mode)
    with pytest.raises(ValueError, match='openai'):
        planner_mode()


def test_production_import_graph_excludes_legacy_nlp():
    root = Path(__file__).resolve().parents[1] / 'app'
    legacy = {'command_parser', 'intent_router', 'entity_extractor',
              'analytical_request', 'report_planner', 'response_generator',
              'source_policy', 'legacy_nlp'}
    # Retired NLP code has been deleted; prevent reintroducing it into production.
    for path in root.rglob('*.py'):
        tree = ast.parse(path.read_text(encoding='utf-8-sig'))
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module:
                assert not legacy.intersection(node.module.split('.')), str(path)
            if isinstance(node, ast.Import):
                assert all(not legacy.intersection(n.name.split('.')) for n in node.names), str(path)


def test_missing_credentials_report_stops_without_output(tmp_path):
    source = tmp_path/'input'
    source.mkdir()
    (source/'staff.csv').write_text('name,salary\nAn,10\n')
    with pytest.raises(ValueError, match='OPENAI_API_KEY'):
        reports.automatic_request(source, 'demo', 'show staff')
    assert not (tmp_path/'output').exists()


def test_command_adapter_provider_error_is_safe(monkeypatch):
    from app import main
    monkeypatch.setenv('REPORT_PLANNER', 'auto')
    with patch.object(main, 'ensure_session'), patch.object(main, 'create_task', return_value=1), \
         patch.object(main, 'update_task_status') as status, \
         patch('app.services.chat.chat_conversation.chat', side_effect=ValueError('AI unavailable')):
        result = asyncio.run(main.handle_command(main.CommandRequest(text='list files')))
    assert result.result is None
    assert result.error == 'AI unavailable'
    status.assert_called_once_with(1, 'failed', error_msg='AI unavailable')


def test_chat_rejects_rules_before_provider(tmp_path, monkeypatch):
    from app.services.chat import chat_conversation
    monkeypatch.setenv('REPORT_PLANNER', 'rules')
    with patch.object(chat_conversation, 'route_turn') as provider:
        with pytest.raises(ValueError, match='REPORT_PLANNER=openai'):
            chat_conversation.chat(tmp_path, 'demo', 'help')
    provider.assert_not_called()


def test_command_adapter_preserves_server_conversation_id():
    from app import main
    with patch.object(main, "ensure_session"), patch.object(main, "create_task", return_value=1), \
         patch.object(main, "update_task_status"), \
         patch("app.services.chat.chat_conversation.chat", return_value={"session_id": "server-session", "action": "chat", "reply": "hello"}) as chat:
        result = asyncio.run(main.handle_command(main.CommandRequest(text="hello", session_id="server-session")))
    assert result.session_id == result.result["session_id"] == "server-session"
    assert chat.call_args.args[3] == "server-session"


@pytest.mark.parametrize("name", ["../outside.csv", "C:/outside.csv", "missing.csv"])
def test_explicit_comparison_rejects_unlisted_sources(tmp_path, name):
    from app import main
    source = tmp_path / "input"
    source.mkdir()
    with patch.object(main, "get_input_dir", return_value=source), \
         patch.object(main, "update_task_status"), patch.object(main, "run_comparison") as compare:
        req = main.ExecuteComparisonRequest(session_id="s", task_id=1, primary_key="id", root_file=name)
        result = asyncio.run(main.execute_comparison(req))
    assert result.error
    compare.assert_not_called()


def test_retired_nlp_package_is_removed():
    engine = Path(__file__).resolve().parents[1]
    assert not (engine / "legacy_nlp").exists()
    assert not (engine / "app/workflows/revenue_report.py").exists()
    assert not (engine.parent / "scripts/run_test_cases.py").exists()
