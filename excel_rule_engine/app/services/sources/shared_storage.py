"""Private shared object storage with a disposable, project-scoped local cache.

Local mode performs no network requests. Supabase errors deliberately never include
response bodies, URLs, credentials, or the underlying requests exception.
"""
from __future__ import annotations

import os
from pathlib import Path
import tempfile
from urllib.parse import quote, urlsplit

import requests


class StorageError(ValueError):
    """A safe-to-display shared storage failure."""


def _config():
    backend = os.environ.get("FILE_STORAGE_BACKEND", "local").strip().lower()
    if backend == "local":
        return None
    if backend != "supabase":
        raise StorageError("Unsupported file storage backend.")
    url = os.environ.get("SUPABASE_URL", "").strip().rstrip("/")
    key = os.environ.get("SUPABASE_SECRET_KEY", "").strip() or os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "").strip()
    bucket = os.environ.get("SUPABASE_STORAGE_BUCKET", "").strip()
    try:
        parsed = urlsplit(url)
    except ValueError:
        raise StorageError("Shared storage configuration is incomplete or invalid.") from None
    if (parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password
            or parsed.query or parsed.fragment or parsed.path not in ("", "/")
            or not key or not bucket or any(c in bucket for c in "/\\:\r\n")):
        raise StorageError("Shared storage configuration is incomplete or invalid.")
    return url, key, bucket


def config():
    """Return validated (URL, credential, bucket), or None for local mode.

    Server-side callers must never log or expose this tuple.
    """
    return _config()


def is_enabled() -> bool:
    return _config() is not None


def _part(value: str) -> bool:
    return bool(value) and value not in (".", "..") and not any(c in value for c in '/\\:\x00\r\n') and not value.endswith((" ", "."))


def _relative(path: str | Path, *, folder=False):
    from app.services.sources.file_manager import get_projects_root
    root = get_projects_root().absolute()
    candidate = Path(path).absolute()
    try:
        relative = candidate.relative_to(root)
    except ValueError:
        raise StorageError("Storage path is outside the projects directory.") from None
    parts = relative.parts
    if len(parts) != (2 if folder else 3) or not all(_part(p) for p in parts) or parts[1] not in {"input", "output", "backups"}:
        raise StorageError("Invalid project storage path.")
    current = root
    if current.is_symlink():
        raise StorageError("Symlink storage paths are not supported.")
    for part in parts:
        current = current / part
        if current.is_symlink():
            raise StorageError("Symlink storage paths are not supported.")
    if not candidate.resolve().is_relative_to(root.resolve()):
        raise StorageError("Storage path is outside the projects directory.")
    return candidate, "projects/" + "/".join(parts)


def object_key(path: str | Path) -> str:
    return _relative(path)[1]


def _request(method, suffix, **kwargs):
    config = _config()
    if config is None:
        raise StorageError("Shared storage is not enabled.")
    url, key, bucket = config
    headers = {"apikey": key}
    if not key.startswith("sb_secret_"):
        headers["Authorization"] = "Bearer " + key
    headers.update(kwargs.pop("headers", {}))
    api = kwargs.pop("_api", "/storage/v1/")
    try:
        response = requests.request(method, url + api + suffix.format(bucket=quote(bucket, safe="")),
                                    headers=headers, timeout=(10, 60), allow_redirects=False, **kwargs)
        if response.status_code == 404 and method == "GET":
            raise FileNotFoundError("Shared storage object was not found.")
        if response.status_code == 409:
            raise FileExistsError("Shared storage object already exists.")
        if response.status_code == 400 and method == "POST" and suffix.startswith("object/"):
            try:
                conflict = response.json()
            except ValueError:
                conflict = {}
            if isinstance(conflict, dict) and (str(conflict.get("statusCode")) == "409" or conflict.get("error") == "Duplicate"):
                raise FileExistsError("Shared storage object already exists.")
        if not 200 <= response.status_code < 300:
            raise StorageError("Shared storage request failed (HTTP %s)." % response.status_code)
        return response
    except requests.RequestException:
        raise StorageError("Shared storage is unavailable; please retry.") from None


