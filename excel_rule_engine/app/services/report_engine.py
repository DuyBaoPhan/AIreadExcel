"""Bounded, deterministic pandas reporting; no expressions or executable config.

Version 1 configs contain filters, filter_logic, date_group, group_by, metrics,
pivot, top_n, comparison. Missing metrics means detail-only (empty summary).
Filters never mutate input; explicit conversions reject invalid non-null values.
Ambiguous date strings use day-first parsing; ISO dates remain year-first. Comparison bounds are inclusive timestamps;
summary columns are ``alias_current/previous/delta/percent`` (percent in 0..100
units). Missing groups remain NaN, never invented zeroes. Pivot is exclusive with
metrics/comparison and labels are JSON-encoded tuples to avoid collisions.
Limits apply before and after joins and before pivot allocation.
"""
from __future__ import annotations

import json
import math
import re
import pandas as pd
from pandas.api.types import is_bool_dtype, is_datetime64_any_dtype, is_complex_dtype

MAX_ROWS = 100_000
MAX_COLUMNS = 200
MAX_SUMMARY_CELLS = 1_000_000
MAX_CONFIG_BYTES = 100 * 1024
MAX_MEMORY_BYTES = 200 * 1024 * 1024
OPS = {'eq', 'ne', 'gt', 'ge', 'lt', 'le', 'contains', 'in', 'between', 'is_null', 'not_null'}
AGGS = {'sum', 'mean', 'min', 'max', 'count', 'nunique', 'rows'}


def _require(condition, message):
    if not condition:
        raise ValueError(message)


def _frame(df):
    _require(isinstance(df, pd.DataFrame), 'Expected a DataFrame')
    _require(len(df) <= MAX_ROWS and len(df.columns) <= MAX_COLUMNS, 'Data exceeds row/column limits')
    _require(df.columns.is_unique and all(isinstance(c, str) for c in df.columns), 'Column names must be unique strings')
    _require(df.memory_usage(index=True, deep=True).sum() <= MAX_MEMORY_BYTES, 'Data exceeds memory limit')


def _cols(columns, available, label):
    _require(isinstance(columns, list) and all(isinstance(c, str) for c in columns), f'{label} must be a list of column names')
    _require(len(columns) == len(set(columns)), f'{label} contains duplicate columns')
    _require(all(c in available for c in columns), f'{label} contains unknown columns')


def _keys(obj, allowed, label):
    _require(isinstance(obj, dict), f'{label} must be an object')
    _require(not (obj.keys() - allowed), f'{label} has unknown fields: {obj.keys() - allowed}')


