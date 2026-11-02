"""
Report Export Workflow - Tạo báo cáo tổng hợp từ dữ liệu.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import pandas as pd
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment
from openpyxl.utils.dataframe import dataframe_to_rows

from app.services.excel_reader import read_excel
from app.services.excel_writer import generate_timestamped_name
from app.services.file_manager import list_excel_files, safe_output_path

logger = logging.getLogger(__name__)


def run_export_report(
    input_dir: Path,
    project_name: str,
    report_title: str = "Báo Cáo Tổng Hợp",
) -> dict[str, Any]:
    """
    Tạo báo cáo tổng hợp từ tất cả file Excel trong input_dir.
    Bao gồm: Summary sheet, Data sheet, và thống kê cơ bản.
    """
    warnings: list[str] = []

    files = list_excel_files(input_dir)
    if not files:
        raise FileNotFoundError(
            f"Không tìm thấy file Excel nào trong '{input_dir}'."
        )

    frames: list[pd.DataFrame] = []
    for fpath in files:
        try:
            df = read_excel(fpath)
            df["_source"] = fpath.name
            frames.append(df)
        except Exception as exc:
            warnings.append(f"Bỏ qua '{fpath.name}': {exc}")

    if not frames:
        raise ValueError("Không đọc được file nào.")

    combined = pd.concat(frames, ignore_index=True, sort=False)

    # Tạo Workbook với nhiều sheet
    wb = Workbook()
    wb.remove(wb.active)

    # --- Summary Sheet ---
    ws_sum = wb.create_sheet("Summary")
    _write_summary(ws_sum, combined, files, report_title)

    # --- Data Sheet ---
    ws_data = wb.create_sheet("Data")
    _write_data_sheet(ws_data, combined)

    # --- Stats Sheet ---
    ws_stats = wb.create_sheet("Statistics")
    _write_stats_sheet(ws_stats, combined)

    # Lưu file
    out_name = generate_timestamped_name("Report")
    out_path = safe_output_path(project_name, out_name)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    wb.save(out_path)
    logger.info("Report saved: %s", out_path)

    return {
        "output_path": str(out_path),
        "total_rows": len(combined),
        "files_included": len(frames),
        "warnings": warnings,
    }


def _write_summary(ws: Any, df: pd.DataFrame, files: list[Path], title: str) -> None:
    header_fill = PatternFill(start_color="1F4E79", end_color="1F4E79", fill_type="solid")
    header_font = Font(color="FFFFFF", bold=True, size=14)
    ws["A1"] = title
    ws["A1"].font = header_font
    ws["A1"].fill = header_fill
    ws.merge_cells("A1:D1")
    ws["A1"].alignment = Alignment(horizontal="center")

    ws.append([])
    ws.append(["Tổng quan báo cáo"])
    ws.append(["Số file nguồn", len(files)])
    ws.append(["Tổng số dòng", len(df)])
    ws.append(["Số cột", len(df.columns)])
    ws.append([])
    ws.append(["Danh sách file nguồn:"])
    for f in files:
        ws.append([f"  • {f.name}"])


def _write_data_sheet(ws: Any, df: pd.DataFrame) -> None:
    header_fill = PatternFill(start_color="1F4E79", end_color="1F4E79", fill_type="solid")
    header_font = Font(color="FFFFFF", bold=True)
    for row in dataframe_to_rows(df, index=False, header=True):
        ws.append(row)
    for cell in ws[1]:
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = Alignment(horizontal="center")
    for col in ws.columns:
        max_len = max((len(str(c.value)) if c.value else 0 for c in col), default=8)
        ws.column_dimensions[col[0].column_letter].width = min(max_len + 4, 50)


def _write_stats_sheet(ws: Any, df: pd.DataFrame) -> None:
    header_fill = PatternFill(start_color="375623", end_color="375623", fill_type="solid")
    header_font = Font(color="FFFFFF", bold=True)
    ws.append(["Cột", "Kiểu dữ liệu", "Giá trị min", "Giá trị max", "Trung bình", "Null count"])
    for cell in ws[1]:
        cell.font = header_font
        cell.fill = header_fill

    for col in df.columns:
        dtype = str(df[col].dtype)
        null_cnt = int(df[col].isna().sum())
        if pd.api.types.is_numeric_dtype(df[col]):
            mn = round(float(df[col].min()), 2) if not df[col].isna().all() else "N/A"
            mx = round(float(df[col].max()), 2) if not df[col].isna().all() else "N/A"
            avg = round(float(df[col].mean()), 2) if not df[col].isna().all() else "N/A"
        else:
            mn = mx = avg = "N/A"
        ws.append([col, dtype, mn, mx, avg, null_cnt])

