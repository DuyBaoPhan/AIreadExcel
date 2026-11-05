"""Conservative product/year revenue requests; never fall back to all-source export."""
import re
import unicodedata
from pathlib import Path

import pandas as pd

from app.services.excel.excel_reader import read_excel
from app.services.sources.file_manager import list_excel_files, safe_output_path
from app.services.excel.excel_writer import generate_timestamped_name
from app.services.reports.report_engine import run_report
from app.services.reports.advanced_report_export import build_advanced_report_bytes


def normalize(value):
    return ''.join(c for c in unicodedata.normalize('NFD', str(value).lower().replace('đ', 'd'))
                   if unicodedata.category(c) != 'Mn').strip()


def is_revenue_request(text):
    return 'doanh thu' in normalize(text) or 'revenue' in normalize(text)


def parse_revenue_request(text):
    """Support only an explicit product and full calendar year; reject other grammar."""
    normalized = normalize(text)
    match = re.fullmatch(
        r'(?:bao cao |tinh |tong |cho toi |xuat )*(?:tong )?(?:doanh thu|revenue)'
        r'\s+(?:cua\s+)?(.+?)\s+nam\s+(\d{4})(?:\s+(?:la bao nhieu|bao nhieu))?[?.!]*',
        normalized,
    )
    if not match:
        raise ValueError('Yêu cầu doanh thu chưa đủ rõ. Hỗ trợ: “Doanh thu của Laptop Pro X năm 2024 là bao nhiêu?”. Với điều kiện khác, dùng Báo cáo nâng cao; không tự xuất toàn bộ file.')
    product = match.group(1).strip(' "\'')
    if not product or any(x in product for x in (' theo ', ' thang ', ' va ', ' quy ')):
        raise ValueError('Chưa xác định duy nhất sản phẩm. Hãy chỉ rõ tên sản phẩm và năm hoặc dùng Báo cáo nâng cao.')
    year = int(match.group(2))
    if not 1900 <= year <= 2100:
        raise ValueError('Năm báo cáo phải nằm trong khoảng 1900–2100.')
    return product, year


def _column(df, aliases):
    matches = [c for c in df.columns if normalize(c).replace(' ', '_') in aliases]
    if len(matches) > 1:
        raise ValueError(f'Có nhiều cột phù hợp: {matches}. Hãy chọn cột trong Báo cáo nâng cao.')
    return matches[0] if matches else None


def run_revenue_request(input_dir: Path, project_name: str, text: str):
    product, year = parse_revenue_request(text)
    candidates = []
    for path in list_excel_files(input_dir):
        try:
            df = read_excel(path)
        except ValueError:
            continue
        product_col = _column(df, {'product', 'product_name', 'san_pham', 'ten_san_pham'})
        revenue_col = _column(df, {'revenue', 'doanh_thu', 'sales_amount'})
        if product_col and revenue_col:
            candidates.append((path, df, product_col, revenue_col))
    if len(candidates) != 1:
        raise ValueError('Cần đúng một file có cột sản phẩm và doanh thu. Không tìm thấy hoặc có nhiều nguồn phù hợp; hãy chọn nguồn trong Báo cáo nâng cao.')
    path, df, product_col, revenue_col = candidates[0]
    year_col = _column(df, {'year', 'nam'})
    date_col = _column(df, {'date', 'order_date', 'sale_date', 'sales_date', 'ngay', 'ngay_ban', 'ngay_don_hang'})
    if not year_col and not date_col:
        month_col = _column(df, {'month', 'thang'})
        if month_col and df[month_col].dropna().astype(str).str.fullmatch(r'\d{4}-(?:0[1-9]|1[0-2])').all():
            df = df.copy()
            derived = '__report_year__'
            while derived in df.columns:
                derived += '_'
            df[derived] = df[month_col].astype('string').str.slice(0, 4).astype('Int64')
            year_col = derived
    if not year_col and not date_col:
        raise ValueError(f'File {path.name} không có cột năm hoặc ngày bán hàng để xác định năm {year}. Cột tháng đơn thuần không đủ. Hãy bổ sung cột year/năm hoặc date/ngày; không thể suy đoán năm từ tên file.')
    if year_col and date_col:
        raise ValueError('Nguồn có cả cột năm và ngày. Hãy chọn cột thời gian cần dùng trong Báo cáo nâng cao để tránh mâu thuẫn.')
    config = {'version': 1, 'filters': [], 'metrics': [
        {'column': revenue_col, 'operation': 'sum', 'alias': 'Revenue'}]}
    if year_col:
        config['filters'].append({'column': year_col, 'operator': 'eq', 'type': 'number', 'value': year})
    else:
        config['filters'].append({'column': date_col, 'operator': 'between', 'type': 'date',
                                  'value': [f'{year}-01-01', f'{year}-12-31 23:59:59.999999']})
    # Literal case-insensitive product matching, never fuzzy/partial matching.
    chosen = df.loc[df[product_col].map(normalize).eq(product)].copy()
    if chosen.empty:
        raise ValueError(f'Không tìm thấy sản phẩm “{product}” trong {path.name}. Kiểm tra tên hoặc chọn nguồn khác.')
    report = run_report(chosen, config)
    if report['data'].empty:
        raise ValueError(f'Không có bản ghi sản phẩm “{product}” trong năm {year}; không đủ dữ liệu để kết luận doanh thu bằng 0.')
    if report['data'][revenue_col].isna().any():
        raise ValueError('Có doanh thu trống trong các dòng phù hợp. Hãy bổ sung dữ liệu trước khi tính tổng.')
    total = float(report['summary']['Revenue'].iloc[0])
    out = safe_output_path(project_name, generate_timestamped_name('Revenue'))
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(build_advanced_report_bytes(report, config, title=f'Doanh thu {product} - {year}'))
    return {'output_path': str(out), 'report_type': 'revenue', 'revenue_total': total,
            'product': str(report['data'][product_col].iloc[0]), 'year': year,
            'total_rows': len(report['data']), 'files_included': 1, 'source_file': path.name,
            'warnings': ['Đơn vị tiền tệ theo cột doanh thu nguồn; không tự quy đổi hoặc loại trùng.']}
