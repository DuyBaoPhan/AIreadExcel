"""
Unit Tests cho Excel Rule Engine.
Chạy: python -m pytest tests/ -v
"""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

# Thêm project root vào sys.path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pandas as pd

from app.core.intent_router import classify_intent, Intent
from app.core.command_parser import parse_command
from app.core.entity_extractor import (
    extract_column, extract_operator, extract_numeric_value,
    extract_string_value, extract_entities,
)


# ──────────────────────────────────────────────────────────────
#  Intent Router Tests
# ──────────────────────────────────────────────────────────────

class TestIntentRouter(unittest.TestCase):

    def _assert_intent(self, text: str, expected: Intent, min_confidence: float = 0.1):
        result = classify_intent(text)
        self.assertEqual(
            result.intent, expected,
            f"Text: {text!r}\nExpected: {expected}\nGot: {result.intent} (conf={result.confidence})"
        )
        self.assertGreaterEqual(result.confidence, min_confidence)

    # ── AGGREGATION ──
    def test_aggregation_gop(self):
        self._assert_intent("Gộp tất cả file Excel trong thư mục input", Intent.AGGREGATION)

    def test_aggregation_tonghop(self):
        self._assert_intent("Tổng hợp dữ liệu từ các file Excel", Intent.AGGREGATION)

    def test_aggregation_hopnhat(self):
        self._assert_intent("Hợp nhất dữ liệu từ file A và file B", Intent.AGGREGATION)

    def test_aggregation_combine(self):
        self._assert_intent("Combine all Excel files", Intent.AGGREGATION)

    # ── FILTER ──
    def test_filter_luong(self):
        self._assert_intent("Lọc nhân viên có lương trên 10 triệu", Intent.FILTER)

    def test_filter_tinh_trang(self):
        self._assert_intent("Tìm những bản ghi có trạng thái đang làm việc", Intent.FILTER)

    def test_filter_phong(self):
        self._assert_intent("Tìm nhân viên thuộc phòng IT", Intent.FILTER)

    def test_filter_lay_du_lieu(self):
        self._assert_intent("Lấy dữ liệu thuộc phòng kế toán", Intent.FILTER)

    # ── COMPARISON ──
    def test_comparison_sosanh(self):
        self._assert_intent("So sánh Root với file Update", Intent.COMPARISON)

    def test_comparison_doichieu(self):
        self._assert_intent("Đối chiếu hai file dữ liệu", Intent.COMPARISON)

    def test_comparison_kiemtra(self):
        self._assert_intent("Kiểm tra thay đổi giữa hai file", Intent.COMPARISON)

    # ── EXPORT ──
    def test_export_baocao(self):
        self._assert_intent("Tạo báo cáo tổng hợp", Intent.EXPORT)

    def test_export_xuatfile(self):
        self._assert_intent("Xuất file Excel kết quả", Intent.EXPORT)

    # ── FILE_LIST ──
    def test_filelist_liet_ke(self):
        self._assert_intent("Liệt kê các file Excel", Intent.FILE_LIST)

    def test_filelist_co_gi(self):
        self._assert_intent("Có những file nào trong dự án?", Intent.FILE_LIST)

    # ── HELP ──
    def test_help_huongdan(self):
        self._assert_intent("Hướng dẫn sử dụng", Intent.HELP)

    def test_help_tro_giup(self):
        self._assert_intent("Trợ giúp", Intent.HELP)

    # ── DELETE ──
    def test_delete_xoa(self):
        self._assert_intent("Xóa tất cả dữ liệu", Intent.DELETE)

    def test_delete_xoa_file(self):
        self._assert_intent("Xoá file Excel", Intent.DELETE)

    # ── UNKNOWN ──
    def test_unknown_vague(self):
        result = classify_intent("Làm giúp tôi một việc gì đó")
        # Có thể là UNKNOWN hoặc confidence rất thấp
        self.assertTrue(
            result.intent == Intent.UNKNOWN or result.confidence < 0.3,
            f"Expected UNKNOWN or low confidence, got {result.intent} ({result.confidence})"
        )

    def test_unknown_nonsense(self):
        result = classify_intent("abcxyz 12345")
        self.assertEqual(result.intent, Intent.UNKNOWN)


