"""Regression checks for upload resource limits."""
import sys
import unittest
from io import BytesIO
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import pandas as pd
from app.services.report_builder import read_uploaded_table, inspect_sheets


class TestUploadLimits(unittest.TestCase):
    def test_too_many_columns(self):
        raw = pd.DataFrame([[1] * 201], columns=[f'c{i}' for i in range(201)]).to_csv(index=False).encode()
        with self.assertRaisesRegex(ValueError, '200 column'):
            read_uploaded_table('wide.csv', raw)

    def test_archive_metadata_bound_before_parser(self):
        archive = BytesIO()
        with ZipFile(archive, 'w', compression=ZIP_DEFLATED) as wb:
            wb.writestr('document.xml', 'abc')
        with patch('app.services.report_builder.ZipFile') as zipfile:
            entry = type('Entry', (), {'file_size': 201 * 1024 * 1024})()
            zipfile.return_value.__enter__.return_value.infolist.return_value = [entry]
            with self.assertRaisesRegex(ValueError, '200 MB'):
                inspect_sheets('large.xlsx', archive.getvalue())
