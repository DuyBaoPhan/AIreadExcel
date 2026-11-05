"""Contextual export naming never leaks row identifiers or permits unsafe paths."""
import re
from pathlib import Path
from unittest.mock import patch
import pandas as pd
import pytest
from app.services.reports.report_naming import report_stem,report_filename,safe_stem
from app.services.reports import conversation_reporting as reports


def config(**extra):
    return {'version':1,'filters':[],'group_by':[],
            'metrics':[{'column':'revenue','operation':'sum','alias':'Total'}],**extra}


@pytest.mark.parametrize('a,b,label',[
    ('2024-10-01','2024-10-31','2024-10'),('2024-01-01','2024-12-31','2024'),
    ('2024-04-01','2024-06-30','Q2_2024'),('2024-02-01','2024-02-29','2024-02'),
    ('2024-10-03','2024-10-09','2024-10-03_2024-10-09')])
def test_date_periods(a,b,label):
    c=config(filters=[{'column':'month','type':'date','operator':'between','value':[a,b]}])
    assert report_stem(c,['revenue','month'])=='Doanh_thu_'+label


def test_employee_detail_department():
    c=config(metrics=[],filters=[{'column':'department','operator':'eq','value':'IT'}])
    assert report_stem(c,['name','employee_id'])=='Nhan_vien_IT'


def test_grouping_mean_and_position():
    c=config(metrics=[{'column':'salary','operation':'mean','alias':'Salary'}],group_by=['department'],
             top_n={'column':'Salary','n':1,'offset':1,'ascending':False})
    name=report_stem(c,['name','salary'])
    assert name == 'Hang2_luong_TB_phong_ban'


def test_untrusted_data_not_used_for_naming():
    c=config(metrics=[{'column':'private_custom_column','operation':'sum','alias':'private@email.com'}],
        filters=[{'column':'name','operator':'eq','value':'private person'},
                 {'column':'department','operator':'eq','value':'../../secret'}])
    name=report_filename(c,['private_column'])
    assert 'private' not in name and 'secret' not in name and '@' not in name
    assert re.fullmatch(r'[A-Za-z0-9_-]+\.xlsx',name)


@pytest.mark.parametrize('value',['CON','NUL','COM1','../report.xlsx','a:b*?"<>|','', 'x'*500])
def test_windows_safe_stems(value):
    name=safe_stem(value)
    assert 1<=len(name)<=140
    assert re.fullmatch(r'[A-Za-z0-9_-]+',name)
    assert name not in {'CON','NUL','COM1'}


def test_repeated_reports_unique_and_valid():
    a,b=report_filename(config(),[]),report_filename(config(),[],sequence=2)
    assert a!=b
    assert len(a)<=95
    assert a == 'Doanh_thu.xlsx'
    assert b == 'Doanh_thu_2.xlsx'
    assert '__' not in a


def test_real_export_uses_context_name_and_no_input_overwrite(tmp_path,monkeypatch):
    monkeypatch.setenv('REPORT_PLANNER','openai')
    source=tmp_path/'input';source.mkdir()
    output=tmp_path/'output';output.mkdir()
    path=source/'sales.csv';path.write_text('month,revenue\n2024-10,100\n2024-11,200\n')
    original=path.read_bytes()
    monkeypatch.setattr(reports,'safe_output_path',lambda p,n:output/n)
    planned = {'status': 'ready', 'source': 'sales.csv',
               'config': config(filters=[{'column':'month','type':'date','operator':'between',
                                         'value':['2024-10-01','2024-10-31']}])}
    with patch('app.services.ai.openai_planner.plan_with_openai', return_value=planned):
        responses=[reports.automatic_request(source,'demo','doanh thu thang 10 nam 2024')['result'] for _ in range(2)]
    for r in responses:
        name=r['output_filename']
        assert name in {'Doanh_thu_2024-10.xlsx', 'Doanh_thu_2024-10_2.xlsx'},name
        assert Path(r['output_path']).name==name
        assert pd.ExcelFile(r['output_path']).sheet_names
    assert len(list(output.iterdir()))==2
    assert path.read_bytes()==original


def test_equivalent_paired_date_bounds():
    c=config(filters=[{'column':'month','type':'date','operator':'ge','value':'2024-10-01'},
                      {'column':'month','type':'date','operator':'le','value':'2024-10-31'}])
    assert report_stem(c,[])=='Doanh_thu_2024-10'


def test_pivot_comparison_and_multiple_metrics():
    c=config(metrics=[],pivot={'values':'revenue','index':['product'],'columns':'region','operation':'sum'})
    assert report_stem(c,[]) == 'Doanh_thu_pivot'
    c=config(comparison={'date_column':'month','current_start':'2024-01-01','current_end':'2024-12-31',
        'previous_start':'2023-01-01','previous_end':'2023-12-31'})
    assert report_stem(c,[]).endswith('vs_2024_2023')
    c=config(metrics=[{'column':'revenue','operation':'sum','alias':'a'},
                      {'column':'profit','operation':'sum','alias':'b'}])
    assert report_stem(c,[]) == 'Doanh_thu_loi_nhuan'


def test_top_product_example():
    c=config(group_by=['product'], top_n={'column':'Total','n':5,'ascending':False},
             filters=[{'column':'month','type':'text','operator':'between','value':['2024-01','2024-12']}])
    assert report_filename(c,[]) == 'Top5_doanh_thu_san_pham_2024.xlsx'


def test_long_titles_keep_period_and_are_bounded():
    c=config(metrics=[{'column':col,'operation':'mean','alias':str(i)} for i,col in enumerate(
        ['revenue','profit','cost','salary','quantity'])],
        group_by=['department','region','status'],
        filters=[{'column':'month','type':'date','operator':'between','value':['2024-01-01','2024-12-31']}])
    assert len(report_stem(c,[])) <= 90
    assert report_stem(c,[]).endswith('_2024')


@pytest.mark.parametrize('sequence', [0, -1, True, '2'])
def test_invalid_sequence_rejected(sequence):
    with pytest.raises(ValueError):report_filename(config(),[],sequence)


def test_existing_report_never_overwritten(tmp_path,monkeypatch):
    source=tmp_path/'input';source.mkdir()
    output=tmp_path/'output';output.mkdir()
    (source/'sales.csv').write_text('revenue\n100\n')
    original=output/'Doanh_thu.xlsx';original.write_bytes(b'keep-existing')
    second=output/'Doanh_thu_2.xlsx';second.write_bytes(b'keep-second')
    monkeypatch.setattr(reports,'safe_output_path',lambda p,n:output/n)
    plan={'status':'ready','source':'sales.csv','config':config()}
    with patch('app.services.ai.openai_planner.plan_with_openai', return_value=plan):
        result=reports.automatic_request(source,'demo','export revenue')['result']
    assert result['output_filename']=='Doanh_thu_3.xlsx'
    assert original.read_bytes()==b'keep-existing'
    assert second.read_bytes()==b'keep-second'
    assert pd.ExcelFile(result['output_path']).sheet_names
