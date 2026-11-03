"""Fixed Vietnamese NLP acceptance corpus; expectations are authored, never planned.

Accent pairs measure normalization explicitly, not extra semantic coverage. Finance
and HR records deliberately include duplicate order/employee IDs, null metrics,
negative/zero amounts, leap day and last-instant year/month boundaries.
"""
from __future__ import annotations
import copy
import unicodedata
import pandas as pd


def unaccent(text):
    return ''.join(c for c in unicodedata.normalize('NFD', text.replace('đ', 'd').replace('Đ', 'D')) if not unicodedata.combining(c))


def fixtures(kind='both'):
    sales = pd.DataFrame({
        'Ngày': ['2023-12-31 23:59:59', '2024-02-29', '2024-12-31 23:59:59', '2025-01-01', '2025-01-31 23:59:59', '2025-02-01', '2025-02-28 23:59:59', '2025-03-01', '2025-12-31 23:59:59', '2026-01-01'],
        'Sản phẩm': ['Máy in', 'Bàn phím', 'Chuột', 'Máy in', 'Bàn phím', 'Chuột', 'Màn hình', 'Máy in', 'Màn hình', 'Chuột'],
        'Khu vực': ['Miền Bắc', 'Miền Nam', 'Miền Trung', 'Miền Bắc', 'Miền Nam', 'Miền Trung', 'Miền Bắc', 'Miền Nam', 'Miền Trung', 'Miền Bắc'],
        'Trạng thái': ['Hoàn tất', 'Đã hủy', 'Chờ xử lý', 'Hoàn tất', 'Hoàn tất', 'Đã hủy', 'Chờ xử lý', 'Hoàn tất', 'Hoàn tất', 'Hoàn tất'],
        'Doanh thu': [7e6, 2e6, 3e6, 20e6, 15e6, 0, None, 8e6, 40e6, -1e6],
        'Lợi nhuận': [1e6, 0, 5e5, 4e6, 3e6, -1e6, 0, 2e6, 12e6, -2e5],
        'Chi phí': [6e6, 2e6, 2.5e6, 16e6, 12e6, 1e6, 3e6, 6e6, 28e6, 0],
        'Số lượng': [1, 2, 3, 2, 5, 0, 4, 2, 10, -1],
        'Mã đơn hàng': ['O1', 'O2', 'O3', 'O4', 'O4', 'O5', None, 'O6', 'O7', 'O8'],
    })
    hr = pd.DataFrame({
        'Ngày': ['2024-02-29', '2025-01-01', '2025-01-31 23:59:59', '2025-02-01', '2025-12-31 23:59:59', '2026-01-01'],
        'Mã nhân viên': ['E01', 'E01', 'E02', 'E03', 'E04', 'E05'],
        'Tên nhân viên': ['Nguyễn An', 'Nguyễn An', 'Nguyễn An', 'Trần Bình', 'Lê Chi', 'Đỗ Dũng'],
        'Phòng ban': ['Kỹ thuật', 'Kỹ thuật', 'Kế toán', 'Kỹ thuật', 'Nhân sự', 'Kế toán'],
        'Lương': [10e6, 12e6, 30e6, 45e6, None, 0],
    })
    if kind == 'sales': return {'sales.xlsx': sales}
    if kind == 'hr': return {'hr.xlsx': hr}
    if kind == 'duplicate': return {'sales.xlsx': sales, 'backup.xlsx': sales.copy()}
    if kind == 'duplicate_hr': return {'hr.xlsx': hr, 'payroll.xlsx': hr.copy()}
    if kind == 'missing_identity': return {'hr.xlsx': hr.drop(columns='Mã nhân viên')}
    return {'sales.xlsx': sales, 'hr.xlsx': hr}


def metric(column, operation, alias):
    return dict(operation=operation, alias=alias, **({'column': column} if column else {}))


def config(metrics, groups=(), filters=(), date=None, top=None):
    result = dict(version=1, filters=list(filters), filter_logic='and', group_by=list(groups), metrics=metrics)
    if date: result['date_group'] = date
    if top: result['top_n'] = top
    return result


def eq(column, value): return dict(column=column, operator='eq', value=value, type='text')


def date_filter(year, month=None):
    import calendar
    end_month = month or 12
    return dict(column='Ngày', operator='between', type='date', value=[f'{year}-{month or 1:02d}-01', f'{year}-{end_month:02d}-{calendar.monthrange(year, end_month)[1]} 23:59:59.999999999'])


CASES = []
def add(category, text, expected=None, *, source='sales.xlsx', kind='both', status='ready', accents=True, route=False):
    for style, sentence in [('accented', text), ('unaccented', unaccent(text))] if accents else [('original', text)]:
        if any(c['text'] == sentence and c['kind'] == kind and c['route'] == route for c in CASES): continue
        CASES.append(dict(id=f'{category}-{len(CASES)+1:04d}-{style}', category=category, text=sentence, expected=copy.deepcopy(expected), source=source if status == 'ready' else None, kind=kind, status=status, route=route))


