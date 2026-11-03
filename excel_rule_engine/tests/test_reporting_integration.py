"""Integration tests spanning engine, templates, configuration and Excel output."""
import sys
import unittest
from pathlib import Path
from io import BytesIO

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import pandas as pd
from openpyxl import load_workbook
from app.services.report_engine import run_report, load_config, serialize_config, join_sources
from app.services.advanced_report_export import build_advanced_report_bytes


class TestReportingIntegration(unittest.TestCase):
    def test_iso_date_and_dayfirst_are_consistent(self):
        df = pd.DataFrame({'day': ['2026-11-03', '03/11/2026', '2026-03-11'], 'value': [1, 2, 3]})
        result = run_report(df, {'version': 1, 'filters': [
            {'column': 'day', 'operator': 'between', 'value': ['2026-11-01', '2026-11-30'], 'type': 'date'}],
            'metrics': [{'column': 'value', 'operation': 'sum', 'alias': 'Total'}]})
        self.assertEqual(result['summary']['Total'].iloc[0], 3)

    def test_examples_run_and_export(self):
        frame = pd.DataFrame({'employee_id': ['A', 'B', 'C'], 'department': ['IT', 'IT', 'HR'],
                              'salary': [12000000, 16000000, 20000000],
                              'status': ['active', 'active', 'inactive'],
                              'start_date': ['2024-03-02', '2025-06-01', '2025-07-01']})
        root = Path(__file__).resolve().parents[1] / 'examples'
        for path in root.glob('*.json'):
            with self.subTest(config=path.name):
                config = load_config(path.read_bytes())
                self.assertEqual(load_config(serialize_config(config)), config)
                result = run_report(frame, config)
                blob = build_advanced_report_bytes(result, config)
                wb = load_workbook(BytesIO(blob))
                self.assertIn('Summary', wb.sheetnames)
                self.assertIn('Configuration', wb.sheetnames)
                wb.close()

    def test_join_then_group_does_not_inflate(self):
        left = pd.DataFrame({'product': ['A', 'A', 'B'], 'revenue': [10, 20, 5]})
        right = pd.DataFrame({'code': ['A', 'B'], 'category': ['C1', 'C2']})
        joined, warnings = join_sources(left, right, ['product'], ['code'])
        result = run_report(joined, {'version': 1, 'group_by': ['category'],
            'metrics': [{'column': 'revenue', 'operation': 'sum', 'alias': 'Revenue'}]})
        self.assertEqual(result['summary']['Revenue'].sum(), 35)
        self.assertEqual(warnings, [])
