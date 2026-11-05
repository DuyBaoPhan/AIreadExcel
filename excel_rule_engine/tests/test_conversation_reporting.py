"""Approval, source-isolation and evidence regressions for conversational reports."""
import copy
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.services.reports import conversation_reporting as service


class ConversationReportingTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.input = self.root / 'input'
        self.input.mkdir()
        self.output = self.root / 'output'
        self.output.mkdir()
        (self.input / 'a.csv').write_text('team,value\nA,10\nA,20\nB,5\n', encoding='utf-8')
        (self.input / 'b.csv').write_text('team,value\nX,999\n', encoding='utf-8')
        self.config = {'version': 1, 'group_by': ['team'], 'metrics': [
            {'column': 'value', 'operation': 'sum', 'alias': 'Total'}]}
        self.plan = {'status': 'ready', 'source': 'a.csv', 'config': self.config,
                     'explanation': ['Sum value by team'], 'questions': [], 'unsupported': []}
        self.addCleanup(patch.stopall)
        patch.dict(os.environ, {'REPORT_PLANNER': 'openai'}).start()
        self.planner = patch(
            'app.services.ai.openai_planner.plan_with_openai',
            side_effect=lambda *args, **kwargs: copy.deepcopy(self.plan),
        ).start()
        patch.object(service, 'safe_output_path', side_effect=lambda project, name: self.output / name).start()

    def preview(self, selected=None):
        return service.preview_request(self.input, 'sum value by team', selected)

    def execute(self, approval, selected=None):
        return service.execute_request(self.input, 'demo', 'sum value by team', selected, approval['fingerprint'])

    def test_preview_has_no_output_and_execute_totals_only_selected_source(self):
        approval = self.preview('a.csv')
        self.assertEqual(list(self.output.iterdir()), [])
        self.assertEqual(set(self.planner.call_args.args[1]), {'a.csv'})
        self.assertEqual(approval['available_sources'], ['a.csv', 'b.csv'])
        result = self.execute(approval, 'a.csv')
        self.assertEqual(result['summary'], [{'team': 'A', 'Total': 30}, {'team': 'B', 'Total': 5}])
        self.assertEqual(result['total_rows'], 3)
        self.assertEqual(result['planner'], 'openai')
        self.planner.assert_called_once()
        self.assertEqual(result['files_included'], 1)
        self.assertTrue(Path(result['output_path']).exists())
        self.assertEqual(len(list(self.output.iterdir())), 1)
        json.dumps(result, allow_nan=False)

    def test_changed_bytes_reject_stale_approval(self):
        approval = self.preview()
        (self.input / 'a.csv').write_text('team,value\nA,1000\n', encoding='utf-8')
        with self.assertRaisesRegex(ValueError, 'thay doi'):
            self.execute(approval)
        self.assertEqual(list(self.output.iterdir()), [])

    def test_changed_planner_configuration_executes_frozen_approval(self):
        approval = self.preview()
        approved_config = copy.deepcopy(approval['config'])
        self.config['top_n'] = {'column': 'Total', 'n': 1}
        self.config['metrics'][0]['operation'] = 'count'
        result = self.execute(approval)
        self.assertEqual(result['evidence']['config'], approved_config)
        self.assertEqual(result['summary'], [{'team': 'A', 'Total': 30}, {'team': 'B', 'Total': 5}])
        self.assertEqual(result['evidence']['snapshot_fingerprint'], approval['fingerprint'])
        self.planner.assert_called_once()

    def test_changed_model_does_not_replan_approved_configuration(self):
        with patch.dict(os.environ, {'OPENAI_MODEL': 'preview-model'}):
            approval = self.preview()
        with patch.dict(os.environ, {'OPENAI_MODEL': 'different-model'}):
            result = self.execute(approval)
        self.assertEqual(result['evidence']['config'], approval['config'])
        self.assertEqual(result['summary'], [{'team': 'A', 'Total': 30}, {'team': 'B', 'Total': 5}])
        self.planner.assert_called_once()

    def test_mutating_returned_preview_does_not_change_stored_approval(self):
        approval = self.preview()
        approved_config = copy.deepcopy(approval['config'])
        approval['config']['metrics'][0]['operation'] = 'count'
        approval['source'] = 'b.csv'
        result = self.execute(approval)
        self.assertEqual(result['evidence']['config'], approved_config)
        self.assertEqual(result['source_file'], 'a.csv')
        self.assertEqual(result['summary'], [{'team': 'A', 'Total': 30}, {'team': 'B', 'Total': 5}])
        self.planner.assert_called_once()

    def test_changed_selected_source_rejects_approval(self):
        approval = self.preview('a.csv')
        with self.assertRaises(ValueError):
            self.execute(approval, 'b.csv')
        self.assertEqual(list(self.output.iterdir()), [])
        self.planner.assert_called_once()

    def test_changed_request_rejects_stale_approval(self):
        approval = self.preview()
        with self.assertRaises(ValueError):
            service.execute_request(self.input, 'demo', 'another request', None, approval['fingerprint'])

    def test_configuration_key_order_does_not_change_fingerprint(self):
        first = self.preview()['fingerprint']
        self.plan['config'] = dict(reversed(list(self.config.items())))
        self.assertEqual(first, self.preview()['fingerprint'])

    def test_path_traversal_and_unknown_sources_rejected(self):
        for name in ('../a.csv', '..\\a.csv', str(self.input / 'a.csv'), 'unknown.csv'):
            with self.subTest(name=name), self.assertRaises(ValueError):
                self.preview(name)
        self.plan['source'] = '../a.csv'
        with self.assertRaises(ValueError):
            self.preview()
        self.assertEqual(list(self.output.iterdir()), [])

    def test_unsupported_and_ambiguous_never_export(self):
        for status in ('unsupported', 'clarify'):
            self.plan.update(status=status, source=None, config=None)
            approval = self.preview()
            self.assertNotIn('fingerprint', approval)
            with self.assertRaises(ValueError):
                service.execute_request(self.input, 'demo', 'sum value by team', None, 'bad')
        self.assertEqual(list(self.output.iterdir()), [])

    def test_unreadable_sources_have_visible_warnings(self):
        (self.input / 'broken.xlsx').write_bytes(b'not an excel file')
        approval = self.preview()
        self.assertTrue(any('broken.xlsx' in warning for warning in approval['warnings']))
        self.assertNotIn('broken.xlsx', self.planner.call_args.args[1])

    def test_empty_match_does_not_create_zero_report(self):
        self.config['filters'] = [{'column': 'team', 'operator': 'eq', 'value': 'absent'}]
        approval = self.preview()
        with self.assertRaisesRegex(ValueError, 'Khong co dong'):
            self.execute(approval)
        self.assertEqual(list(self.output.iterdir()), [])

    def test_null_sum_does_not_create_zero_report(self):
        (self.input / 'a.csv').write_text('team,value\nA,\nB,\n', encoding='utf-8')
        approval = self.preview()
        with self.assertRaisesRegex(ValueError, 'Khong co gia tri'):
            self.execute(approval)
        self.assertEqual(list(self.output.iterdir()), [])

    def test_valid_zero_is_evidence_not_absence(self):
        (self.input / 'a.csv').write_text('team,value\nA,0\n', encoding='utf-8')
        result = self.execute(self.preview())
        self.assertEqual(result['summary'], [{'team': 'A', 'Total': 0}])

    def test_count_explains_non_null_count(self):
        self.config['metrics'][0]['operation'] = 'count'
        result = self.execute(self.preview())
        self.assertTrue(any('count' in w for w in result['warnings']))

    def test_file_limit_refuses_partial_loading(self):
        for i in range(19):
            (self.input / f'extra{i}.csv').write_text('x\n1\n', encoding='utf-8')
        with self.assertRaisesRegex(ValueError, '20'):
            self.preview()

    def test_total_size_limit(self):
        with patch.object(service, 'MAX_SOURCE_BYTES', 1):
            with self.assertRaisesRegex(ValueError, '40 MB'):
                self.preview()

    def test_non_ascii_fingerprint_is_cleanly_rejected(self):
        with self.assertRaises(ValueError):
            service.execute_request(self.input, 'demo', 'sum value by team', None, '\u2603')

    def test_project_traversal_rejected_before_output(self):
        approval = self.preview()
        with self.assertRaises(ValueError):
            service.execute_request(self.input, '../demo', 'sum value by team', None, approval['fingerprint'])
        self.assertEqual(list(self.output.iterdir()), [])


if __name__ == '__main__':
    unittest.main()