METRICS = [('doanh thu', 'Doanh thu', 'Revenue'), ('lợi nhuận', 'Lợi nhuận', 'Profit'), ('chi phí', 'Chi phí', 'Cost'), ('số lượng', 'Số lượng', 'Quantity')]
GROUPS = [('', ()), (' theo sản phẩm', ('Sản phẩm',)), (' theo khu vực', ('Khu vực',)), (' theo trạng thái', ('Trạng thái',))]
for phrase, column, alias in METRICS:
    for prefix, operation, suffix in [('Tổng ', 'sum', 'Sum'), ('Trung bình ', 'mean', 'Mean'), ('Bình quân ', 'mean', 'Mean'), ('Đếm ', 'count', 'Count')]:
        for tail, groups in GROUPS:
            add('finance_aggregate', prefix + phrase + tail, config([metric(column, operation, alias+suffix)], groups))
    for frequency, word, date_alias in [('month', 'tháng', 'Month'), ('quarter', 'quý', 'Quarter'), ('year', 'năm', 'Year')]:
        add('date_group', f'Tổng {phrase} theo {word} năm 2025', config([metric(column, 'sum', alias+'Sum')], [date_alias], [date_filter(2025)], dict(column='Ngày', frequency=frequency, alias=date_alias)))
    for year, month in [(2024, 2), (2024, 12), (2025, 1), (2025, 2), (2025, 12), (2026, 1)]:
        add('date_boundary', f'Tổng {phrase} tháng {month} năm {year}', config([metric(column, 'sum', alias+'Sum')], filters=[date_filter(year, month)]))
    for word, ascending in [('cao nhất', False), ('thấp nhất', True)]:
        for n in (1, 2, 3):
            add('ranking', f'Top {n} sản phẩm {phrase} {word}', config([metric(column, 'sum', alias+'Sum')], ['Sản phẩm'], top=dict(column=alias+'Sum', n=n, ascending=ascending)))
    for col, value in [('Sản phẩm', 'Máy in'), ('Sản phẩm', 'Màn hình'), ('Khu vực', 'Miền Bắc'), ('Khu vực', 'Miền Trung'), ('Trạng thái', 'Hoàn tất'), ('Trạng thái', 'Đã hủy')]:
        add('literal_filter', f'Tổng {phrase} {col.lower()} {value}', config([metric(column, 'sum', alias+'Sum')], filters=[eq(col, value)]))
    for word, op, value in [('trên 10 triệu', 'gt', 1e7), ('dưới 2 triệu', 'lt', 2e6), ('>= 0', 'ge', 0), ('<= 20 triệu', 'le', 2e7), ('bằng 0', 'eq', 0), ('từ 0 đến 20 triệu', 'between', [0, 2e7])]:
        add('numeric_filter', f'Đếm dòng {phrase} {word}', config([metric(None, 'rows', 'Rows')], filters=[dict(column=column, operator=op, value=value, type='number')]))
for prefix, operation, alias in [('Tổng', 'sum', 'SalarySum'), ('Lương trung bình', 'mean', 'SalaryMean'), ('Đếm', 'count', 'SalaryCount')]:
    phrase = prefix + (' lương' if prefix != 'Lương trung bình' else '')
    for tail, groups in [('', []), (' theo phòng ban', ['Phòng ban'])]:
        add('hr_aggregate', phrase+tail, config([metric('Lương', operation, alias)], groups), source='hr.xlsx')
        for dept in ['Kỹ thuật', 'Kế toán', 'Nhân sự']:
            # 'Nhân sự' alone also means personnel, so state department context.
            context = ' phòng ban ' if dept == 'Nhân sự' and not tail else ' '
            add('hr_literal', phrase+tail+context+dept, config([metric('Lương', operation, alias)], groups, [eq('Phòng ban', dept)]), source='hr.xlsx')
for phrase, col, operation, alias, source, group in [('Đếm nhân viên', 'Mã nhân viên', 'nunique', 'Employees', 'hr.xlsx', 'Phòng ban'), ('Bao nhiêu đơn hàng', 'Mã đơn hàng', 'nunique', 'Orders', 'sales.xlsx', 'Sản phẩm'), ('Đếm dòng', None, 'rows', 'Rows', 'sales.xlsx', 'Trạng thái')]:
    add('identity_counts', phrase+' theo '+group.lower(), config([metric(col, operation, alias)], [group]), source=source)
for word, ascending in [('cao nhất', False), ('thấp nhất', True)]:
    add('hr_ranking', f'Nhân viên nào có tổng lương {word}', config([metric('Lương', 'sum', 'SalarySum')], ['Mã nhân viên', 'Tên nhân viên'], top=dict(column='SalarySum', n=1, ascending=ascending)), source='hr.xlsx')
for text, kind in [('Doanh thu', 'duplicate'), ('Tổng doanh thu theo sản phẩm', 'duplicate'), ('Lương trung bình theo phòng ban', 'duplicate_hr'), ('Doanh thu tháng 2', 'sales'), ('Doanh thu sản phẩm', 'sales'), ('Nhân viên nào lương cao nhất', 'missing_identity'), ('Top 2 doanh thu', 'sales'), ('Tổng doanh thu và trung bình lợi nhuận', 'sales')]:
    add('ambiguity', text, kind=kind, status='clarify')
