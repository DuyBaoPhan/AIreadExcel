"""
Report Export Workflow - Tạo báo cáo tổng hợp từ dữ liệu.
"""

from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd
from openpyxl import Workbook
from app.services.reports.report_storage import save_workbook
from openpyxl.styles import Font, PatternFill, Alignment
from openpyxl.chart import BarChart, Reference
from openpyxl.formatting.rule import CellIsRule
from app.services.reports.report_styles import (
    NAVY, TEAL, LIGHT, prepare_sheet, title_band, write_table,
)

from app.services.excel.excel_reader import read_excel
from app.services.excel.excel_writer import generate_timestamped_name
from app.services.sources.file_manager import list_excel_files, safe_output_path

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
    included_files: list[Path] = []
    for fpath in files:
        try:
            df = read_excel(fpath)
            df["_source"] = fpath.name
            frames.append(df)
            included_files.append(fpath)
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
    _write_summary(ws_sum, combined, included_files, report_title)

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
    save_workbook(wb, out_path)
    logger.info("Report saved: %s", out_path)

    return {
        "output_path": str(out_path),
        "total_rows": len(combined),
        "files_included": len(frames),
        "warnings": warnings,
    }


def _write_summary(ws: Any, df: pd.DataFrame, files: list[Path], title: str) -> None:
    """Trang tổng quan với chỉ số, danh sách nguồn và biểu đồ."""
    prepare_sheet(ws, title)
    title_band(ws, title, f"TỔNG QUAN  |  Ngày tạo: {datetime.now():%d/%m/%Y %H:%M}")
    business_columns = [col for col in df.columns if col != "_source"]
    missing = int(df[business_columns].isna().sum().sum())
    metrics = [
        ("FILE NGUỒN", len(files)),
        ("DÒNG DỮ LIỆU", len(df)),
        ("CỘT DỮ LIỆU", len(business_columns)),
        ("Ô CÒN TRỐNG", missing),
    ]
    for index, (label, value) in enumerate(metrics):
        col = 1 + index * 2
        for row in (4, 5):
            ws.merge_cells(start_row=row, start_column=col, end_row=row, end_column=col + 1)
            for c in range(col, col + 2):
                ws.cell(row, c).fill = PatternFill("solid", fgColor=LIGHT)
        ws.cell(4, col, label).font = Font(name="Calibri", size=10, color=NAVY, bold=True)
        ws.cell(5, col, value).font = Font(name="Calibri", size=26, color=TEAL, bold=True)
        ws.cell(5, col).number_format = "#,##0"
        for row in (4, 5):
            ws.cell(row, col).alignment = Alignment(horizontal="center", vertical="center")
    ws.row_dimensions[4].height = 25
    ws.row_dimensions[5].height = 42

    ws["A7"] = "01 / NGUỒN DỮ LIỆU"
    ws["A7"].font = Font(name="Calibri", bold=True, size=13, color=NAVY)
    counts = df["_source"].value_counts()
    source_df = pd.DataFrame({
        "File nguồn": [f.name for f in files],
        "Số dòng": [int(counts.get(f.name, 0)) for f in files],
    })
    write_table(ws, source_df, "ReportSources", start_row=8)
    ws.column_dimensions["A"].width = 36
    for col in "BCDEFGH":
        ws.column_dimensions[col].width = 18

    if len(df) and len(files):
        # Bound the chart to keep reports readable with large source lists.
        chart = BarChart()
        chart.title = "Số dòng theo file nguồn" + (" (20 file đầu)" if len(files) > 20 else "")
        chart.y_axis.title = "Số dòng"
        chart.x_axis.title = "File nguồn"
        chart.style = 10
        end_row = 8 + min(len(files), 20)
        chart.add_data(Reference(ws, min_col=2, min_row=8, max_row=end_row), titles_from_data=True)
        chart.set_categories(Reference(ws, min_col=1, min_row=9, max_row=end_row))
        chart.legend = None
        chart.width = 22
        chart.height = 10
        ws.add_chart(chart, "D8")
    note_row = max(29, 11 + len(files))
    ws.merge_cells(start_row=note_row, start_column=1, end_row=note_row, end_column=8)
    ws.cell(note_row, 1, "Hướng dẫn: mở Data để lọc dữ liệu; Statistics để xem chất lượng dữ liệu. Cột _source ghi nhận file gốc.")
    ws.cell(note_row, 1).font = Font(name="Calibri", italic=True, color="64748B", size=10)
    ws.cell(note_row, 1).alignment = Alignment(wrap_text=True, vertical="center")
    ws.row_dimensions[note_row].height = 36
    ws.freeze_panes = "A8"
    ws.print_area = f"A1:K{note_row}"


def _write_data_sheet(ws: Any, df: pd.DataFrame) -> None:
    """Giữ header tại dòng 1 để file có thể tiếp tục được đọc tự động."""
    prepare_sheet(ws, "Dữ liệu báo cáo")
    write_table(ws, df, "ReportData")


def _write_stats_sheet(ws: Any, df: pd.DataFrame) -> None:
    """Thống kê theo cột, nhấn mạnh dữ liệu bị thiếu."""
    prepare_sheet(ws, "Thống kê và chất lượng dữ liệu")
    rows = []
    for col in df.columns:
        dtype = str(df[col].dtype)
        null_cnt = int(df[col].isna().sum())
        if pd.api.types.is_numeric_dtype(df[col]):
            mn = round(float(df[col].min()), 2) if not df[col].isna().all() else "N/A"
            mx = round(float(df[col].max()), 2) if not df[col].isna().all() else "N/A"
            avg = round(float(df[col].mean()), 2) if not df[col].isna().all() else "N/A"
        else:
            mn = mx = avg = "N/A"
        rows.append([col, dtype, mn, mx, avg, null_cnt, null_cnt / len(df) if len(df) else 0])
    stats = pd.DataFrame(rows, columns=[
        "Cột", "Kiểu dữ liệu", "Giá trị min", "Giá trị max", "Trung bình", "Null count", "Tỷ lệ trống",
    ])
    write_table(ws, stats, "ReportStatistics")
    for row in range(2, len(stats) + 2):
        ws.cell(row, 7).number_format = "0.0%"
    if len(stats):
        ws.conditional_formatting.add(
            f"F2:G{len(stats) + 1}",
            CellIsRule(operator="greaterThan", formula=["0"],
                       fill=PatternFill("solid", fgColor="FFF0CC"),
                       font=Font(color="9C5700", bold=True)),
        )
