"""Preview and execute evidence-bound conversational reports over local uploads."""
from __future__ import annotations

import hashlib
import hmac
import json
from pathlib import Path
from app.services.reports.report_naming import report_filename
from app.services.reports.report_storage import upload_report


from app.services.reports.advanced_report_export import build_advanced_report_bytes
from app.services.sources.file_manager import list_excel_files, safe_output_path
from app.services.reports.report_builder import read_uploaded_table
from app.services.reports.report_engine import run_report, serialize_config
from app.services.ai.planner_settings import planner_mode

MAX_SOURCE_FILES = 20
MAX_SOURCE_BYTES = 40 * 1024 * 1024


def _load_sources(input_dir: Path, source_name: str | None):
    """Read bounded snapshots; only exact, listed basenames are selectable."""
    root = Path(input_dir).resolve()
    from app.services.sources import shared_storage
    from app.services.sources.file_manager import SUPPORTED_EXTENSIONS
    shared = shared_storage.is_enabled()
    if shared:
        files = [root / name for name in sorted(shared_storage.list_objects(root))
                 if Path(name).suffix.lower() in SUPPORTED_EXTENSIONS and not name.startswith('~$')]
    else:
        files = list_excel_files(root)
    names = [path.name for path in files]
    if source_name is not None and source_name not in names:
        raise ValueError('Tep nguon khong nam trong danh sach tep da tai len.')
    if len(files) > MAX_SOURCE_FILES:
        raise ValueError('Toi da 20 tep nguon; hay giam so tep truoc khi lap bao cao.')
    if any(not p.resolve().is_relative_to(root) for p in files):
        raise ValueError('Tep nguon nam ngoai thu muc input.')
    if not shared:
        try:
            total_size = sum(p.stat().st_size for p in files)
        except OSError as exc:
            raise ValueError('Tep nguon da thay doi hoac khong the truy cap; vui long thu lai.') from exc
        if total_size > MAX_SOURCE_BYTES:
            raise ValueError('Tong dung luong tep nguon vuot gioi han 40 MB.')
    sources, snapshots, warnings = {}, {}, []
    total_bytes = 0
    for path in files:
        if source_name is not None and path.name != source_name:
            continue
        try:
            # A bounded read also protects against a file growing after stat().
            if shared:
                # Own immutable response bytes; concurrent cache sync cannot alter approval evidence.
                raw = shared_storage.read_bytes(path)
            else:
                with path.open('rb') as stream:
                    raw = stream.read(MAX_SOURCE_BYTES - total_bytes + 1)
            total_bytes += len(raw)
            if total_bytes > MAX_SOURCE_BYTES:
                raise ValueError('Tong dung luong tep nguon vuot gioi han 40 MB.')
            sources[path.name] = read_uploaded_table(path.name, raw, sheet_name=0)
            snapshots[path.name] = raw
        except shared_storage.StorageError:
            raise
        except (ValueError, OSError) as exc:
            if shared and isinstance(exc, OSError):
                raise ValueError('Tep nguon da thay doi hoac khong the truy cap; vui long thu lai.') from exc
            if total_bytes > MAX_SOURCE_BYTES:
                raise ValueError('Tong dung luong tep nguon vuot gioi han 40 MB.') from exc
            warnings.append(f'Khong doc duoc {path.name}: {exc}')
    return sources, snapshots, names, warnings


def _preview(input_dir: Path, text: str, source_name: str | None):
    if not isinstance(text, str) or not text.strip():
        raise ValueError('Vui long nhap yeu cau bao cao.')
    sources, snapshots, names, warnings = _load_sources(input_dir, source_name)
    planner_mode()  # Validate configuration without selecting a local fallback.
    from app.services.ai.openai_planner import plan_with_openai
    policy_path = Path(input_dir).parent / 'source_policy.json'
    policy = None
    if policy_path.exists():
        if policy_path.stat().st_size > 64 * 1024:
            raise ValueError('Source policy exceeds 64 KB.')
        try:
            policy = json.loads(policy_path.read_text(encoding='utf-8-sig'))
        except (ValueError, OSError) as exc:
            raise ValueError('Cau hinh nguon khong hop le.') from exc
    if source_name is not None and isinstance(policy, dict) and isinstance(policy.get('department_sources'), dict):
        policy = {**policy, 'department_sources': {k: v for k, v in policy['department_sources'].items() if v in sources}}
    plan = dict(plan_with_openai(text, sources, source_policy=policy))
    plan['planner'] = 'openai'
    plan.update(available_sources=names, warnings=warnings)
    plan.pop('fingerprint', None)
    if plan.get('status') == 'ready':
        source, config = plan.get('source'), plan.get('config')
        if not isinstance(source, str) or source not in sources:
            raise ValueError('Ke hoach chon tep nguon khong hop le hoac khong doc duoc.')
        if source_name is not None and source != source_name:
            raise ValueError('Tep nguon khong khop lua chon chinh xac.')
        if not isinstance(config, dict):
            raise ValueError('Ke hoach thieu cau hinh bao cao hop le.')
        try:
            serialize_config(config)
        except (KeyError, TypeError, OverflowError) as exc:
            raise ValueError('Cau hinh bao cao khong hop le.') from exc
        canonical = json.dumps({'source': source, 'request': text, 'config': config},
                               ensure_ascii=False, sort_keys=True, separators=(',', ':'),
                               allow_nan=False).encode('utf-8')
        digest = hashlib.sha256()
        digest.update(len(canonical).to_bytes(8, 'big'))
        digest.update(canonical)
        digest.update(snapshots[source])
        plan['fingerprint'] = digest.hexdigest()
        if plan.get('planner') == 'openai':
            from app.services.ai.ai_approval import remember
            remember(input_dir, text, plan, snapshots)
    return plan, sources


