"""Advanced reporting UI; shared mode persists outputs, while uploads stay private to the session."""
from __future__ import annotations

import hashlib
import json
from datetime import date

import pandas as pd
import streamlit as st

from app.services.runtime.download_service import EXCEL_MIME
from app.services.reports.report_storage import persist_wizard_report
from app.services.reports.report_builder import inspect_sheets, read_uploaded_table
from app.services.reports.report_engine import join_sources, load_config, run_report, serialize_config
from app.services.reports.advanced_report_export import build_advanced_report_bytes

_RESULT_KEY = "advanced_report_result"


def _invalidate() -> None:
    st.session_state.pop(_RESULT_KEY, None)


def _source(label: str, key: str):
    uploaded = st.file_uploader(label, type=["xlsx", "csv"], key=key)
    if uploaded is None:
        return None
    raw = uploaded.getvalue()
    source_id = hashlib.sha256(raw).hexdigest()
    sheets = inspect_sheets(uploaded.name, raw)
    c1, c2 = st.columns(2)
    sheet = c1.selectbox("Sheet dữ liệu", sheets, key=f"{key}_sheet_{source_id}")
    header = c2.number_input("Dòng tiêu đề (bắt đầu từ 1)", min_value=1, max_value=100,
                             value=1, step=1, key=f"{key}_header_{source_id}")
    frame = read_uploaded_table(uploaded.name, raw, sheet_name=sheet, header_row=int(header) - 1)
    st.caption(f"{uploaded.name}: {len(frame):,} dòng · {len(frame.columns)} cột (xem trước 50 dòng)")
    st.dataframe(frame.head(50), use_container_width=True)
    return frame, [uploaded.name, source_id, sheet, header]


def _records(frame: pd.DataFrame):
    """Discard blank editor rows and normalize pandas missing values."""
    return frame.astype(object).where(pd.notna(frame), None).to_dict("records")


def _filter_value(value, operator: str, value_type: str):
    """Editor values are strings; lists use explicit JSON or comma syntax."""
    def scalar(item):
        if value_type == "number":
            return float(item)
        return str(item).strip()
    if operator in {"is_null", "not_null"}:
        return None
    if operator in {"in", "between"}:
        text = str(value).strip()
        items = json.loads(text) if text.startswith("[") else text.split(",")
        if not isinstance(items, list) or (operator == "between" and len(items) != 2):
            raise ValueError("Bộ lọc between cần đúng hai giá trị; in cần một danh sách.")
        return [scalar(item) for item in items]
    return scalar(value) if value is not None else None


