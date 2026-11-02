"""
Excel Reader Service - Đọc file Excel/CSV an toàn với kiểm tra đầu vào.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

import pandas as pd

logger = logging.getLogger(__name__)

SUPPORTED_EXTENSIONS = {".xlsx", ".xls", ".csv"}
MAX_FILE_SIZE_MB = 100


def _validate_file(file_path: Path) -> None:
    """Kiểm tra file trước khi đọc. Raise ValueError nếu không hợp lệ."""
    if not file_path.exists():
        raise FileNotFoundError(f"File không tồn tại: {file_path}")

    if not file_path.is_file():
        raise ValueError(f"Đường dẫn không phải file: {file_path}")

    if file_path.suffix.lower() not in SUPPORTED_EXTENSIONS:
        raise ValueError(
            f"Định dạng không hỗ trợ: '{file_path.suffix}'. "
            f"Chỉ chấp nhận: {', '.join(SUPPORTED_EXTENSIONS)}"
        )

    size_mb = file_path.stat().st_size / (1024 * 1024)
    if size_mb > MAX_FILE_SIZE_MB:
        raise ValueError(
            f"File quá lớn: {size_mb:.1f}MB (giới hạn {MAX_FILE_SIZE_MB}MB)."
        )


def read_excel(
    file_path: str | Path,
    sheet_name: str | int | None = 0,
    header_row: int = 0,
) -> pd.DataFrame:
    """
    Đọc file Excel hoặc CSV, trả về DataFrame.

    Args:
        file_path: Đường dẫn file.
        sheet_name: Tên hoặc index của sheet (mặc định sheet đầu tiên).
        header_row: Dòng tiêu đề (0-indexed).

    Returns:
        DataFrame chứa dữ liệu.

    Raises:
        FileNotFoundError: Nếu file không tồn tại.
        ValueError: Nếu file không hợp lệ.
    """
    path = Path(file_path)
    _validate_file(path)

    logger.info("Đọc file: %s", path)

    try:
        if path.suffix.lower() == ".csv":
            df = pd.read_csv(path, header=header_row, encoding="utf-8-sig")
        else:
            df = pd.read_excel(path, sheet_name=sheet_name, header=header_row)

        logger.info("  → %d dòng × %d cột", len(df), len(df.columns))
        return df

    except Exception as exc:
        logger.error("Lỗi đọc file %s: %s", path, exc)
        raise ValueError(f"Không thể đọc file '{path.name}': {exc}") from exc


def read_all_sheets(file_path: str | Path) -> dict[str, pd.DataFrame]:
    """Đọc tất cả sheet trong file Excel."""
    path = Path(file_path)
    _validate_file(path)

    if path.suffix.lower() == ".csv":
        return {"Sheet1": pd.read_csv(path, encoding="utf-8-sig")}

    try:
        sheets = pd.read_excel(path, sheet_name=None)
        logger.info("File %s có %d sheet(s)", path.name, len(sheets))
        return sheets
    except Exception as exc:
        raise ValueError(f"Không thể đọc '{path.name}': {exc}") from exc


def get_column_info(df: pd.DataFrame) -> dict[str, str]:
    """Trả về mapping tên cột → kiểu dữ liệu."""
    return {col: str(dtype) for col, dtype in df.dtypes.items()}

