"""Acceptance tests and non-failing audit CLI for the fixed NLP corpus.

Run from repository root:
  python -m pytest excel_rule_engine/tests/test_nlp_benchmark.py -q
  python excel_rule_engine/tests/test_nlp_benchmark.py --audit docs/nlp_benchmark_current.json
The audit always exits zero after writing per-sentence expected/actual failures;
pytest is the strict gate. No network, UI, export, or database writes are used.
"""
from __future__ import annotations
import asyncio
from collections import Counter, defaultdict
import json
from pathlib import Path
import sys
from unittest.mock import patch

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.core.report_planner import plan_report
from app.services.reports.report_engine import run_report
try:
    from .nlp_benchmark_cases import CASES, fixtures
except ImportError:
    from nlp_benchmark_cases import CASES, fixtures


def oracle(frame, expected):
    """Independent pandas computation driven ONLY by hand-authored expectations.

    Intentionally does not call planner, report engine, or engine conversion /
    filtering helpers. Row order is stable first-occurrence order, including ties.
    """
    data = frame.copy(deep=True)
    for condition in expected['filters']:
        values = data[condition['column']]
        target = condition['value']
        if condition['type'] == 'date':
            values = values.map(pd.Timestamp)
            target = [pd.Timestamp(v) for v in target]
        operator = condition['operator']
        mask = values.between(*target) if operator == 'between' else getattr(values, operator)(target)
        data = data.loc[mask.fillna(False)].copy()
    if 'date_group' in expected:
        date = expected['date_group']
        data[date['alias']] = data[date['column']].map(pd.Timestamp).dt.to_period({'month':'M', 'quarter':'Q', 'year':'Y'}[date['frequency']]).astype('string')
    groups = expected['group_by']
    records = []
    partitions = data.groupby(groups, sort=False, dropna=False) if groups else [((), data)]
    for key, partition in partitions:
        if not isinstance(key, tuple): key = (key,)
        row = dict(zip(groups, key))
        for item in expected['metrics']:
            op = item['operation']
            values = partition[item['column']] if item.get('column') else None
            row[item['alias']] = len(partition) if op == 'rows' else values.sum(min_count=1) if op == 'sum' else getattr(values, op)()
        records.append(row)
    result = pd.DataFrame(records, columns=groups + [item['alias'] for item in expected['metrics']])
    if 'top_n' in expected:
        top = expected['top_n']
        result = result.sort_values(top['column'], ascending=top['ascending'], kind='stable').head(top['n'])
    return result.reset_index(drop=True)


def canonical_config(config):
    result = dict(config)
    result['filters'] = sorted(result.get('filters', []), key=lambda x: json.dumps(x, sort_keys=True, ensure_ascii=False))
    return result


def plain(value):
    if isinstance(value, pd.DataFrame):
        return json.loads(value.to_json(orient='records', force_ascii=False))
    return value


def evaluate(case):
    """Return a reproducible report instead of suppressing unexpected exceptions."""
    report = {key: case[key] for key in ('id', 'category', 'text', 'status', 'kind')}
    report.update(expected={'status': case['status'], 'source': case['source'], 'config': case['expected']}, failures=[])
    try:
        if case['route']:
            from app.main import CommandRequest, handle_command
            with patch('app.main.ensure_session'), patch('app.main.create_task', return_value=1), patch('app.main.update_task_status'), patch('app.main.run_export_report') as export, patch('app.main.run_aggregation'), patch('app.main.run_filter'), patch('app.main.run_comparison'), patch('app.services.reports.conversation_reporting.preview_request', return_value={'status':'ready', 'source':'fixture', 'config':{'version':1}, 'fingerprint':'benchmark'}) as preview:
                response = asyncio.run(handle_command(CommandRequest(text=case['text'])))
            report['actual'] = {'preview_calls':preview.call_count, 'export_calls':export.call_count, 'requires_input':response.requires_input}
            if preview.call_count != 1 or export.call_count != 0 or not response.requires_input or response.requires_input.get('type') != 'report_plan':
                report['failures'].append('routing: analytical requests must preview exactly once, never export')
        else:
            sources = fixtures(case['kind'])
            plan = plan_report(case['text'], sources)
            report['actual'] = plan
            if plan['status'] != case['status']:
                report['failures'].append(f"status: expected {case['status']}, actual {plan['status']}")
            if case['status'] != 'ready':
                if plan.get('config') is not None: report['failures'].append('safety: non-ready expectation must not yield executable config')
            else:
                expected_result = oracle(sources[case['source']], case['expected'])
                report['expected']['result'] = plain(expected_result)
                if plan['status'] == 'ready':
                    if plan['source'] != case['source']: report['failures'].append('source mismatch')
                    if canonical_config(plan['config']) != canonical_config(case['expected']): report['failures'].append('configuration mismatch')
                    actual_result = run_report(sources[plan['source']], plan['config'])['summary'].reset_index(drop=True)
                    report['actual_result'] = plain(actual_result)
                    try:
                        pd.testing.assert_frame_equal(actual_result, expected_result, check_dtype=False, check_index_type=False, rtol=1e-10, atol=1e-8)
                    except AssertionError as error:
                        report['failures'].append('result mismatch: '+str(error))
    except Exception as error:
        report['failures'].append(f'exception: {type(error).__name__}: {error}')
    report['passed'] = not report['failures']
    return report