def _editor_config(df: pd.DataFrame) -> dict:
    columns = list(df.columns)
    st.subheader("Bộ lọc và tổng hợp")
    st.caption("Thêm dòng bằng nút +. in: danh sách cách nhau bằng dấu phẩy hoặc mảng JSON. "
               "between: hai giá trị cách nhau bằng dấu phẩy hoặc [giá trị đầu, giá trị cuối]. "
               "Ngày dùng YYYY-MM-DD. Bỏ trống cột để bỏ qua dòng bộ lọc.")
    filters = st.data_editor(
        pd.DataFrame(columns=["column", "operator", "value", "type"]), num_rows="dynamic",
        key="advanced_filters", use_container_width=True,
        column_config={
            "column": st.column_config.SelectboxColumn("Cột", options=columns),
            "operator": st.column_config.SelectboxColumn("Toán tử", options=["eq", "ne", "gt", "ge", "lt", "le", "in", "between", "contains", "is_null", "not_null"], default="eq"),
            "value": st.column_config.TextColumn("Giá trị / danh sách"),
            "type": st.column_config.SelectboxColumn("Kiểu", options=["text", "number", "date"], default="text"),
        },
    )
    logic = st.selectbox("Kết hợp bộ lọc", ["and", "or"], key="advanced_logic")
    group_by = st.multiselect("Cột phân nhóm", columns, key="advanced_groups")
    config = {"version": 1, "filters": [], "filter_logic": logic, "group_by": group_by, "metrics": []}
    for row in _records(filters):
        if row.get("column"):
            op, kind = row.get("operator") or "eq", row.get("type") or "text"
            config["filters"].append(dict(column=row["column"], operator=op, type=kind,
                                          value=_filter_value(row.get("value"), op, kind)))
    if st.checkbox("Phân nhóm theo ngày", key="advanced_date_enabled"):
        col = st.selectbox("Cột ngày phân nhóm", columns, key="advanced_date_column")
        freq = st.selectbox("Đơn vị thời gian", ["day", "month", "quarter", "year"], key="advanced_frequency")
        alias = st.text_input("Tên cột thời gian", value="period", key="advanced_date_alias")
        config["date_group"] = {"column": col, "frequency": freq, "alias": alias}
        if alias and alias not in config["group_by"]:
            config["group_by"] = config["group_by"] + [alias]
    st.caption("rows = đếm số dòng (không cần cột). count = đếm ô không trống; nunique = đếm giá trị duy nhất. "
               "sum / mean chỉ dùng cho cột số. Thêm dòng để tạo nhiều chỉ tiêu.")
    metrics = st.data_editor(
        pd.DataFrame([{"column": None, "operation": "rows", "alias": "row_count"}]),
        num_rows="dynamic", key="advanced_metrics", use_container_width=True,
        column_config={"column": st.column_config.SelectboxColumn("Cột chỉ tiêu", options=columns),
                       "operation": st.column_config.SelectboxColumn("Phép tính", options=["rows", "sum", "mean", "min", "max", "count", "nunique"], required=True),
                       "alias": st.column_config.TextColumn("Tên kết quả", required=True)},
    )
    for row in _records(metrics):
        if row.get("operation") or row.get("alias"):
            config["metrics"].append(row)
    if st.checkbox("Tạo bảng pivot", key="advanced_pivot_enabled"):
        st.caption("Pivot sử dụng dữ liệu sau lọc; chọn tên cột gốc, không dùng tên chỉ tiêu tổng hợp.")
        config["metrics"] = []
        config["group_by"] = []
        config.pop("date_group", None)
        st.info("Chế độ pivot thay thế phân nhóm và các chỉ tiêu ở trên; không kết hợp so sánh kỳ.")
        config["pivot"] = {
            "index": st.multiselect("Dòng pivot", columns, key="advanced_pivot_index"),
            "columns": st.selectbox("Cột pivot", columns, key="advanced_pivot_columns"),
            "values": st.selectbox("Giá trị pivot", columns, key="advanced_pivot_values"),
            "operation": st.selectbox("Phép tính pivot", ["sum", "mean", "min", "max", "count", "nunique"], key="advanced_pivot_operation"),
        }
    if st.checkbox("Giới hạn Top N", key="advanced_top_enabled"):
        config["top_n"] = {
            "column": st.text_input("Tên cột kết quả để xếp hạng", value="row_count", key="advanced_top_column"),
            "n": int(st.number_input("Số dòng Top N", min_value=1, value=10, key="advanced_top_n")),
            "ascending": st.checkbox("Sắp xếp tăng dần", key="advanced_top_ascending"),
        }
    if st.checkbox("So sánh hai kỳ", key="advanced_comparison_enabled", disabled="pivot" in config) and "pivot" not in config:
        date_col = st.selectbox("Cột ngày so sánh", columns, key="advanced_comparison_column")
        config["comparison"] = {"date_column": date_col}
        today = date.today()
        previous_year = today.year - 1
        defaults = {"current_start": date(today.year, 1, 1), "current_end": today,
                    "previous_start": date(previous_year, 1, 1),
                    "previous_end": date(previous_year, 12, 31)}
        for field, label in [("current_start", "Kỳ hiện tại: từ ngày"), ("current_end", "Kỳ hiện tại: đến ngày"),
                             ("previous_start", "Kỳ trước: từ ngày"), ("previous_end", "Kỳ trước: đến ngày")]:
            value = st.date_input(label, value=defaults[field], key=f"advanced_{field}").isoformat()
            config["comparison"][field] = value + " 23:59:59.999999" if field.endswith("_end") else value
    return config


