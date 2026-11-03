"""API-level routing tests: analytical requests preview, never legacy export."""
import asyncio
import sys
import unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.main import handle_command, CommandRequest, confirm_conversation_report, ConfirmReportRequest


class TestNaturalLanguageAPI(unittest.TestCase):
    def test_revenue_is_preview_even_if_legacy_parser_rejects(self):
        with patch('app.main.ensure_session'), patch('app.main.create_task', return_value=1), \
             patch('app.main.update_task_status'), patch('app.main.run_export_report') as generic, \
             patch('app.services.conversation_reporting.preview_request', return_value={
                 'status':'ready','source':'sales.csv','config':{'version':1},'fingerprint':'abc'}) as preview:
            result = asyncio.run(handle_command(CommandRequest(text='doanh thu theo san pham')))
        self.assertEqual(result.requires_input['type'],'report_plan')
        self.assertIsNone(result.result)
        generic.assert_not_called()
        preview.assert_called_once()

    def test_unrecognized_constraint_has_no_export(self):
        with patch('app.main.ensure_session'), patch('app.main.create_task', return_value=1), \
             patch('app.main.update_task_status'), patch('app.main.run_export_report') as generic, \
             patch('app.services.conversation_reporting.preview_request', return_value={
                 'status':'unsupported','questions':['Clarify'],'unsupported':['forecast']}) :
            result = asyncio.run(handle_command(CommandRequest(text='du bao doanh thu')))
        self.assertEqual(result.requires_input['status'],'unsupported')
        generic.assert_not_called()

    def test_confirm_executes_only_explicit_endpoint(self):
        with patch('app.services.conversation_reporting.execute_request', return_value={'output_path':'x.xlsx'}) as execute:
            result = asyncio.run(confirm_conversation_report(ConfirmReportRequest(
                text='doanh thu', source_name='sales.csv', fingerprint='abc')))
        self.assertEqual(result['result']['output_path'],'x.xlsx')
        execute.assert_called_once()
