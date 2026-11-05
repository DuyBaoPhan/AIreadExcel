"""Bounded short-lived approval snapshots: confirming never asks AI to re-plan."""
from collections import OrderedDict
from copy import deepcopy
import hashlib
from pathlib import Path
from threading import Lock
from time import monotonic

_CACHE = OrderedDict()
_LOCK = Lock()
TTL = 900
LIMIT = 128


def remember(input_dir, text, plan, snapshots):
    entry = (monotonic(), str(Path(input_dir).resolve()), text, deepcopy(plan),
             hashlib.sha256(snapshots[plan['source']]).digest())
    with _LOCK:
        _CACHE[plan['fingerprint']] = entry
        _CACHE.move_to_end(plan['fingerprint'])
        while len(_CACHE) > LIMIT:
            _CACHE.popitem(last=False)


def approved(input_dir, text, source_name, fingerprint, snapshots):
    if not isinstance(fingerprint, str):
        raise ValueError('Fingerprint khong hop le.')
    with _LOCK:
        entry = _CACHE.get(fingerprint)
    if entry is None:
        return None
    created, root, request, plan, digest = entry
    if monotonic() - created > TTL:
        with _LOCK:
            _CACHE.pop(fingerprint, None)
        raise ValueError('Ke hoach AI da het han; vui long phan tich lai.')
    if root != str(Path(input_dir).resolve()) or request != text or (source_name is not None and source_name != plan['source']):
        raise ValueError('Ke hoach khong khop yeu cau da xac nhan.')
    raw = snapshots.get(plan['source'])
    if raw is None or hashlib.sha256(raw).digest() != digest:
        raise ValueError('Du lieu da thay doi; vui long phan tich lai.')
    return deepcopy(plan)