def _validate_config(config):
    _keys(config, {'version', 'filters', 'filter_logic', 'date_group', 'group_by', 'metrics', 'pivot', 'top_n', 'comparison'}, 'config')
    _require(type(config.get('version')) is int and config['version'] == 1, 'Config version must be 1')
    _require(config.get('filter_logic', 'and') in ('and', 'or'), 'filter_logic must be and or or')
    _require(isinstance(config.get('filters', []), list), 'filters must be a list')
    for f in config.get('filters', []):
        _keys(f, {'column', 'operator', 'value', 'type'}, 'filter')
        _require(isinstance(f.get('column'), str) and isinstance(f.get('operator'), str) and f.get('operator') in OPS, 'Invalid filter column/operator')
        _require(isinstance(f.get('type', 'text'), str) and f.get('type', 'text') in {'number', 'date', 'text'}, 'Invalid filter type')
        op = f['operator']
        if op not in {'is_null', 'not_null'}:
            _require('value' in f, 'Filter value required')
        if op in {'in', 'between'}:
            _require(isinstance(f.get('value'), list), f'{op} requires a list')
        if op == 'between':
            _require(len(f['value']) == 2, 'between requires two bounds')
    group = config.get('group_by', [])
    _require(isinstance(group, list) and all(isinstance(x, str) for x in group) and len(set(group)) == len(group), 'Invalid group_by')
    metrics = config.get('metrics', [])
    _require(isinstance(metrics, list), 'metrics must be a list')
    aliases = []
    for metric in metrics:
        _keys(metric, {'column', 'operation', 'alias'}, 'metric')
        _require(isinstance(metric.get('operation'), str) and metric.get('operation') in AGGS, 'Invalid metric operation')
        _require(isinstance(metric.get('alias'), str) and bool(metric['alias']), 'Metric alias required')
        if metric['operation'] != 'rows':
            _require(isinstance(metric.get('column'), str), 'Metric column required')
        aliases.append(metric['alias'])
    _require(len(set(aliases)) == len(aliases) and not set(aliases).intersection(group), 'Duplicate/colliding metric aliases')
    if 'date_group' in config:
        d = config['date_group']
        _keys(d, {'column', 'frequency', 'alias'}, 'date_group')
        _require(isinstance(d.get('column'), str) and isinstance(d.get('frequency'), str) and d.get('frequency') in {'month', 'quarter', 'year', 'day'}, 'Invalid date_group')
        _require(isinstance(d.get('alias', 'Period'), str) and bool(d.get('alias', 'Period')), 'Invalid date_group alias')
    if 'pivot' in config:
        p = config['pivot']
        _keys(p, {'index', 'columns', 'values', 'operation'}, 'pivot')
        _require(not metrics and 'comparison' not in config and not group, 'pivot cannot be combined with metrics, group_by or comparison')
        _require(isinstance(p.get('index'), list) and all(isinstance(x, str) for x in p['index']), 'pivot index must be a list')
        _require(isinstance(p.get('columns'), str) and isinstance(p.get('operation'), str) and p.get('operation') in AGGS, 'Invalid pivot')
        if p['operation'] != 'rows':
            _require(isinstance(p.get('values'), str), 'pivot values required')
    if 'top_n' in config:
        t = config['top_n']
        _keys(t, {'column', 'n', 'ascending'}, 'top_n')
        _require(isinstance(t.get('column'), str) and type(t.get('n')) is int and 1 <= t['n'] <= MAX_ROWS, 'Invalid top_n')
        _require(type(t.get('ascending', False)) is bool, 'top_n ascending must be boolean')
    if 'comparison' in config:
        c = config['comparison']
        _keys(c, {'date_column', 'current_start', 'current_end', 'previous_start', 'previous_end'}, 'comparison')
        _require(isinstance(c.get('date_column'), str) and bool(metrics), 'comparison requires date_column and metrics')
        bounds = [_date_scalar(c.get(k)) for k in ['current_start', 'current_end', 'previous_start', 'previous_end']]
        a, b, x, y = bounds
        _require(a <= b and x <= y, 'Comparison bounds are reversed')
        _require(b < x or y < a, 'Comparison windows overlap')
        names = [f'{alias}_{suffix}' for alias in aliases for suffix in ('current', 'previous', 'delta', 'percent')]
        _require(not set(names).intersection(group), 'Comparison aliases collide with group_by')
    return config


def serialize_config(config: dict) -> bytes:
    """Validate and encode JSON only; reject nonfinite numbers and payloads >100 KiB."""
    _validate_config(config)
    try:
        raw = json.dumps(config, ensure_ascii=False, allow_nan=False).encode('utf-8')
    except (TypeError, ValueError) as exc:
        raise ValueError('Config must be finite JSON data') from exc
    _require(len(raw) <= MAX_CONFIG_BYTES, 'Config exceeds 100 KiB')
    return raw


def load_config(raw: bytes) -> dict:
    """Decode bounded UTF-8 JSON; reject duplicate keys and unsupported versions."""
    _require(isinstance(raw, bytes) and len(raw) <= MAX_CONFIG_BYTES, 'Config must be bytes of at most 100 KiB')
    def pairs(items):
        result = {}
        for k, v in items:
            _require(k not in result, 'Duplicate JSON key')
            result[k] = v
        return result
    try:
        value = json.loads(raw.decode('utf-8-sig'), object_pairs_hook=pairs, parse_constant=lambda v: (_ for _ in ()).throw(ValueError('Nonfinite JSON number')))
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError('Invalid JSON config') from exc
    serialize_config(value)
    return value