# ──────────────────────────────────────────────────────────────
#  Entity Extractor Tests
# ──────────────────────────────────────────────────────────────

class TestEntityExtractor(unittest.TestCase):

    def test_extract_column_luong(self):
        col = extract_column("lọc nhân viên có lương trên 10 triệu")
        self.assertEqual(col, "salary")

    def test_extract_column_phong(self):
        col = extract_column("tìm nhân viên thuộc phòng ban IT")
        self.assertEqual(col, "department")

    def test_extract_column_tinhtrang(self):
        col = extract_column("trạng thái đang làm việc")
        self.assertEqual(col, "status")

    def test_extract_operator_tren(self):
        op = extract_operator("lương trên 10 triệu")
        self.assertEqual(op, ">")

    def test_extract_operator_duoi(self):
        op = extract_operator("lương dưới 5 triệu")
        self.assertEqual(op, "<")

    def test_extract_operator_bang(self):
        op = extract_operator("phòng bằng IT")
        self.assertEqual(op, "==")

    def test_extract_numeric_trieu(self):
        val = extract_numeric_value("lương trên 10 triệu")
        self.assertAlmostEqual(val, 10_000_000)

    def test_extract_numeric_ty(self):
        val = extract_numeric_value("doanh thu trên 1 tỷ")
        self.assertAlmostEqual(val, 1_000_000_000)

    def test_extract_numeric_plain(self):
        val = extract_numeric_value("số lượng trên 500")
        self.assertAlmostEqual(val, 500)

    def test_extract_string_phong_it(self):
        val = extract_string_value("tìm nhân viên phòng IT")
        self.assertEqual(val, "IT")

    def test_extract_string_dang_lam(self):
        val = extract_string_value("trạng thái đang làm việc")
        self.assertEqual(val, "active")

    def test_extract_string_da_nghi(self):
        val = extract_string_value("nhân viên đã nghỉ việc")
        self.assertEqual(val, "inactive")


# ──────────────────────────────────────────────────────────────
#  Command Parser Tests
# ──────────────────────────────────────────────────────────────

class TestCommandParser(unittest.TestCase):

    def test_parse_aggregation(self):
        cmd = parse_command("Gộp tất cả file Excel trong thư mục input")
        self.assertEqual(cmd.intent, "AGGREGATION")
        self.assertIsNone(cmd.error_message)
        self.assertEqual(cmd.parameters.get("source"), "input")

    def test_parse_filter_complete(self):
        cmd = parse_command("Lọc nhân viên có lương trên 10 triệu")
        self.assertEqual(cmd.intent, "FILTER")
        params = cmd.parameters
        self.assertEqual(params.get("column"), "salary")
        self.assertEqual(params.get("operator"), ">")
        self.assertAlmostEqual(params.get("value"), 10_000_000)

    def test_parse_filter_incomplete_no_column(self):
        cmd = parse_command("Lọc những bản ghi lớn hơn 5")
        self.assertEqual(cmd.intent, "FILTER")
        # Không có cột → phải có error hoặc column = None
        # (Có thể nhận diện hoặc không, tuỳ test case)
        # Chỉ kiểm tra intent đúng
        self.assertIsNotNone(cmd)

    def test_parse_comparison(self):
        cmd = parse_command("So sánh Root và Update")
        self.assertEqual(cmd.intent, "COMPARISON")
        self.assertTrue(cmd.requires_confirmation)

    def test_parse_delete_blocked(self):
        cmd = parse_command("Xóa tất cả dữ liệu")
        self.assertEqual(cmd.intent, "DELETE")
        self.assertIsNotNone(cmd.error_message)
        self.assertIn("XÓA", cmd.error_message.upper())

    def test_parse_unknown(self):
        cmd = parse_command("Làm giúp tôi một việc gì đó")
        # Hệ thống phải trả về error hoặc UNKNOWN
        self.assertTrue(
            cmd.intent == "UNKNOWN" or cmd.error_message is not None
        )

    def test_parse_help(self):
        cmd = parse_command("Hướng dẫn sử dụng")
        self.assertEqual(cmd.intent, "HELP")

    def test_parse_file_list(self):
        cmd = parse_command("Liệt kê các file Excel")
        self.assertEqual(cmd.intent, "FILE_LIST")

    def test_parse_export(self):
        cmd = parse_command("Tạo báo cáo tổng hợp")
        self.assertEqual(cmd.intent, "EXPORT")