@pytest.mark.parametrize('case', CASES, ids=[case['id'] for case in CASES])
def test_nlp_benchmark(case):
    report = evaluate(case)
    assert report['passed'], json.dumps(report, ensure_ascii=False, indent=2, default=str)


def test_benchmark_coverage_contract():
    assert len(CASES) >= 300
    assert len({(c['text'], c['kind'], c['route']) for c in CASES}) == len(CASES)
    assert sum(c['status'] == 'ready' for c in CASES) >= 250
    assert {'finance_aggregate', 'hr_aggregate', 'hr_ranking', 'ranking', 'literal_filter', 'numeric_filter', 'date_group', 'date_boundary', 'identity_counts', 'ambiguity', 'unsupported_safety', 'command_routing'} <= {c['category'] for c in CASES}


def audit(path):
    results = [evaluate(case) for case in CASES]
    categories = defaultdict(Counter)
    statuses = defaultdict(Counter)
    for result in results:
        key = 'passed' if result['passed'] else 'failed'
        categories[result['category']][key] += 1
        statuses[result['status']][key] += 1
    payload = {'corpus_revision': 'campaign-expanded-v2', 'distinct_sentences': len({c['text'] for c in CASES}), 'total': len(results), 'passed':sum(r['passed'] for r in results), 'failed':sum(not r['passed'] for r in results), 'by_category':dict(categories), 'by_expected_status':dict(statuses), 'methodology':'Fixed hand-authored configs, independent pandas oracle. Accent pairs explicitly included. Supported and safety denominators separate. Routing mocked at preview boundary; no I/O.', 'results':results}
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str), encoding='utf-8')
    print(json.dumps({k:v for k,v in payload.items() if k != 'results'}, ensure_ascii=False, indent=2))
    return payload


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--audit', type=Path, required=True)
    parser.add_argument('--baseline-ref', help='Evaluate a trusted local Git revision of planner/classifier, e.g. HEAD')
    args = parser.parse_args()
    if args.baseline_ref:
        import subprocess
        import types
        repository = Path(__file__).resolve().parents[2]
        modules = {}
        for filename in ('report_planner', 'analytical_request'):
            relative = f'excel_rule_engine/app/core/{filename}.py'
            source = subprocess.check_output(['git', 'show', f'{args.baseline_ref}:{relative}'], cwd=repository).decode('utf-8-sig')
            module = types.ModuleType('baseline_' + filename)
            exec(compile(source, relative, 'exec'), module.__dict__)
            modules[filename] = module
        plan_report = modules['report_planner'].plan_report
        import app.core.analytical_request as classifier
        classifier.is_analytical_request = modules['analytical_request'].is_analytical_request
    payload = audit(args.audit)
    if args.baseline_ref:
        payload['baseline_ref'] = args.baseline_ref
        payload['methodology'] += ' Planner/classifier from trusted local Git revision; current engine, fixed corpus.'
        args.audit.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str), encoding='utf-8')
