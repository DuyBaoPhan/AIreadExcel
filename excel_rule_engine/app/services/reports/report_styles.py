"""Reusable presentation helpers for Excel reports; values remain unchanged."""
from __future__ import annotations

from datetime import date, datetime
from numbers import Real
from typing import Any

import pandas as pd
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.table import Table, TableStyleInfo
from openpyxl.worksheet.page import PageMargins

NAVY = "17365D"
TEAL = "008C95"
LIGHT = "EAF3F8"
TEXT = "243746"
NUMBER_FORMAT = '#,##0.##;[Red](#,##0.##);"–"'


def prepare_sheet(ws: Any, title: str) -> None:
    """Set consistent viewing and printing defaults."""
    ws.sheet_view.showGridLines = False
    ws.sheet_properties.pageSetUpPr.fitToPage = True
    ws.sheet_properties.tabColor = TEAL
    ws.page_setup.orientation = "landscape"
    ws.page_setup.paperSize = ws.PAPERSIZE_A4
    ws.page_setup.fitToWidth = 1
    ws.page_setup.fitToHeight = 0
    ws.page_margins = PageMargins(left=0.3, right=0.3, top=0.5, bottom=0.5)
    ws.oddHeader.center.text = title.replace("&", "&&")
    ws.oddFooter.left.text = "Excel Rule Engine"
    ws.oddFooter.right.text = "Trang &P / &N"


def title_band(ws: Any, title: str, subtitle: str, width: int = 8) -> None:
    """Draw a prominent title and a quiet subtitle."""
    for row, text, color, size in ((1, title, NAVY, 22), (2, subtitle, TEAL, 11)):
        ws.merge_cells(start_row=row, start_column=1, end_row=row, end_column=width)
        for cells in ws.iter_rows(min_row=row, max_row=row, max_col=width):
            for cell in cells:
                cell.fill = PatternFill("solid", fgColor=color)
        cell = ws.cell(row, 1, text)
        cell.data_type = "s"
        cell.font = Font(name="Calibri", size=size, color="FFFFFF", bold=row == 1)
        cell.alignment = Alignment(vertical="center", indent=1, wrap_text=True)
    ws.row_dimensions[1].height = 44
    ws.row_dimensions[2].height = 30


def write_table(ws: Any, df: pd.DataFrame, name: str, start_row: int = 1) -> None:
    """Write a filterable, striped table with type-aware formats and safe text."""
    if df.size > 1_000_000:
        raise ValueError("Excel export exceeds the 1,000,000 cell limit; filter or aggregate first.")
    for value in list(df.columns):
        if len(str(value).encode('utf-16-le')) // 2 > 32767:
            raise ValueError("Excel column header exceeds 32,767 characters.")
    for column in df.columns:
        if df[column].map(lambda value: isinstance(value, str) and len(value.encode('utf-16-le')) // 2 > 32767).any():
            raise ValueError("Excel cell text exceeds 32,767 characters; shorten source values.")
    if not len(df.columns):
        ws.cell(start_row, 1, "Không có cột dữ liệu")
        return
    # Excel tables require non-empty, case-insensitively unique string headers.
    headers: list[str] = []
    used: set[str] = set()
    for index, col in enumerate(df.columns, 1):
        base = str(col).strip() or f"Cột {index}"
        label, suffix = base, 2
        while label.casefold() in used:
            label = f"{base} ({suffix})"
            suffix += 1
        headers.append(label)
        used.add(label.casefold())
    for col, label in enumerate(headers, 1):
        cell = ws.cell(start_row, col, label)
        cell.data_type = "s"
        cell.fill = PatternFill("solid", fgColor=NAVY)
        cell.font = Font(name="Calibri", bold=True, color="FFFFFF", size=11)
        cell.alignment = Alignment(wrap_text=True, vertical="center")
    ws.row_dimensions[start_row].height = 32
    widths = [max(14, min(len(h) + 4, 44)) for h in headers]
    for row_num, values in enumerate(df.itertuples(index=False, name=None), start_row + 1):
        for col, value in enumerate(values, 1):
            if pd.isna(value):
                value = None
            elif hasattr(value, "item"):
                value = value.item()
            cell = ws.cell(row_num, col, value)
            if isinstance(value, str):
                cell.data_type = "s"  # Source text must never become an Excel formula.
            cell.font = Font(name="Calibri", size=11, color=TEXT)
            cell.alignment = Alignment(vertical="top", wrap_text=True)
            if isinstance(value, (date, datetime)):
                cell.number_format = "dd/mm/yyyy"
            elif isinstance(value, Real) and not isinstance(value, bool):
                cell.number_format = NUMBER_FORMAT
            if row_num % 2 == 0:
                cell.fill = PatternFill("solid", fgColor=LIGHT)
            widths[col - 1] = max(widths[col - 1], min(len(str(value or "")) + 3, 44))
    last_col = get_column_letter(len(headers))
    last_row = start_row + len(df)
    if len(df):
        table = Table(displayName=name, ref=f"A{start_row}:{last_col}{last_row}")
        table.tableStyleInfo = TableStyleInfo(name="TableStyleMedium2", showRowStripes=True)
        ws.add_table(table)
    else:
        ws.auto_filter.ref = f"A{start_row}:{last_col}{start_row}"
    for col, width in enumerate(widths, 1):
        ws.column_dimensions[get_column_letter(col)].width = width
    ws.freeze_panes = f"A{start_row + 1}"
    ws.print_title_rows = f"1:{start_row}"
    ws.print_options.horizontalCentered = True
    ws.print_area = f"A1:{last_col}{max(last_row, start_row)}"
