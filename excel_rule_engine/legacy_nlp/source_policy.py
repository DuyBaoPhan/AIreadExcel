"""Project-owned source priorities; never infer authority from filenames."""
import json
from pathlib import Path

from legacy_nlp.report_planner import normalize, plan_report, SCHEMA_ALIASES


def apply_source_policy(input_dir, text, sources, plan):
    """Resolve only equivalent candidate ambiguity using a validated department rule.

    Missing/stale policies fail closed. Selected tables must contain the requested
    department and the replanned request must retain an exact department filter.
    """
    if plan.get('status') != 'clarify' or len(plan.get('ambiguity_candidates', [])) < 2:
        return plan
    path = Path(input_dir).parent / 'source_policy.json'
    if not path.exists():
        return plan
    try:
        if path.stat().st_size > 64 * 1024:
            raise ValueError('Source policy exceeds 64 KB.')
        policy = json.loads(path.read_text(encoding='utf-8-sig'))
        if not isinstance(policy, dict) or policy.get('version') != 1:
            raise ValueError('Invalid source policy version.')
        rules = policy.get('department_sources')
        if not isinstance(rules, dict) or any(
                not isinstance(k, str) or not k.strip() or
                not isinstance(v, str) or Path(v).name != v or '/' in v or '\\' in v
                for k, v in rules.items()):
            raise ValueError('Invalid department source rules.')
    except (ValueError, OSError) as exc:
        raise ValueError('Cau hinh uu tien nguon khong hop le: ' + str(exc)) from exc
    # Use parsed filters rather than raw substring matching (e.g. "IT" in text).
    matches = []
    for department, name in rules.items():
        if name not in plan['ambiguity_candidates'] or name not in sources:
            continue
        candidate = plan_report(text, {name: sources[name]})
        if candidate.get('status') != 'ready':
            continue
        aliases = {normalize(a) for a in SCHEMA_ALIASES['department']}
        if any(normalize(f.get('column', '')) in aliases and
               f.get('operator') == 'eq' and
               normalize(f.get('value', '')) == normalize(department)
               for f in candidate['config'].get('filters', [])):
            matches.append((department, name, candidate))
    if len(matches) != 1:
        return plan
    department, name, result = matches[0]
    result['selection_reason'] = (
        f'Nguon uu tien da cau hinh cho phong ban {department}: {name}. '
        'Khong gop cac tep Root/Update hoac suy doan theo ten tep.')
    result['source_policy'] = {'version': 1, 'department': department, 'source': name}
    return result
