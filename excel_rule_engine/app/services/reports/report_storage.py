"""Persist report outputs before acknowledging success in shared-storage mode."""
from pathlib import Path

from app.services.runtime.environment import load_environment
load_environment()

from app.services.sources import shared_storage


def upload_report(path: str | Path) -> Path:
    """Upload a completed output without replacing another user's report."""
    path = Path(path)
    if shared_storage.is_enabled():
        shared_storage.upload_file(path, overwrite=False)
    return path


def save_workbook(workbook, path: str | Path) -> Path:
    """Keep local defaults; shared outputs use exclusive create and remote insert."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if shared_storage.is_enabled():
        # Never truncate a local report before discovering a naming collision.
        with path.open('xb') as stream:
            workbook.save(stream)
        upload_report(path)
    else:
        workbook.save(path)
    return path


def persist_wizard_report(data: bytes, filename: str, project: str = 'demo_project') -> str:
    """Publish wizard outputs only in shared mode; local uploads stay session-only."""
    if not shared_storage.is_enabled():
        return filename
    from uuid import uuid4
    from app.services.sources.file_manager import safe_output_path
    name = Path(filename)
    for _ in range(10):
        candidate = safe_output_path(project, f'{name.stem}_{uuid4().hex[:12]}{name.suffix}')
        try:
            with candidate.open('xb') as stream:
                stream.write(data)
            upload_report(candidate)
        except FileExistsError:
            continue
        return candidate.name
    raise ValueError('Could not reserve a unique report name; please retry.')
