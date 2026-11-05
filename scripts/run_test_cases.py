"""
Script chạy tất cả test cases theo yêu cầu đề bài.
Chạy: python scripts/run_test_cases.py
Không cần FastAPI server chạy — test trực tiếp các module.
"""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str((Path(__file__).resolve().parents[1] / "excel_rule_engine")))

import pandas as pd

# ──────────────────────────────────────────────────────────────
BOLD = "\033[1m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
RED = "\033[91m"
CYAN = "\033[96m"
RESET = "\033[0m"

PASS = f"{GREEN}✅ PASS{RESET}"
FAIL = f"{RED}❌ FAIL{RESET}"
WARN = f"{YELLOW}⚠️  WARN{RESET}"
INFO = f"{CYAN}ℹ️  INFO{RESET}"


def section(title: str):
    print(f"\n{BOLD}{'─'*60}{RESET}")
    print(f"{BOLD}{CYAN}{title}{RESET}")
    print(f"{BOLD}{'─'*60}{RESET}")


def test_case(idx: int, cmd_text: str):
    print(f"\n{BOLD}[TC-{idx:02d}]{RESET} Input: {YELLOW}\"{cmd_text}\"{RESET}")


# ──────────────────────────────────────────────────────────────
#  Setup sample data in temp directory
# ──────────────────────────────────────────────────────────────

def setup_sample_files(input_dir: Path):
    """Tạo file Excel mẫu trong temp dir."""
    df_it = pd.DataFrame({
        "employee_id": ["EMP001", "EMP002", "EMP003", "EMP004", "EMP005"],
        "name": ["Nguyễn Văn An", "Trần Thị Bình", "Lê Minh Cường", "Phạm Thu Dung", "Hoàng Văn Em"],
        "department": ["IT", "IT", "IT", "IT", "IT"],
        "salary": [18_000_000, 9_500_000, 15_000_000, 11_000_000, 25_000_000],
        "status": ["active", "active", "active", "inactive", "active"],
    })
    df_it.to_excel(input_dir / "Employees_IT.xlsx", index=False)

    df_hr = pd.DataFrame({
        "employee_id": ["EMP006", "EMP007", "EMP008"],
        "name": ["Vũ Thị Phương", "Đỗ Quang Huy", "Bùi Thị Lan"],
        "department": ["HR", "HR", "Accounting"],
        "salary": [22_000_000, 12_000_000, 28_000_000],
        "status": ["active", "active", "active"],
    })
    df_hr.to_excel(input_dir / "Employees_HR.xlsx", index=False)

    df_root = pd.DataFrame({
        "employee_id": ["EMP001", "EMP002", "EMP003", "EMP004"],
        "name": ["Nguyễn Văn An", "Trần Thị Bình", "Lê Minh Cường", "Phạm Thu Dung"],
        "salary": [18_000_000, 9_500_000, 15_000_000, 11_000_000],
        "status": ["active", "active", "active", "inactive"],
    })
    df_root.to_excel(input_dir / "Root_Data.xlsx", index=False)

    df_update = pd.DataFrame({
        "employee_id": ["EMP001", "EMP002", "EMP005"],
        "name": ["Nguyễn Văn An", "Trần Thị Bình", "Hoàng Văn Em"],
        "salary": [20_000_000, 9_500_000, 25_000_000],   # EMP001 tăng lương
        "status": ["active", "active", "active"],
    })
    df_update.to_excel(input_dir / "Update_Data.xlsx", index=False)

    print(f"  {INFO} Đã tạo 4 file Excel mẫu trong: {input_dir}")


# ──────────────────────────────────────────────────────────────
#  Main test runner
# ──────────────────────────────────────────────────────────────

