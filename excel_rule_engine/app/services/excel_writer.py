"""
Excel Writer Service - Ghi dữ liệu ra file Excel với định dạng cơ bản.
Không bao giờ ghi đè file gốc (input).
"""

from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment
from openpyxl.utils.dataframe import dataframe_to_rows

logger = logging.getLogger(__name__)

HEADER_FILL = PatternFill(start_color="1F4E79", end_color="1F4E79", fill_type="solid")
HEADER_FONT = Font(color="FFFFFF", bold=True)
ADDED_FILL = PatternFill(start_color="C6EFCE", end_color="C6EFCE", fill_type="solid")
UPDATED_FILL = PatternFill(start_color="FFEB9C", end_color="FFEB9C", fill_type="solid")
DELETED_FILL = PatternFill(start_color="FFC7CE", end_color="FFC7CE", fill_type="solid")


def _ensure_output_dir(output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)


def _apply_header_style(ws: Any) -> None:
    """Áp dụng style cho dòng header."""
    for cell in ws[1]:
        cell.font = HEADER_FONT
        cell.fill = HEADER_FILL
        cell.alignment = Alignment(horizontal="center", vertical="center")


def write_excel(
    df: pd.DataFrame,
    output_path: str | Path,
    sheet_name: str = "Data",
    apply_style: bool = True,
) -> Path:
    """
    Ghi DataFrame ra file Excel.

    Args:
        df: Dữ liệu cần ghi.
        output_path: Đường dẫn file đầu ra.
        sheet_name: Tên sheet.
        apply_style: Có áp dụng header style không.

    Returns:
        Path của file đã ghi.
    """
    path = Path(output_path)
    _ensure_output_dir(path)

    wb = Workbook()
    ws = wb.active
    ws.title = sheet_name

    for row in dataframe_to_rows(df, index=False, header=True):
        ws.append(row)

    if apply_style and len(df) > 0:
        _apply_header_style(ws)
        # Auto-fit columns (approx)
        for col in ws.columns:
            max_len = max(
                (len(str(cell.value)) if cell.value else 0 for cell in col),
                default=10,
            )
            ws.column_dimensions[col[0].column_letter].width = min(max_len + 4, 50)

    wb.save(path)
    logger.info("Đã ghi file: %s (%d dòng)", path, len(df))
    return path


def write_comparison_excel(
    added: pd.DataFrame,
    updated: pd.DataFrame,
    unchanged: pd.DataFrame,
    output_path: str | Path,
) -> Path:
    """Ghi Change Log với nhiều sheet và màu sắc phân biệt."""
    path = Path(output_path)
    _ensure_output_dir(path)

    wb = Workbook()
    wb.remove(wb.active)  # Xóa sheet mặc định

    def _write_sheet(df: pd.DataFrame, title: str, fill: PatternFill) -> None:
        ws = wb.create_sheet(title=title)
        if df.empty:
            ws.append(["(Không có dữ liệu)"])
            return
        for row in dataframe_to_rows(df, index=False, header=True):
            ws.append(row)
        # Header style
        for cell in ws[1]:
            cell.font = HEADER_FONT
            cell.fill = HEADER_FILL
            cell.alignment = Alignment(horizontal="center")
        # Data rows color
        for row in ws.iter_rows(min_row=2):
            for cell in row:
                cell.fill = fill
        # Auto-fit
        for col in ws.columns:
            max_len = max((len(str(c.value)) if c.value else 0 for c in col), default=8)
            ws.column_dimensions[col[0].column_letter].width = min(max_len + 4, 50)

    _write_sheet(added, "Added", ADDED_FILL)
    _write_sheet(updated, "Updated", UPDATED_FILL)
    _write_sheet(unchanged, "Unchanged", PatternFill())

    # Summary sheet
    ws_sum = wb.create_sheet(title="Summary", index=0)
    ws_sum.append(["Category", "Count"])
    ws_sum.append(["Added", len(added)])
    ws_sum.append(["Updated", len(updated)])
    ws_sum.append(["Unchanged", len(unchanged)])
    ws_sum.append(["Total (Update)", len(added) + len(updated) + len(unchanged)])
    for cell in ws_sum[1]:
        cell.font = HEADER_FONT
        cell.fill = HEADER_FILL

    wb.save(path)
    logger.info("Đã ghi Change Log: %s", path)
    return path


def generate_timestamped_name(prefix: str, ext: str = ".xlsx") -> str:
    """Tạo tên file có timestamp, ví dụ: Master_Report_20241102_140000.xlsx"""
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    return f"{prefix}_{ts}{ext}"

