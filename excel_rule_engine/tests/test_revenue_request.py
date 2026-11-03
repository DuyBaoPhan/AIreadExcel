import sys
import unittest
import tempfile
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import pandas as pd
from app.workflows.revenue_report import run_revenue_request
from app.core.command_parser import parse_command

REQUEST = 'bao cao doanh thu cua Laptop Pro X nam 2024 la bao nhieu'

class TestRevenueRequest(unittest.TestCase):
    def test_parser_routes_specific_report(self):
        cmd = parse_command(REQUEST)
        self.assertIsNone(cmd.error_message)
        self.assertEqual(cmd.parameters['report_type'], 'revenue')

    def test_filtered_product_and_month_year(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            pd.DataFrame({'product': ['Laptop Pro X', 'Laptop Pro X', 'Other', 'Laptop Pro X'],
                          'month': ['2024-01', '2024-12', '2024-01', '2025-01'],
                          'revenue': [10, 20, 999, 100]}).to_excel(root / 'sales.xlsx', index=False)
            with patch('app.workflows.revenue_report.safe_output_path', return_value=root / 'out.xlsx'):
                result = run_revenue_request(root, 'demo', REQUEST)
            self.assertEqual(result['revenue_total'], 30)
            self.assertEqual(result['total_rows'], 2)
            self.assertTrue((root / 'out.xlsx').exists())

    def test_missing_year_not_guessed(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            pd.DataFrame({'product': ['Laptop Pro X'], 'month': [1], 'revenue': [10]}).to_excel(root / 'sales.xlsx', index=False)
            with self.assertRaises(ValueError):
                run_revenue_request(root, 'demo', REQUEST)
            self.assertEqual(len(list(root.glob('Revenue*'))), 0)

    def test_unsupported_revenue_request_never_generic_export(self):
        cmd = parse_command('doanh thu theo tung thang')
        self.assertIsNotNone(cmd.error_message)
        self.assertEqual(cmd.parameters['report_type'], 'revenue')
