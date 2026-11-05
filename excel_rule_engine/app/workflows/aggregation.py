"""
Aggregation Workflow - Gộp nhiều file Excel thành một Master Report.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import pandas as pd
from rapidfuzz import fuzz

from app.services.excel.excel_reader import read_excel
from app.services.excel.excel_writer import write_excel, generate_timestamped_name
from app.services.sources.file_manager import list_excel_files, safe_output_path

logger = logging.getLogger(__name__)

# Ngưỡng fuzzy matching để chuẩn hoá tên cột
COL_FUZZY_THRESHOLD = 80


def _normalize_col_name(name: str) -> str:
    """Chuẩn hoá tên cột: lowercase, bỏ khoảng trắng thừa."""
    return str(name).strip().lower().replace(" ", "_")


def _build_column_mapping(
    all_columns: list[list[str]],
) -> dict[str, str]:
    """
    Xây dựng mapping từ tên cột gốc → tên chuẩn.
    Dùng fuzzy matching để gộp các biến thể (ví dụ: 'Salary', 'salary', 'Lương').
    """
    canonical: dict[str, str] = {}  # raw → canonical

    # Lấy set tất cả tên cột
    all_col_names: list[str] = []
    for cols in all_columns:
        all_col_names.extend(cols)

    # Nhóm theo fuzzy similarity
    groups: list[list[str]] = []
    used: set[str] = set()

    for col in all_col_names:
        if col in used:
            continue
        group = [col]
        used.add(col)
        for other in all_col_names:
            if other not in used and fuzz.ratio(_normalize_col_name(col), _normalize_col_name(other)) >= COL_FUZZY_THRESHOLD:
                group.append(other)
                used.add(other)
        groups.append(group)

    # Tên chuẩn = tên đầu tiên trong nhóm (theo thứ tự xuất hiện)
    for group in groups:
        representative = group[0]
        for member in group:
            canonical[member] = representative

    return canonical


def run_aggregation(
    input_dir: Path,
    project_name: str = "demo_project",
    specific_files: list[str] | None = None,
) -> dict[str, Any]:
    """
    Gộp tất cả file Excel trong input_dir.

    Returns:
        dict chứa: total_rows, files_merged, output_path, warnings.
    """
    warnings: list[str] = []

    # 1. Lấy danh sách file
    if specific_files:
        files = [input_dir / f for f in specific_files if (input_dir / f).exists()]
        missing = [f for f in specific_files if not (input_dir / f).exists()]
        if missing:
            warnings.append(f"Không tìm thấy file: {', '.join(missing)}")
    else:
        files = list_excel_files(input_dir)

    if not files:
        raise FileNotFoundError(
            f"Không tìm thấy file Excel nào trong '{input_dir}'. "
            "Vui lòng đặt file vào thư mục input."
        )

    logger.info("Aggregation: %d file(s)", len(files))

    # 2. Đọc từng file
    frames: list[pd.DataFrame] = []
    file_col_lists: list[list[str]] = []

    for fpath in files:
        try:
            df = read_excel(fpath)
            df["__source_file__"] = fpath.name   # metadata
            frames.append(df)
            file_col_lists.append([c for c in df.columns if not c.startswith("__")])
        except Exception as exc:
            warnings.append(f"Bỏ qua '{fpath.name}': {exc}")

    if not frames:
        raise ValueError("Không thể đọc được file nào. " + "; ".join(warnings))

    # 3. Kiểm tra cấu trúc cột
    col_sets = [set(cols) for cols in file_col_lists]
    all_same = all(s == col_sets[0] for s in col_sets)

    if not all_same:
        # Thông báo sự khác biệt
        diffs = []
        base_set = col_sets[0]
        for i, s in enumerate(col_sets[1:], 1):
            missing = base_set - s
            extra = s - base_set
            if missing:
                diffs.append(f"'{files[i].name}' thiếu: {missing}")
            if extra:
                diffs.append(f"'{files[i].name}' thêm: {extra}")
        warnings.append("Cấu trúc cột không đồng nhất:\n" + "\n".join(diffs))
        logger.warning("Column mismatch: %s", diffs)

    # 4. Xây dựng column mapping
    col_map = _build_column_mapping(file_col_lists)

    # 5. Chuẩn hoá tên cột và gộp
    normalized_frames: list[pd.DataFrame] = []
    for df in frames:
        src = df.pop("__source_file__")
        renamed = {c: col_map.get(c, c) for c in df.columns}
        df = df.rename(columns=renamed)
        df["source_file"] = src
        normalized_frames.append(df)

    master_df = pd.concat(normalized_frames, ignore_index=True, sort=False)

    # 6. Xuất file
    out_name = generate_timestamped_name("Master_Report")
    out_path = safe_output_path(project_name, out_name)
    write_excel(master_df, out_path, sheet_name="Master_Data")

    return {
        "total_rows": len(master_df),
        "files_merged": len(normalized_frames),
        "output_path": str(out_path),
        "warnings": warnings,
    }

