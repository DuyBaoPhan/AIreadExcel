"""Build presentation-ready Excel reports exclusively in memory.

Column mappings are always explicitly selected by the caller. Source values are
never replaced by aggregated values, and source strings are written as text.
"""
from __future__ import annotations

from io import BytesIO
from pathlib import Path
from zipfile import ZipFile, BadZipFile

import numpy as np
import pandas as pd
from openpyxl import Workbook
from openpyxl.chart import BarChart, Reference
from openpyxl.styles import Alignment, Font

from app.services.report_styles import NAVY, prepare_sheet, title_band, write_table
from app.workflows.report_export import _write_data_sheet, _write_stats_sheet

MAX_UPLOAD_BYTES = 20 * 1024 * 1024
MAX_ROWS = 100_000


def _upload_type(filename: str, data: bytes) -> str:
    if not isinstance(data, bytes) or not data:
        raise ValueError("Upload is empty; provide file bytes.")
    if len(data) > MAX_UPLOAD_BYTES:
        raise ValueError("Upload exceeds the 20 MB limit.")
    extension = Path(filename).suffix.lower()
    if extension not in {".xlsx", ".csv"}:
        raise ValueError("Unsupported file type. Choose .xlsx or .csv.")
    if extension == ".xlsx":
        try:
            with ZipFile(BytesIO(data)) as archive:
                if len(archive.infolist()) > 10_000 or sum(
                    entry.file_size for entry in archive.infolist()
                ) > 200 * 1024 * 1024:
                    raise ValueError("Excel workbook expands beyond the safe 200 MB limit.")
        except BadZipFile as exc:
            raise ValueError("Unable to open the Excel workbook.") from exc
    return extension


def inspect_sheets(filename: str, data: bytes) -> list[str]:
    """Return Excel sheet names, or the single virtual sheet ``CSV``."""
    extension = _upload_type(filename, data)
    if extension == ".csv":
        # Parsing is deferred until the user selects the header row.
        return ["CSV"]
    try:
        with pd.ExcelFile(BytesIO(data), engine="openpyxl") as book:
            return list(book.sheet_names)
    except Exception as exc:
        raise ValueError("Unable to open the Excel workbook.") from exc


def read_uploaded_table(
    filename: str, data: bytes, sheet_name: str | int = 0, header_row: int = 0,
) -> pd.DataFrame:
    """Read a zero-based header row and selected sheet, bounded to 100,000 rows.

    CSV is UTF-8 (optionally BOM-prefixed). Missing values retain pandas' normal
    null representation; no business-column detection or renaming is performed.
    """
    extension = _upload_type(filename, data)
    if isinstance(header_row, bool) or not isinstance(header_row, int) or header_row < 0:
        raise ValueError("Header row must be a non-negative integer (zero-based).")
    if header_row > MAX_ROWS:
        raise ValueError("Header row exceeds the 100,000 row limit.")
    try:
        if extension == ".csv":
            if sheet_name not in (0, "CSV"):
                raise ValueError("CSV has only one sheet: CSV.")
            frame = pd.read_csv(BytesIO(data), header=header_row, nrows=MAX_ROWS + 1,
                                encoding="utf-8-sig")
        else:
            if isinstance(sheet_name, bool) or not isinstance(sheet_name, (int, str)):
                raise ValueError("Select a single sheet name or zero-based index.")
            if isinstance(sheet_name, int) and sheet_name < 0:
                raise ValueError("Sheet index must be non-negative.")
            frame = pd.read_excel(BytesIO(data), sheet_name=sheet_name, header=header_row,
                                  nrows=MAX_ROWS + 1, engine="openpyxl")
    except Exception as exc:
        raise ValueError(f"Unable to read the selected table: {exc}") from exc
    _validate_frame(frame)
    return frame


def _validate_frame(df: pd.DataFrame) -> None:
    if not isinstance(df, pd.DataFrame) or df.empty or df.isna().all().all():
        raise ValueError("The selected table is empty.")
    if len(df) > MAX_ROWS:
        raise ValueError("The table exceeds the 100,000 row limit.")
    if len(df.columns) > 200:
        raise ValueError("The table exceeds the 200 column report limit.")
    if not df.columns.is_unique:
        raise ValueError("Column names must be unique for explicit mapping.")


def _selected(df: pd.DataFrame, column, label: str) -> None:
    if column is None or column not in df.columns:
        raise ValueError(f"Select a valid {label} column.")


def _numeric(df: pd.DataFrame, column) -> pd.Series:
    _selected(df, column, "numeric value")
    original = df[column]
    if pd.api.types.is_bool_dtype(original):
        raise ValueError("The selected value column must contain numbers, not booleans.")
    converted = pd.to_numeric(original, errors="coerce")
    if converted.notna().sum() == 0 or (original.notna() & converted.isna()).any():
        raise ValueError("The selected value column must contain numeric values only (blanks allowed).")
    if not np.isfinite(converted.dropna().to_numpy(dtype=float)).all():
        raise ValueError("Numeric values must be finite.")
    return converted


