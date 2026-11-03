import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import unittest
import pandas as pd
from pandas.testing import assert_frame_equal
from app.services.report_engine import run_report, serialize_config, load_config, join_sources


class ReportEngineTests(unittest.TestCase):
    def setUp(self):
        self.df = pd.DataFrame({'team': ['A', 'A', 'B', 'B'], 'amount': [10, None, 30, 0], 'date': ['01/01/2025', '15/01/2025', '01/02/2025', '15/02/2025'], 'name': ['alpha', 'beta', None, 'a.b']})

    def config(self, **kwargs):
        return {'version': 1, **kwargs}

    def test_metrics_and_nonmutation(self):
        original = self.df.copy(deep=True)
        metrics = [{'column': 'amount', 'operation': op, 'alias': op} for op in ['sum', 'mean', 'min', 'max', 'count', 'nunique']]
        metrics += [{'operation': 'rows', 'alias': 'rows'}]
        out = run_report(self.df, self.config(group_by=['team'], metrics=metrics))['summary'].set_index('team')
        self.assertEqual(out.loc['A', 'sum'], 10)
        self.assertEqual(out.loc['A', 'rows'], 2)
        self.assertEqual(out.loc['A', 'count'], 1)
        self.assertEqual(out.loc['B', 'mean'], 15)
        assert_frame_equal(self.df, original)

    def test_all_filters(self):
        cases = [('eq', 10, 1), ('ne', 10, 2), ('gt', 10, 1), ('ge', 10, 2), ('lt', 10, 1), ('le', 10, 2), ('in', [10, 30], 2), ('between', [0, 10], 2), ('is_null', None, 1), ('not_null', None, 3)]
        for op, value, expected in cases:
            with self.subTest(op=op):
                cfg = self.config(filters=[{'column': 'amount', 'operator': op, 'value': value, 'type': 'number'}])
                self.assertEqual(len(run_report(self.df, cfg)['data']), expected)
        cfg = self.config(filters=[{'column': 'name', 'operator': 'contains', 'value': '.'}])
        self.assertEqual(len(run_report(self.df, cfg)['data']), 1)

    def test_or_and_empty(self):
        filters = [{'column': 'amount', 'operator': 'gt', 'value': 20, 'type': 'number'}, {'column': 'team', 'operator': 'eq', 'value': 'A'}]
        self.assertEqual(len(run_report(self.df, self.config(filters=filters, filter_logic='or'))['data']), 3)
        self.assertEqual(len(run_report(self.df, self.config(filters=filters))['data']), 0)
        cfg = self.config(filters=filters, metrics=[{'column': 'amount', 'operation': 'sum', 'alias': 'total'}])
        out = run_report(self.df, cfg)
        self.assertTrue(pd.isna(out['summary'].iloc[0, 0]))
        self.assertTrue(out['warnings'])

    def test_strict_conversions(self):
        for values in [['1', 'bad'], [True, False], [1, float('inf')]]:
            frame = pd.DataFrame({'x': values})
            with self.assertRaises(ValueError):
                run_report(frame, self.config(metrics=[{'column': 'x', 'operation': 'sum', 'alias': 'total'}]))
        with self.assertRaises(ValueError):
            run_report(pd.DataFrame({'d': ['bad']}), self.config(date_group={'column': 'd', 'frequency': 'month'}))

    def test_date_group_and_filter(self):
        cfg = self.config(date_group={'column': 'date', 'frequency': 'quarter'}, group_by=['Period'], metrics=[{'operation': 'rows', 'alias': 'rows'}], filters=[{'column': 'date', 'operator': 'between', 'type': 'date', 'value': ['01/02/2025', '28/02/2025']}])
        out = run_report(self.df, cfg)
        self.assertEqual(out['summary'].iloc[0]['Period'], '2025Q1')
        self.assertEqual(out['summary'].iloc[0]['rows'], 2)
        self.assertNotIn('Period', self.df.columns)

    def test_iso_date_is_not_inverted(self):
        frame = pd.DataFrame({'d': ['2025-02-01', '01/02/2025']})
        out = run_report(frame, self.config(date_group={'column': 'd', 'frequency': 'month'}))
        self.assertEqual(out['data']['Period'].tolist(), ['2025-02', '2025-02'])

    def test_no_inferred_metrics_and_top(self):
        self.assertTrue(run_report(self.df, self.config())['summary'].empty)
        out = run_report(self.df, self.config(top_n={'column': 'amount', 'n': 1}))
        self.assertEqual(out['data'].iloc[0]['amount'], 30)

    def test_all_null_sum(self):
        frame = pd.DataFrame({'g': ['x', 'x'], 'v': [None, None]})
        cfg = self.config(group_by=['g'], metrics=[{'column': 'v', 'operation': 'sum', 'alias': 'sum'}])
        self.assertTrue(pd.isna(run_report(frame, cfg)['summary'].iloc[0]['sum']))

    def test_pivot(self):
        frame = pd.DataFrame({'g': ['A', 'A', 'B'], 'p': ['x', 'y', 'x'], 'v': [1, None, 3]})
        cfg = self.config(pivot={'index': ['g'], 'columns': 'p', 'values': 'v', 'operation': 'sum'})
        out = run_report(frame, cfg)['summary'].set_index('g')
        self.assertEqual(out.loc['A', '["v", "x"]'], 1)
        self.assertTrue(pd.isna(out.loc['A', '["v", "y"]']))
        self.assertTrue(pd.isna(out.loc['B', '["v", "y"]']))
        cfg['pivot']['operation'] = 'rows'
        self.assertEqual(run_report(frame, cfg)['summary'].iloc[0]['["v", "x"]'], 1)

    def test_comparison(self):
        frame = pd.DataFrame({'g': ['A', 'A', 'B', 'B'], 'd': ['01/01/2025', '01/02/2025', '01/01/2025', '01/02/2025'], 'v': [10, 15, 0, 5]})
        cfg = self.config(group_by=['g'], metrics=[{'column': 'v', 'operation': 'sum', 'alias': 'total'}], comparison={'date_column': 'd', 'current_start': '01/02/2025', 'current_end': '28/02/2025', 'previous_start': '01/01/2025', 'previous_end': '31/01/2025'})
        out = run_report(frame, cfg)
        s = out['summary'].set_index('g')
        self.assertEqual(s.loc['A', 'total_delta'], 5)
        self.assertEqual(s.loc['A', 'total_percent'], 50)
        self.assertTrue(pd.isna(s.loc['B', 'total_percent']))
        self.assertTrue(out['warnings'])
        cfg['comparison']['previous_end'] = '01/02/2025'
        with self.assertRaises(ValueError): run_report(frame, cfg)

    def test_missing_comparison_groups_and_empty(self):
        cfg = self.config(group_by=['team'], metrics=[{'operation': 'rows', 'alias': 'rows'}], comparison={'date_column': 'date', 'current_start': '01/02/2025', 'current_end': '28/02/2025', 'previous_start': '01/01/2025', 'previous_end': '31/01/2025'})
        out = run_report(self.df, cfg)['summary'].set_index('team')
        self.assertTrue(pd.isna(out.loc['A', 'rows_current']))
        self.assertTrue(pd.isna(out.loc['B', 'rows_previous']))
        self.assertTrue(run_report(self.df.iloc[:0], cfg)['summary'].empty)

    def test_validation(self):
        configs = [self.config(version=2), self.config(metrics=[{'operation': 'eval', 'alias': 'x'}]), self.config(group_by=['nope']), self.config(metrics=[{'operation': 'rows', 'alias': 'team'}], group_by=['team']), self.config(date_group={'column': 'date', 'frequency': 'month', 'alias': 'team'}), self.config(filters=[{'column': 'amount', 'operator': 'between', 'value': [5, 1], 'type': 'number'}]), self.config(top_n={'column': 'team', 'n': True})]
        for cfg in configs:
            with self.subTest(cfg=cfg), self.assertRaises(ValueError): run_report(self.df, cfg)

    def test_json(self):
        cfg = self.config(metrics=[{'operation': 'rows', 'alias': 'records'}])
        self.assertEqual(load_config(serialize_config(cfg)), cfg)
        for raw in [b'{"version":1,"version":1}', b'{"version":NaN}', b'{"version":1,"filters":[{"column":"x","operator":"eq","value":1e999}]}', b'not json', b' ' * (100 * 1024 + 1), b'[]']:
            with self.subTest(raw=raw[:30]), self.assertRaises(ValueError): load_config(raw)

    def test_join(self):
        left = pd.DataFrame({'id': [1, 1, 2], 'v': [1, 2, 3]})
        right = pd.DataFrame({'id': [1, 3], 'v': [10, 30]})
        joined, warnings = join_sources(left, right, ['id'], ['id'])
        self.assertEqual(len(joined), 3)
        self.assertIn('v_right', joined)
        self.assertTrue(warnings)
        self.assertEqual(len(join_sources(left, right, ['id'], ['id'], how='outer')[0]), 4)
        with self.assertRaises(ValueError): join_sources(left, right, ['id'], ['id'], relationship='one_to_one')
        with self.assertRaises(ValueError): join_sources(left, right, ['id'], ['id'], relationship='many_to_many')
        with self.assertRaises(ValueError): join_sources(pd.DataFrame({'id': [None]}), right, ['id'], ['id'])
        with self.assertRaises(ValueError): join_sources(left.assign(v_right=1), right, ['id'], ['id'])

    def test_limits(self):
        with self.assertRaises(ValueError): run_report(pd.DataFrame({'x': range(100001)}), self.config())
        with self.assertRaises(ValueError): run_report(pd.DataFrame(columns=[str(i) for i in range(201)]), self.config())
        with self.assertRaises(ValueError): run_report(pd.DataFrame([[1, 2]], columns=['x', 'x']), self.config())
        left = pd.DataFrame({'k': [1], 'v': ['a']})
        right = pd.DataFrame({'k': [1, 1]})
        with self.assertRaises(ValueError): join_sources(left, right, ['k'], ['k'])


if __name__ == '__main__':
    unittest.main()
