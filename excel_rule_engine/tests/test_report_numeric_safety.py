"""Numeric aggregation must fail explicitly instead of silently wrapping."""
import pandas as pd
import pytest
from pandas.testing import assert_frame_equal

from app.services.reports.report_engine import run_report


def report(values, grouped=False, operations=('sum',)):
    data = pd.DataFrame({'revenue': values, 'team': ['A'] * len(values)})
    config = {'version': 1, 'group_by': ['team'] if grouped else [], 'metrics': [
        {'column': 'revenue', 'operation': op, 'alias': op} for op in operations]}
    return run_report(data, config)['summary']


@pytest.mark.parametrize('grouped', [False, True])
@pytest.mark.parametrize('values', [
    pd.Series([2**62, 2**62], dtype='int64'),
    pd.Series([2**63, 2**63], dtype='uint64'),
    pd.Series([-2**62, -2**62, -1], dtype='int64'),
    pd.Series([2**62, 2**62, None], dtype='Int64'),
    pd.Series([2**63, 2**63, None], dtype='UInt64'),
    pd.Series([1e308, 1e308]),
])
def test_unsupported_sum_rejected(values, grouped):
    with pytest.raises(ValueError, match='SUM.*supported numeric range.*Excel'):
        report(values, grouped)


@pytest.mark.parametrize('grouped', [False, True])
@pytest.mark.parametrize('dtype', ['int64', 'uint64', 'Int64', 'UInt64'])
def test_excel_integer_precision_boundary(dtype, grouped):
    assert report(pd.Series([999_999_999_999_998, 1], dtype=dtype), grouped)['sum'].iloc[0] == 999_999_999_999_999
    with pytest.raises(ValueError, match='15 significant digits'):
        report(pd.Series([999_999_999_999_999, 1], dtype=dtype), grouped)


@pytest.mark.parametrize('grouped', [False, True])
def test_exact_accumulation_does_not_reject_large_cancellation(grouped):
    assert report(pd.Series([2**62, 2**62, -2**62, -2**62, 7], dtype='int64'), grouped)['sum'].iloc[0] == 7


@pytest.mark.parametrize('grouped', [False, True])
@pytest.mark.parametrize('dtype', ['float64', 'Int64', 'UInt64'])
def test_normal_and_null_sum_semantics(dtype, grouped):
    result = report(pd.Series([2, None, 5], dtype=dtype), grouped, ('sum', 'count', 'min'))
    assert result[['sum', 'count', 'min']].iloc[0].tolist() == [7, 2, 2]
    assert pd.isna(report(pd.Series([None, None], dtype=dtype), grouped)['sum'].iloc[0])


def test_individual_groups_are_checked_not_only_global_total():
    data = pd.DataFrame({'team': ['A', 'A', 'B', 'B'], 'revenue': [2**62, 2**62, -2**62, -2**62]})
    with pytest.raises(ValueError, match='SUM'):
        run_report(data, {'version': 1, 'group_by': ['team'], 'metrics': [
            {'column': 'revenue', 'operation': 'sum', 'alias': 'total'}]})


def test_pivot_sum_uses_same_safety_checks():
    data = pd.DataFrame({'team': ['A', 'A'], 'revenue': [2**62, 2**62]})
    with pytest.raises(ValueError, match='SUM'):
        run_report(data, {'version': 1, 'pivot': {'index': [], 'columns': 'team',
                   'values': 'revenue', 'operation': 'sum'}})


def test_text_min_and_source_are_not_coerced():
    data = pd.DataFrame({'team': ['A', 'A', None], 'revenue': ['2', '10', None]})
    before = data.copy(deep=True)
    result = run_report(data, {'version': 1, 'group_by': ['team'], 'metrics': [
        {'column': 'revenue', 'operation': op, 'alias': op} for op in ['sum', 'count', 'min']]})['summary']
    assert result.iloc[0][['sum', 'count', 'min']].tolist() == [12, 2, '10']
    assert pd.isna(result.iloc[1]['sum'])
    assert_frame_equal(data, before)


def test_empty_sum_remains_null():
    assert pd.isna(report(pd.Series([], dtype='int64'))['sum'].iloc[0])
    assert report(pd.Series([], dtype='int64'), grouped=True).empty

@pytest.mark.parametrize('grouped', [False, True])
@pytest.mark.parametrize('values,expected', [([1e308, 1e308], 1e308),
    ([1e308, -1e308], 0), ([1, 2, None], 1.5)])
def test_mean_does_not_overflow_intermediate_sum(grouped, values, expected):
    assert report(pd.Series(values), grouped, ('mean',))['mean'].iloc[0] == pytest.approx(expected)
