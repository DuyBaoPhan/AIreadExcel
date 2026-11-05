"""Regression coverage for explicit source-update confirmation and safe writes."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from openpyxl import Workbook, load_workbook
from openpyxl.styles import Font

from app.services.source_updates import propose_update, confirm_update


class SourceUpdateTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.path = self.root / 'staff.xlsx'
        book = Workbook()
        sheet = book.active
        sheet.append(['id', 'name', 'salary'])
        sheet.append([1, 'Alice', 100])
        sheet.append([2, 'Bob', 200])
        sheet['B2'].font = Font(bold=True, color='FF0000')
        other = book.create_sheet('Other')
        other['A1'] = '=1+1'
        book.save(self.path)
        book.close()

    def propose(self, **kwargs):
        args = dict(input_dir=self.root, source_name='staff.xlsx', key_column='id', key_value=1, column='name', value='Updated')
        args.update(kwargs)
        return propose_update(**args)

    def test_preview_confirmation_backup_and_workbook_preservation(self):
        original = self.path.read_bytes()
        result = self.propose()
        self.assertEqual(result['status'], 'confirmation_required')
        self.assertEqual(result['preview']['old_value'], 'Alice')
        self.assertEqual(self.path.read_bytes(), original)
        self.assertEqual(len(list(self.root.iterdir())), 1)
        update = confirm_update(self.root, result['token'])
        self.assertEqual(update['status'], 'updated')
        self.assertEqual((self.root / update['backup']).read_bytes(), original)
        book = load_workbook(self.path)
        self.addCleanup(book.close)
        self.assertEqual(book.active['B2'].value, 'Updated')
        self.assertTrue(book.active['B2'].font.bold)
        self.assertEqual(book['Other']['A1'].value, '=1+1')
        self.assertEqual(book.active.max_row, 3)
        with self.assertRaises(ValueError):
            confirm_update(self.root, result['token'])

    def test_csv_roundtrip_and_backup(self):
        path = self.root / 'staff.csv'
        original = b'\xef\xbb\xbfid;name\r\n1;Alice\r\n2;Bob\r\n'
        path.write_bytes(original)
        result = self.propose(source_name=path.name, key_value='1', value='A, B')
        update = confirm_update(self.root, result['token'])
        self.assertEqual((self.root / update['backup']).read_bytes(), original)
        self.assertIn('1;A, B', path.read_text(encoding='utf-8-sig'))
        with self.assertRaises(ValueError):
            self.propose(source_name=path.name, key_value='1', value=123)

    def test_stale_token_never_writes(self):
        result = self.propose()
        self.path.write_bytes(self.path.read_bytes() + b'changed')
        changed = self.path.read_bytes()
        with self.assertRaisesRegex(ValueError, 'changed'):
            confirm_update(self.root, result['token'])
        self.assertEqual(self.path.read_bytes(), changed)
        self.assertEqual(len(list(self.root.iterdir())), 1)

    def test_expired_token_and_root_binding(self):
        result = self.propose()
        with tempfile.TemporaryDirectory() as second:
            (Path(second) / self.path.name).write_bytes(self.path.read_bytes())
            with self.assertRaises(ValueError):
                confirm_update(second, result['token'])
        with patch('app.services.source_updates.time.monotonic', return_value=float('inf')):
            with self.assertRaisesRegex(ValueError, 'expired'):
                confirm_update(self.root, result['token'])

    def test_bad_paths_columns_keys_and_types(self):
        for name in ['../staff.xlsx', '..\\staff.xlsx', str(self.path), 'staff.xlsx:stream']:
            with self.subTest(name=name), self.assertRaises(ValueError):
                self.propose(source_name=name)
        for kwargs in [dict(column='id'), dict(column='missing'), dict(key_value=999), dict(value=[]), dict(value=12), dict(column='salary', value='12'), dict(value='=SUM(A1)'), dict(value=' +1'), dict(column='salary', value=float('nan'))]:
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                self.propose(**kwargs)

    def test_duplicate_keys_headers_formulas_and_merged_cells(self):
        for scenario in ['key', 'header', 'formula', 'merged']:
            with self.subTest(scenario=scenario):
                book = load_workbook(self.path)
                sheet = book.active
                if scenario == 'key':
                    sheet['A3'] = 1
                elif scenario == 'header':
                    sheet['C1'] = 'name'
                elif scenario == 'formula':
                    sheet['B2'] = '=1+1'
                else:
                    sheet.merge_cells('B2:C2')
                book.save(self.path)
                book.close()
                with self.assertRaises(ValueError):
                    self.propose()
                # Restore an independent workbook for each scenario.
                book = Workbook()
                book.active.append(['id', 'name', 'salary'])
                book.active.append([1, 'Alice', 100])
                book.active.append([2, 'Bob', 200])
                book.save(self.path)
                book.close()

    def test_replace_failure_leaves_original_and_backup(self):
        result = self.propose()
        original = self.path.read_bytes()
        with patch('app.services.source_updates.os.replace', side_effect=OSError('failure')):
            with self.assertRaises(OSError):
                confirm_update(self.root, result['token'])
        self.assertEqual(self.path.read_bytes(), original)
        self.assertEqual(len(list(self.root.glob('staff.xlsx.backup-*'))), 1)
        self.assertFalse(list(self.root.glob('.source-update-*')))


if __name__ == '__main__':
    unittest.main()
