"""In-memory upload and report-generation contract tests."""
import unittest
from io import BytesIO
from unittest.mock import patch

import pandas as pd
from openpyxl import load_workbook

from app.services.report_builder import (
    inspect_sheets, read_uploaded_table, build_report_bytes, MAX_UPLOAD_BYTES,
)


class ReportBuilderTests(unittest.TestCase):
    def setUp(self):
        self.df = pd.DataFrame({"Department": ["A", "A", "B"],
                                "Salary": [10, 20, 30], "ID": [100, 101, 102],
                                "Text": ["=SUM(1,2)", "@cmd", None]})

    def workbook(self):
        buffer = BytesIO()
        with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
            self.df.to_excel(writer, sheet_name="People", index=False)
            writer.sheets["People"].cell(2, 4).data_type = "s"
            pd.DataFrame({"Group": ["West"], "Amount": [23]}).to_excel(
                writer, sheet_name="Sales", index=False, startrow=2)
        return buffer.getvalue()

    def test_xlsx_sheet_and_header_selection(self):
        data = self.workbook()
        self.assertEqual(inspect_sheets("input.XLSX", data), ["People", "Sales"])
        selected = read_uploaded_table("input.xlsx", data, "Sales", 2)
        self.assertEqual(selected.iloc[0].tolist(), ["West", 23])
        actual = read_uploaded_table("input.xlsx", data)
        expected = self.df.copy()
        expected["Text"] = expected["Text"].fillna(float("nan"))
        pd.testing.assert_frame_equal(actual, expected)

    def test_csv_upload_and_header(self):
        data = b"Report\nGroup,Amount\nWest,12\nEast,5\n"
        self.assertEqual(inspect_sheets("sales.csv", data), ["CSV"])
        self.assertEqual(read_uploaded_table("sales.csv", data, header_row=1).shape, (2, 2))
        self.assertEqual(inspect_sheets("x.csv", b"A,B\n1,2\n"), ["CSV"])
        self.assertEqual(read_uploaded_table("x.csv", b"\xef\xbb\xbfA\n1\n").columns.tolist(), ["A"])

    def test_upload_errors(self):
        for filename, data in [("a.xls", b"abc"), ("a.csv", b""),
                               ("a.xlsx", b"not xlsx"), ("a.csv", b"A,B\n"),
                               ("a.csv", b"x" * (MAX_UPLOAD_BYTES + 1))]:
            with self.subTest(filename=filename, size=len(data)), self.assertRaises(ValueError):
                read_uploaded_table(filename, data)
        for kwargs in ({"sheet_name": "Missing"}, {"header_row": -1},
                       {"sheet_name": None}, {"header_row": True}):
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                read_uploaded_table("a.xlsx", self.workbook(), **kwargs)
        with patch("app.services.report_builder.MAX_ROWS", 1), self.assertRaises(ValueError):
            read_uploaded_table("x.csv", b"A\n1\n2\n")

    def test_general_workbook_and_safe_detail(self):
        before = self.df.copy(deep=True)
        result = build_report_bytes(self.df, title="=Title", company="=Company", prepared_by="=Name")
        wb = load_workbook(BytesIO(result))
        self.assertEqual(wb.sheetnames, ["Report", "Data", "Statistics"])
        self.assertEqual(wb["Report"]["A1"].value, "=Title")
        self.assertEqual(wb["Report"]["A1"].data_type, "s")
        self.assertEqual(wb["Report"]["B4"].data_type, "s")
        self.assertEqual(wb["Report"]["B10"].value, 3)
        self.assertEqual(wb["Report"]["B12"].value, 1)
        self.assertEqual(wb["Data"]["D2"].value, "=SUM(1,2)")
        self.assertEqual(wb["Data"]["D2"].data_type, "s")
        self.assertEqual(wb["Data"]["C2"].value, 100)
        self.assertTrue(wb["Data"].tables)
        pd.testing.assert_frame_equal(self.df, before)

    def test_hr_summary_and_chart(self):
        wb = load_workbook(BytesIO(build_report_bytes(self.df, "hr", group_column="Department", value_column="Salary")))
        ws = wb["Report"]
        self.assertEqual([ws.cell(10, c).value for c in range(1, 5)], ["A", 2, 30, 15])
        self.assertEqual(len(ws._charts), 1)
        self.assertEqual(ws["C9"].value, "Tổng lương")
        wb = load_workbook(BytesIO(build_report_bytes(self.df, "hr", group_column="Department")))
        self.assertEqual(wb["Report"]["C9"].value, None)

    def test_sales_explicit_mapping(self):
        wb = load_workbook(BytesIO(build_report_bytes(self.df, "sales", group_column="Department", value_column="Salary")))
        self.assertEqual(wb["Report"]["C10"].value, 30)
        self.assertEqual(wb["Report"]["C11"].value, 30)
        self.assertNotEqual(wb["Report"]["C10"].value, 201)

    def test_validation_and_no_inferred_mapping(self):
        bad_cases = [({}, pd.DataFrame()), ({"template": "unknown"}, self.df),
                     ({"template": "hr"}, self.df),
                     ({"template": "sales", "group_column": "Department"}, self.df),
                     ({"template": "sales", "group_column": "Department", "value_column": "Text"}, self.df),
                     ({"template": "hr", "group_column": "Absent"}, self.df),
                     ({"template": "sales", "group_column": "Salary", "value_column": "Salary"}, self.df)]
        for kwargs, frame in bad_cases:
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                build_report_bytes(frame, **kwargs)
        for values in ([True, False], [float("inf"), 2], [None, None], ["12", "bad"]):
            with self.subTest(values=values), self.assertRaises(ValueError):
                build_report_bytes(pd.DataFrame({"Group": ["A", "B"], "Value": values}),
                                   "sales", group_column="Group", value_column="Value")

    def test_numeric_strings_and_missing_groups(self):
        frame = pd.DataFrame({"Group": ["A", None], "Value": ["12", "8"]})
        wb = load_workbook(BytesIO(build_report_bytes(frame, "sales", group_column="Group", value_column="Value")))
        self.assertEqual(wb["Report"]["C10"].value, 12)
        self.assertEqual(wb["Report"]["C11"].value, 8)
        self.assertEqual(wb["Data"]["B2"].value, "12")


if __name__ == "__main__":
    unittest.main()