for text in ['Dự báo doanh thu năm 2027', 'So sánh doanh thu năm 2024 và 2025', 'Doanh thu tăng trưởng', 'Doanh thu không bao gồm Đã hủy', 'Doanh thu ghép nhân viên', 'Doanh thu sản phẩm Sao Hỏa', 'Doanh thu theo khách hàng', 'Doanh thu hôm qua', 'Doanh thu sau thuế', 'Doanh thu trên 20 triệu hoặc dưới 2 triệu', 'Doanh thu tháng 13 năm 2025', 'Doanh thu giảm 10 phần trăm', 'Top 0 sản phẩm doanh thu', 'Xóa doanh thu', 'Doanh thu từ 30 đến 10 triệu']:
    add('unsupported_safety', text, kind='sales', status='unsupported')
add('explicit_source', 'Tổng doanh thu theo sản phẩm file sales.xlsx', config([metric('Doanh thu', 'sum', 'RevenueSum')], ['Sản phẩm']), kind='duplicate')
for text in ['Tổng doanh thu theo sản phẩm', 'Lương trung bình theo phòng ban', 'Nhân viên nào có lương cao nhất', 'Đếm nhân viên theo phòng ban', 'Đếm dòng theo trạng thái', 'Top 2 sản phẩm lợi nhuận cao nhất', 'Doanh thu tháng 2 năm 2025', 'Dự báo doanh thu năm 2027']:
    add('command_routing', text, status='preview', route=True)

# Bare salary on repeated employee records must not imply a payroll sum.
for word in ['cao nhất', 'thấp nhất']:
    add('ambiguity', f'Nhân viên nào có lương {word}', kind='hr', status='clarify')

# Campaign expansion: new supported phrasings, each with independent expectations.
for phrase, column, alias in METRICS:
    for prefix in ['Cho mình xem tổng ', 'Bạn hãy tính tổng ', 'Tôi cần báo cáo tổng ', 'Cho biết tổng ']:
        add('expanded_polite', prefix + phrase + ' theo từng sản phẩm',
            config([metric(column, 'sum', alias+'Sum')], ['Sản phẩm']))
    for quarter, lower, upper in [(1, '2025-01-01', '2025-03-31 23:59:59.999999999'),
                                   (2, '2025-04-01', '2025-06-30 23:59:59.999999999')]:
        add('expanded_quarter', f'Tổng {phrase} quý {quarter} năm 2025',
            config([metric(column, 'sum', alias+'Sum')], filters=[dict(column='Ngày', operator='between', value=[lower, upper], type='date')]))
    add('expanded_date_range', f'Tổng {phrase} từ ngày 01/01/2025 đến ngày 28/02/2025',
        config([metric(column, 'sum', alias+'Sum')], filters=[dict(column='Ngày', operator='between', type='date', value=['2025-01-01', '2025-02-28 23:59:59.999999999'])]))
    add('expanded_multi_group', f'Tổng {phrase} theo sản phẩm và khu vực',
        config([metric(column, 'sum', alias+'Sum')], ['Sản phẩm', 'Khu vực']))
    for qualifier, op, value in [('lớn hơn hoặc bằng 1.000.000', 'ge', 1e6),
                                  ('nhỏ hơn hoặc bằng 1,5 triệu', 'le', 1.5e6),
                                  ('trên 1.000', 'gt', 1000),
                                  ('tối thiểu 0', 'ge', 0)]:
        add('expanded_number', f'Đếm dòng {phrase} {qualifier}',
            config([metric(None, 'rows', 'Rows')], filters=[dict(column=column, operator=op, value=value, type='number')]))
for phrase in ['Số nhân viên', 'Tổng số nhân viên', 'Số lượng nhân sự', 'Có bao nhiêu nhân viên']:
    add('expanded_identity', phrase+' theo phòng ban',
        config([metric('Mã nhân viên', 'nunique', 'Employees')], ['Phòng ban']), source='hr.xlsx')
for phrase, operation, alias in [('Max doanh thu', 'max', 'RevenueMax'), ('Min doanh thu', 'min', 'RevenueMin'),
                                  ('Giá trị lớn nhất của doanh thu', 'max', 'RevenueMax'),
                                  ('Giá trị nhỏ nhất của doanh thu', 'min', 'RevenueMin')]:
    add('expanded_scalar', phrase, config([metric('Doanh thu', operation, alias)]))
for text in ['Tổng và trung bình doanh thu', 'Đếm và tổng doanh thu',
             'Top 1 sản phẩm doanh thu theo tháng',
             'Tổng doanh thu theo sản phẩm doanh thu trên 10 triệu']:
    add('expanded_scope_safety', text, kind='sales', status='clarify')
for text in ['Số nhân viên theo phòng ban', 'Số đơn hàng theo sản phẩm', 'Số lượng theo sản phẩm',
             'Đếm dòng số lượng từ 0 đến 20 triệu', 'Giá trị nhỏ nhất của doanh thu']:
    add('command_routing', text, status='preview', route=True)
