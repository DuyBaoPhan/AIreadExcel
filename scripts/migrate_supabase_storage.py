"""Explicit non-destructive migration; dry run by default, no remote overwrite."""
from __future__ import annotations

import argparse
import hashlib
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "excel_rule_engine"))
from app.paths import PROJECTS_DIR
from app.services.sources import file_manager, shared_storage


def inventory(project):
    """Read only original project folders, never the disposable shared cache."""
    if not project or project in {".", ".."} or any(c in project for c in "/\\:\r\n"):
        raise ValueError("Invalid project name.")
    root = PROJECTS_DIR / project
    if root.is_symlink() or not root.resolve().is_relative_to(PROJECTS_DIR.resolve()):
        raise ValueError("Invalid project path.")
    result = []
    for folder in ("input", "output", "backups"):
        directory = root / folder
        if directory.is_symlink():
            raise ValueError("Symlink migration directories are not allowed.")
        if not directory.exists():
            continue
        for path in sorted(directory.iterdir()):
            if path.is_symlink():
                raise ValueError("Symlink migration files are not allowed.")
            if not path.is_file() or path.name.startswith((".", "~$")):
                continue
            backup = ".backup-" in path.name and Path(path.name.split(".backup-", 1)[0]).suffix.lower() in {".xlsx", ".xls", ".csv"}
            if path.suffix.lower() in {".xlsx", ".xls", ".csv"} or backup:
                result.append((path, "backups" if backup else folder))
    return result


def migrate(project, apply=False):
    items = inventory(project)
    print("APPLY (no overwrite)" if apply else "DRY RUN: no network or file changes")
    for path, folder in items:
        print(f"{path.name} -> projects/{project}/{folder}/{path.name}")
    print(f"Files: {len(items)}")
    if not apply:
        return 0
    if not shared_storage.is_enabled():
        raise ValueError("Set FILE_STORAGE_BACKEND=supabase before applying migration.")
    cache_root = file_manager.get_projects_root()
    remote_names = {}
    failed = False
    for path, folder in items:
        destination = cache_root / project / folder / path.name
        if folder not in remote_names:
            remote_names[folder] = set(shared_storage.list_objects(destination.parent))
        raw = path.read_bytes()
        if path.name not in remote_names[folder]:
            try:
                shared_storage.upload_bytes(destination, raw, overwrite=False)
            except FileExistsError:
                pass  # Another migration created it; compare bytes, never overwrite.
        remote = shared_storage.read_bytes(destination)
        if hashlib.sha256(remote).digest() != hashlib.sha256(raw).digest():
            print(f"CONFLICT: {folder}/{path.name}; remote preserved, no overwrite")
            failed = True
        else:
            print(f"VERIFIED: {folder}/{path.name}")
        remote_names[folder].add(path.name)
    return 1 if failed else 0


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", default="demo_project")
    parser.add_argument("--apply", action="store_true", help="Upload and verify; never overwrite remote files")
    args = parser.parse_args()
    from app.services.runtime.environment import load_environment
    load_environment()
    try:
        return migrate(args.project, args.apply)
    except (ValueError, OSError):
        # Do not print arbitrary provider responses or environment values.
        print("Migration stopped. Check configuration, permissions, and connectivity; originals are unchanged.", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
