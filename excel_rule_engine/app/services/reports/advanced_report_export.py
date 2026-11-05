"""Excel presentation for validated configurable report results (no evaluation)."""
from __future__ import annotations

import json
from io import BytesIO
from datetime import datetime
from typing import Any

import pandas as pd
from openpyxl import Workbook
from openpyxl.chart import BarChart, Reference
from openpyxl.styles import Alignment, Font
from openpyxl.utils import get_column_letter

from app.services.reports.report_styles import NAVY, TEAL, prepare_sheet, title_band, write_table


def _literal(ws: Any, row: int, col: int, value: str) -> None:
    if len(str(value).encode('utf-16-le')) // 2 > 32767:
        raise ValueError('Report metadata exceeds the Excel text limit.')
    cell = ws.cell(row, col, str(value))
    cell.data_type = 's'
    cell.font = Font(name='Calibri', size=11, color=NAVY)
    cell.alignment = Alignment(wrap_text=True, vertical='top')


def build_advanced_report_bytes(
    result: dict, config: dict, title: str = 'BÁO CÁO PHÂN TÍCH',
    company: str = '', prepared_by: str = '',
) -> bytes:
    """Export summary, full processed detail, quality notes and reproducible config.

    Percent comparison columns are percentages on a 0..100 scale, not fractions.
    Source formulas/text are never evaluated. No silent formula/total insertion.
    """
    data, summary = result.get('data'), result.get('summary')
    if not isinstance(data, pd.DataFrame) or not isinstance(summary, pd.DataFrame):
        raise ValueError('Kết quả báo cáo phải có bảng data và summary.')
    if len(data) > 100_000 or max(len(data.columns), len(summary.columns)) > 200:
        raise ValueError('Báo cáo vượt giới hạn 100.000 dòng hoặc 200 cột.')
    if len(summary) > 100_000 or summary.size > 1_000_000:
        raise ValueError('Bảng tổng hợp quá lớn; hãy giảm số nhóm hoặc cột pivot.')
    if data.size + summary.size > 1_000_000:
        raise ValueError('Excel export exceeds 1,000,000 total cells; filter or aggregate first.')
    if any(len(str(v).encode('utf-16-le')) // 2 > 32767 for v in (title, company, prepared_by)):
        raise ValueError('Report metadata exceeds the Excel text limit.')
    wb = Workbook()
    ws = wb.active
    ws.title = 'Report'
    prepare_sheet(ws, title)
    title_band(ws, title or 'BÁO CÁO PHÂN TÍCH',
               f'{company} | {datetime.now():%d/%m/%Y %H:%M}', width=10)
    metadata = [f'Đơn vị: {company}', f'Người lập: {prepared_by}',
                f'Dòng sau xử lý: {len(data):,} | Dòng kết quả: {len(summary):,}',
                'Tổng hợp được tính theo cấu hình trong sheet Configuration. Không tự loại trùng.']
    for row, text in enumerate(metadata, 4):
        ws.merge_cells(start_row=row, start_column=1, end_row=row, end_column=10)
        _literal(ws, row, 1, text)
        ws.row_dimensions[row].height = 25
    _literal(ws, 9, 1, 'TỔNG QUAN KẾT QUẢ')
    # Display only a small excerpt here; Summary always contains the complete result.
    # Detail-only reports use Data as the complete result instead.
    display = summary if not summary.empty else data
    preview = display.head(15).iloc[:, :5]
    write_table(ws, preview, 'OverviewPreview', start_row=11)
    for c in range(1, 16):
        ws.column_dimensions[get_column_letter(c)].width = 18
    numeric = [i + 1 for i, dtype in enumerate(preview.dtypes)
               if pd.api.types.is_numeric_dtype(dtype) and not pd.api.types.is_bool_dtype(dtype)]
    if len(preview) and numeric and len(preview.columns) > 1:
        chart = BarChart()
        chart.title = 'Trích kết quả (tối đa 15 dòng)'
        chart.style = 10
        chart.width, chart.height = 20, 10
        measure = numeric[0]
        category = next((i for i in range(1, len(preview.columns) + 1) if i != measure), 1)
        chart.add_data(Reference(ws, min_col=measure, min_row=11, max_row=11 + len(preview)), titles_from_data=True)
        chart.set_categories(Reference(ws, min_col=category, min_row=12, max_row=11 + len(preview)))
        ws.add_chart(chart, 'G11')
    for col, text in ((1, 'Người lập'), (6, 'Người kiểm tra'), (11, 'Người duyệt')):
        _literal(ws, 34, col, text)
        _literal(ws, 35, col, '(Ký, ghi rõ họ tên)')
    _literal(ws, 38, 1, prepared_by)
    ws.print_area = 'A1:O40'
    for name, frame, table in [('Summary', summary, 'AdvancedSummary'), ('Data', data, 'AdvancedDetail')]:
        sheet = wb.create_sheet(name)
        prepare_sheet(sheet, name)
        write_table(sheet, frame, table)
        for col, label in enumerate(frame.columns, 1):
            if str(label).endswith('_percent'):
                for row in range(2, len(frame) + 2):
                    sheet.cell(row, col).number_format = '0.00"%"'
    quality = wb.create_sheet('Quality')
    prepare_sheet(quality, 'Chất lượng dữ liệu')
    warnings = list(result.get('warnings', []))
    warnings += [f'Dòng sau xử lý: {len(data)}', f'Ô trống sau xử lý: {int(data.isna().sum().sum())}',
                 'Không tính phần trăm tăng giảm khi giá trị kỳ trước bằng 0.',
                 'Giá trị văn bản được ghi dưới dạng chữ, không chạy như công thức Excel.']
    write_table(quality, pd.DataFrame({'Ghi chú': warnings}), 'QualityNotes')
    quality.column_dimensions['A'].width = 100
    configuration = wb.create_sheet('Configuration')
    prepare_sheet(configuration, 'Cấu hình báo cáo')
    serialized = json.dumps(config, ensure_ascii=False, indent=2, default=str)
    # Fixed small chunks preserve long JSON strings; concatenate cells with no separator.
    chunks = [serialized[i:i + 8000] for i in range(0, len(serialized), 8000)]
    write_table(configuration, pd.DataFrame({'JSON chunks (concatenate without separator)': chunks}), 'ConfigurationLines')
    configuration.column_dimensions['A'].width = 100
    output = BytesIO()
    wb.save(output)
    wb.close()
    return output.getvalue()
