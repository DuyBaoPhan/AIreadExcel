"""Safe column format descriptors, never sample cell values."""
import re


def describe_column(series):
    result={'name':series.name,'dtype':str(series.dtype)}
    nonnull=series.dropna()
    if len(nonnull) and nonnull.map(lambda v:isinstance(v,str) and bool(re.fullmatch(r'\d{4}-(?:0[1-9]|1[0-2])',v))).all():
        result.update(semantic_type='monthly_period',format='YYYY-MM',granularity='month',
                      filter_hint='Use date between first and last day for whole months; never compare text to MM/YYYY or month number.')
    return result
