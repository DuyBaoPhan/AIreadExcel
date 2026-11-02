"""
Comparison Workflow - So sánh Root vs Update file, phân loại Added/Updated/Unchanged.
Không tự suy đoán Primary Key – yêu cầu người dùng xác nhận.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import pandas as pd

from app.services.excel_reader import read_excel
from app.services.excel_writer import write_comparison_excel, generate_timestamped_name
from app.services.file_manager import list_excel_files, safe_output_path

logger = logging.getLogger(__name__)


def _detect_possible_primary_keys(df: pd.DataFrame) -> list[str]:
    """Gợi ý các cột có thể làm Primary Key (unique, không null)."""
    candidates = []
    for col in df.columns:
        if df[col].nunique() == len(df) and df[col].notna().all():
            candidates.append(col)
    return candidates


def run_comparison(
    input_dir: Path,
    project_name: str,
    primary_key: str,
    root_file: str | None = None,
    update_file: str | None = None,
    treat_as_full_snapshot: bool = False,
) -> dict[str, Any]:
    """
    So sánh Root và Update file.

    Args:
        input_dir: Thư mục chứa file.
        project_name: Tên project.
        primary_key: Cột dùng làm khóa chính.
        root_file: Tên file Root (nếu None → tìm file có 'root' trong tên).
        update_file: Tên file Update (nếu None → tìm file có 'update' trong tên).
        treat_as_full_snapshot: Nếu True → phân loại Deleted (yêu cầu xác nhận từ người dùng).

    Returns:
        dict chứa: added, updated, unchanged, [deleted], output_path, suggestions.
    """
    warnings: list[str] = []

    # 1. Xác định file Root và Update
    all_files = list_excel_files(input_dir)
    all_names = {f.name.lower(): f for f in all_files}

    if root_file:
        root_path = input_dir / root_file
    else:
        # Tìm file có 'root' trong tên
        root_path = next(
            (f for name, f in all_names.items() if "root" in name), None
        )

    if update_file:
        update_path = input_dir / update_file
    else:
        update_path = next(
            (f for name, f in all_names.items() if "update" in name), None
        )

    if root_path is None:
        raise FileNotFoundError(
            "Không tìm thấy file Root. Vui lòng đặt file có 'root' trong tên vào thư mục input, "
            "hoặc chỉ định tên file cụ thể."
        )
    if update_path is None:
        raise FileNotFoundError(
            "Không tìm thấy file Update. Vui lòng đặt file có 'update' trong tên vào thư mục input, "
            "hoặc chỉ định tên file cụ thể."
        )

    logger.info("Comparison: root=%s update=%s key=%s", root_path.name, update_path.name, primary_key)

    # 2. Đọc dữ liệu
    df_root = read_excel(root_path)
    df_update = read_excel(update_path)

    # 3. Kiểm tra primary key tồn tại
    def _find_pk_col(df: pd.DataFrame, pk: str) -> str:
        lower_map = {c.lower().replace(" ", "_"): c for c in df.columns}
        key = pk.lower().replace(" ", "_")
        if key in lower_map:
            return lower_map[key]
        for k, v in lower_map.items():
            if pk.lower() in k or k in pk.lower():
                return v
        return None

    pk_root = _find_pk_col(df_root, primary_key)
    pk_update = _find_pk_col(df_update, primary_key)

    if pk_root is None:
        suggestions_root = _detect_possible_primary_keys(df_root)
        raise ValueError(
            f"Không tìm thấy cột '{primary_key}' trong file Root.\n"
            f"Các cột hiện có: {list(df_root.columns)}\n"
            f"Gợi ý Primary Key: {suggestions_root}"
        )
    if pk_update is None:
        suggestions_update = _detect_possible_primary_keys(df_update)
        raise ValueError(
            f"Không tìm thấy cột '{primary_key}' trong file Update.\n"
            f"Các cột hiện có: {list(df_update.columns)}\n"
            f"Gợi ý Primary Key: {suggestions_update}"
        )

    # 4. Set index theo Primary Key
    df_root_idx = df_root.set_index(pk_root)
    df_update_idx = df_update.set_index(pk_update)

    # 5. So sánh
    root_keys = set(df_root_idx.index)
    update_keys = set(df_update_idx.index)

    # Added: có trong Update nhưng không có trong Root
    added_keys = update_keys - root_keys
    # Potential Deleted: có trong Root nhưng không có trong Update
    deleted_keys = root_keys - update_keys
    # Common: có trong cả hai
    common_keys = root_keys & update_keys

    # Kiểm tra Changed vs Unchanged trong common keys
    # Chỉ so sánh các cột chung
    common_cols = [c for c in df_root_idx.columns if c in df_update_idx.columns]

    changed_keys: set = set()
    unchanged_keys: set = set()

    for key in common_keys:
        row_root = df_root_idx.loc[key, common_cols]
        row_update = df_update_idx.loc[key, common_cols]
        # So sánh giá trị (bỏ qua NaN == NaN)
        try:
            if not row_root.equals(row_update):
                changed_keys.add(key)
            else:
                unchanged_keys.add(key)
        except Exception:
            changed_keys.add(key)

    # 6. Tạo DataFrames kết quả
    df_added = df_update.loc[df_update[pk_update].isin(added_keys)].copy() if added_keys else pd.DataFrame(columns=df_update.columns)
    df_updated_rows = df_update.loc[df_update[pk_update].isin(changed_keys)].copy() if changed_keys else pd.DataFrame(columns=df_update.columns)
    df_unchanged = df_update.loc[df_update[pk_update].isin(unchanged_keys)].copy() if unchanged_keys else pd.DataFrame(columns=df_update.columns)

    # Thêm cột change_type
    df_added["change_type"] = "Added"
    df_updated_rows["change_type"] = "Updated"
    df_unchanged["change_type"] = "Unchanged"

    # Deleted chỉ hiển thị khi người dùng xác nhận full snapshot
    df_deleted = pd.DataFrame()
    if treat_as_full_snapshot and deleted_keys:
        df_deleted = df_root.loc[df_root[pk_root].isin(deleted_keys)].copy()
        df_deleted["change_type"] = "Deleted"
        warnings.append(
            f"Phát hiện {len(deleted_keys)} bản ghi trong Root không có trong Update "
            "(được đánh dấu là Deleted)."
        )
    elif deleted_keys:
        warnings.append(
            f"Có {len(deleted_keys)} bản ghi trong Root không có trong Update. "
            "Nếu file Update là Full Snapshot, hãy xác nhận để phân loại là 'Deleted'."
        )

    # 7. Xuất Change Log
    out_name = generate_timestamped_name("Change_Log")
    out_path = safe_output_path(project_name, out_name)
    write_comparison_excel(df_added, df_updated_rows, df_unchanged, out_path)

    return {
        "added": len(df_added),
        "updated": len(df_updated_rows),
        "unchanged": len(df_unchanged),
        "deleted": len(df_deleted),
        "output_path": str(out_path),
        "warnings": warnings,
        "root_file": root_path.name,
        "update_file": update_path.name,
    }


def get_primary_key_suggestions(
    input_dir: Path,
    file_name: str | None = None,
) -> list[str]:
    """Trả về danh sách gợi ý Primary Key từ file."""
    all_files = list_excel_files(input_dir)
    if not all_files:
        return []

    target = None
    if file_name:
        target = next((f for f in all_files if f.name.lower() == file_name.lower()), None)
    if target is None:
        target = all_files[0]

    try:
        df = read_excel(target)
        return _detect_possible_primary_keys(df)
    except Exception:
        return list(all_files[0].name for _ in range(1))[:1]

