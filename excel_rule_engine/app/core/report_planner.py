"""Deterministic Vietnamese finance/HR report planning (no execution or I/O).

Extend SCHEMA_ALIASES to support local column names. Every meaningful request
span must be accounted for; unknown clauses never become a generic report.
"""
from __future__ import annotations

import calendar
import re
import unicodedata

import pandas as pd

SCHEMA_ALIASES = {
    'revenue': ('doanh thu', 'revenue', 'sales', 'thanh tien'),
    'profit': ('loi nhuan', 'profit'),
    'cost': ('chi phi', 'cost', 'expense', 'expenses'),
    'quantity': ('so luong', 'quantity', 'qty'),
    'salary': ('luong', 'salary', 'payroll', 'tien luong'),
    'product': ('san pham', 'product', 'product name', 'ten san pham'),
    'department': ('phong ban', 'department', 'phong'),
    'region': ('khu vuc', 'region', 'vung', 'mien'),
    'status': ('trang thai', 'status'),
    'employee_id': ('ma nhan vien', 'employee id', 'employee_id', 'manv'),
    'order_id': ('ma don hang', 'order id', 'order_id', 'ma don'),
    'date': ('ngay', 'date', 'ngay ban', 'ngay giao dich', 'order date', 'thang', 'month', 'period'),
}
METRIC_NAMES = {'revenue': 'Revenue', 'profit': 'Profit', 'cost': 'Cost',
                'quantity': 'Quantity', 'salary': 'Salary'}
DIMENSIONS = ('product', 'department', 'region', 'status')


def normalize(text: str) -> str:
    """Accent-insensitive matching; never applied to returned data values."""
    text = unicodedata.normalize('NFD', str(text).lower().replace('đ', 'd'))
    return re.sub(r'\s+', ' ', ''.join(c for c in text if not unicodedata.combining(c)).replace('_', ' ')).strip()


def _pattern(phrases):
    return r'(?<!\w)(?:' + '|'.join(re.escape(normalize(p)) for p in sorted(phrases, key=len, reverse=True)) + r')(?!\w)'


def _result(status, source=None, config=None, explanation=None, questions=None, unsupported=None):
    return dict(status=status, source=source, config=config, explanation=explanation or [],
                questions=questions or [], unsupported=unsupported or [])


