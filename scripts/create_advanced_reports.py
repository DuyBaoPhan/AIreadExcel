"""Generate reproducible demonstration workbooks with no server or external API."""
from pathlib import Path
import sys

sys.path.insert(0, str((Path(__file__).resolve().parents[1] / "excel_rule_engine")))
import pandas as pd
from app.services.reports.report_engine import run_report, load_config
from app.services.reports.advanced_report_export import build_advanced_report_bytes


def main():
    base = (Path(__file__).resolve().parents[1] / "excel_rule_engine")
    source = pd.DataFrame({
        'employee_id': ['E1', 'E2', 'E3', 'E4', 'E5'],
        'department': ['IT', 'IT', 'HR', 'HR', 'Sales'],
        'salary': [12_000_000, 18_000_000, 15_000_000, 16_000_000, 20_000_000],
        'status': ['active', 'active', 'active', 'inactive', 'active'],
        'start_date': ['2024-03-01', '2025-04-01', '2024-06-01', '2025-06-01', '2025-07-01'],
    })
    output = base / 'projects' / 'demo_project' / 'output'
    output.mkdir(parents=True, exist_ok=True)
    for path in (base / 'examples').glob('*.json'):
        config = load_config(path.read_bytes())
        result = run_report(source, config)
        filename = output / f'Advanced_{path.stem}_Demo.xlsx'
        filename.write_bytes(build_advanced_report_bytes(
            result, config, title=f'DEMO - {path.stem}', company='Demo company', prepared_by='Demo',
        ))
        print(filename)


if __name__ == '__main__':
    main()
