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
    'revenue': ('doanh so', 'doanh thu', 'revenue', 'sales', 'thanh tien'),
    'profit': ('loi nhuan', 'profit'),
    'cost': ('chi phi', 'cost', 'expense', 'expenses'),
    'quantity': ('so luong', 'quantity', 'qty'),
    'salary': ('quy luong', 'luong', 'salary', 'payroll', 'tien luong'),
    'product': ('san pham', 'product', 'product name', 'ten san pham'),
    'department': ('bo phan', 'phong ban', 'department', 'phong'),
    'region': ('khu vuc', 'region', 'vung', 'mien'),
    'status': ('trang thai', 'status'),
    'employee_name': ('ten nhan vien', 'ho ten', 'ho va ten', 'employee name', 'employee_name', 'name'),
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
    forbidden_text = re.sub(r'\b(lon hon|nho hon) hoac bang\b', r'\1 bang', text)
    for p in ('xoa', 'delete', 'remove', 'du bao', 'forecast', 'so sanh', 'tang truong', 'chenh lech', 'ket hop', 'ghep',
              'join', 'khong', 'ngoai tru', 'loai tru', 'khong tinh', 'khong bao gom', 'tru don', 'hoac'):
        if re.search(_pattern([p]), forbidden_text):
            return _result('unsupported', unsupported=[f'Chưa hỗ trợ điều kiện: {p}.'])

    # Expand only explicit coordinated grouping terms; unknown dimensions remain.
    dimension_terms = _pattern(tuple(a for k in DIMENSIONS for a in SCHEMA_ALIASES[k]) + ('thang', 'quy', 'nam'))
    text = re.sub(r'\btheo\s+tung\s+', 'theo ', text)
    group_clause = r'\btheo\s+' + dimension_terms + r'(?:(?:\s+va\s+|\s*,\s*)(?:tung\s+)?' + dimension_terms + r')+'
    def expand_group(match):
        return re.sub(r'(?:\s+va\s+|\s*,\s*)(?:tung\s+)?', ' theo ', match.group())
    text = re.sub(group_clause, expand_group, text)
    used = [False] * len(text)
    for m in matches(_pattern([name])):
        marker = re.search(r'\b(?:file|tep|nguon|du lieu)\s*$', text[:m.start()])
        if '.' in name or marker:
            mark(marker.start() if marker else m.start(), m.end())
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

    # Explicit employee listings preserve source rows, not salary aggregates.
    # Keep this grammar narrow: unfamiliar constraints still fail span coverage.
    detail_phrases = matches(r'\b(?:loc|liet ke|danh sach)\s+(?:cac\s+)?nhan vien\b')
    employee_detail = bool(detail_phrases)
    for m in detail_phrases:
        mark(*m.span())
    if employee_detail:
        if not schema['employee_id'] and not schema['employee_name']:
            questions.append('Cần cột mã hoặc tên nhân viên để liệt kê nhân viên.')
        if config['group_by']:
            questions.append('Danh sách chi tiết không tổng hợp theo nhóm; hãy chỉ rõ lọc từng dòng hoặc báo cáo tổng hợp.')

    # Absolute quarters and date ranges become inclusive row filters. They are
    # parsed before single months/years so their scope cannot be discarded.
    quarter_pattern = r'\bquy\s+(iv|iii|ii|i|[1-9])(?:\s*(?:/|-|nam)\s*(\d{4}))?\b'
    range_pattern = r'\btu\s+(?:ngay\s+)?(\d{1,2}/\d{1,2}/\d{4})\s+den\s+(?:ngay\s+)?(\d{1,2}/\d{1,2}/\d{4})\b'
    special_dates = [m for m in matches(range_pattern) + matches(quarter_pattern)
                     if not any(used[m.start():m.end()])]
    if len(special_dates) > 1:
        errors.append('Chỉ hỗ trợ một khoảng thời gian.')
    for m in special_dates:
        col = column('date')
        mark(*m.span())
        try:
            if re.match(range_pattern, m.group()):
                lo_date = pd.to_datetime(m.group(1), format='%d/%m/%Y')
                hi_date = pd.to_datetime(m.group(2), format='%d/%m/%Y')
            else:
                q = {'i': 1, 'ii': 2, 'iii': 3, 'iv': 4}.get(m.group(1))
                q = q or int(m.group(1))
                if not 1 <= q <= 4:
                    raise ValueError('quarter')
                year = int(m.group(2)) if m.group(2) else None
                if col and year is None:
                    from app.services.report_engine import _convert
                    years = _convert(df[col], 'date').dropna().dt.year.unique()
                    if len(years) == 1:
                        year = int(years[0])
                    else:
                        questions.append('Bạn muốn quý này của năm nào?')
                if not year:
                    continue
                lo_date = pd.Timestamp(year, q * 3 - 2, 1)
                hi_date = pd.Timestamp(year, q * 3, calendar.monthrange(year, q * 3)[1])
            if lo_date > hi_date:
                raise ValueError('reversed date interval')
            if col:
                vals = df[col].dropna().astype(str)
                ym = not vals.empty and vals.str.fullmatch(r'\d{4}-\d{2}').all()
                if ym and re.match(range_pattern, m.group()) and (
                        lo_date.day != 1 or hi_date.day != calendar.monthrange(hi_date.year, hi_date.month)[1]):
                    questions.append('Nguồn chỉ có dữ liệu theo tháng; không thể lọc chính xác khoảng ngày lẻ. Hãy chọn trọn tháng hoặc dùng nguồn có ngày chi tiết.')
                    continue
                config['filters'].append({'column': col, 'operator': 'between',
                    'value': [lo_date.strftime('%Y-%m' if ym else '%Y-%m-%d'),
                              hi_date.strftime('%Y-%m' if ym else '%Y-%m-%d') + ('' if ym else ' 23:59:59.999999999')],
                    'type': 'text' if ym else 'date'})
        except (ValueError, OverflowError):
            errors.append('Quý hoặc khoảng ngày không hợp lệ.')

    # Dates: calendar month requires a year unless a single data year is certain.
    date_pattern = r'\bthang\s+(\d{1,2})(?:\s*(?:/|-|nam)\s*(\d{4}))?\b|\bnam\s+(\d{4})\b|\b(20\d{2}|19\d{2})\b'
    date_matches = [m for m in matches(date_pattern) if not any(used[m.start():m.end()])]
    if date_matches:
        col = column('date')
        if len(date_matches) > 1 or special_dates:
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

    # A threshold on an aggregate is HAVING, not a row filter. The engine's
    # supported row filters must never silently stand in for aggregate scope.
    threshold = r'(?:>=|<=|>|<|=|tren|duoi|lon hon|nho hon|it nhat|toi da|toi thieu|bang)'
    if re.search(r'\b(?:tong|trung binh|binh quan|sum|mean|average)\s+' +
                 _pattern(tuple(a for k in METRIC_NAMES for a in SCHEMA_ALIASES[k])) +
                 r'\s*' + threshold + r'\s*\d', text):
        return _result('clarify', questions=['Bạn muốn lọc theo giá trị tổng hợp hay từng dòng? Hãy chỉ rõ điều kiện lọc từng dòng.'])

    for key in METRIC_NAMES:
        metric_term = _pattern(SCHEMA_ALIASES[key])
        for condition in matches(metric_term + r'\s*' + threshold + r'\s*\d'):
            before = text[:condition.start()]
            if config['group_by'] and re.search(r'\btheo\b', before) and re.search(metric_term, before):
                return _result('clarify', questions=['Điều kiện này áp dụng cho từng dòng hay cho kết quả sau khi nhóm?'])

    numeric_keys = set()
    # Numeric conditions are bound to explicitly mentioned metric columns.
    number = r'(\d{1,3}(?:\.\d{3})+(?:,\d+)?|\d+(?:[.,]\d+)?)\s*(ty|trieu|nghin|ngan|million|billion)?(?![\w.,]\d)'
    def amount(value, unit):
        if re.fullmatch(r'\d{1,3}(?:\.\d{3})+(?:,\d+)?', value):
            value = value.replace('.', '')
        return float(value.replace(',', '.')) * {'ty': 1e9, 'billion': 1e9, 'trieu': 1e6, 'million': 1e6, 'nghin': 1e3, 'ngan': 1e3, None: 1}[unit]
    for key in METRIC_NAMES:
        term = _pattern(SCHEMA_ALIASES[key])
        between = term + r'\s+tu\s+' + number + r'\s+den\s+' + number
        for m in matches(between):
            if any(used[m.start():m.end()]):
                continue
            numeric_keys.add(key)
            col = column(key)
            lo = amount(m.group(1), m.group(2) or m.group(4))
            hi = amount(m.group(3), m.group(4))
            if lo > hi:
                errors.append('Cận dưới lớn hơn cận trên.')
            if col:
                config['filters'].append({'column': col, 'operator': 'between', 'value': [lo, hi], 'type': 'number'})
            mark(*m.span())
        comparison = term + r'\s*(>=|<=|>|<|=|lon hon hoac bang|nho hon hoac bang|lon hon|nho hon|tren|duoi|it nhat|toi thieu|toi da|bang)\s*' + number
        for m in matches(comparison):
            if any(used[m.start():m.end()]):
                continue
            numeric_keys.add(key)
            col = column(key)
            op = {'>=': 'ge', '<=': 'le', '>': 'gt', '<': 'lt', '=': 'eq', 'tren': 'gt', 'duoi': 'lt', 'lon hon': 'gt', 'nho hon': 'lt', 'it nhat': 'ge', 'toi thieu': 'ge', 'toi da': 'le', 'lon hon hoac bang': 'ge', 'nho hon hoac bang': 'le', 'bang': 'eq'}[m.group(1)]
            if col:
                config['filters'].append({'column': col, 'operator': op, 'value': amount(m.group(2), m.group(3)), 'type': 'number'})
            mark(*m.span())

    # Match data values (including unquoted values), longest first. Keep originals.
    candidates = []
    reserved_values = {'cao nhat', 'thap nhat', 'lon nhat', 'nho nhat', 'it nhat',
                       'toi da', 'toi thieu', 'gia tri', 'tong cong', 'trung binh',
                       'binh quan', 'vui long', 'nhan vien', 'don hang', 'nhan su',
                       'hay', 'lam on', 'giup toi', 'giup minh', 'cho toi', 'cho minh',
                       'cho biet', 'ban hay', 'toi muon', 'toi can', 'xem', 'nhe',
                       'tinh', 'xuat', 'lap', 'tao', 'la', 'co', 'trong', 'vao', 'voi',
                       'du lieu', 'file', 'tep', 'tu file', 'loc', 'liet ke', 'danh sach', 'cac'}
    reserved_values.update(normalize(a) for aliases in SCHEMA_ALIASES.values() for a in aliases)
    for key in DIMENSIONS:
        for col in schema[key]:
            for value in df[col].dropna().unique():
                if isinstance(value, str) and normalize(value) and (normalize(value) not in reserved_values or (key == 'department' and normalize(value) == 'nhan su')) and normalize(value) not in {'tong', 'trung binh', 'binh quan', 'dem', 'top', 'bao cao', 'sum', 'mean', 'average', 'count', 'theo', 'nam', 'thang', 'quy', 'va', 'hoac', 'cua', 'cho'}:
                    candidates.append((normalize(value), col, value))
    for value, col, original in sorted(candidates, key=lambda item: len(item[0]), reverse=True):
        for m in matches(_pattern([value])):
            if value == 'nhan su' and any(
                phrase.start() <= m.start() and m.end() <= phrase.end()
                for phrase in matches(_pattern(['so luong nhan su', 'dem nhan su', 'bao nhieu nhan su']))
            ):
                continue
            if any(used[m.start():m.end()]):
                continue
            collisions = {(c, str(v)) for nv, c, v in candidates if nv == value}
            if len(collisions) > 1:
                questions.append(f'Giá trị {original!r} xuất hiện trong nhiều cột hoặc dạng viết; cần làm rõ.')
            config['filters'].append({'column': col, 'operator': 'eq', 'value': original, 'type': 'text'})
            mark(*m.span())

    # Metric phrases, not merely a domain keyword, establish an aggregation.
    average = bool(re.search(r'\b(trung binh|binh quan|average|mean)\b', text))
    scalar_ops = []
    for m in matches(r'\b(?:gia tri\s+)?(lon nhat|nho nhat|toi da|toi thieu|min|max|minimum|maximum)\s+(?:cua\s+)?(' + _pattern(tuple(a for k in METRIC_NAMES for a in SCHEMA_ALIASES[k])) + r')'):
        scalar_ops.append((m, 'min' if m.group(1) in ('nho nhat', 'toi thieu', 'min', 'minimum') else 'max'))
    explicit_scalar = scalar_ops[0][1] if len(scalar_ops) == 1 else None
    if scalar_ops and average:
        questions.append('Giá trị nhỏ nhất/lớn nhất và trung bình có phạm vi tính khác nhau; hãy làm rõ.')
    if len(scalar_ops) > 1:
        questions.append('Hãy chỉ rõ từng phép tổng hợp nhỏ nhất/lớn nhất riêng biệt.')
    identity_spans = [m.span() for m in matches(_pattern(['so luong nhan vien', 'so nhan vien', 'dem nhan vien', 'dem so nhan vien', 'tong so nhan vien', 'so luong nhan su', 'bao nhieu nhan vien', 'so don hang', 'dem don hang', 'bao nhieu don hang']))]
    for key, alias in METRIC_NAMES.items():
        found = [m for m in matches(_pattern(SCHEMA_ALIASES[key])) if not any(used[m.start():m.end()]) and not any(a <= m.start() and m.end() <= b for a, b in identity_spans)]
        if found:
            col = column(key)
            if col:
                op = explicit_scalar or ('mean' if average else 'sum')
                config['metrics'].append({'column': col, 'operation': op, 'alias': alias + op.title()})
            for m in found:
                mark(*m.span())
    for m, _ in scalar_ops:
        mark(*m.span())
    for key, phrases, alias in (
        ('employee_id', ('so nhan vien', 'so luong nhan vien', 'dem nhan vien', 'dem so nhan vien', 'tong so nhan vien', 'so luong nhan su', 'bao nhieu nhan vien'), 'Employees'),
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
    if not config['metrics'] and numeric_keys and not employee_detail:
        for key in sorted(numeric_keys):
            col = column(key)
            if col:
                op = explicit_scalar or ('mean' if average else 'sum')
                config['metrics'].append({'column': col, 'operation': op, 'alias': METRIC_NAMES[key] + op.title()})
    # Explicit count of non-null metric cells is distinct from rows/nunique.
    if re.search(r'\bdem\b(?!\s+(?:dong|ban ghi|nhan vien|don hang)\b)', text) and config['metrics']:
        for metric in config['metrics']:
            if metric['operation'] in ('sum', 'mean'):
                metric['operation'] = 'count'
                metric['alias'] = metric['alias'].removesuffix('Sum').removesuffix('Mean') + 'Count'

    # Ranking qualifiers are grammar only in an explicit, bounded ranking.
    highest = ('cao nhat', 'lon nhat', 'nhieu nhat', 'highest', 'largest', 'greatest', 'most')
    lowest = ('thap nhat', 'nho nhat', 'it nhat', 'lowest', 'smallest', 'least')
    qualifiers = [m for m in matches(_pattern(highest + lowest))
                  if not any(used[m.start():m.end()])]
    tops = matches(r'\btop\s+(\d+)\b')
    ranking = bool(tops or qualifiers)
    directions = {normalize(m.group()) in lowest for m in qualifiers}
    if len(directions) > 1 or len(tops) > 1:
        return _result('clarify', questions=['Bạn muốn xếp hạng cao nhất hay thấp nhất, và lấy bao nhiêu kết quả?'])

    # A named dimension must mean a group or a literal filter, not vanish.
    for key in DIMENSIONS:
        mentions = [m for m in matches(_pattern(SCHEMA_ALIASES[key])) if not any(used[m.start():m.end()])]
        if not mentions:
            continue
        cols = schema[key]
        filtered = any(f['column'] in cols for f in config['filters'])
        if not filtered:
            if ranking or config['group_by']:
                col = column(key)
                if col and col not in config['group_by']:
                    config['group_by'].append(col)
            else:
                questions.append(f'Bạn muốn nhóm theo {key} hay lọc giá trị nào?')
        for m in mentions:
            mark(*m.span())

    # Employee rankings must preserve identity, not merge people sharing a name.
    employees = [m for m in matches(_pattern(['nhan vien', 'employee', 'employees']))
                 if not any(used[m.start():m.end()])]
    if ranking and employees:
        ids, names = schema['employee_id'], schema['employee_name']
        if ids:
            identity = column('employee_id')
            if identity:
                if df[identity].isna().any():
                    questions.append('Mã nhân viên bị thiếu; cần xác định danh tính trước khi xếp hạng.')
                config['group_by'].append(identity)
                if df[identity].duplicated().any() and not re.search(r'\b(tong|trung binh|binh quan|sum|mean|average)\b', text):
                    questions.append('Một nhân viên có nhiều dòng; hãy chỉ rõ tính tổng hay trung bình lương trước khi xếp hạng.')
            if names:
                display = column('employee_name')
                if display and identity:
                    if df.groupby(identity)[display].nunique().gt(1).any():
                        questions.append('Một mã nhân viên có nhiều tên; hãy làm rõ danh tính trước khi xếp hạng.')
                    # Null display names must not drop an otherwise identified person.
                    if not df[display].isna().any():
                        config['group_by'].append(display)
        elif names:
            display = column('employee_name')
            if display:
                if df[display].isna().any() or df[display].duplicated().any():
                    questions.append('Tên nhân viên trùng hoặc thiếu; cần mã nhân viên để phân biệt danh tính.')
                config['group_by'].append(display)
        else:
            questions.append('Cần cột mã hoặc tên nhân viên để xếp hạng từng người.')
        for m in employees:
            mark(*m.span())

    if ranking and config.get('date_group') and any(g != config['date_group']['alias'] for g in config['group_by']):
        questions.append('Bạn muốn xếp hạng chung mọi kỳ hay xếp hạng riêng trong từng kỳ?')

    if ranking:
        n = int(tops[0].group(1)) if tops else 1
        if n < 1 or n > 10000:
            errors.append('Top N phải trong 1–10000.')
        elif len(config['metrics']) != 1 or not config['group_by']:
            # A bare metric superlative has no safe entity to rank.
            if tops or employees or config['group_by']:
                questions.append('Top N cần một chỉ tiêu và một nhóm xếp hạng rõ ràng.')
            else:
                errors.append('Cần chỉ rõ nhóm để xếp hạng chỉ tiêu.')
        else:
            config['top_n'] = {'column': config['metrics'][0]['alias'], 'n': n,
                               'ascending': next(iter(directions), False)}
        for m in tops + qualifiers:
            mark(*m.span())
        # "which" is meaningful only when attached to a ranking entity.
        if config['group_by'] or employees:
            for m in matches(r'\bnao\b'):
                mark(*m.span())

    # Multiple operations on the same metric must not silently collapse to one.
    has_sum_op = bool(re.search(r'\b(?:tong|sum)\b', text))
    has_mean_op = bool(re.search(r'\b(?:trung binh|binh quan|average|mean)\b', text))
    has_count_op = bool(re.search(r'\bdem\b(?!\s+(?:dong|ban ghi|nhan vien|so nhan vien|don hang)\b)', text))
    if config['metrics'] and sum((has_sum_op, has_mean_op, has_count_op)) > 1:
        questions.append('Có nhiều phép tính cho chỉ tiêu; hãy tách yêu cầu hoặc cấu hình từng phép tính trong Báo cáo nâng cao.')

    # Multiple metrics with differently scoped operators require clarification.
    metric_columns = {m.get('column') for m in config['metrics'] if m.get('column')}
    if scalar_ops and len(metric_columns) > 1:
        questions.append('Phép tính nhỏ nhất/lớn nhất phải chỉ rõ một chỉ tiêu duy nhất.')
    if len(metric_columns) > 1:
        has_sum = bool(re.search(r'\b(tong|sum)\b', text))
        has_mean = bool(re.search(r'\b(trung binh|binh quan|average|mean)\b', text))
        has_count = bool(re.search(r'\bdem\b', text))
        scoped_operator = re.search(r'\b(trung binh|binh quan|average|mean|dem|tong|sum)\b', text)
        preceding_metric = scoped_operator and any(
            m.start() < scoped_operator.start() for m in matches(
                _pattern(tuple(a for k in METRIC_NAMES for a in SCHEMA_ALIASES[k]))))
        if sum((has_sum, has_mean, has_count)) > 1 or preceding_metric:
            questions.append('Có nhiều chỉ tiêu với phép tính khác nhau. Hãy tách yêu cầu hoặc cấu hình từng chỉ tiêu trong Báo cáo nâng cao.')

    # Consume narrowly defined grammar, never unknown constraints or qualifiers.
    boilerplate = ('vui long', 'lam on', 'giup toi', 'giup minh', 'cho toi', 'cho minh', 'cho biet', 'ban hay', 'hay', 'toi muon', 'toi can', 'xem', 'nhe', 'bao cao', 'thong ke',
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
        errors.append('Chưa hỗ trợ nhiều giá trị trên cùng một cột; cần làm rõ logic lọc.')
    if rest:
        errors.append(f'Chưa hiểu đầy đủ điều kiện: {rest}.')
    if errors:
        return _result('unsupported', unsupported=errors)
    if employee_detail and (config['metrics'] or ranking):
        questions.append('Danh sách chi tiết không tính tổng hay xếp hạng; hãy tách yêu cầu tổng hợp riêng.')
    if not config['metrics'] and not employee_detail:
        questions.append('Bạn muốn tính tổng, trung bình hay đếm chỉ tiêu nào?')
    if questions:
        return _result('clarify', questions=list(dict.fromkeys(questions)))
    config['group_by'] = list(dict.fromkeys(config['group_by']))
    if employee_detail:
        return _result('ready', source=name, config=config,
                       explanation=[f'Nguồn: {name}', 'Danh sách nhân viên chi tiết (không tổng hợp).',
                                    f"Điều kiện: {len(config['filters'])}."])
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
    normalized = re.sub(r'\bca nam(?=\s+\d{4}\b)', 'nam', normalized)
    # A short source label may also be a data literal or metric alias. Require
    # an explicit source marker rather than consuming it as a filename.
    for name, frame in sources.items():
        if '.' in name or not isinstance(frame, pd.DataFrame) or not frame.columns.is_unique:
            continue
        for match in re.finditer(_pattern([name]), normalized):
            if re.search(r'\b(?:file|tep|nguon|du lieu)\s*$', normalized[:match.start()]):
                continue
            dimension_cols = [c for c in frame.columns if isinstance(c, str) and any(
                normalize(c) in {normalize(a) for a in SCHEMA_ALIASES[k]} for k in DIMENSIONS)]
            if any(frame[c].dropna().map(lambda v: normalize(v) == normalize(name)).any() for c in dimension_cols):
                return _result('clarify', questions=['Tên nguồn trùng với giá trị dữ liệu. Hãy ghi rõ file/nguồn hoặc giá trị cần lọc.'])
    explicit = [name for name in sources if any(
        '.' in name or re.search(r'\b(?:file|tep|nguon|du lieu)\s*$', normalized[:m.start()])
        for m in re.finditer(_pattern([name]), normalized))]
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