def _date_scalar(value):
    _require(value is not None and not isinstance(value, (bool, int, float, list, dict)), 'Date bounds must be date strings')
    try:
        # ISO year-first dates are unambiguous; pandas dayfirst would invert them.
        iso = isinstance(value, str) and re.match(r'^\d{4}-\d{2}-\d{2}(?:$|[T ])', value)
        out = pd.to_datetime(value, dayfirst=not bool(iso), errors='raise')
        _require(not pd.isna(out) and out.tzinfo is None, 'Date must be non-null and timezone-naive')
        return out
    except (TypeError, ValueError) as exc:
        raise ValueError(f'Invalid date: {value!r}') from exc


def _convert(series, kind):
    try:
        if kind == 'number':
            _require(not is_bool_dtype(series) and not is_datetime64_any_dtype(series) and not is_complex_dtype(series) and not series.dropna().map(lambda v: isinstance(v, (bool, complex, pd.Timestamp))).any(), 'Boolean/date/complex is not numeric')
            result = pd.to_numeric(series, errors='raise')
            _require(not is_bool_dtype(result) and not is_complex_dtype(result), 'Boolean/complex is not numeric')
            _require(not result.dropna().map(lambda v: not math.isfinite(v)).any(), 'Nonfinite numeric value')
            return result
        if kind == 'date':
            _require(not is_bool_dtype(series) and not series.dropna().map(lambda v: isinstance(v, (int, float, bool))).any(), 'Numeric dates are ambiguous')
            # Per-value parsing avoids pandas mixed-format inference silently rejecting valid dates.
            return series.map(lambda v: pd.NaT if pd.isna(v) else _date_scalar(v)).astype('datetime64[ns]')
        return series.astype('string')
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError(f'Invalid {kind} values in column {series.name!r}: {exc}') from exc


def _filtered(df, config):
    masks = []
    for f in config.get('filters', []):
        _cols([f['column']], df.columns, 'filter')
        s = df[f['column']]
        op = f['operator']
        if op in {'is_null', 'not_null'}:
            mask = s.isna() if op == 'is_null' else s.notna()
        else:
            kind = f.get('type', 'text')
            s = _convert(s, kind)
            raw = f['value'] if op in {'in', 'between'} else [f['value']]
            values = _convert(pd.Series(raw, dtype=object), kind).tolist()
            _require(all(not pd.isna(v) for v in values), 'Use is_null/not_null for null filters')
            v = values[0] if values else None
            if op == 'in': mask = s.isin(values)
            elif op == 'between':
                _require(values[0] <= values[1], 'between bounds are reversed')
                mask = s.between(*values)
            elif op == 'contains':
                _require(kind == 'text', 'contains requires text type')
                mask = s.str.contains(v, regex=False, na=False)
            else: mask = getattr(s, op)(v)
            mask = mask.fillna(False) & s.notna()
        masks.append(mask)
    if not masks:
        return df.copy(deep=True)
    mask = masks[0]
    for other in masks[1:]:
        mask = mask & other if config.get('filter_logic', 'and') == 'and' else mask | other
    return df.loc[mask].copy(deep=True)


def _aggregate(df, groups, metrics):
    _cols(groups, df.columns, 'group_by')
    estimated_rows = len(df[groups].drop_duplicates()) if groups else 1
    _require((len(groups) + len(metrics)) <= MAX_COLUMNS and estimated_rows * (len(groups) + len(metrics)) <= MAX_SUMMARY_CELLS, 'Summary exceeds limits')
    for m in metrics:
        if m['operation'] != 'rows':
            _cols([m['column']], df.columns, 'metric')
    if not metrics:
        return pd.DataFrame()
    result = None
    for m in metrics:
        op, alias = m['operation'], m['alias']
        # Convert a private metric series, never the grouping keys or siblings.
        values = None if op == 'rows' else df[m['column']]
        if op in {'sum', 'mean'}:
            values = _convert(values, 'number')
        if groups:
            if op == 'rows':
                series = df.groupby(groups, dropna=False, observed=True, sort=False).size()
            else:
                temporary = '__metric_value__'
                while temporary in df.columns:
                    temporary += '_'
                work = df[groups].copy()
                work[temporary] = values
                target = work.groupby(groups, dropna=False, observed=True, sort=False)[temporary]
                series = target.sum(min_count=1) if op == 'sum' else getattr(target, op)()
            series = series.rename(alias)
            result = series.to_frame() if result is None else result.join(series)
        else:
            value = len(df) if op == 'rows' else values.sum(min_count=1) if op == 'sum' else getattr(values, op)()
            if result is None:
                result = pd.DataFrame(index=[0])
            result[alias] = [value]
    return result.reset_index() if groups else result


