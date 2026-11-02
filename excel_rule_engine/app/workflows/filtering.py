"""
Filtering Workflow - Lọc dữ liệu theo điều kiện từ câu lệnh người dùng.
"""

from __future__ import annotations

import logging
import operator as op_module
from pathlib import Path
from typing import Any

import pandas as pd

from app.services.excel_reader import read_excel
from app.services.excel_writer import write_excel, generate_timestamped_name
from app.services.file_manager import list_excel_files, safe_output_path

logger = logging.getLogger(__name__)

# Toán tử hợp lệ (whitelist)
ALLOWED_OPERATORS: dict[str, Any] = {
    ">": op_module.gt,
    "<": op_module.lt,
    ">=": op_module.ge,
    "<=": op_module.le,
    "==": op_module.eq,
    "!=": op_module.ne,
}


def _find_column(df: pd.DataFrame, canonical_col: str) -> str | None:
    """
    Tìm cột trong DataFrame theo tên chuẩn (case-insensitive, partial match).
    """
    lower_map = {c.lower().replace(" ", "_"): c for c in df.columns}

    # Exact match (normalized)
    key = canonical_col.lower().replace(" ", "_")
    if key in lower_map:
        return lower_map[key]

    # Partial match
    for col_key, col_real in lower_map.items():
        if canonical_col.lower() in col_key or col_key in canonical_col.lower():
            return col_real

    return None


def _apply_filter(
    df: pd.DataFrame,
    column: str,
    operator: str,
    value: Any,
) -> pd.DataFrame:
    """Áp dụng điều kiện lọc an toàn."""
    if operator not in ALLOWED_OPERATORS:
        raise ValueError(f"Toán tử không hợp lệ: '{operator}'")

    fn = ALLOWED_OPERATORS[operator]

    # Kiểm tra kiểu dữ liệu
    col_dtype = df[column].dtype

    if pd.api.types.is_numeric_dtype(col_dtype):
        try:
            value = float(value)
        except (TypeError, ValueError):
            raise ValueError(
                f"Cột '{column}' là kiểu số, nhưng giá trị '{value}' không phải số."
            )
        mask = fn(df[column], value)
    else:
        # Chuỗi: chuyển về lowercase để so sánh
        col_lower = df[column].astype(str).str.lower()
        val_lower = str(value).lower()
        if operator in ("==", "!="):
            mask = col_lower == val_lower if operator == "==" else col_lower != val_lower
        else:
            raise ValueError(
                f"Toán tử '{operator}' không hợp lệ cho cột kiểu chuỗi '{column}'. "
                "Dùng 'bằng' hoặc 'khác'."
            )

    return df[mask].copy()


def run_filter(
    input_dir: Path,
    project_name: str,
    column: str,
    operator: str,
    value: Any,
    source_files: list[str] | None = None,
) -> dict[str, Any]:
    """
    Lọc dữ liệu từ file Excel.

    Returns:
        dict chứa: filtered_rows, output_path, column_used, warnings.
    """
    warnings: list[str] = []

    # Lấy file
    if source_files:
        files = [input_dir / f for f in source_files if (input_dir / f).exists()]
    else:
        files = list_excel_files(input_dir)

    if not files:
        raise FileNotFoundError(
            f"Không tìm thấy file Excel nào trong '{input_dir}'."
        )

    # Lấy file: Ưu tiên lọc trên những file thực sự có chứa cột cần tìm
    frames: list[pd.DataFrame] = []
    for fpath in files:
        try:
            df = read_excel(fpath)
            # Kiểm tra xem file này có cột đang cần lọc không
            if _find_column(df, column) is not None:
                df["source_file"] = fpath.name
                frames.append(df)
        except Exception as exc:
            warnings.append(f"Bỏ qua '{fpath.name}': {exc}")

    # Nếu không file nào chứa cột, fallback đọc tất cả
    if not frames:
        for fpath in files:
            try:
                df = read_excel(fpath)
                df["source_file"] = fpath.name
                frames.append(df)
            except Exception:
                pass

    if not frames:
        raise ValueError("Không đọc được file nào.")

    combined = pd.concat(frames, ignore_index=True, sort=False)

    # Tìm cột
    real_col = _find_column(combined, column)
    if real_col is None:
        available = ", ".join(f"'{c}'" for c in combined.columns)
        raise ValueError(
            f"Không tìm thấy cột '{column}' trong dữ liệu.\n"
            f"Các cột hiện có: {available}"
        )

    logger.info(
        "Filter: column=%r op=%r value=%r", real_col, operator, value
    )

    # Áp dụng lọc
    result = _apply_filter(combined, real_col, operator, value)

    if result.empty:
        warnings.append("Không có bản ghi nào khớp điều kiện lọc.")

    # Xuất file
    out_name = generate_timestamped_name("Filtered_Result")
    out_path = safe_output_path(project_name, out_name)
    write_excel(result, out_path, sheet_name="Filtered")

    return {
        "filtered_rows": len(result),
        "output_path": str(out_path),
        "column_used": real_col,
        "warnings": warnings,
    }

