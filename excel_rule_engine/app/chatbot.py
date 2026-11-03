"""
Streamlit Chatbot Interface - Giao diện hội thoại cho Excel Rule Engine.
Chạy: streamlit run app/chatbot.py
"""

from __future__ import annotations

import uuid
from pathlib import Path
from typing import Any

import requests
import streamlit as st

from app.services.download_service import EXCEL_MIME, fetch_output_file
from app.report_wizard import render_report_wizard
from app.advanced_report_wizard import render_advanced_report_wizard
from app.report_plan_ui import render_pending_report
from app.ui_theme import inject_theme, render_hero, render_empty_chat, render_section_intro, render_sidebar_brand

# ──────────────────────────────────────────────────────────────
#  Config
# ──────────────────────────────────────────────────────────────
API_BASE = "http://localhost:8000"
DEFAULT_PROJECT = "demo_project"

st.set_page_config(
    page_title="Excel Studio | Data workspace",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ──────────────────────────────────────────────────────────────
#  Session State Init
# ──────────────────────────────────────────────────────────────
if "session_id" not in st.session_state:
    st.session_state.session_id = str(uuid.uuid4())
if "messages" not in st.session_state:
    st.session_state.messages = []
if "pending_comparison" not in st.session_state:
    st.session_state.pending_comparison = None
if "project" not in st.session_state:
    st.session_state.project = DEFAULT_PROJECT


# ──────────────────────────────────────────────────────────────
#  Helper Functions
# ──────────────────────────────────────────────────────────────

def call_api(endpoint: str, payload: dict) -> dict | None:
    try:
        resp = requests.post(f"{API_BASE}{endpoint}", json=payload, timeout=30)
        resp.raise_for_status()
        return resp.json()
    except requests.ConnectionError:
        return {"error": "❌ Không thể kết nối với API server. Hãy chắc chắn FastAPI đang chạy tại port 8000."}
    except requests.HTTPError as e:
        return {"error": f"❌ Lỗi HTTP {e.response.status_code}: {e.response.text}"}
    except Exception as e:
        return {"error": f"❌ Lỗi không xác định: {e}"}


def get_file_list(folder: str = "input") -> list[dict]:
    try:
        resp = requests.get(
            f"{API_BASE}/api/files",
            params={"project": st.session_state.project, "folder": folder},
            timeout=10,
        )
        if resp.status_code == 200:
            return resp.json().get("files", [])
    except Exception:
        pass
    return []


def add_message(role: str, content: str, metadata: dict | None = None):
    st.session_state.messages.append({
        "role": role,
        "content": content,
        "metadata": metadata or {},
    })


def render_message(msg: dict, message_index: int = 0):
    role = msg["role"]
    content = msg["content"]
    meta = msg.get("metadata", {})

    with st.chat_message(role, avatar="🧑‍💻" if role == "user" else "⚡"):
        st.markdown(content)

        if meta.get("intent_display"):
            with st.expander("🔍 Chi tiết phân tích", expanded=False):
                st.markdown(f"**Intent:** {meta['intent_display']}")
                st.markdown(f"**Workflow:** {meta['workflow_display']}")
                if meta.get("parsed"):
                    st.json(meta["parsed"])

        if meta.get("output_path"):
            _render_download_button(
                meta["output_path"],
                project=meta.get("project", st.session_state.project),
                key=f"chat_download_{message_index}",
            )

        if meta.get('summary'):
            st.dataframe(meta['summary'], use_container_width=True)

        if meta.get("file_list"):
            _render_file_list(meta["file_list"])

        if meta.get("warnings"):
            for w in meta["warnings"]:
                st.warning(w)


@st.cache_data(ttl=60, max_entries=32, show_spinner=False)
def _load_download_data(project: str, filename: str) -> bytes:
    return fetch_output_file(API_BASE, project, filename)


def _render_download_button(output_path: str, project: str | None = None, key: str | None = None):
    filename = Path(output_path).name
    project = project or st.session_state.project
    try:
        data = _load_download_data(project, filename)
    except requests.RequestException:
        st.warning(f"Kh\u00f4ng th\u1ec3 t\u1ea3i file {filename}. File c\u00f3 th\u1ec3 \u0111\u00e3 b\u1ecb x\u00f3a sau khi kh\u1edfi \u0111\u1ed9ng l\u1ea1i server; h\u00e3y t\u1ea1o l\u1ea1i k\u1ebft qu\u1ea3 ho\u1eb7c th\u1eed l\u1ea1i.")
        return
    st.download_button(
        label=f"T\u1ea3i xu\u1ed1ng {filename}",
        data=data,
        file_name=filename,
        mime=EXCEL_MIME,
        key=key,
    )


def _render_file_list(files: list[dict]):
    if not files:
        st.info("Không có file nào.")
        return
    for f in files:
        col1, col2, col3 = st.columns([3, 1, 1])
        col1.text(f.get("name", ""))
        col2.text(f.get("size", ""))
        col3.text(f.get("extension", ""))


def process_command(user_text: str):
    """Gửi lệnh tới API và xử lý phản hồi."""
    st.session_state.pending_report = None
    add_message("user", user_text)

    from app.core.analytical_request import is_analytical_request
    if is_analytical_request(user_text):
        with st.spinner("Đang phân tích nguồn và yêu cầu..."):
            plan = call_api("/api/report/preview", {
                "text": user_text, "project": st.session_state.project,
            })
        if not plan or plan.get("error"):
            add_message("assistant", "Không thể mở bộ phân tích báo cáo. Backend có thể chưa cập nhật; hãy khởi động lại backend/ứng dụng. Không chạy thay bằng gộp file.\n\n" + str((plan or {}).get("error", "Không có phản hồi.")))
        else:
            _handle_requires_input({"type": "report_plan", "text": user_text,
                                    "project": st.session_state.project, **plan}, {}, {})
        return
    with st.spinner("Đang xử lý..."):
        response = call_api("/api/command", {
            "text": user_text,
            "session_id": st.session_state.session_id,
            "project": st.session_state.project,
        })

    if not response:
        add_message("assistant", "❌ Không nhận được phản hồi từ server.")
        return

    if "error" in response and response.get("intent_display") is None:
        # Connection error
        add_message("assistant", response["error"])
        return

    intent_display = response.get("intent_display", "")
    workflow_display = response.get("workflow_display", "")
    parsed = response.get("parsed", {})
    error = response.get("error")
    result = response.get("result")
    requires_input = response.get("requires_input")

    meta = {
        "intent_display": intent_display,
        "workflow_display": workflow_display,
        "parsed": parsed,
        "project": st.session_state.project,
    }

    # ── Error ──
    if error and not result:
        add_message("assistant", f"⚠️ {error}", meta)
        return

    # ── HELP ──
    if result and "help_text" in result:
        add_message("assistant", result["help_text"], meta)
        return

    # ── Requires more input (multi-turn) ──
    if requires_input:
        _handle_requires_input(requires_input, meta, response)
        return

    # ── Success ──
    if result:
        _handle_success_result(parsed.get("intent", ""), result, meta)

    if error:
        meta_copy = {**meta}
        add_message("assistant", f"⚠️ {error}", meta_copy)


def _handle_requires_input(
    requires_input: dict,
    meta: dict,
    full_response: dict,
):
    """Xử lý khi cần thêm thông tin từ người dùng."""
    input_type = requires_input.get("type")
    if input_type == "report_plan":
        st.session_state.pending_report = requires_input
        add_message("assistant", "Đã phân tích yêu cầu. Hãy kiểm tra kế hoạch bên dưới trước khi tạo báo cáo.", meta)
        return
    message = requires_input.get("message", "Cần thêm thông tin.")

    if input_type == "primary_key":
        suggestions = requires_input.get("suggestions", [])
        task_id = requires_input.get("task_id")
        root_file = requires_input.get("root_file")
        update_file = requires_input.get("update_file")

        # Lưu context để dùng ở bước tiếp theo
        st.session_state.pending_comparison = {
            "task_id": task_id,
            "root_file": root_file,
            "update_file": update_file,
            "suggestions": suggestions,
        }
        msg = (
            f"📊 **So sánh dữ liệu**\n\n"
            f"{message}\n\n"
            f"Các cột gợi ý: `{', '.join(suggestions) if suggestions else 'không có gợi ý'}`\n\n"
            "_Nhập tên cột Primary Key vào ô chat bên dưới._"
        )
        add_message("assistant", msg, meta)

    elif input_type == "filter_params":
        add_message("assistant", f"⚠️ {message}", meta)


def _handle_success_result(intent: str, result: dict, meta: dict):
    """Xử lý và hiển thị kết quả thành công."""
    warnings = result.pop("warnings", [])
    output_path = result.get("output_path")

    if intent == "AGGREGATION":
        msg = (
            f"✅ **Gộp dữ liệu thành công!**\n"
            f"- Đã gộp **{result.get('files_merged', 0)}** file\n"
            f"- Tổng cộng **{result.get('total_rows', 0):,}** dòng"
        )
    elif intent == "FILTER":
        msg = (
            f"✅ **Lọc dữ liệu thành công!**\n"
            f"- Cột: `{result.get('column_used', '?')}`\n"
            f"- Tìm thấy **{result.get('filtered_rows', 0):,}** bản ghi"
        )
    elif intent == "COMPARISON":
        msg = (
            f"✅ **So sánh dữ liệu thành công!**\n"
            f"- 🟢 Thêm mới: **{result.get('added', 0)}**\n"
            f"- 🟡 Thay đổi: **{result.get('updated', 0)}**\n"
            f"- ⚪ Không đổi: **{result.get('unchanged', 0)}**"
        )
    elif intent == "FILE_LIST":
        files_detail = result.get("file_details", [])
        meta["file_list"] = files_detail
        file_names = result.get("files", [])
        if file_names:
            msg = f"📁 **Tìm thấy {len(file_names)} file:**\n" + "\n".join(f"  • `{f}`" for f in file_names)
        else:
            msg = "📁 Không tìm thấy file Excel nào."
        add_message("assistant", msg, meta)
        return
    elif intent == "EXPORT" and result.get("report_type") == "revenue":
        msg = (
            f"**Doanh thu {result['product']} năm {result['year']}: {result['revenue_total']:,.2f}**\n\n"
            f"Nguồn: {result['source_file']} · {result['total_rows']} dòng phù hợp. "
            "Đơn vị tiền tệ theo dữ liệu nguồn."
        )
    elif intent == "EXPORT":
        msg = (
            f"✅ **Tạo báo cáo thành công!**\n"
            f"- Tổng **{result.get('total_rows', 0):,}** dòng từ **{result.get('files_included', 0)}** file"
        )
    else:
        msg = "✅ Thao tác hoàn thành."

    if output_path:
        meta["output_path"] = output_path
        meta["project"] = st.session_state.project

    add_message("assistant", msg, {**meta, "warnings": warnings})


def handle_pending_comparison(user_text: str) -> bool:
    """Kiểm tra xem input hiện tại có phải là primary key cho comparison không."""
    pending = st.session_state.pending_comparison
    if not pending:
        return False

    primary_key = user_text.strip()
    st.session_state.pending_report = None
    add_message("user", user_text)

    with st.spinner("Đang so sánh dữ liệu..."):
        response = call_api("/api/execute/comparison", {
            "session_id": st.session_state.session_id,
            "task_id": pending.get("task_id"),
            "project": st.session_state.project,
            "primary_key": primary_key,
            "root_file": pending.get("root_file"),
            "update_file": pending.get("update_file"),
            "treat_as_full_snapshot": False,
        })

    st.session_state.pending_comparison = None

    if not response:
        add_message("assistant", "❌ Lỗi kết nối.")
        return True

    error = response.get("error")
    result = response.get("result")

    if error:
        add_message("assistant", f"❌ {error}")
    elif result:
        _handle_success_result("COMPARISON", result, {})

    return True


# ──────────────────────────────────────────────────────────────
#  SIDEBAR
# ──────────────────────────────────────────────────────────────

inject_theme()


def backend_online() -> bool:
    """Keep backend state explicit; offline report tools remain usable."""
    try:
        return requests.get(f"{API_BASE}/health", timeout=2).status_code == 200
    except requests.RequestException:
        return False


online = backend_online()
with st.sidebar:
    render_sidebar_brand()
    section = st.radio(
        "Không gian làm việc",
        ["Chatbot", "Tạo báo cáo", "Báo cáo nâng cao"],
        key="workspace_section",
    )
    st.divider()
    project = st.selectbox("Dự án chatbot", options=["demo_project"], index=0)
    st.session_state.project = project
    st.caption("File upload trong công cụ báo cáo được xử lý riêng, không tự thêm vào nguồn chatbot.")
    if st.button("↻ Làm mới kết nối & file", key="refresh_workspace", use_container_width=True):
        _load_download_data.clear()
        st.rerun()

    # File browsing is loaded only when explicitly requested, not on every chat rerun.
    if st.checkbox("Mở thư viện file dự án", key="show_project_files"):
        if not online:
            st.info("Kết nối backend để xem file dự án.")
        else:
            input_files = get_file_list("input")
            output_files = get_file_list("output")
            with st.expander(f"Nguồn dữ liệu · {len(input_files)}", expanded=True):
                if not input_files:
                    st.caption("Chưa có file nguồn.")
                for f in input_files:
                    st.write(f"📄 {f.get('name', '')}")
                    st.caption(f.get("size", ""))
            with st.expander(f"Kết quả · {len(output_files)}"):
                selected_name = st.selectbox(
                    "Chọn kết quả để tải", [f.get("name", "") for f in output_files],
                    key="selected_output_file",
                ) if output_files else None
                if selected_name:
                    _render_download_button(selected_name, project=project, key="sidebar_selected_download")
                else:
                    st.caption("Chưa có file kết quả.")
    st.divider()
    st.caption("RULE-BASED ENGINE · Không sử dụng LLM")
    st.caption(f"Phiên làm việc: {st.session_state.session_id[:8]}")
    st.caption("Dữ liệu phiên không thay thế kho lưu trữ. Hãy tải kết quả trước khi đóng ứng dụng.")

# ──────────────────────────────────────────────────────────────
#  MAIN AREA
# ──────────────────────────────────────────────────────────────
render_hero(online, section)
if section == "Tạo báo cáo":
    render_section_intro("Từ dữ liệu đến báo cáo.", "Chọn một mẫu có sẵn, xem trước và xuất Excel chỉ trong vài bước.")
    render_report_wizard()
elif section == "Báo cáo nâng cao":
    render_section_intro("Thiết kế phân tích của riêng bạn.", "Lọc, nối nguồn, pivot và so sánh kỳ bằng cấu hình rõ ràng — không cần viết code.")
    render_advanced_report_wizard()
else:
    # Gợi ý nhanh
    if not online:
        st.warning("Chatbot chưa kết nối backend. Bạn vẫn có thể dùng Tạo báo cáo và Báo cáo nâng cao ở thanh bên.")
    if st.session_state.pending_comparison:
        st.info("Đang chờ khóa đối chiếu. Nhập tên cột khóa bên dưới hoặc hủy tác vụ để bắt đầu yêu cầu khác.")
        if st.button("Hủy đối chiếu đang chờ", key="cancel_comparison"):
            st.session_state.pending_comparison = None
            st.rerun()
    if not st.session_state.messages:
        render_empty_chat()
    with st.expander("Thao tác nhanh · chọn một yêu cầu mẫu", expanded=not st.session_state.messages):
        quick_commands = [
            ("📂 Xem nguồn dữ liệu", "Liệt kê các file Excel"),
            ("🔗 Gộp file Excel", "Gộp tất cả file Excel"),
            ("🔎 Lọc theo mức lương", "Lọc nhân viên có lương trên 10 triệu"),
            ("⚖️ Đối chiếu thay đổi", "So sánh Root và Update"),
            ("📊 Báo cáo tổng hợp", "Tạo báo cáo tổng hợp"),
            ("💡 Hướng dẫn sử dụng", "Hướng dẫn"),
        ]
        quick_cols = st.columns(2)
        for i, (label, command) in enumerate(quick_commands):
            if quick_cols[i % 2].button(
                label, key=f"quick_{i}", use_container_width=True,
                help=command, disabled=not online or bool(st.session_state.pending_comparison),
            ):
                process_command(command)
                st.rerun()
    if st.session_state.messages:
        c1, c2 = st.columns([3, 1])
        c1.caption(f"HỘI THOẠI · {len(st.session_state.messages)} tin nhắn")
        with c2:
            with st.expander("Quản lý hội thoại"):
                history = "\n\n".join(f"{m['role'].upper()}: {m['content']}" for m in st.session_state.messages)
                st.download_button("Lưu hội thoại", data=history, file_name="conversation.txt", mime="text/plain", key="save_chat")
                confirm_clear = st.checkbox("Xác nhận xóa lịch sử phiên", key="confirm_clear_chat")
                if st.button("Xóa hội thoại", disabled=not confirm_clear, key="clear_chat"):
                    st.session_state.pending_report = None
                    st.session_state.messages = []
                    st.session_state.pending_comparison = None
                    st.rerun()
    # Hiển thị lịch sử chat
    for message_index, msg in enumerate(st.session_state.messages):
        render_message(msg, message_index)
    render_pending_report(call_api, add_message)
    # Chat input
    placeholder = "Nhập tên cột khóa, ví dụ employee_id…" if st.session_state.pending_comparison else "Bạn muốn xử lý dữ liệu như thế nào? Ví dụ: lọc nhân viên có lương trên 10 triệu…"
    if prompt := st.chat_input(placeholder, disabled=not online, key="workspace_chat_input"):
        # Kiểm tra xem có đang chờ primary key không
        if st.session_state.pending_comparison:
            handle_pending_comparison(prompt)
        else:
            process_command(prompt)
        st.rerun()