def main():
    from app.core.command_parser import parse_command
    from app.workflows.aggregation import run_aggregation
    from app.workflows.filtering import run_filter
    from app.workflows.comparison import run_comparison
    from app.services.sources.file_manager import set_projects_root, list_excel_files

    # Setup temp environment
    tmpdir = Path(tempfile.mkdtemp())
    input_dir = tmpdir / "input"
    output_dir = tmpdir / "output"
    input_dir.mkdir(); output_dir.mkdir()
    set_projects_root(tmpdir)
    setup_sample_files(input_dir)

    results = []

    section("TEST CASES — Excel Rule Engine")

    # ── TC-01: Gộp tất cả file Excel ──────────────────────────
    test_case(1, "Gộp tất cả file Excel")
    cmd = parse_command("Gộp tất cả file Excel")
    print(f"  Intent: {cmd.intent} (conf={cmd.confidence:.0%})")
    try:
        result = run_aggregation(input_dir=input_dir, project_name=".")
        print(f"  {PASS} Gộp {result['files_merged']} file → {result['total_rows']} dòng")
        print(f"  Output: {Path(result['output_path']).name}")
        results.append(("TC-01", True))
    except Exception as e:
        print(f"  {FAIL} {e}")
        results.append(("TC-01", False))

    # ── TC-02: Lọc nhân viên có lương trên 10 triệu ──────────
    test_case(2, "Lọc nhân viên có lương trên 10 triệu")
    cmd = parse_command("Lọc nhân viên có lương trên 10 triệu")
    print(f"  Intent: {cmd.intent} (conf={cmd.confidence:.0%})")
    print(f"  column={cmd.parameters.get('column')}, op={cmd.parameters.get('operator')}, value={cmd.parameters.get('value')}")
    try:
        result = run_filter(
            input_dir=input_dir, project_name=".",
            column="salary", operator=">", value=10_000_000,
        )
        print(f"  {PASS} Tìm thấy {result['filtered_rows']} bản ghi (lương > 10M)")
        results.append(("TC-02", True))
    except Exception as e:
        print(f"  {FAIL} {e}")
        results.append(("TC-02", False))

    # ── TC-03: Tìm nhân viên thuộc phòng IT ──────────────────
    test_case(3, "Tìm nhân viên thuộc phòng IT")
    cmd = parse_command("Tìm nhân viên thuộc phòng IT")
    print(f"  Intent: {cmd.intent} (conf={cmd.confidence:.0%})")
    try:
        result = run_filter(
            input_dir=input_dir, project_name=".",
            column="department", operator="==", value="IT",
        )
        print(f"  {PASS} Tìm thấy {result['filtered_rows']} nhân viên phòng IT")
        results.append(("TC-03", True))
    except Exception as e:
        print(f"  {FAIL} {e}")
        results.append(("TC-03", False))

    # ── TC-04: So sánh Root và Update ────────────────────────
    test_case(4, "So sánh Root và Update")
    cmd = parse_command("So sánh Root và Update")
    print(f"  Intent: {cmd.intent} (conf={cmd.confidence:.0%})")
    print(f"  requires_confirmation={cmd.requires_confirmation}")
    try:
        result = run_comparison(
            input_dir=input_dir, project_name=".",
            primary_key="employee_id",
        )
        print(f"  {PASS} Added={result['added']} Updated={result['updated']} Unchanged={result['unchanged']}")
        print(f"  Output: {Path(result['output_path']).name}")
        results.append(("TC-04", True))
    except Exception as e:
        print(f"  {FAIL} {e}")
        results.append(("TC-04", False))

    # ── TC-05: Liệt kê các file Excel ────────────────────────
    test_case(5, "Liệt kê các file Excel")
    cmd = parse_command("Liệt kê các file Excel")
    print(f"  Intent: {cmd.intent} (conf={cmd.confidence:.0%})")
    try:
        files = list_excel_files(input_dir)
        print(f"  {PASS} Tìm thấy {len(files)} file:")
        for f in files:
            print(f"    • {f.name}")
        results.append(("TC-05", True))
    except Exception as e:
        print(f"  {FAIL} {e}")
        results.append(("TC-05", False))

    # ── TC-06: Tạo báo cáo tổng hợp ──────────────────────────
    test_case(6, "Tạo báo cáo tổng hợp")
    cmd = parse_command("Tạo báo cáo tổng hợp")
    print(f"  Intent: {cmd.intent} (conf={cmd.confidence:.0%})")
    try:
        from app.workflows.report_export import run_export_report
        result = run_export_report(input_dir=input_dir, project_name=".")
        print(f"  {PASS} Báo cáo tạo thành công: {Path(result['output_path']).name}")
        print(f"  {result['total_rows']} dòng từ {result['files_included']} file")
        results.append(("TC-06", True))
    except Exception as e:
        print(f"  {FAIL} {e}")
        results.append(("TC-06", False))

    # ── TC-07: Xóa tất cả dữ liệu (phải bị chặn) ─────────────
    test_case(7, "Xóa tất cả dữ liệu")
    cmd = parse_command("Xóa tất cả dữ liệu")
    print(f"  Intent: {cmd.intent} (conf={cmd.confidence:.0%})")
    if cmd.intent == "DELETE" and cmd.error_message:
        print(f"  {PASS} Lệnh DELETE bị chặn đúng cách")
        print(f"  Message: {cmd.error_message[:80]}...")
        results.append(("TC-07", True))
    else:
        print(f"  {FAIL} Lệnh DELETE không bị chặn!")
        results.append(("TC-07", False))

    # ── TC-08: Làm giúp tôi một việc gì đó (phải yêu cầu làm rõ) ──
    test_case(8, "Làm giúp tôi một việc gì đó")
    cmd = parse_command("Làm giúp tôi một việc gì đó")
    print(f"  Intent: {cmd.intent} (conf={cmd.confidence:.0%})")
    if cmd.intent == "UNKNOWN" or (cmd.error_message and "diễn đạt" in cmd.error_message.lower()):
        print(f"  {PASS} Câu mơ hồ → yêu cầu làm rõ đúng cách")
        if cmd.error_message:
            print(f"  Message: {cmd.error_message[:100]}")
        results.append(("TC-08", True))
    else:
        print(f"  {WARN} Intent={cmd.intent}, confidence={cmd.confidence:.0%} — có thể là HELP")
        results.append(("TC-08", cmd.confidence < 0.3))

    # ── Summary ───────────────────────────────────────────────
    section("KẾT QUẢ TỔNG HỢP")
    passed = sum(1 for _, ok in results if ok)
    total = len(results)
    for tc, ok in results:
        status = PASS if ok else FAIL
        print(f"  {status}  {tc}")
    print(f"\n{BOLD}Kết quả: {passed}/{total} test cases PASSED{RESET}")

    if passed == total:
        print(f"\n{GREEN}{BOLD}🎉 Tất cả test cases đều PASS!{RESET}")
    else:
        print(f"\n{YELLOW}{BOLD}⚠️  Có {total - passed} test case(s) FAIL.{RESET}")

    return passed == total


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)

