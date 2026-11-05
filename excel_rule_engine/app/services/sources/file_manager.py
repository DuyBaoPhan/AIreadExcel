"""
File Manager Service - Quản lý file trong phạm vi project.
Giới hạn truy cập chỉ trong thư mục project để đảm bảo an toàn.
"""

from __future__ import annotations

from app.paths import PROJECTS_DIR

import logging
import os
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

SUPPORTED_EXTENSIONS = {".xlsx", ".xls", ".csv"}

# Thư mục gốc của tất cả project
_PROJECTS_ROOT: Path | None = None


def set_projects_root(root: str | Path) -> None:
    """Đặt thư mục gốc cho tất cả project."""
    global _PROJECTS_ROOT
    _PROJECTS_ROOT = Path(root).resolve()
    logger.info("Projects root: %s", _PROJECTS_ROOT)


def get_local_projects_root() -> Path:
    """Original local files, kept separate from the disposable shared cache."""
    if _PROJECTS_ROOT is None:
        # Default: thư mục 'projects' nằm cùng cấp với app/
        return PROJECTS_DIR
    return _PROJECTS_ROOT


def get_projects_root() -> Path:
    from app.services.sources.shared_storage import is_enabled
    root = get_local_projects_root()
    if is_enabled():
        root = root / ".shared-cache"
    if any(node.is_symlink() for node in (root, *root.parents)):
        raise ValueError("Symlink project paths are not supported.")
    root.mkdir(parents=True, exist_ok=True)
    return root


def _safe_resolve(base: Path, *parts: str) -> Path:
    """
    Tạo đường dẫn an toàn, đảm bảo kết quả nằm trong base.
    Raise ValueError nếu path traversal được phát hiện.
    """
    unresolved = base / Path(*parts)
    for node in (unresolved, *unresolved.parents):
        if node.is_symlink():
            raise ValueError("Symlink project paths are not supported.")
        if node == base:
            break
    candidate = unresolved.resolve()
    if not candidate.is_relative_to(base.resolve()):
        raise ValueError(
            f"Path traversal bị phát hiện: '{candidate}' nằm ngoài '{base}'."
        )
    return candidate


def get_project_dir(project_name: str = "demo_project") -> Path:
    if not project_name or project_name in {".", ".."} or any(c in project_name for c in "/\\:\x00"):
        raise ValueError("Invalid project name.")
    root = get_projects_root()
    return _safe_resolve(root, project_name)


def get_input_dir(project_name: str = "demo_project") -> Path:
    project = get_project_dir(project_name)
    d = _safe_resolve(project, "input")
    from app.services.sources.shared_storage import sync_folder
    sync_folder(d)
    d.mkdir(parents=True, exist_ok=True)
    return d


def get_output_dir(project_name: str = "demo_project") -> Path:
    project = get_project_dir(project_name)
    d = _safe_resolve(project, "output")
    d.mkdir(parents=True, exist_ok=True)
    return d


def list_excel_files(
    folder: str | Path,
    extensions: set[str] | None = None,
) -> list[Path]:
    """Liệt kê tất cả file Excel trong thư mục (không đệ quy)."""
    exts = extensions or SUPPORTED_EXTENSIONS
    folder_path = Path(folder)

    if not folder_path.exists():
        logger.warning("Thư mục không tồn tại: %s", folder_path)
        return []

    files = [
        f for f in sorted(folder_path.iterdir())
        if f.is_file() and f.suffix.lower() in exts and not f.name.startswith("~$")
    ]
    logger.info("Tìm thấy %d file Excel trong %s", len(files), folder_path)
    return files


def file_info(file_path: str | Path) -> dict[str, str]:
    """Trả về thông tin cơ bản về file."""
    p = Path(file_path)
    if not p.exists():
        return {"error": f"File không tồn tại: {p}"}

    size_kb = p.stat().st_size / 1024
    return {
        "name": p.name,
        "extension": p.suffix,
        "size": f"{size_kb:.1f} KB",
        "path": str(p),
    }


def check_file_exists(file_path: str | Path) -> bool:
    return Path(file_path).exists()


def safe_output_path(
    project_name: str,
    filename: str,
) -> Path:
    """
    Tạo đường dẫn output an toàn trong phạm vi project.
    Đảm bảo file không bị ghi vào thư mục input (file gốc).
    """
    output_dir = get_output_dir(project_name)
    return _safe_resolve(output_dir, filename)

