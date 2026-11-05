"""Presentation regression tests for configurable Excel reports."""
import sys
import unittest
from io import BytesIO
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import pandas as pd
from openpyxl import load_workbook
from app.services.reports.advanced_report_export import build_advanced_report_bytes


class TestAdvancedReportExport(unittest.TestCase):
    def test_complete_workbook_and_literal_text(self):
        result = {'data': pd.DataFrame({'name': ['=1+1'], 'amount': [20]}),
                  'summary': pd.DataFrame({'group': ['IT'], 'sales_percent': [50.0]}),
                  'warnings': ['=Do not evaluate']}
        config = {'version': 1, 'group_by': ['name']}
        blob = build_advanced_report_bytes(result, config, title='=Title', company='=Company')
        wb = load_workbook(BytesIO(blob))
        self.addCleanup(wb.close)
        self.assertEqual(wb.sheetnames, ['Report', 'Summary', 'Data', 'Quality', 'Configuration'])
        self.assertEqual(wb['Report']['A1'].data_type, 's')
        self.assertEqual(wb['Data']['A2'].data_type, 's')
        self.assertEqual(wb['Quality']['A2'].data_type, 's')
        self.assertEqual(wb['Summary']['B2'].number_format, '0.00"%"')
        self.assertEqual(len(wb['Report']._charts), 1)
        self.assertEqual(wb['Data'].freeze_panes, 'A2')
        self.assertTrue(wb['Configuration']['A2'].value)

    def test_empty_results_export_without_chart(self):
        result = {'data': pd.DataFrame(columns=['A']),
                  'summary': pd.DataFrame(columns=['A', 'Total']), 'warnings': []}
        wb = load_workbook(BytesIO(build_advanced_report_bytes(result, {'version': 1})))
        self.addCleanup(wb.close)
        self.assertEqual(len(wb['Report']._charts), 0)
        self.assertEqual(wb['Data']['A1'].value, 'A')

    def test_long_config_roundtrips_without_truncation(self):
        import json
        config = {'version': 1, 'filters': [{'column': 'x', 'operator': 'eq', 'value': 'a' * 40000}]}
        result = {'data': pd.DataFrame({'x': ['short']}), 'summary': pd.DataFrame(), 'warnings': []}
        wb = load_workbook(BytesIO(build_advanced_report_bytes(result, config)))
        self.addCleanup(wb.close)
        text = ''.join(row[0] for row in wb['Configuration'].iter_rows(min_row=2, values_only=True))
        self.assertEqual(json.loads(text), config)

    def test_source_long_text_is_not_silently_truncated(self):
        result = {'data': pd.DataFrame({'x': ['a' * 40000]}), 'summary': pd.DataFrame(), 'warnings': []}
        with self.assertRaisesRegex(ValueError, '32,767'):
            build_advanced_report_bytes(result, {'version': 1})

    def test_invalid_results_rejected(self):
        with self.assertRaises(ValueError):
            build_advanced_report_bytes({'data': [], 'summary': []}, {})
        with self.assertRaises(ValueError):
            build_advanced_report_bytes({'data': pd.DataFrame(columns=range(201)),
                                         'summary': pd.DataFrame()}, {})