def _pivot(df, p):
    index, column = p['index'], p['columns']
    _cols(index + [column], df.columns, 'pivot')
    _require(column not in index, 'pivot column cannot be an index')
    # Estimate before unstacking, including missing category values.
    rows = max(1, len(df[index].drop_duplicates())) if index else 1
    columns = df[column].nunique(dropna=False)
    _require(rows * (columns + len(index)) <= MAX_SUMMARY_CELLS and columns + len(index) <= MAX_COLUMNS, 'Pivot exceeds limits')
    alias = '__pivot_value__'
    while alias in df.columns: alias += '_'
    metric = {'operation': p['operation'], 'alias': alias, 'column': p.get('values')}
    aggregate = _aggregate(df, index + [column], [metric])
    if aggregate.empty: return pd.DataFrame(columns=index)
    if index:
        result = aggregate.set_index(index + [column])[alias].unstack(column)
    else:
        result = pd.DataFrame([aggregate.set_index(column)[alias].to_dict()])
    result.columns = [json.dumps([p.get('values', 'rows'), None if pd.isna(c) else str(c)], ensure_ascii=False) for c in result.columns]
    _require(not set(result.columns).intersection(index) and result.columns.is_unique, 'Pivot output labels collide')
    return result.reset_index() if index else result


def run_report(df: pd.DataFrame, config: dict) -> dict:
    """Return independent filtered/derived data, summary and human-readable warnings.

    top_n applies to summary when one is configured, otherwise detail. Source is
    never mutated. Missing sum values stay NaN. Null group keys are preserved.
    All invalid configuration/data raise ValueError rather than silently coerce.
    """
    _frame(df)
    serialize_config(config)
    warnings = []
    data = _filtered(df, config)
    if 'date_group' in config:
        d = config['date_group']
        _cols([d['column']], data.columns, 'date_group')
        alias = d.get('alias', 'Period')
        _require(alias not in data.columns, 'date_group alias collides with existing column')
        freq = {'month': 'M', 'quarter': 'Q', 'year': 'Y', 'day': 'D'}[d['frequency']]
        dates = _convert(data[d['column']], 'date')
        data[alias] = dates.dt.to_period(freq).astype('string')
    groups, metrics = config.get('group_by', []), config.get('metrics', [])
    _cols(groups, data.columns, 'group_by')
    if 'comparison' in config:
        c = config['comparison']
        _cols([c['date_column']], data.columns, 'comparison')
        dates = _convert(data[c['date_column']], 'date')
        estimated_rows = len(data[groups].drop_duplicates()) if groups else 1
        _require(len(groups) + 4 * len(metrics) <= MAX_COLUMNS and estimated_rows * (len(groups) + 4 * len(metrics)) <= MAX_SUMMARY_CELLS, 'Comparison summary exceeds limits')
        summaries = []
        for window in ('current', 'previous'):
            mask = dates.between(_date_scalar(c[f'{window}_start']), _date_scalar(c[f'{window}_end']))
            s = _aggregate(data.loc[mask], groups, metrics)
            summaries.append(s.rename(columns={m['alias']: f"{m['alias']}_{window}" for m in metrics}))
        if groups:
            summary = summaries[0].merge(summaries[1], on=groups, how='outer', validate='one_to_one')
        else: summary = pd.concat(summaries, axis=1)
        ordered = list(groups)
        for m in metrics:
            a = m['alias']
            curr, prev = summary[a + '_current'], summary[a + '_previous']
            try:
                summary[a + '_delta'] = curr - prev
                denominator = prev.where(prev.ne(0))
                summary[a + '_percent'] = (curr - prev) / denominator * 100
            except TypeError as exc:
                raise ValueError('Comparison metrics must have numeric results') from exc
            if prev.eq(0).any(): warnings.append(f'{a}: percent change undefined where previous value is zero')
            ordered += [a + '_' + suffix for suffix in ('current', 'previous', 'delta', 'percent')]
        summary = summary[ordered]
    elif 'pivot' in config:
        summary = _pivot(data, config['pivot'])
    else:
        summary = _aggregate(data, groups, metrics)
    has_summary = bool(metrics) or 'pivot' in config
    if 'top_n' in config:
        t = config['top_n']
        target = summary if has_summary else data
        _cols([t['column']], target.columns, 'top_n')
        target = target.sort_values(t['column'], ascending=t.get('ascending', False), kind='stable').head(t['n']).copy()
        if has_summary: summary = target
        else: data = target
    _frame(data)
    _frame(summary)
    _require(summary.size <= MAX_SUMMARY_CELLS, 'Summary exceeds cell limit')
    if data.empty: warnings.append('No rows match the report filters')
    return {'data': data, 'summary': summary, 'warnings': warnings}


