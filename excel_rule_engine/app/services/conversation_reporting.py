"""Preview and execute evidence-bound conversational reports over local uploads."""
from __future__ import annotations

import hashlib
import hmac
import json
from pathlib import Path
from uuid import uuid4


from app.services.advanced_report_export import build_advanced_report_bytes
from app.services.file_manager import list_excel_files, safe_output_path
from app.services.report_builder import read_uploaded_table
from app.services.report_engine import run_report, serialize_config
from app.core.report_planner import plan_report

MAX_SOURCE_FILES = 20
MAX_SOURCE_BYTES = 40 * 1024 * 1024


def _load_sources(input_dir: Path, source_name: str | None):
    """Read bounded snapshots; only exact, listed basenames are selectable."""
    root = Path(input_dir).resolve()
    files = list_excel_files(root)
    names = [path.name for path in files]
    if source_name is not None and source_name not in names:
        raise ValueError('Tep nguon khong nam trong danh sach tep da tai len.')
    if len(files) > MAX_SOURCE_FILES:
        raise ValueError('Toi da 20 tep nguon; hay giam so tep truoc khi lap bao cao.')
    if any(not p.resolve().is_relative_to(root) for p in files):
        raise ValueError('Tep nguon nam ngoai thu muc input.')
    if sum(p.stat().st_size for p in files) > MAX_SOURCE_BYTES:
        raise ValueError('Tong dung luong tep nguon vuot gioi han 40 MB.')
    sources, snapshots, warnings = {}, {}, []
    total_bytes = 0
    for path in files:
        if source_name is not None and path.name != source_name:
            continue
        try:
            # A bounded read also protects against a file growing after stat().
            with path.open('rb') as stream:
                raw = stream.read(MAX_SOURCE_BYTES - total_bytes + 1)
            total_bytes += len(raw)
            if total_bytes > MAX_SOURCE_BYTES:
                raise ValueError('Tong dung luong tep nguon vuot gioi han 40 MB.')
            sources[path.name] = read_uploaded_table(path.name, raw, sheet_name=0)
            snapshots[path.name] = raw
        except (ValueError, OSError) as exc:
            if total_bytes > MAX_SOURCE_BYTES:
                raise ValueError('Tong dung luong tep nguon vuot gioi han 40 MB.') from exc
            warnings.append(f'Khong doc duoc {path.name}: {exc}')
    return sources, snapshots, names, warnings


def _preview(input_dir: Path, text: str, source_name: str | None):
    if not isinstance(text, str) or not text.strip():
        raise ValueError('Vui long nhap yeu cau bao cao.')
    sources, snapshots, names, warnings = _load_sources(input_dir, source_name)
    plan = dict(plan_report(text, sources))
    plan.update(available_sources=names, warnings=warnings)
    plan.pop('fingerprint', None)
    if plan.get('status') == 'ready':
        source, config = plan.get('source'), plan.get('config')
        if not isinstance(source, str) or source not in sources:
            raise ValueError('Ke hoach chon tep nguon khong hop le hoac khong doc duoc.')
        if not isinstance(config, dict):
            raise ValueError('Ke hoach thieu cau hinh bao cao hop le.')
        serialize_config(config)
        canonical = json.dumps({'source': source, 'request': text, 'config': config},
                               ensure_ascii=False, sort_keys=True, separators=(',', ':'),
                               allow_nan=False).encode('utf-8')
        digest = hashlib.sha256()
        digest.update(len(canonical).to_bytes(8, 'big'))
        digest.update(canonical)
        digest.update(snapshots[source])
        plan['fingerprint'] = digest.hexdigest()
    return plan, sources


def preview_request(input_dir: Path, text: str, source_name: str | None = None) -> dict:
    """Return a plan and approval fingerprint, never create an output workbook."""
    return _preview(input_dir, text, source_name)[0]