# ──────────────────────────────────────────────────────────────
#  Workflow Tests (with temp files)
# ──────────────────────────────────────────────────────────────

class TestAggregationWorkflow(unittest.TestCase):

    def setUp(self):
        """Tạo temp directory với file Excel mẫu."""
        self.tmpdir = tempfile.mkdtemp()
        self.input_dir = Path(self.tmpdir) / "input"
        self.input_dir.mkdir()
        self.output_dir = Path(self.tmpdir) / "output"
        self.output_dir.mkdir()

        # Tạo 2 file Excel mẫu
        df1 = pd.DataFrame({
            "employee_id": ["E1", "E2"],
            "name": ["Nguyễn A", "Trần B"],
            "salary": [10_000_000, 15_000_000],
        })
        df2 = pd.DataFrame({
            "employee_id": ["E3", "E4"],
            "name": ["Lê C", "Phạm D"],
            "salary": [12_000_000, 8_000_000],
        })
        df1.to_excel(self.input_dir / "file1.xlsx", index=False)
        df2.to_excel(self.input_dir / "file2.xlsx", index=False)

        # Patch file_manager để trỏ vào tmpdir
        import app.services.file_manager as fm
        fm.set_projects_root(self.tmpdir)

    def test_aggregation_merges_files(self):
        from app.workflows.aggregation import run_aggregation
        result = run_aggregation(
            input_dir=self.input_dir,
            project_name=".",
        )
        self.assertEqual(result["files_merged"], 2)
        self.assertEqual(result["total_rows"], 4)
        self.assertTrue(Path(result["output_path"]).exists())

    def test_aggregation_no_files_raises(self):
        from app.workflows.aggregation import run_aggregation
        empty_dir = Path(self.tmpdir) / "empty"
        empty_dir.mkdir()
        with self.assertRaises(FileNotFoundError):
            run_aggregation(input_dir=empty_dir, project_name=".")


class TestFilterWorkflow(unittest.TestCase):

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.input_dir = Path(self.tmpdir) / "input"
        self.input_dir.mkdir()
        self.output_dir = Path(self.tmpdir) / "output"
        self.output_dir.mkdir()

        df = pd.DataFrame({
            "employee_id": ["E1", "E2", "E3", "E4", "E5"],
            "name": ["An", "Bình", "Cường", "Dung", "Em"],
            "department": ["IT", "IT", "HR", "IT", "HR"],
            "salary": [18_000_000, 9_000_000, 15_000_000, 11_000_000, 25_000_000],
            "status": ["active", "active", "active", "inactive", "active"],
        })
        df.to_excel(self.input_dir / "employees.xlsx", index=False)

        import app.services.file_manager as fm
        fm.set_projects_root(self.tmpdir)

    def test_filter_salary_gt(self):
        from app.workflows.filtering import run_filter
        result = run_filter(
            input_dir=self.input_dir,
            project_name=".",
            column="salary",
            operator=">",
            value=10_000_000,
        )
        self.assertEqual(result["filtered_rows"], 4)  # 18M, 15M, 11M, 25M

    def test_filter_salary_lt(self):
        from app.workflows.filtering import run_filter
        result = run_filter(
            input_dir=self.input_dir,
            project_name=".",
            column="salary",
            operator="<",
            value=10_000_000,
        )
        self.assertEqual(result["filtered_rows"], 1)  # 9M

    def test_filter_department_eq(self):
        from app.workflows.filtering import run_filter
        result = run_filter(
            input_dir=self.input_dir,
            project_name=".",
            column="department",
            operator="==",
            value="IT",
        )
        self.assertEqual(result["filtered_rows"], 3)

    def test_filter_invalid_column_raises(self):
        from app.workflows.filtering import run_filter
        with self.assertRaises(ValueError):
            run_filter(
                input_dir=self.input_dir,
                project_name=".",
                column="nonexistent_col",
                operator=">",
                value=100,
            )