def _plan_one(text, name, df):
    if not isinstance(df, pd.DataFrame) or not df.columns.is_unique or not all(isinstance(c, str) for c in df.columns):
        return _result('unsupported', unsupported=['Nguồn phải có các cột tên chuỗi duy nhất.'])
    schema = {key: [c for c in df.columns if normalize(c) in {normalize(a) for a in aliases}]
              for key, aliases in SCHEMA_ALIASES.items()}
    used = [False] * len(text)
    errors, questions = [], []
    config = {'version': 1, 'filters': [], 'filter_logic': 'and', 'group_by': [], 'metrics': []}

    def mark(start, end):
        used[start:end] = [True] * (end - start)

    def matches(pattern):
        return list(re.finditer(pattern, text))

    def column(key):
        cols = schema[key]
        if len(cols) != 1:
            questions.append(f"Chọn cột cho {key}: {', '.join(cols) if cols else 'chưa tìm thấy trong nguồn'}.")
            return None
        return cols[0]

    # Only explicit single-source reports are supported.
    for p in ('xoa', 'delete', 'remove', 'du bao', 'forecast', 'so sanh', 'tang truong', 'chenh lech', 'ket hop', 'ghep',
              'join', 'khong', 'ngoai tru', 'loai tru', 'khong tinh', 'khong bao gom', 'tru don', 'hoac'):
        if re.search(_pattern([p]), text):
            return _result('unsupported', unsupported=[f'Chưa hỗ trợ điều kiện: {p}.'])

    for m in matches(_pattern([name])):
        mark(*m.span())
    # Explicit grouping: consume known dimensions only; unknown "theo" remains.
    group_pattern = r'\btheo\s+(' + '|'.join(re.escape(normalize(a)) for k in DIMENSIONS for a in sorted(SCHEMA_ALIASES[k], key=len, reverse=True)) + r'|thang|quy|nam)\b'
    for m in matches(group_pattern):
        word = m.group(1)
        mark(*m.span())
        if word in ('thang', 'quy', 'nam'):
            col = column('date')
            freq, alias = {'thang': ('month', 'Month'), 'quy': ('quarter', 'Quarter'), 'nam': ('year', 'Year')}[word]
            if 'date_group' in config and config['date_group']['frequency'] != freq:
                errors.append('Chỉ hỗ trợ một cấp nhóm thời gian.')
            if col:
                while alias in df.columns:
                    alias = '_' + alias
                config['date_group'] = {'column': col, 'frequency': freq, 'alias': alias}
                config['group_by'].append(alias)
        else:
            key = next(k for k in DIMENSIONS if word in [normalize(a) for a in SCHEMA_ALIASES[k]])
            col = column(key)
            if col:
                config['group_by'].append(col)

    # Dates: calendar month requires a year unless a single data year is certain.
    date_pattern = r'\bthang\s+(\d{1,2})(?:\s*(?:/|-|nam)\s*(\d{4}))?\b|\bnam\s+(\d{4})\b|\b(20\d{2}|19\d{2})\b'
    date_matches = [m for m in matches(date_pattern) if not any(used[m.start():m.end()])]
    if date_matches:
        col = column('date')
        if len(date_matches) > 1:
            errors.append('Chưa hỗ trợ nhiều khoảng thời gian trong một yêu cầu.')
        for m in date_matches:
            mark(*m.span())
        m = date_matches[0]
        month = int(m.group(1)) if m.group(1) else None
        year = int(m.group(2) or m.group(3) or m.group(4)) if any(m.group(i) for i in (2, 3, 4)) else None
        if col and not year:
            vals = df[col].dropna().astype(str)
            try:
                from app.services.report_engine import _convert
                parsed_dates = _convert(df[col], 'date')
                years = set(parsed_dates.dropna().dt.year.astype(str))
            except ValueError:
                years = set()
            if len(years) == 1:
                year = int(next(iter(years)))
            else:
                questions.append('Bạn muốn tháng này của năm nào?')
        if month is not None and not 1 <= month <= 12:
            errors.append('Tháng phải nằm trong 1–12.')
        elif col and year:
            vals = df[col].dropna().astype(str)
            ym = not vals.empty and vals.str.fullmatch(r'\d{4}-\d{2}').all()
            if ym:
                lo = f'{year:04d}-{month or 1:02d}'
                hi = f'{year:04d}-{month or 12:02d}'
            else:
                lo = f'{year:04d}-{month or 1:02d}-01'
                hi = f'{year:04d}-{month or 12:02d}-{calendar.monthrange(year, month or 12)[1]:02d} 23:59:59.999999999'
            config['filters'].append({'column': col, 'operator': 'between', 'value': [lo, hi], 'type': 'text' if ym else 'date'})

    numeric_keys = set()
    # Numeric conditions are bound to explicitly mentioned metric columns.
    number = r'(\d+(?:[.,]\d+)?)\s*(ty|trieu|nghin|million|billion)?'
    def amount(value, unit):
        return float(value.replace(',', '.')) * {'ty': 1e9, 'billion': 1e9, 'trieu': 1e6, 'million': 1e6, 'nghin': 1e3, None: 1}[unit]
    for key in METRIC_NAMES:
        term = _pattern(SCHEMA_ALIASES[key])
        between = term + r'\s+tu\s+' + number + r'\s+den\s+' + number
        for m in matches(between):
            numeric_keys.add(key)
            col = column(key)
            lo = amount(m.group(1), m.group(2) or m.group(4))
            hi = amount(m.group(3), m.group(4))
            if lo > hi:
                errors.append('Cận dưới lớn hơn cận trên.')
            if col:
                config['filters'].append({'column': col, 'operator': 'between', 'value': [lo, hi], 'type': 'number'})
            mark(*m.span())
        comparison = term + r'\s*(>=|<=|>|<|=|tren|duoi|lon hon|nho hon|it nhat|toi da|bang)\s*' + number
        for m in matches(comparison):
            if any(used[m.start():m.end()]):
                continue
            numeric_keys.add(key)
            col = column(key)
            op = {'>=': 'ge', '<=': 'le', '>': 'gt', '<': 'lt', '=': 'eq', 'tren': 'gt', 'duoi': 'lt', 'lon hon': 'gt', 'nho hon': 'lt', 'it nhat': 'ge', 'toi da': 'le', 'bang': 'eq'}[m.group(1)]
            if col:
                config['filters'].append({'column': col, 'operator': op, 'value': amount(m.group(2), m.group(3)), 'type': 'number'})
            mark(*m.span())

    # Match data values (including unquoted values), longest first. Keep originals.
    candidates = []
    for key in DIMENSIONS:
        for col in schema[key]:
            for value in df[col].dropna().unique():
                if isinstance(value, str) and normalize(value) and normalize(value) not in {'tong', 'trung binh', 'binh quan', 'dem', 'top', 'bao cao', 'sum', 'mean', 'average', 'count', 'theo', 'nam', 'thang', 'quy', 'va', 'hoac', 'cua', 'cho'}:
                    candidates.append((normalize(value), col, value))
    for value, col, original in sorted(candidates, key=lambda item: len(item[0]), reverse=True):
        for m in matches(_pattern([value])):
            if any(used[m.start():m.end()]):
                continue
            collisions = {(c, str(v)) for nv, c, v in candidates if nv == value}
            if len(collisions) > 1:
                questions.append(f'Giá trị {original!r} xuất hiện trong nhiều cột hoặc dạng viết; cần làm rõ.')
            config['filters'].append({'column': col, 'operator': 'eq', 'value': original, 'type': 'text'})
            mark(*m.span())

    # Metric phrases, not merely a domain keyword, establish an aggregation.
    average = bool(re.search(r'\b(trung binh|binh quan|average|mean)\b', text))
    identity_spans = [m.span() for m in matches(_pattern(['so luong nhan vien', 'so nhan vien', 'dem nhan vien', 'bao nhieu nhan vien', 'so don hang', 'dem don hang', 'bao nhieu don hang']))]
    for key, alias in METRIC_NAMES.items():
        found = [m for m in matches(_pattern(SCHEMA_ALIASES[key])) if not any(used[m.start():m.end()]) and not any(a <= m.start() and m.end() <= b for a, b in identity_spans)]
        if found:
            col = column(key)
            if col:
                op = 'mean' if average else 'sum'
                config['metrics'].append({'column': col, 'operation': op, 'alias': alias + ('Mean' if average else 'Sum')})
            for m in found:
                mark(*m.span())
    for key, phrases, alias in (
        ('employee_id', ('so nhan vien', 'so luong nhan vien', 'dem nhan vien', 'bao nhieu nhan vien'), 'Employees'),
        ('order_id', ('so don hang', 'dem don hang', 'bao nhieu don hang'), 'Orders'),
    ):
        for m in matches(_pattern(phrases)):
            if any(used[m.start():m.end()]):
                continue
            col = column(key)
            if col:
                config['metrics'].append({'column': col, 'operation': 'nunique', 'alias': alias})
            mark(*m.span())
    for m in matches(_pattern(['dem dong', 'so dong', 'bao nhieu dong', 'so ban ghi', 'dem ban ghi'])):
        config['metrics'].append({'operation': 'rows', 'alias': 'Rows'})
        mark(*m.span())
    if not config['metrics'] and numeric_keys:
        for key in sorted(numeric_keys):
            col = column(key)
            if col:
                op = 'mean' if average else 'sum'
                config['metrics'].append({'column': col, 'operation': op, 'alias': METRIC_NAMES[key] + ('Mean' if average else 'Sum')})
    # Explicit count of non-null metric cells is distinct from rows/nunique.
    if re.search(r'\bdem\b(?!\s+(?:dong|ban ghi|nhan vien|don hang)\b)', text) and config['metrics']:
        for metric in config['metrics']:
            if metric['operation'] in ('sum', 'mean'):
                metric['operation'] = 'count'
                metric['alias'] = metric['alias'].removesuffix('Sum').removesuffix('Mean') + 'Count'

    for m in matches(r'\btop\s+(\d+)\b'):
        mark(*m.span())
        for qualifier in matches(r'\bcao nhat\b'):
            mark(*qualifier.span())
        n = int(m.group(1))
        if n < 1 or n > 10000:
            errors.append('Top N phải trong 1–10000.')
        elif len(config['metrics']) != 1 or not config['group_by']:
            questions.append('Top N cần một chỉ tiêu và một nhóm xếp hạng rõ ràng.')
        else:
            config['top_n'] = {'column': config['metrics'][0]['alias'], 'n': n, 'ascending': False}

    # A named dimension must mean a group or a literal filter, not vanish.
    for key in DIMENSIONS:
        mentions = [m for m in matches(_pattern(SCHEMA_ALIASES[key])) if not any(used[m.start():m.end()])]
        if not mentions:
            continue
        cols = schema[key]
        filtered = any(f['column'] in cols for f in config['filters'])
        if not filtered:
            if re.search(r'\btop\s+\d+\b', text) or config['group_by']:
                col = column(key)
                if col and col not in config['group_by']:
                    config['group_by'].append(col)
            else:
                questions.append(f'B?n mu?n nh?m theo {key} hay l?c gi? tr? n?o?')
        for m in mentions:
            mark(*m.span())
    # Natural top N dimension phrases imply the ranking group.
    if re.search(r'\btop\s+\d+\b', text) and config['group_by'] and len(config['metrics']) == 1:
        n = int(re.search(r'\btop\s+(\d+)\b', text).group(1))
        if 1 <= n <= 10000:
            config['top_n'] = {'column': config['metrics'][0]['alias'], 'n': n, 'ascending': False}
            questions[:] = [q for q in questions if not normalize(q).startswith('top n')]

    # Multiple metrics with differently scoped operators require clarification.
    metric_columns = {m.get('column') for m in config['metrics'] if m.get('column')}
    if len(metric_columns) > 1:
        has_sum = bool(re.search(r'\b(tong|sum)\b', text))
        has_mean = bool(re.search(r'\b(trung binh|binh quan|average|mean)\b', text))
        has_count = bool(re.search(r'\bdem\b', text))
        if sum((has_sum, has_mean, has_count)) > 1:
            questions.append('Có nhiều chỉ tiêu với phép tính khác nhau. Hãy tách yêu cầu hoặc cấu hình từng chỉ tiêu trong Báo cáo nâng cao.')

    # Consume narrowly defined grammar, never unknown constraints or qualifiers.
    boilerplate = ('vui long', 'lam on', 'giup toi', 'cho toi', 'hay', 'toi muon', 'bao cao', 'thong ke',
                   'tinh', 'xuat', 'lap', 'tao', 'tong cong', 'tong', 'trung binh', 'binh quan', 'dem',
                   'la bao nhieu', 'bao nhieu', 'la', 'cua', 'cho', 'co', 'trong', 'vao', 'va', 'voi',
                   'du lieu', 'file', 'tep', 'tu file')
    # Dimension words are grammar only next to a matched literal value; unknown
    # values remain uncovered and therefore unsupported.
    for m in matches(_pattern(boilerplate + tuple(a for k in DIMENSIONS for a in SCHEMA_ALIASES[k]))):
        mark(*m.span())
    rest = ''.join(' ' if used[i] else c for i, c in enumerate(text))
    rest = re.sub(r'[\s,;:.!?"\'()]+', ' ', rest).strip()
    literal_columns = [f['column'] for f in config['filters'] if f['operator'] == 'eq' and f['type'] == 'text']
    if len(literal_columns) != len(set(literal_columns)):
        errors.append('Ch?a h? tr? nhi?u gi? tr? tr?n c?ng m?t c?t; c?n l?m r? logic l?c.')
    if rest:
        errors.append(f'Chưa hiểu đầy đủ điều kiện: {rest}.')
    if errors:
        return _result('unsupported', unsupported=errors)
    if not config['metrics']:
        questions.append('Bạn muốn tính tổng, trung bình hay đếm chỉ tiêu nào?')
    if questions:
        return _result('clarify', questions=list(dict.fromkeys(questions)))
    config['group_by'] = list(dict.fromkeys(config['group_by']))
    return _result('ready', source=name, config=config,
                   explanation=[f'Nguồn: {name}', 'Chỉ tiêu: ' + ', '.join(f"{m['operation']}({m.get('column', '*')}) → {m['alias']}" for m in config['metrics']),
                                f"Nhóm: {', '.join(config['group_by']) or 'toàn bộ'}; điều kiện: {len(config['filters'])}."])