def _summary(df: pd.DataFrame, template: str, group_column, value_column) -> pd.DataFrame:
    if template == "general":
        return pd.DataFrame({"Chỉ tiêu": ["Số dòng dữ liệu", "Số cột dữ liệu", "Ô còn trống"],
                             "Value": [len(df), len(df.columns), int(df.isna().sum().sum())]})
    _selected(df, group_column, "group / department")
    if value_column is not None and group_column == value_column:
        raise ValueError("Group and numeric value columns must be different.")
    # Build a separate frame: neither numeric coercion nor grouping changes detail.
    working = pd.DataFrame({"Group": df[group_column]})
    groups = working.groupby("Group", dropna=False, sort=False, observed=True)
    result = groups.size().rename("Số bản ghi" if template == "hr" else "Số dòng").to_frame()
    if value_column is not None or template == "sales":
        working["Value"] = _numeric(df, value_column)
        amounts = working.groupby("Group", dropna=False, sort=False, observed=True)["Value"]
        result["Tổng lương" if template == "hr" else "Tổng doanh thu"] = amounts.sum(min_count=1)
        if template == "hr":
            result["Lương trung bình"] = amounts.mean()
    return result.reset_index()


def build_report_bytes(
    df: pd.DataFrame, template: str = "general", title: str = "", company: str = "",
    period: str = "", prepared_by: str = "", group_column=None, value_column=None,
) -> bytes:
    """Return an XLSX containing Report, unchanged Data, and Statistics sheets.

    HR requires an explicit department/group and optionally a numeric salary.
    Sales requires both an explicit group and numeric value. No columns, including
    numeric IDs, are automatically selected or summed. Callers are responsible
    for selecting the intended business measure.
    """
    _validate_frame(df)
    if template not in {"general", "hr", "sales"}:
        raise ValueError("Template must be general, hr, or sales.")
    summary = _summary(df, template, group_column, value_column)
    report_title = title or {"general": "BÁO CÁO TỔNG HỢP", "hr": "BÁO CÁO NHÂN SỰ",
                             "sales": "BÁO CÁO DOANH THU"}[template]
    wb = Workbook()
    ws = wb.active
    ws.title = "Report"
    prepare_sheet(ws, report_title)
    title_band(ws, report_title, f"{template.upper()} | {period or 'Reporting overview'}", width=10)
    for row, (label, value) in enumerate((("Đơn vị", company), ("Kỳ báo cáo", period),
                                         ("Người lập", prepared_by)), 4):
        ws.cell(row, 1, label).font = Font(name="Calibri", bold=True, color=NAVY)
        cell = ws.cell(row, 2, value)
        cell.data_type = "s"
    ws.cell(8, 1, "TỔNG HỢP").font = Font(name="Calibri", bold=True, size=14, color=NAVY)
    write_table(ws, summary, "ReportSummary", start_row=9)
    for col in "ABCDEFGHIJ":
        ws.column_dimensions[col].width = 20
    ws.column_dimensions["A"].width = 30
    if template != "general" and len(summary):
        chart = BarChart()
        chart.title = "Số bản ghi theo nhóm" if template == "hr" else "Doanh thu theo nhóm"
        chart.style = 10
        chart.legend = None
        # Keep the figure readable; the complete aggregation remains in the table.
        end_row = 9 + min(len(summary), 20)
        measure_col = 2 if template == "hr" else 3
        chart.add_data(Reference(ws, min_col=measure_col, min_row=9, max_row=end_row), titles_from_data=True)
        chart.set_categories(Reference(ws, min_col=1, min_row=10, max_row=end_row))
        chart.width, chart.height = 21, 10
        ws.add_chart(chart, "F9")
        if len(summary) > 20:
            ws.cell(7, 6, "Biểu đồ hiển thị 20 nhóm đầu; bảng tổng hợp bao gồm tất cả nhóm.")
    signature_row = max(31, len(summary) + 13)
    for column, label in ((1, "Người lập"), (5, "Người kiểm tra"), (8, "Người duyệt")):
        ws.cell(signature_row, column, label).font = Font(name="Calibri", bold=True, color=NAVY)
        ws.cell(signature_row + 1, column, "Ký, ghi rõ họ tên / Ngày").alignment = Alignment(vertical="top")
    ws.cell(signature_row + 4, 1, prepared_by).data_type = "s"
    ws.freeze_panes = "B10"
    ws.print_area = f"A1:O{signature_row + 5}"
    _write_data_sheet(wb.create_sheet("Data"), df)
    _write_stats_sheet(wb.create_sheet("Statistics"), df)
    output = BytesIO()
    wb.save(output)
    return output.getvalue()
