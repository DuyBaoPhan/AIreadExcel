"""Regression tests for the formatted report workbook."""
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from datetime import datetime

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import pandas as pd
from openpyxl import load_workbook
from app.workflows.report_export import run_export_report


class TestReportExport(unittest.TestCase):
    def export(self, frames, broken=False):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        root = Path(directory.name)
        source = root / 'input'
        source.mkdir()
        for name, frame in frames.items():
            frame.to_excel(source / name, index=False)
            # Preserve formula-like input as literal text in the source fixture.
            source_wb = load_workbook(source / name)
            for row_index, values in enumerate(frame.itertuples(index=False, name=None), 2):
                for col_index, value in enumerate(values, 1):
                    if isinstance(value, str) and value.startswith('='):
                        source_wb.active.cell(row_index, col_index).data_type = 's'
            source_wb.save(source / name)
            source_wb.close()
        if broken:
            (source / 'broken.xlsx').write_bytes(b'not an Excel file')
        output = root / 'report.xlsx'
        with patch('app.workflows.report_export.safe_output_path', return_value=output):
            result = run_export_report(source, 'demo', 'Report title')
        wb = load_workbook(output)
        self.addCleanup(wb.close)
        return result, wb

    def test_report_layout_and_data(self):
        df = pd.DataFrame({'name': ['An', '=1+1'], 'salary': [12500000.5, None],
                           'date': [datetime(2026, 1, 2), None]})
        result, wb = self.export({'one.xlsx': df})
        self.assertEqual(result['total_rows'], 2)
        self.assertEqual(wb.sheetnames, ['Summary', 'Data', 'Statistics'])
        summary, data, stats = (wb[name] for name in wb.sheetnames)
        self.assertEqual(summary['A1'].value, 'Report title')
        self.assertEqual(summary['A5'].value, 1)
        self.assertEqual(summary['C5'].value, 2)
        self.assertEqual(summary['E5'].value, 3)
        self.assertEqual(summary['G5'].value, 2)
        self.assertEqual(len(summary._charts), 1)
        self.assertEqual(data.freeze_panes, 'A2')
        self.assertIn('ReportData', data.tables)
        self.assertEqual(data['B2'].value, 12500000.5)
        self.assertEqual(data['C2'].number_format, 'dd/mm/yyyy')
        self.assertEqual(data['A3'].data_type, 's')
        self.assertFalse(data.sheet_view.showGridLines)
        self.assertEqual(data.page_setup.fitToWidth, 1)
        self.assertEqual(stats['G3'].value, 0.5)
        self.assertTrue(len(stats.conditional_formatting))

    def test_failed_files_not_counted(self):
        result, wb = self.export({'good.xlsx': pd.DataFrame({'value': [1]})}, broken=True)
        self.assertEqual(result['files_included'], 1)
        self.assertEqual(len(result['warnings']), 1)
        self.assertEqual(wb['Summary']['A5'].value, 1)
        self.assertEqual(wb['Summary']['A9'].value, 'good.xlsx')

    def test_empty_data_has_headers_and_no_chart(self):
        result, wb = self.export({'empty.xlsx': pd.DataFrame(columns=['name', 'salary'])})
        self.assertEqual(result['total_rows'], 0)
        self.assertEqual(wb['Data']['A1'].value, 'name')
        self.assertEqual(len(wb['Summary']._charts), 0)
        self.assertEqual(wb['Summary']['B9'].value, 0)


if __name__ == '__main__':
    unittest.main()
