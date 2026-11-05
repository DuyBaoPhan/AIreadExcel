"""Session-local upload and report wizard, independent from the chatbot API."""
from __future__ import annotations

import hashlib
import json

import pandas as pd
import streamlit as st

from app.services.runtime.download_service import EXCEL_MIME
from app.services.reports.report_builder import (
    inspect_sheets, read_uploaded_table, build_report_bytes,
)


def render_report_wizard() -> None:
    """Preview exactly one selected source and export only that dataset."""
    with st.expander("Tạo báo cáo từ file của bạn", expanded=True):
        st.caption(
            "Upload → chọn sheet và dòng tiêu đề → xem trước → chọn mẫu → tải Excel. "
            "File này chỉ dùng trong phiên hiện tại, không được thêm vào dữ liệu demo/chatbot."
        )
        uploaded = st.file_uploader(
            "Chọn file Excel hoặc CSV (tối đa 20 MB)",
            type=["xlsx", "csv"], key="report_upload",
        )
        if uploaded is None:
            st.session_state.pop("uploaded_report_result", None)
            return
        raw = uploaded.getvalue()
        source_id = hashlib.sha256(raw).hexdigest()
        try:
            sheets = inspect_sheets(uploaded.name, raw)
        except (ValueError, OSError) as exc:
            st.error(str(exc))
            st.session_state.pop("uploaded_report_result", None)
            return
        left, right = st.columns(2)
        sheet = left.selectbox("Sheet dữ liệu", sheets, key=f"report_sheet_{source_id}_{uploaded.name}")
        header = right.number_input(
            "Dòng tiêu đề (bắt đầu từ 1)", min_value=1, max_value=100,
            value=1, step=1, key=f"report_header_{source_id}",
        )
        try:
            df = read_uploaded_table(uploaded.name, raw, sheet_name=sheet, header_row=int(header) - 1)
        except (ValueError, OSError) as exc:
            st.error(str(exc))
            st.session_state.pop("uploaded_report_result", None)
            return
        st.write(f"**{len(df):,} dòng · {len(df.columns)} cột** — xem trước tối đa 50 dòng")
        st.dataframe(df.head(50), use_container_width=True)
        st.caption("Báo cáo lấy toàn bộ dữ liệu của sheet đang chọn, không chỉ 50 dòng xem trước.")
        missing = int(df.isna().sum().sum())
        if missing:
            st.warning(f"Có {missing:,} ô trống. Hãy kiểm tra dữ liệu trước khi lập báo cáo.")

        labels = {"Tổng hợp": "general", "Nhân sự": "hr", "Doanh thu / bán hàng": "sales"}
        selected = st.selectbox("Mẫu báo cáo", list(labels), key="report_template")
        template = labels[selected]
        titles = {"general": "BÁO CÁO TỔNG HỢP", "hr": "BÁO CÁO NHÂN SỰ", "sales": "BÁO CÁO DOANH THU"}
        title = st.text_input("Tiêu đề báo cáo", value=titles[template], key=f"report_title_{template}")
        c1, c2 = st.columns(2)
        company = c1.text_input("Tên công ty / đơn vị", key="report_company")
        period = c2.text_input("Kỳ báo cáo (nhãn hiển thị)", placeholder="Ví dụ: Tháng 11/2026", key="report_period")
        st.caption("Kỳ báo cáo là nhãn trình bày, không tự lọc ngày trong dữ liệu.")
        prepared_by = st.text_input("Người lập báo cáo", key="report_preparer")
        group_column = value_column = None
        numeric = [col for col in df.columns if pd.api.types.is_numeric_dtype(df[col])
                   and not pd.api.types.is_bool_dtype(df[col])]
        ready = True
        if template in ("hr", "sales"):
            group_column = st.selectbox(
                "Cột phòng ban" if template == "hr" else "Cột phân nhóm (sản phẩm, tháng, nhân viên...)",
                list(df.columns), key=f"report_group_{source_id}_{template}",
            )
            value_column = st.selectbox(
                "Cột lương (không bắt buộc)" if template == "hr" else "Cột doanh thu cần cộng",
                [None] + numeric,
                format_func=lambda col: "— Chưa chọn —" if col is None else str(col),
                key=f"report_value_{source_id}_{template}",
            )
            st.info(
                "Mỗi dòng được tính là một bản ghi; không tự loại trùng. "
                "Chỉ chọn cột tiền thực tế để cộng, không chọn mã định danh. "
                "Cột dạng chữ sẽ không được tự chuyển thành tiền."
            )
            if template == "sales" and value_column is None:
                st.warning("Chọn cột doanh thu dạng số để tạo báo cáo bán hàng.")
                ready = False
        config = dict(template=template, title=title, company=company, period=period,
                      prepared_by=prepared_by, group_column=group_column, value_column=value_column)
        signature = hashlib.sha256(json.dumps(
            [source_id, uploaded.name, sheet, header, config], ensure_ascii=False, default=str,
        ).encode("utf-8")).hexdigest()
        result = st.session_state.get("uploaded_report_result")
        if result and result["signature"] != signature:
            st.session_state.pop("uploaded_report_result", None)
            result = None
        if st.button("Tạo báo cáo Excel", type="primary", disabled=not ready, key="create_uploaded_report"):
            try:
                with st.spinner("Đang tạo báo cáo..."):
                    data = build_report_bytes(df, **config)
                result = {"signature": signature, "data": data,
                          "filename": f"Report_{template}_{signature[:10]}.xlsx"}
                st.session_state.uploaded_report_result = result
            except (ValueError, OSError) as exc:
                st.error(str(exc))
                st.session_state.pop("uploaded_report_result", None)
                result = None
        if result:
            st.success("Báo cáo đã sẵn sàng. Dữ liệu upload không được ghi vào thư mục dùng chung.")
            st.download_button("Tải báo cáo Excel", data=result["data"],
                               file_name=result["filename"], mime=EXCEL_MIME,
                               key=f"uploaded_download_{signature}")