def preview_request(input_dir: Path, text: str, source_name: str | None = None) -> dict:
    """Return a plan and approval fingerprint, never create an output workbook."""
    return _preview(input_dir, text, source_name)[0]


def _evidence_warnings(result: dict, config: dict) -> list[str]:
    """Reject absent sum evidence and distinguish rows, populated counts and sums."""
    data, summary = result['data'], result['summary']
    comparison = config.get('comparison')
    if comparison:
        from app.services.reports.report_engine import _convert, _date_scalar
        dates = _convert(data[comparison['date_column']], 'date')
        evidence = dates.between(_date_scalar(comparison['current_start']), _date_scalar(comparison['current_end']))
        evidence |= dates.between(_date_scalar(comparison['previous_start']), _date_scalar(comparison['previous_end']))
        if not evidence.any():
            raise ValueError('Khong co dong du lieu trong cac ky so sanh.')
    if data.empty:
        raise ValueError('Khong co dong du lieu phu hop; khong tao bao cao rong.')
    if (config.get('metrics') or config.get('pivot')) and summary.empty:
        raise ValueError('Khong co bang chung du lieu trong bang tong hop; khong tao bao cao rong.')
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
    """Read fresh bytes and execute only the exact approved AI snapshot/config."""
    planner_mode()
    from app.services.ai.ai_approval import approved
    sources, snapshots, _, _ = _load_sources(input_dir, source_name)
    plan = approved(input_dir, text, source_name, fingerprint, snapshots)
    if plan is None:
        raise ValueError('Ke hoach AI khong con trong phien; vui long phan tich lai.')
    if plan.get('status') != 'ready':
        raise ValueError('Yeu cau chua san sang; hay xem va xac nhan ke hoach truoc.')
    if source_name is not None and plan['source'] != source_name:
        raise ValueError('Tep nguon khong khop ke hoach da xac nhan.')
    if not isinstance(fingerprint, str) or not hmac.compare_digest(
            plan['fingerprint'].encode('ascii'), fingerprint.encode('utf-8')):
        raise ValueError('Du lieu hoac ke hoach da thay doi; vui long xem truoc va xac nhan lai.')
    return _render_report(plan, sources, project_name, source_name)


def automatic_request(input_dir: Path, project_name: str, text: str,
                      source_name: str | None = None) -> dict:
    """Plan once and execute a ready read-only report from the same bounded snapshot.

    Ambiguous and unsupported requests return a plan without creating an output.
    No independent confirm/read pass is used: the user has authorized auto reporting.
    """
    plan, sources = _preview(input_dir, text, source_name)
    if plan.get('status') != 'ready':
        return {'status': 'requires_input', 'report_plan': plan}
    return {'status': 'ready',
            'result': _render_report(plan, sources, project_name, source_name)}


def _render_report(plan: dict, sources: dict, project_name: str,
                   source_name: str | None, export: bool = True) -> dict:
    """Render only validated, evidence-backed snapshots, never the raw input files."""
    if (not isinstance(project_name, str) or not project_name or
            project_name in {'.', '..'} or any(c in project_name for c in '/\\:')):
        raise ValueError('Ten project khong hop le.')
    config = plan['config']
    try:
        result = run_report(sources[plan['source']].copy(deep=True), config)
        warnings = list(plan['warnings']) + list(result.get('warnings', []))
        warnings += _evidence_warnings(result, config)
    except (KeyError, TypeError, OverflowError) as exc:
        raise ValueError('Du lieu hoac cau hinh khong hop le de tao bao cao.') from exc
    result['warnings'] = warnings
    blob = build_advanced_report_bytes(result, config) if export else None
    records = json.loads(result['summary'].to_json(orient='records', date_format='iso'))
    detail_preview = (json.loads(result['data'].head(50).to_json(orient='records', date_format='iso'))
                      if not config.get('metrics') and not config.get('pivot') else [])
    # Render and serialize fully before creating a unique output.
    output = None
    if export:
        columns = list(sources[plan['source']].columns)
        for sequence in range(1, 10001):
            candidate = safe_output_path(project_name, report_filename(config, columns, sequence))
            try:
                stream = candidate.open('xb')
            except FileExistsError:
                continue
            with stream:
                stream.write(blob)
            try:
                upload_report(candidate)
            except FileExistsError:
                # Another app instance already claimed this remote report name.
                # Retain this local snapshot; do not delete or overwrite reports.
                continue
            output = candidate
            break
        else:
            raise ValueError('Too many reports with the same name; archive old reports and retry.')
    return {'output_path': str(output) if output else None, 'output_filename': output.name if output else None, 'report_type': 'planned',
            'detail_preview': detail_preview,
            'total_rows': len(result['data']), 'files_included': 1,
            'source_file': plan['source'], 'summary': records,
            'planner': plan.get('planner', 'openai'),
            'selection_reason': plan.get('selection_reason', ''),
            'candidate_sources': plan.get('candidate_sources', [plan['source']]),
            'source_selection': {'mode': 'explicit' if source_name is not None else 'automatic',
                                 'requested_source': source_name, 'selected_source': plan['source'],
                                 'available_sources': plan['available_sources']},
            'evidence': {'snapshot_fingerprint': plan['fingerprint'],
                         'source_rows': len(sources[plan['source']]),
                         'matched_rows': len(result['data']),
                         'summary_rows': len(result['summary']), 'config': config},
            'explanation': plan.get('explanation', []), 'warnings': warnings}