def join_sources(left: pd.DataFrame, right: pd.DataFrame, left_on: list, right_on: list,
                 how: str = 'left', relationship: str = 'many_to_one') -> tuple:
    """Validated bounded join with explicit ``_right`` suffix; never many-to-many.

    Null keys are rejected on both sides (pandas otherwise matches nulls).
    Allowed relationships: one_to_one, one_to_many, many_to_one; joins: left,
    inner, outer. Overlapping output names/suffix collisions are rejected.
    Unmatched keys produce a warning; input DataFrames remain unchanged.
    """
    _frame(left); _frame(right)
    _cols(left_on, left.columns, 'left_on'); _cols(right_on, right.columns, 'right_on')
    _require(bool(left_on) and len(left_on) == len(right_on), 'Join keys must have equal nonzero lengths')
    _require(how in {'left', 'inner', 'outer'}, 'Unsupported join type')
    _require(relationship in {'one_to_one', 'one_to_many', 'many_to_one'}, 'Unsafe join relationship')
    _require(not left[left_on].isna().any().any() and not right[right_on].isna().any().any(), 'Null join keys are forbidden')
    if relationship in {'one_to_one', 'one_to_many'}:
        _require(not left.duplicated(left_on).any(), 'Left join keys violate relationship')
    if relationship in {'one_to_one', 'many_to_one'}:
        _require(not right.duplicated(right_on).any(), 'Right join keys violate relationship')
    overlap = set(left.columns) & set(right.columns)
    shared_keys = {a for a, b in zip(left_on, right_on) if a == b}
    names = list(left.columns) + [c + '_right' if c in overlap else c for c in right.columns if c not in shared_keys]
    _require(len(names) == len(set(names)) and len(names) <= MAX_COLUMNS, 'Join suffix collision or column limit')
    # Bound cardinality without materializing expanded records.
    lc = left.groupby(left_on, dropna=False).size().rename('l')
    rc = right.groupby(right_on, dropna=False).size().rename('r')
    rc.index.names = lc.index.names
    counts = pd.concat([lc, rc], axis=1).fillna(0)
    both = counts.l.gt(0) & counts.r.gt(0)
    total = int((counts.loc[both, 'l'] * counts.loc[both, 'r']).sum())
    if how in {'left', 'outer'}: total += int(counts.loc[counts.r.eq(0), 'l'].sum())
    if how == 'outer': total += int(counts.loc[counts.l.eq(0), 'r'].sum())
    _require(total <= MAX_ROWS, 'Join exceeds row limit')
    avg = sum(f.memory_usage(index=True, deep=True).sum() / max(1, len(f)) for f in [left, right])
    _require(total * avg <= MAX_MEMORY_BYTES, 'Join exceeds estimated memory limit')
    try:
        result = left.merge(right, left_on=left_on, right_on=right_on, how=how, suffixes=('', '_right'), validate=relationship)
    except (pd.errors.MergeError, TypeError, ValueError) as exc:
        raise ValueError(f'Invalid join: {exc}') from exc
    _frame(result)
    warnings = ['Some join keys have no match in the other source'] if (~both).any() else []
    return result, warnings