def render_advanced_report_wizard() -> None:
    """Render an independent, explicit advanced pipeline without a chatbot/API call."""
    with st.expander("Báo cáo nâng cao: lọc, ghép dữ liệu, pivot và so sánh kỳ", expanded=False):
        st.caption("Dữ liệu và kết quả chỉ lưu trong phiên hiện tại. Không gọi AI/API, không ghi vào dữ liệu dùng chung.")
        try:
            primary = _source("Nguồn dữ liệu chính (Excel / CSV)", "advanced_primary")
            if primary is None:
                _invalidate()
                return
            df, identity = primary
            join_config = None
            source_warnings = []
            if st.checkbox("Ghép thêm một nguồn dữ liệu", key="advanced_join_enabled"):
                secondary = _source("Nguồn dữ liệu thứ hai (Excel / CSV)", "advanced_secondary")
                if secondary is None:
                    _invalidate()
                    st.info("Chọn nguồn thứ hai để tiếp tục ghép dữ liệu.")
                    return
                right, secondary_identity = secondary
                left_on = st.multiselect("Khóa nguồn chính (theo thứ tự)", list(df.columns), key="advanced_left_on")
                right_on = st.multiselect("Khóa nguồn thứ hai (cùng thứ tự)", list(right.columns), key="advanced_right_on")
                how = st.selectbox("Kiểu ghép", ["left", "inner", "outer"], key="advanced_join_how")
                relationship = st.selectbox("Quan hệ khóa", ["many_to_one", "one_to_one", "one_to_many"], key="advanced_relationship")
                st.caption("Không cho phép many-to-many. Khóa trùng không phù hợp quan hệ sẽ bị từ chối để tránh nhân đôi tổng tiền.")
                join_config = [left_on, right_on, how, relationship]
                identity = [identity, secondary_identity, join_config]
                if not left_on or len(left_on) != len(right_on):
                    _invalidate()
                    st.warning("Chọn cùng số lượng khóa cho hai nguồn.")
                    return
                df, warnings = join_sources(df, right, left_on=left_on, right_on=right_on, how=how, relationship=relationship)
                source_warnings.extend(warnings)
                if relationship == 'one_to_many':
                    source_warnings.append('One-to-many join repeats left-source values; verify measures before summing.')
                for warning in source_warnings:
                    st.warning(str(warning))
                st.write("Xem trước dữ liệu đã ghép")
                st.dataframe(df.head(50), use_container_width=True)
            imported = st.file_uploader("Nhập cấu hình JSON (không chứa dữ liệu nguồn)", type=["json"], key="advanced_config_upload")
            use_imported = st.checkbox("Dùng cấu hình đã nhập", key="advanced_use_imported")
            if use_imported:
                if imported is None:
                    _invalidate()
                    st.warning("Chọn file JSON cấu hình trước khi bật chế độ này.")
                    return
                config = load_config(imported.getvalue())
                st.json(config)
                st.caption("Cấu hình đã nhập sẽ được kiểm tra với dữ liệu đang chọn khi bấm Kiểm tra hoặc Tạo báo cáo.")
            else:
                config = _editor_config(df)
            title = st.text_input("Tiêu đề báo cáo nâng cao", value="BÁO CÁO PHÂN TÍCH", key="advanced_title")
            company = st.text_input("Tên công ty / đơn vị", key="advanced_company")
            prepared_by = st.text_input("Người lập báo cáo", key="advanced_prepared_by")
            config_json = serialize_config(config)
            signature = hashlib.sha256(json.dumps([identity, config, title, company, prepared_by],
                                                    ensure_ascii=False, default=str, sort_keys=True).encode("utf-8")).hexdigest()
            result = st.session_state.get(_RESULT_KEY)
            if result and result["signature"] != signature:
                _invalidate()
                result = None
            st.download_button("Tải cấu hình JSON", data=config_json, file_name="advanced_report_config.json",
                               mime="application/json", key="advanced_config_download")
            if st.button("Kiểm tra cấu hình với dữ liệu", key="advanced_validate"):
                run_report(df, config)
                st.success("Cấu hình hợp lệ với dữ liệu đang chọn.")
            if st.button("Tạo báo cáo nâng cao", type="primary", key="advanced_generate"):
                _invalidate()
                with st.spinner("Đang xử lý và tạo báo cáo..."):
                    report = run_report(df, config)
                    report['warnings'] = source_warnings + report.get('warnings', [])
                    data = build_advanced_report_bytes(report, config, title=title, company=company, prepared_by=prepared_by)
                filename = persist_wizard_report(data, f"Advanced_Report_{signature[:10]}.xlsx",
                                                 st.session_state.get("project", "demo_project"))
                result = {"signature": signature, "data": data, "report": report, "filename": filename}
                st.session_state[_RESULT_KEY] = result
            if result:
                for warning in result["report"].get("warnings", []):
                    st.warning(str(warning))
                st.success("Báo cáo đã sẵn sàng. Thay đổi đầu vào sẽ hủy kết quả tải cũ.")
                st.dataframe(result["report"]["summary"].head(100), use_container_width=True)
                st.download_button("Tải Excel nâng cao", data=result["data"],
                                   file_name=result["filename"], mime=EXCEL_MIME,
                                   key=f"advanced_excel_{signature}")
        except (ValueError, TypeError, KeyError, OSError, UnicodeError) as exc:
            _invalidate()
            st.error(f"Không thể tạo báo cáo: {exc}")

