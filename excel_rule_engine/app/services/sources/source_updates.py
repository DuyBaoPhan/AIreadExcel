"""Explicit, preview-first single-cell source edits with expiring confirmation tokens."""
import csv
import hashlib
import io
import math
import os
import secrets
import threading
import time
from datetime import date, datetime
from pathlib import Path
from zipfile import ZipFile

from openpyxl import load_workbook

from app.services.sources import shared_storage

MAX_BYTES = 40 * 1024 * 1024
TOKEN_TTL = 300
_LOCK = threading.RLock()
_PENDING = {}


def _source(input_dir, name):
    root = Path(input_dir).resolve(strict=True)
    if not isinstance(name, str) or not name or name in {'.', '..'} or '/' in name or '\\' in name or ':' in name:
        raise ValueError('Source must be an exact listed basename.')
    path = root / name
    if path.is_symlink() or path.resolve(strict=True).parent != root or not path.is_file():
        raise ValueError('Source must be a regular file in the input directory.')
    if name not in {p.name for p in root.iterdir()} or path.suffix.lower() not in {'.xlsx', '.csv'}:
        raise ValueError('Only listed XLSX and CSV sources can be updated.')
    return root, path


def _read(path):
    with path.open('rb') as stream:
        data = stream.read(MAX_BYTES + 1)
    if len(data) > MAX_BYTES:
        raise ValueError('Source exceeds the 40 MB limit.')
    return data


def _formula(value):
    return isinstance(value, str) and value.lstrip().startswith(('=', '+', '-', '@'))


def _scalar(value):
    if value is not None and not isinstance(value, (str, bool, int, float, date, datetime)):
        raise ValueError('Only scalar cell values are supported.')
    if isinstance(value, float) and not math.isfinite(value):
        raise ValueError('Non-finite numbers are not supported.')
    if isinstance(value, str) and (len(value) > 32767 or any(ord(c) < 32 and c not in '\t\n\r' for c in value)):
        raise ValueError('Invalid cell text.')
    if _formula(value):
        raise ValueError('Formula-like values cannot be updated.')


def _kind(value):
    if value is None or value == '':
        return None
    if isinstance(value, bool):
        return 'boolean'
    if isinstance(value, (int, float)):
        return 'number'
    if isinstance(value, (date, datetime)):
        return 'date'
    return 'text'


def _table(data, suffix):
    if suffix == '.xlsx':
        with ZipFile(io.BytesIO(data)) as archive:
            if sum(item.file_size for item in archive.infolist()) > 200 * 1024 * 1024:
                raise ValueError('Expanded workbook is too large.')
        book = load_workbook(io.BytesIO(data), data_only=False)
        sheet = book.worksheets[0]
        rows = list(sheet.values)
        return rows, book, sheet, None
    text = data.decode('utf-8-sig')
    try:
        dialect = csv.Sniffer().sniff(text[:8192], delimiters=',;\t|')
    except csv.Error:
        dialect = csv.excel
    rows = list(csv.reader(io.StringIO(text, newline=''), dialect))
    return rows, None, None, (dialect, data.startswith(b'\xef\xbb\xbf'))


def _prepare(data, suffix, key_column, key_value, column, value):
    _scalar(key_value)
    _scalar(value)
    if not isinstance(key_column, str) or not isinstance(column, str) or column == key_column:
        raise ValueError('A distinct non-key column is required.')
    rows, book, sheet, dialect = _table(data, suffix)
    try:
        if not rows:
            raise ValueError('Source has no header.')
        headers = list(rows[0])
        if any(not isinstance(h, str) or not h.strip() for h in headers) or len(set(h.strip().casefold() for h in headers)) != len(headers):
            raise ValueError('Source has invalid or duplicate headers.')
        if key_column not in headers or column not in headers:
            raise ValueError('Column not found.')
        ki, ci = headers.index(key_column), headers.index(column)
        if any(len(row) != len(headers) for row in rows):
            raise ValueError('Source has inconsistent row widths.')
        matches = [i for i, row in enumerate(rows[1:], 1) if row[ki] == key_value and type(row[ki]) is type(key_value)]
        if len(matches) != 1:
            raise ValueError('Key must match exactly one row.')
        ri = matches[0]
        old = rows[ri][ci]
        if _formula(old):
            raise ValueError('Existing formulas cannot be overwritten.')
        if sheet is not None:
            for merged in sheet.merged_cells.ranges:
                if any((ri + 1, col + 1) in merged.cells for col in (ki, ci)):
                    raise ValueError('Merged cells cannot be updated.')
            old_kind = _kind(old)
            expected = old_kind or next((_kind(row[ci]) for row in rows[1:] if _kind(row[ci])), None)
            if value is not None and value != '' and expected and _kind(value) != expected:
                raise ValueError('Replacement type does not match the source column.')
        elif value is not None and not isinstance(value, str):
            raise ValueError('CSV replacements must be strings or null.')
        return rows, book, sheet, dialect, ri, ci, old
    except Exception:
        if book is not None:
            book.close()
        raise


def _public(value):
    return value.isoformat() if isinstance(value, (date, datetime)) else value