def upload_bytes(path: str | Path, raw: bytes, overwrite: bool = False) -> None:
    if not is_enabled():
        return
    key = object_key(path)
    _request("POST", "object/{bucket}/" + quote(key, safe="/"), data=raw,
             headers={"Content-Type": "application/octet-stream", "x-upsert": str(bool(overwrite)).lower()})


def upload_file(path: str | Path, overwrite: bool = False) -> None:
    if not is_enabled():
        return
    candidate, _ = _relative(path)
    upload_bytes(candidate, candidate.read_bytes(), overwrite=overwrite)


def read_bytes(path: str | Path) -> bytes:
    """Read authoritative object bytes without changing the local cache."""
    if not is_enabled():
        return Path(path).read_bytes()
    candidate, _ = _relative(path)
    return _download(candidate)


def _download(path: Path) -> bytes:
    return _request("GET", "object/authenticated/{bucket}/" + quote(object_key(path), safe="/")).content


def _stage(path: Path, raw: bytes) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, name = tempfile.mkstemp(prefix=".storage-", dir=path.parent)
    staged = Path(name)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(raw)
            stream.flush()
            os.fsync(stream.fileno())
    except BaseException:
        staged.unlink(missing_ok=True)
        raise
    return staged


def download_file(path: str | Path) -> Path:
    if not is_enabled():
        return Path(path)
    candidate, _ = _relative(path)
    staged = _stage(candidate, _download(candidate))
    try:
        os.replace(staged, candidate)
    finally:
        staged.unlink(missing_ok=True)
    return candidate


def list_objects(folder: str | Path) -> list[str]:
    """List every direct object in a project folder (including all REST pages)."""
    _, prefix = _relative(folder, folder=True)
    names = []
    offset = 0
    limit = 100
    while True:
        response = _request("POST", "object/list/{bucket}", json={"prefix": prefix, "limit": limit,
                            "offset": offset, "sortBy": {"column": "name", "order": "asc"}})
        try:
            page = response.json()
        except ValueError:
            raise StorageError("Invalid shared storage listing.") from None
        if not isinstance(page, list) or len(page) > limit:
            raise StorageError("Invalid shared storage listing.")
        for item in page:
            if not isinstance(item, dict) or not isinstance(item.get("name"), str) or not _part(item["name"]):
                raise StorageError("Invalid shared storage object name.")
            if item.get("id") is not None:  # Supabase directory placeholders have no object ID.
                if item["name"] in names:
                    raise StorageError("Inconsistent shared storage listing.")
                names.append(item["name"])
        if len(page) < limit:
            return names
        offset += limit


def sync_folder(folder: str | Path) -> None:
    """Refresh supported source cache from remote; never publish local inputs."""
    if not is_enabled():
        return
    from app.services.sources.file_manager import SUPPORTED_EXTENSIONS
    candidate, _ = _relative(folder, folder=True)
    names = {name for name in list_objects(candidate)
             if Path(name).suffix.lower() in SUPPORTED_EXTENSIONS and not name.startswith("~$")}
    staged = []
    try:
        # Fetch everything before modifying/removing cache files. Any error propagates.
        for name in sorted(names):
            target, _ = _relative(candidate / name)
            staged.append((target, _stage(target, _download(target))))
        candidate.mkdir(parents=True, exist_ok=True)
        for target, temp in staged:
            _relative(target)
            os.replace(temp, target)
        for local in candidate.iterdir() if candidate.name == "input" else ():
            if local.suffix.lower() in SUPPORTED_EXTENSIONS and not local.name.startswith("~$") and local.name not in names:
                _relative(local)
                if local.is_file():
                    local.unlink()
    finally:
        for _, temp in staged:
            temp.unlink(missing_ok=True)


def rpc(name: str, payload: dict) -> bool:
    """Call one of the two server-side lock RPCs with strict boolean results."""
    if name not in {"acquire_source_update_lock", "release_source_update_lock"}:
        raise StorageError("Unsupported shared storage RPC.")
    response = _request("POST", name, _api="/rest/v1/rpc/", json=payload)
    try:
        value = response.json()
    except ValueError:
        raise StorageError("Invalid shared storage lock response.") from None
    if not isinstance(value, bool):
        raise StorageError("Invalid shared storage lock response.")
    return value
