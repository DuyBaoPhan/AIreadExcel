"""Shared edits use durable cooperative locks; all storage calls are mocked."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app.services.sources import source_updates as updates


class SharedSourceUpdateTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / 'project' / 'input'
        self.root.mkdir(parents=True)
        self.path = self.root / 'staff.csv'
        self.original = b'id,name\r\n1,Alice\r\n'
        self.path.write_bytes(self.original)
        self.remote = self.original
        self.events = []
        self.locked = False
        self.backups = {}
        self.storage = patch.object(updates, 'shared_storage').start()
        self.addCleanup(patch.stopall)
        self.storage.is_enabled.return_value = True
        self.storage.object_key.return_value = 'projects/project/input/staff.csv'
        self.storage.download_file.side_effect = self.download
        self.storage.rpc.side_effect = self.rpc
        self.storage.upload_file.side_effect = self.backup
        self.storage.upload_bytes.side_effect = self.upload
        self.storage.read_bytes.side_effect = self.read_remote

    def read_remote(self, path):
        self.events.append('read')
        return self.backups[Path(path).name] if Path(path).parent.name == 'backups' else self.remote

    def download(self, path):
        self.events.append('download')
        Path(path).write_bytes(self.remote)

    def rpc(self, name, payload):
        self.events.append(name)
        if name == 'acquire_source_update_lock':
            if self.locked:
                return False
            self.locked = True
        else:
            self.locked = False
        return True

    def backup(self, path, overwrite=False):
        self.assertTrue(self.locked)
        self.assertFalse(overwrite)
        self.assertEqual(Path(path).parent.name, 'backups')
        self.backups[Path(path).name] = Path(path).read_bytes()
        self.events.append('backup')

    def upload(self, path, raw, overwrite=False):
        self.assertTrue(self.locked)
        self.assertTrue(overwrite)
        self.assertEqual(self.path.read_bytes(), self.original)
        self.events.append('upload')
        self.remote = raw

    def propose(self):
        return updates.propose_update(self.root, self.path.name, 'id', '1', 'name', 'Updated')['token']

    def test_remote_backup_then_verified_write_and_local_replace(self):
        token = self.propose()
        self.events.clear()
        result = updates.confirm_update(self.root, token)
        self.assertEqual(result['status'], 'updated')
        self.assertEqual(self.events, ['acquire_source_update_lock', 'read', 'backup', 'read', 'upload', 'read', 'release_source_update_lock'])
        self.assertEqual(self.backups[result['backup']], self.original)
        self.assertEqual(self.path.read_bytes(), self.remote)
        self.assertIn(b'Updated', self.remote)
        self.assertFalse(self.locked)
        with self.assertRaisesRegex(ValueError, 'consumed'):
            updates.confirm_update(self.root, token)

    def test_fresh_remote_preview_and_stale_confirm_rejected(self):
        self.remote = b'id,name\r\n1,Fresh\r\n'
        token = self.propose()
        self.assertEqual(updates._PENDING[token]['digest'], updates.hashlib.sha256(self.remote).digest())
        self.remote = b'id,name\r\n1,Other writer\r\n'
        with self.assertRaisesRegex(ValueError, 'changed'):
            updates.confirm_update(self.root, token)
        self.storage.upload_bytes.assert_not_called()
        self.assertFalse(self.locked)

    def test_busy_distributed_lock_never_reads_or_writes(self):
        token = self.propose()
        self.locked = True
        self.events.clear()
        with self.assertRaisesRegex(ValueError, 'locked'):
            updates.confirm_update(self.root, token)
        self.assertEqual(self.events, ['acquire_source_update_lock'])
        self.storage.upload_bytes.assert_not_called()

    def test_ambiguous_upload_retains_lock_and_original_local_file(self):
        token = self.propose()
        self.storage.upload_bytes.side_effect = TimeoutError('uncertain')
        with self.assertRaises(TimeoutError):
            updates.confirm_update(self.root, token)
        self.assertTrue(self.locked)
        self.assertEqual(self.path.read_bytes(), self.original)
        self.assertNotIn('release_source_update_lock', self.events)
        self.assertFalse(list(self.root.glob('.source-update-*')))

    def test_failed_backup_never_uploads_source_and_retains_lock(self):
        token = self.propose()
        self.storage.upload_file.side_effect = TimeoutError('uncertain backup')
        with self.assertRaises(TimeoutError):
            updates.confirm_update(self.root, token)
        self.storage.upload_bytes.assert_not_called()
        self.assertTrue(self.locked)

    def test_write_verification_failure_retains_lock(self):
        token = self.propose()
        reads = iter([self.original, self.original, b'wrong'])
        self.storage.read_bytes.side_effect = lambda path: next(reads)
        with self.assertRaisesRegex(RuntimeError, 'verified'):
            updates.confirm_update(self.root, token)
        self.assertEqual(self.path.read_bytes(), self.original)
        self.assertTrue(self.locked)

    def test_release_failure_does_not_report_success(self):
        token = self.propose()
        self.locked = True
        self.storage.rpc.side_effect = [True, False]
        with self.assertRaisesRegex(RuntimeError, 'release'):
            updates.confirm_update(self.root, token)

    def test_download_failure_no_local_fallback(self):
        token = self.propose()
        self.storage.read_bytes.side_effect = ConnectionError('offline')
        with self.assertRaises(ConnectionError):
            updates.confirm_update(self.root, token)
        self.storage.upload_bytes.assert_not_called()
        self.assertFalse(self.locked)

    def test_cache_mutation_cannot_change_approved_snapshot(self):
        def racing_read(path):
            raw = self.read_remote(path)
            self.path.write_bytes(b'id,name\r\n1,Unapproved cache\r\n2,Injected\r\n')
            return raw
        self.storage.read_bytes.side_effect = racing_read
        token = self.propose()
        self.assertEqual(updates._PENDING[token]['digest'], updates.hashlib.sha256(self.original).digest())
        # Normal upload mock checks local bytes; this regression intentionally changes them.
        def upload_snapshot(path, raw, overwrite=False):
            self.assertTrue(self.locked)
            self.assertEqual(raw, b'id,name\r\n1,Updated\r\n')
            self.remote = raw
        self.storage.upload_bytes.side_effect = upload_snapshot
        result = updates.confirm_update(self.root, token)
        self.assertEqual(result['status'], 'updated')
        self.assertEqual(self.backups[result['backup']], self.original)
        self.assertEqual(self.path.read_bytes(), b'id,name\r\n1,Updated\r\n')
        self.storage.download_file.assert_not_called()

    def test_mode_change_consumes_token_without_upload(self):
        token = self.propose()
        self.storage.is_enabled.return_value = False
        with self.assertRaisesRegex(ValueError, 'mode changed'):
            updates.confirm_update(self.root, token)
        self.storage.upload_bytes.assert_not_called()

    def test_sql_rpc_is_service_role_only_and_has_no_expiring_lease(self):
        sql = (Path(__file__).resolve().parents[2] / 'scripts' / 'supabase_storage_setup.sql').read_text()
        self.assertIn('on conflict (object_key) do nothing', sql)
        self.assertIn('owner_token = p_owner_token', sql)
        self.assertIn('from public, anon, authenticated', sql)
        self.assertIn('to service_role', sql)
        self.assertNotIn('interval ', sql)