def propose_update(input_dir, source_name, key_column, key_value, column, value):
    """Validate one edit and return a one-use token; never alter source content."""
    with _LOCK:
        now = time.monotonic()
        for token in list(_PENDING):
            if _PENDING[token]['expires'] <= now:
                del _PENDING[token]
        if len(_PENDING) >= 1000:
            raise ValueError('Too many pending updates; retry after tokens expire.')
        root, path = _source(input_dir, source_name)
        shared = shared_storage.is_enabled()
        # Shared content is an immutable remote snapshot, never the mutable cache.
        data = shared_storage.read_bytes(path) if shared else _read(path)
        if len(data) > MAX_BYTES:
            raise ValueError('Source exceeds the 40 MB limit.')
        prepared = _prepare(data, path.suffix.lower(), key_column, key_value, column, value)
        old = prepared[-1]
        if prepared[1] is not None:
            prepared[1].close()
        token = secrets.token_urlsafe(32)
        _PENDING[token] = dict(root=str(root), name=source_name, digest=hashlib.sha256(data).digest(),
                               key_column=key_column, key_value=key_value, column=column, value=value,
                               expires=now + TOKEN_TTL, shared=shared)
        return {'status': 'confirmation_required', 'token': token, 'preview': {
            'source': source_name, 'key_column': key_column, 'key_value': _public(key_value),
            'column': column, 'old_value': _public(old), 'new_value': _public(value)}}


def confirm_update(input_dir, token):
    """Consume a root-bound token, back up the original, then atomically replace it."""
    with _LOCK:
        if not isinstance(token, str):
            raise ValueError('Invalid confirmation token.')
        proposal = _PENDING.get(token)
        if proposal is None:
            raise ValueError('Invalid or consumed confirmation token.')
        root, path = _source(input_dir, proposal['name'])
        if str(root) != proposal['root']:
            raise ValueError('Confirmation token belongs to another input directory.')
        del _PENDING[token]
        if time.monotonic() >= proposal['expires']:
            raise ValueError('Confirmation token expired.')
        shared = shared_storage.is_enabled()
        if shared != proposal.get('shared', False):
            raise ValueError('Storage mode changed; request a fresh preview.')
        if not shared:
            return _apply_update(root, path, proposal, False, {})
        # No lease/expiry: an old in-flight writer must never outlive its lock.
        import uuid
        owner = str(uuid.uuid4())
        key = shared_storage.object_key(path)
        payload = {'p_object_key': key, 'p_owner_token': owner}
        if shared_storage.rpc('acquire_source_update_lock', payload) is not True:
            raise ValueError('Source is locked by another update; retry later.')
        state = {'uncertain': False}
        try:
            # Fresh remote bytes are read only AFTER acquiring the distributed lock.
            data = shared_storage.read_bytes(path)
            return _apply_update(root, path, proposal, True, state, original_data=data)
        finally:
            if not state['uncertain']:
                if shared_storage.rpc('release_source_update_lock', payload) is not True:
                    raise RuntimeError('Shared source lock release was not confirmed; administrator recovery required.')


def _apply_update(root, path, proposal, shared, state, original_data=None):
    """Write under the process lock and, in shared mode, the durable remote lock."""
    data = original_data if shared else _read(path)
    if data is None or len(data) > MAX_BYTES:
        raise ValueError('Source exceeds the 40 MB limit or remote snapshot is missing.')
    if hashlib.sha256(data).digest() != proposal['digest']:
        raise ValueError('Source changed; request a fresh preview.')
    rows, book, sheet, dialect, ri, ci, old = _prepare(data, path.suffix.lower(), proposal['key_column'], proposal['key_value'], proposal['column'], proposal['value'])
    temp = root / ('.source-update-' + secrets.token_hex(16) + '.tmp')
    backup_root = root.parent / 'backups' if shared else root
    if shared:
        if backup_root.is_symlink() or backup_root.resolve().parent != root.parent:
            if book is not None:
                book.close()
            raise ValueError('Backup directory must be inside the project.')
        backup_root.mkdir(parents=True, exist_ok=True)
    backup = backup_root / (path.name + '.backup-' + secrets.token_hex(16))
    try:
        # Exclusive names prevent overwriting either another backup or a temporary file.
        with backup.open('xb') as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        with temp.open('xb') as stream:
            if book is not None:
                sheet.cell(ri + 1, ci + 1).value = proposal['value']
                book.save(stream)
            else:
                rows[ri][ci] = proposal['value']
                output = io.StringIO(newline='')
                csv.writer(output, dialect[0]).writerows(rows)
                stream.write(output.getvalue().encode('utf-8-sig' if dialect[1] else 'utf-8'))
            stream.flush()
            os.fsync(stream.fileno())
        _, current = _source(root, path.name)
        if not shared and hashlib.sha256(_read(current)).digest() != proposal['digest']:
            raise ValueError('Source changed; request a fresh preview.')
        if shared:
            # A timed-out write may still finish remotely: retain the durable lock.
            state['uncertain'] = True
            shared_storage.upload_file(backup, overwrite=False)
            if shared_storage.read_bytes(backup) != data:
                raise RuntimeError('Shared backup could not be verified; administrator recovery required.')
            changed = _read(temp)
            shared_storage.upload_bytes(path, changed, overwrite=True)
            if shared_storage.read_bytes(path) != changed:
                raise RuntimeError('Shared source write could not be verified; administrator recovery required.')
            state['uncertain'] = False
        os.replace(temp, path)
        return {'status': 'updated', 'source': path.name, 'backup': backup.name}
    finally:
        if book is not None:
            book.close()
        if temp.exists():
            temp.unlink()