def plan_report(text: str, sources: dict[str, pd.DataFrame]) -> dict:
    """Plan a bounded finance/HR report, asking rather than guessing a source.

    Examples: ``Tổng doanh thu theo sản phẩm năm 2025``;
    ``Lương trung bình theo phòng ban``; ``Đếm dòng theo trạng thái``.
    Returned configurations are data only and compatible with report_engine.
    """
    if not isinstance(text, str) or not text.strip():
        return _result('clarify', questions=['Bạn muốn lập báo cáo gì?'])
    if not sources:
        return _result('clarify', questions=['Chưa có nguồn dữ liệu; hãy chọn hoặc tải tệp Excel.'])
    normalized = normalize(text)
    explicit = [name for name in sources if re.search(_pattern([name]), normalized)]
    if len(explicit) > 1:
        return _result('unsupported', unsupported=['Chưa hỗ trợ kết hợp nhiều nguồn trong một báo cáo.'])
    names = explicit or list(sources)
    plans = [_plan_one(normalized, name, sources[name]) for name in names]
    ready = [p for p in plans if p['status'] == 'ready']
    if len(ready) > 1:
        return _result('clarify', questions=['Có nhiều nguồn phù hợp. Hãy chỉ rõ tên tệp: ' + ', '.join(p['source'] for p in ready)])
    if ready:
        return ready[0]
    clarify = [p for p in plans if p['status'] == 'clarify']
    return clarify[0] if clarify else plans[0]

