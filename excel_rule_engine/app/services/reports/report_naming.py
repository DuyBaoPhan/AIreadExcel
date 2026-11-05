"""Descriptive Windows-safe filenames derived only from validated report config."""
import calendar
import re
import unicodedata
from datetime import date
from uuid import uuid4
from app.services.reports.schema_matching import SCHEMA_ALIASES, normalize

LABELS = {'revenue':'doanh_thu','profit':'loi_nhuan','cost':'chi_phi','quantity':'so_luong',
          'salary':'luong','product':'san_pham','department':'phong_ban','region':'khu_vuc',
          'status':'trang_thai','employee_id':'nhan_vien','employee_name':'nhan_vien','order_id':'don_hang'}
OPS = {'mean':'trung_binh','min':'nho_nhat','max':'lon_nhat','count':'dem','nunique':'dem_duy_nhat','rows':'dem_dong'}


def _key(column):
    return next((k for k, aliases in SCHEMA_ALIASES.items() if normalize(column) in {normalize(a) for a in aliases}), None)


def safe_stem(value):
    """ASCII only, no separators, device names, hidden files or trailing dots."""
    value=unicodedata.normalize('NFKD',str(value).replace('\u0111','d').replace('\u0110','D'))
    value=value.encode('ascii','ignore').decode()
    value=re.sub(r'[^A-Za-z0-9_-]+','_',value).strip('_-')[:140].rstrip('_-')
    if not value or re.fullmatch(r'(?i:CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9])',value):
        return 'Bao_cao'
    return value


def _period(start,end):
    try:
        a=date.fromisoformat(str(start)[:10]);b=date.fromisoformat(str(end)[:10])
    except ValueError:
        return None
    if a>b:return None
    if a==date(a.year,1,1) and b==date(a.year,12,31):return str(a.year)
    if a.day==1 and a.year==b.year and a.month==b.month and b.day==calendar.monthrange(b.year,b.month)[1]:
        return a.strftime('%Y-%m')
    if a.day==1 and a.month in (1,4,7,10) and b.year==a.year and b.month==a.month+2 and b.day==calendar.monthrange(b.year,b.month)[1]:
        return f'Q{(a.month-1)//3+1}_{a.year}'
    if a==b:return a.isoformat()
    return f'{a.isoformat()}_den_{b.isoformat()}'


def report_stem(config, columns):
    """Use business labels, not arbitrary aliases, source names or person values."""
    metrics=config.get('metrics',[])
    parts=[]
    employee=any(_key(c) in {'employee_id','employee_name'} for c in columns)
    if not metrics and not config.get('pivot'):
        parts=['Danh_sach','nhan_vien' if employee else 'du_lieu']
    else:
        parts=['Bao_cao']
        for m in metrics:
            key=_key(m.get('column',''))
            label=LABELS.get(key,'du_lieu')
            if m['operation'] in OPS:label=OPS[m['operation']]+'_'+label
            if label not in parts:parts.append(label)
        if config.get('pivot'):parts+=['pivot',LABELS.get(_key(config['pivot'].get('values','')),'du_lieu')]
    top=config.get('top_n')
    if top:
        position=top.get('offset',0)
        ranking=f'Hang_{position+1}' if top['n']==1 and position else f'Top_{top["n"]}'
        parts=[ranking]+parts+['thap_nhat' if top.get('ascending',False) else 'cao_nhat']
    groups=[]
    for c in config.get('group_by',[]):
        label=LABELS.get(_key(c))
        if c==config.get('date_group',{}).get('alias'):
            label={'day':'ngay','month':'thang','quarter':'quy','year':'nam'}.get(config['date_group']['frequency'])
        if label and label not in groups:groups.append(label)
    if groups:parts+=['theo']+groups
    # Do not put arbitrary filter values (names, emails, salaries) in filenames.
    # Department codes are included only if short safe business identifiers.
    for f in config.get('filters',[]):
        if _key(f['column'])=='department' and f['operator']=='eq' and isinstance(f.get('value'),str) and re.fullmatch(r'[A-Za-z0-9_-]{1,24}',f['value']):
            parts.append(f['value'])
    periods=[]
    for f in config.get('filters',[]):
        if _key(f['column'])=='date' and f.get('type')=='text':
            value=f.get('value')
            if f['operator']=='eq':value=[value,value]
            if f['operator'] in {'eq','between'} and isinstance(value,list) and len(value)==2 and all(isinstance(v,str) and re.fullmatch(r'\d{4}-(?:0[1-9]|1[0-2])',v) for v in value):
                start,end=value
                y,m=map(int,end.split('-'))
                period=_period(start+'-01',end+f'-{calendar.monthrange(y,m)[1]}')
                if period and period not in periods:periods.append(period)
        if f.get('type')=='date':
            value=f.get('value')
            if f['operator']=='between' and isinstance(value,list):
                period=_period(*value)
            elif f['operator']=='eq':period=_period(value,value)
            else:period=None
            if period and period not in periods:periods.append(period)
    # The model may express the same inclusive interval as ge + le filters.
    bounds={}
    for f in config.get('filters',[]):
        if f.get('type')=='date' and f['operator'] in {'ge','le'}:
            bounds.setdefault(f['column'],{}).setdefault(f['operator'],[]).append(f.get('value'))
    if config.get('filter_logic','and')=='and':
        for pair in bounds.values():
            if len(pair.get('ge',[]))==len(pair.get('le',[]))==1:
                period=_period(pair['ge'][0],pair['le'][0])
                if period and period not in periods:periods.append(period)
    comparison=config.get('comparison')
    if comparison:
        parts.append('so_sanh')
        for prefix in ('current','previous'):
            period=_period(comparison[prefix+'_start'],comparison[prefix+'_end'])
            if period:periods.append(period)
    parts+=periods
    return safe_stem('_'.join(parts))


def report_filename(config,columns):
    # Full UUID plus exclusive creation protects against overwriting existing output.
    return report_stem(config,columns)+'__'+uuid4().hex+'.xlsx'
