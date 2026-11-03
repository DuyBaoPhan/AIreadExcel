"""Regression cases from independent reporting correctness review."""
import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import pandas as pd
from app.services.report_engine import run_report, load_config


class TestReportAuditRegressions(unittest.TestCase):
    def test_metric_conversion_does_not_change_group_keys(self):
        df = pd.DataFrame({'code': ['01', '1', '02']})
        report = run_report(df, {'version': 1, 'group_by': ['code'], 'metrics': [
            {'column': 'code', 'operation': 'sum', 'alias': 'Total'},
            {'operation': 'rows', 'alias': 'Rows'}]})
        self.assertEqual(report['summary']['code'].tolist(), ['01', '1', '02'])
        self.assertEqual(report['summary']['Rows'].tolist(), [1, 1, 1])

    def test_metric_conversion_does_not_change_other_metrics(self):
        result = run_report(pd.DataFrame({'x': ['2', '10']}), {'version': 1, 'metrics': [
            {'column': 'x', 'operation': 'min', 'alias': 'TextMin'},
            {'column': 'x', 'operation': 'sum', 'alias': 'Total'}]})
        self.assertEqual(result['summary']['TextMin'].iloc[0], '10')
        self.assertEqual(result['summary']['Total'].iloc[0], 12)

    def test_malformed_enum_config_is_validation_error(self):
        raw = [b'{"version":1,"filters":[{"column":"x","operator":[]}]}',
               b'{"version":1,"metrics":[{"operation":{},"alias":"bad"}]}',
               b'{"version":1,"date_group":{"column":"x","frequency":[]}}']
        for value in raw:
            with self.subTest(raw=value), self.assertRaises(ValueError):
                load_config(value)

    def test_unknown_comparison_group_rejected(self):
        config = {'version': 1, 'group_by': ['missing'], 'metrics': [{'operation': 'rows', 'alias': 'Rows'}],
                  'comparison': {'date_column': 'day', 'current_start': '2026-01-01', 'current_end': '2026-01-31',
                                 'previous_start': '2025-01-01', 'previous_end': '2025-01-31'}}
        with self.assertRaises(ValueError):
            run_report(pd.DataFrame({'day': ['2026-01-01']}), config)
