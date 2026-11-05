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


class TestAggregationWorkflow(unittest.TestCase):

    def setUp(self):
        """Tạo temp directory với file Excel mẫu."""
        self.tmpdir = tempfile.mkdtemp()
        self.input_dir = Path(self.tmpdir) / "test_project" / "input"
        self.input_dir.mkdir(parents=True)
        self.output_dir = Path(self.tmpdir) / "test_project" / "output"
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
        import app.services.sources.file_manager as fm
        fm.set_projects_root(self.tmpdir)

    def test_aggregation_merges_files(self):
        from app.workflows.aggregation import run_aggregation
        result = run_aggregation(
            input_dir=self.input_dir,
            project_name="test_project",
        )
        self.assertEqual(result["files_merged"], 2)
        self.assertEqual(result["total_rows"], 4)
        self.assertTrue(Path(result["output_path"]).exists())

    def test_aggregation_no_files_raises(self):
        from app.workflows.aggregation import run_aggregation
        empty_dir = Path(self.tmpdir) / "empty"
        empty_dir.mkdir()
        with self.assertRaises(FileNotFoundError):
            run_aggregation(input_dir=empty_dir, project_name="test_project")


class TestFilterWorkflow(unittest.TestCase):

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.input_dir = Path(self.tmpdir) / "test_project" / "input"
        self.input_dir.mkdir(parents=True)
        self.output_dir = Path(self.tmpdir) / "test_project" / "output"
        self.output_dir.mkdir()

        df = pd.DataFrame({
            "employee_id": ["E1", "E2", "E3", "E4", "E5"],
            "name": ["An", "Bình", "Cường", "Dung", "Em"],
            "department": ["IT", "IT", "HR", "IT", "HR"],
            "salary": [18_000_000, 9_000_000, 15_000_000, 11_000_000, 25_000_000],
            "status": ["active", "active", "active", "inactive", "active"],
        })
        df.to_excel(self.input_dir / "employees.xlsx", index=False)

        import app.services.sources.file_manager as fm
        fm.set_projects_root(self.tmpdir)

    def test_filter_salary_gt(self):
        from app.workflows.filtering import run_filter
        result = run_filter(
            input_dir=self.input_dir,
            project_name="test_project",
            column="salary",
            operator=">",
            value=10_000_000,
        )
        self.assertEqual(result["filtered_rows"], 4)  # 18M, 15M, 11M, 25M

    def test_filter_salary_lt(self):
        from app.workflows.filtering import run_filter
        result = run_filter(
            input_dir=self.input_dir,
            project_name="test_project",
            column="salary",
            operator="<",
            value=10_000_000,
        )
        self.assertEqual(result["filtered_rows"], 1)  # 9M

    def test_filter_department_eq(self):
        from app.workflows.filtering import run_filter
        result = run_filter(
            input_dir=self.input_dir,
            project_name="test_project",
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
                project_name="test_project",
                column="nonexistent_col",
                operator=">",
                value=100,
            )


class TestComparisonWorkflow(unittest.TestCase):

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.input_dir = Path(self.tmpdir) / "test_project" / "input"
        self.input_dir.mkdir(parents=True)
        self.output_dir = Path(self.tmpdir) / "test_project" / "output"
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

        import app.services.sources.file_manager as fm
        fm.set_projects_root(self.tmpdir)

    def test_comparison_detects_added(self):
        from app.workflows.comparison import run_comparison
        result = run_comparison(
            input_dir=self.input_dir,
            project_name="test_project",
            primary_key="employee_id",
        )
        self.assertEqual(result["added"], 1)  # E5

    def test_comparison_detects_updated(self):
        from app.workflows.comparison import run_comparison
        result = run_comparison(
            input_dir=self.input_dir,
            project_name="test_project",
            primary_key="employee_id",
        )
        self.assertEqual(result["updated"], 1)  # E1 salary changed

    def test_comparison_unchanged(self):
        from app.workflows.comparison import run_comparison
        result = run_comparison(
            input_dir=self.input_dir,
            project_name="test_project",
            primary_key="employee_id",
        )
        self.assertEqual(result["unchanged"], 1)  # E2

    def test_comparison_invalid_pk_raises(self):
        from app.workflows.comparison import run_comparison
        with self.assertRaises(ValueError):
            run_comparison(
                input_dir=self.input_dir,
                project_name="test_project",
                primary_key="nonexistent_key",
            )

    def test_comparison_output_file_exists(self):
        from app.workflows.comparison import run_comparison
        result = run_comparison(
            input_dir=self.input_dir,
            project_name="test_project",
            primary_key="employee_id",
        )
        self.assertTrue(Path(result["output_path"]).exists())


# ──────────────────────────────────────────────────────────────
#  Safety Tests
# ──────────────────────────────────────────────────────────────

class TestSafetyRules(unittest.TestCase):


    def test_path_traversal_blocked(self):
        """Path traversal phải bị chặn."""
        from app.services.sources.file_manager import _safe_resolve
        import tempfile
        tmpdir = Path(tempfile.mkdtemp())
        with self.assertRaises(ValueError):
            _safe_resolve(tmpdir, "../../etc/passwd")


if __name__ == "__main__":
    unittest.main(verbosity=2)