def _evidence_warnings(result: dict, config: dict) -> list[str]:
    """Reject absent sum evidence and distinguish rows, populated counts and sums."""
    data, summary = result['data'], result['summary']
    comparison = config.get('comparison')
    if comparison:
        from app.services.report_engine import _convert, _date_scalar
        dates = _convert(data[comparison['date_column']], 'date')
        evidence = dates.between(_date_scalar(comparison['current_start']), _date_scalar(comparison['current_end']))
        evidence |= dates.between(_date_scalar(comparison['previous_start']), _date_scalar(comparison['previous_end']))
        if not evidence.any():
            raise ValueError('Khong co dong du lieu trong cac ky so sanh.')
    if data.empty:
        raise ValueError('Khong co dong du lieu phu hop; khong tao bao cao rong.')
    warnings = []
    metrics = config.get('metrics', [])
    for metric in metrics:
        operation, column = metric['operation'], metric.get('column')
        if operation in {'sum', 'mean', 'min', 'max'}:
            if data[column].notna().sum() == 0:
                raise ValueError(f'Khong co gia tri hop le de tinh tong cot {column}.')
            cols = ([metric['alias'] + '_current', metric['alias'] + '_previous']
                    if 'comparison' in config else [metric['alias']])
            if summary.empty or summary[cols].isna().all().all():
                raise ValueError(f'Khong co bang chung du lieu de tinh tong cot {column}.')
        if operation == 'count':
            warnings.append(f"{metric['alias']}: count chi dem gia tri khong rong cua {column}, khong phai tong hay so dong.")
        elif operation == 'rows':
            warnings.append(f"{metric['alias']}: rows dem so dong, khong phai tong gia tri.")
        elif operation == 'sum':
            warnings.append(f"{metric['alias']}: sum cong gia tri cua {column}, khong phai dem so dong.")
    pivot = config.get('pivot', {})
    if pivot.get('operation') == 'sum' and (
            data[pivot['values']].notna().sum() == 0 or summary.empty or
            summary.drop(columns=pivot.get('index', []), errors='ignore').isna().all().all()):
        raise ValueError('Khong co gia tri hop le de tinh tong pivot.')
    return warnings


def execute_request(input_dir: Path, project_name: str, text: str,
                    source_name: str | None, fingerprint: str) -> dict:
    """Replan from fresh bytes and execute only the exact approved snapshot/config."""
    plan, sources = _preview(input_dir, text, source_name)
    if plan.get('status') != 'ready':
        raise ValueError('Yeu cau chua san sang; hay xem va xac nhan ke hoach truoc.')
    if source_name is not None and plan['source'] != source_name:
        raise ValueError('Tep nguon khong khop ke hoach da xac nhan.')
    if not isinstance(fingerprint, str) or not hmac.compare_digest(
            plan['fingerprint'].encode('ascii'), fingerprint.encode('utf-8')):
        raise ValueError('Du lieu hoac ke hoach da thay doi; vui long xem truoc va xac nhan lai.')
    if (not isinstance(project_name, str) or not project_name or
            project_name in {'.', '..'} or any(c in project_name for c in '/\\:')):
        raise ValueError('Ten project khong hop le.')
    config = plan['config']
    result = run_report(sources[plan['source']], config)
    warnings = list(plan['warnings']) + list(result.get('warnings', []))
    warnings += _evidence_warnings(result, config)
    result['warnings'] = warnings
    blob = build_advanced_report_bytes(result, config)
    # Fully render before opening a unique output; never overwrite uploaded input.
    output = safe_output_path(project_name, f'planned_report_{uuid4().hex}.xlsx')
    with output.open('xb') as stream:
        stream.write(blob)
    records = json.loads(result['summary'].to_json(orient='records', date_format='iso'))
    return {'output_path': str(output), 'report_type': 'planned',
            'total_rows': len(result['data']), 'files_included': 1,
            'source_file': plan['source'], 'summary': records,
            'explanation': plan.get('explanation', []), 'warnings': warnings}