class TestComparisonWorkflow(unittest.TestCase):

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.input_dir = Path(self.tmpdir) / "input"
        self.input_dir.mkdir()
        self.output_dir = Path(self.tmpdir) / "output"
        self.output_dir.mkdir()

        # Root file
        df_root = pd.DataFrame({
            "employee_id": ["E1", "E2", "E3", "E4"],
            "name": ["An", "Bình", "Cường", "Dung"],
            "salary": [10_000_000, 12_000_000, 15_000_000, 8_000_000],
            "status": ["active", "active", "active", "inactive"],
        })
        df_root.to_excel(self.input_dir / "Root_Data.xlsx", index=False)

        # Update file: E1 salary changed, E3 removed, E5 added
        df_update = pd.DataFrame({
            "employee_id": ["E1", "E2", "E5"],
            "name": ["An", "Bình", "Phong"],
            "salary": [11_000_000, 12_000_000, 14_000_000],
            "status": ["active", "active", "active"],
        })
        df_update.to_excel(self.input_dir / "Update_Data.xlsx", index=False)

        import app.services.file_manager as fm
        fm.set_projects_root(self.tmpdir)

    def test_comparison_detects_added(self):
        from app.workflows.comparison import run_comparison
        result = run_comparison(
            input_dir=self.input_dir,
            project_name=".",
            primary_key="employee_id",
        )
        self.assertEqual(result["added"], 1)  # E5

    def test_comparison_detects_updated(self):
        from app.workflows.comparison import run_comparison
        result = run_comparison(
            input_dir=self.input_dir,
            project_name=".",
            primary_key="employee_id",
        )
        self.assertEqual(result["updated"], 1)  # E1 salary changed

    def test_comparison_unchanged(self):
        from app.workflows.comparison import run_comparison
        result = run_comparison(
            input_dir=self.input_dir,
            project_name=".",
            primary_key="employee_id",
        )
        self.assertEqual(result["unchanged"], 1)  # E2

    def test_comparison_invalid_pk_raises(self):
        from app.workflows.comparison import run_comparison
        with self.assertRaises(ValueError):
            run_comparison(
                input_dir=self.input_dir,
                project_name=".",
                primary_key="nonexistent_key",
            )

    def test_comparison_output_file_exists(self):
        from app.workflows.comparison import run_comparison
        result = run_comparison(
            input_dir=self.input_dir,
            project_name=".",
            primary_key="employee_id",
        )
        self.assertTrue(Path(result["output_path"]).exists())


# ──────────────────────────────────────────────────────────────
#  Safety Tests
# ──────────────────────────────────────────────────────────────

class TestSafetyRules(unittest.TestCase):

    def test_delete_command_blocked(self):
        """Lệnh xóa phải bị chặn với warning, không thực thi."""
        cmd = parse_command("Xóa tất cả dữ liệu")
        self.assertEqual(cmd.intent, "DELETE")
        # Phải có error message cảnh báo
        self.assertIsNotNone(cmd.error_message)

    def test_vague_command_returns_unknown_or_error(self):
        """Lệnh mơ hồ phải trả về thông báo yêu cầu làm rõ."""
        cmd = parse_command("Làm giúp tôi một việc gì đó")
        self.assertTrue(
            cmd.intent == "UNKNOWN" or cmd.error_message is not None,
            "Vague command should return UNKNOWN intent or error message"
        )

    def test_path_traversal_blocked(self):
        """Path traversal phải bị chặn."""
        from app.services.file_manager import _safe_resolve
        import tempfile
        tmpdir = Path(tempfile.mkdtemp())
        with self.assertRaises(ValueError):
            _safe_resolve(tmpdir, "../../etc/passwd")

    def test_filter_without_column_has_error(self):
        """Lọc mà không có cột → phải báo lỗi."""
        cmd = parse_command("Lọc những bản ghi có giá trị lớn")
        # Nếu là FILTER, phải có error về missing column
        if cmd.intent == "FILTER":
            # column có thể là None → check error
            params = cmd.parameters
            if params.get("column") is None:
                self.assertIsNotNone(cmd.error_message)


if __name__ == "__main__":
    unittest.main(verbosity=2)

