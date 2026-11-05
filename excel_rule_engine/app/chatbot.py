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
    page_title="Excel Assistant",
    page_icon="💬",
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
        resp = requests.post(f"{API_BASE}{endpoint}", json=payload, timeout=150)
        resp.raise_for_status()
        return resp.json()
    except requests.ConnectionError:
        return {"error": "❌ Không thể kết nối với API server. Hãy chắc chắn FastAPI đang chạy tại port 8000."}
    except requests.HTTPError as e:
        try:
            detail = e.response.json().get("detail")
        except (ValueError, AttributeError):
            detail = None
        return {"error": detail if isinstance(detail, str) else f"HTTP {e.response.status_code}: Khong the xu ly yeu cau."}
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

    with st.chat_message(role):
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
        if meta.get('detail_preview'):
            st.caption(f"Xem truoc toi da 50 dong / {meta.get('total_rows', '?')} dong phu hop.")
            st.dataframe(meta['detail_preview'], use_container_width=True)

        if meta.get("citations"):
            with st.expander("Nguồn bằng chứng"):
                for citation in meta["citations"]:
                    st.write(f"[{citation['number']}] {citation['source']} · sheet {citation['sheet']} · dòng {citation['row']}")
                    st.text(citation['text'])

        if meta.get("file_list"):
            _render_file_list(meta["file_list"])

        if meta.get("warnings"):
            from app.services.chat_presentation import visible_chat_warnings
            for w in visible_chat_warnings(meta["warnings"]):
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

    if st.session_state.get("ai_planner_enabled", False):
        st.session_state.pending_update = None
        with st.spinner("Dang trao doi voi tro ly..."):
            response = call_api("/api/chat", {"text": user_text, "project": st.session_state.project,
                "session_id": st.session_state.get("agent_session_id")})
        if not response or response.get("error"):
            add_message("assistant", str((response or {}).get("error", "Khong co phan hoi.")))
            return
        st.session_state.agent_session_id = response["session_id"]
        result = response.get("result") or {}
        add_message("assistant", response.get("reply", ""), {
            "project": st.session_state.project, "applied_filters": result.get("applied_filters"), "citations": response.get("citations", []), "output_path": result.get("output_path"),
            "summary": result.get("summary", []), "detail_preview": result.get("detail_preview", []),
            "total_rows": result.get("total_rows"), "warnings": result.get("warnings", [])})
        if response.get("update_proposal"):
            st.session_state.pending_update = response["update_proposal"]
        return

    from app.core.analytical_request import is_analytical_request
    if is_analytical_request(user_text):
        automatic = st.session_state.get("auto_reports", True)
        endpoint = "/api/report/auto" if automatic else "/api/report/preview"
        with st.spinner("Đang chọn nguồn và xử lý yêu cầu..."):
            response = call_api(endpoint, {
                "text": user_text, "project": st.session_state.project,
            })
        if not response or response.get("error"):
            add_message("assistant", "Không thể xử lý báo cáo. Nếu gặp HTTP 404 trên Streamlit Cloud: cập nhật mã lên đúng nhánh và Reboot app. Không chạy thay bằng gộp file.\n\n" + str((response or {}).get("error", "Không có phản hồi.")))
        elif response.get("result"):
            _handle_success_result("EXPORT", response["result"], {})
        else:
            plan = response.get("report_plan", response.get("requires_input", response))
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
        status = requires_input.get("status")
        if status == "ready":
            message = 'Đã lập kế hoạch. Hãy kiểm tra bên dưới trước khi tạo báo cáo.'
        elif status == "unsupported":
            message = 'Yêu cầu có phần chưa được hỗ trợ. Chưa có báo cáo nào được tạo; xem chi tiết bên dưới.'
        else:
            message = 'Chưa thể tạo báo cáo vì yêu cầu còn điểm chưa xác định. Hãy xem câu hỏi bên dưới.'
        add_message("assistant", message, meta)
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
    elif intent == "EXPORT" and result.get("report_type") == "planned":
        msg = (f"**Đã xử lý báo cáo.**\n\nNguồn: {result.get('source_file', '')} · "
               f"{result.get('total_rows', 0):,} dòng phù hợp.")
        if result.get("selection_reason"):
            msg += "\n\n" + result["selection_reason"]
        if result.get("explanation"):
            msg += "\n\n" + "\n".join("• " + str(line) for line in result["explanation"])
        meta.update(summary=result.get("summary", []), detail_preview=result.get("detail_preview", []),
                    total_rows=result.get("total_rows"), selection_reason=result.get("selection_reason", ""))
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
# Read server mode: AI routing must not be gated by keyword detection.
try:
    planner_info = requests.get(f"{API_BASE}/api/planner/status", timeout=3).json() if online else {}
except (requests.RequestException, ValueError):
    planner_info = {}
st.session_state.ai_planner_enabled = planner_info.get("planner") == "openai"

with st.sidebar:
    render_sidebar_brand()
    if st.button("＋ Cuộc trò chuyện mới", key="new_chat", use_container_width=True):
        if st.session_state.get("pending_update") and st.session_state.get("agent_session_id"):
            call_api("/api/chat/update/cancel", {"project": st.session_state.project,
                "session_id": st.session_state.agent_session_id,
                "token": st.session_state.pending_update["token"]})
        st.session_state.messages = []
        st.session_state.agent_session_id = None
        st.session_state.pending_update = None
        st.session_state.pending_report = None
        st.session_state.pending_comparison = None
        st.session_state.session_id = str(uuid.uuid4())
        st.rerun()

    section = st.radio(
        "Không gian làm việc",
        ["Chatbot", "Tạo báo cáo", "Báo cáo nâng cao"],
        key="workspace_section",
    )
    st.divider()
    project = st.selectbox("Dự án chatbot", options=["demo_project"], index=0)
    st.session_state.project = project
    if section == "Chatbot" and st.checkbox("Thêm nguồn cho chatbot / RAG", key="show_chat_upload"):
        with st.expander("Thêm Excel làm nguồn chatbot / RAG"):
            st.caption("Tệp sẽ được lưu làm nguồn của dự án; không ghi đè tệp trùng tên. Các đoạn truy xuất có thể được gửi lên OpenAI.")
            uploaded_source = st.file_uploader("Nguồn Excel/CSV", type=["xlsx", "csv"], key="chat_source_upload")
            if st.button("Lưu làm nguồn chatbot", key="save_chat_source", disabled=not online or uploaded_source is None):
                try:
                    upload_result = requests.post(f"{API_BASE}/api/chat/sources/upload", data={"project": project},
                        files={"file": (uploaded_source.name, uploaded_source.getvalue())}, timeout=60)
                    upload_result.raise_for_status()
                    st.success("Đã thêm nguồn. Chỉ mục sẽ được tạo/làm mới khi tra cứu.")
                except requests.RequestException:
                    st.error("Không thể thêm nguồn; kiểm tra tên tệp trùng, định dạng hoặc giới hạn 20 tệp / 40 MB.")

    if st.session_state.get("ai_planner_enabled", False):
        st.caption("OpenAI + RAG: truy xuất Excel cục bộ; các đoạn bằng chứng liên quan được gửi lên OpenAI để trả lời có dẫn nguồn.")
        if not planner_info.get("configured"):
            st.warning("Chưa cấu hình OPENAI_API_KEY trong backend / Streamlit Secrets.")
    else:
        st.caption("Đang dùng bộ quy tắc offline. Cấu hình OPENAI_API_KEY để bật AI agent, sau đó Reboot app.")

    st.caption("File upload trong công cụ báo cáo được xử lý riêng, không tự thêm vào nguồn chatbot.")
    st.checkbox("Tự động tạo báo cáo khi yêu cầu rõ ràng", value=True, disabled=st.session_state.get("ai_planner_enabled", False), key="auto_reports")
    st.caption("Chỉ hỏi lại khi nguồn hoặc phép tính còn mơ hồ. Tắt để xem và xác nhận kế hoạch trước khi xuất.")
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
            ("Khám phá dữ liệu", "Tôi có thể hỏi những gì về dữ liệu hiện có?"),
            ("Phân tích nhân sự", "Ai có lương cao nhất phòng IT?"),
            ("Tra cứu có dẫn nguồn", "Các tệp đã cung cấp có thông tin gì?"),
            ("Hướng dẫn sử dụng", "Hướng dẫn tôi cách hỏi dữ liệu và xuất báo cáo."),
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
                    st.session_state.agent_session_id = None
                    st.session_state.pending_update = None
                    st.session_state.pending_comparison = None
                    st.rerun()
    # Hiển thị lịch sử chat
    for message_index, msg in enumerate(st.session_state.messages):
        render_message(msg, message_index)
    render_pending_report(call_api, add_message)
    pending_update = st.session_state.get("pending_update")
    if pending_update:
        with st.container(border=True):
            st.subheader("Xác nhận sửa trực tiếp tệp nguồn")
            st.json(pending_update["preview"])
            st.warning("Chỉ ghi sau khi xác nhận. Hệ thống sẽ lưu bản sao lưu trước khi thay thế tệp.")
            yes, no = st.columns(2)
            if yes.button("Xác nhận cập nhật", key="confirm_source_update", type="primary"):
                outcome = call_api("/api/chat/update/confirm", {"project": st.session_state.project,
                    "session_id": st.session_state.agent_session_id, "token": pending_update["token"]})
                add_message("assistant", (outcome or {}).get("reply", (outcome or {}).get("error", "Khong co phan hoi.")))
                st.session_state.pending_update = None
                st.rerun()
            if no.button("Hủy thay đổi", key="cancel_source_update"):
                call_api("/api/chat/update/cancel", {"project": st.session_state.project,
                    "session_id": st.session_state.agent_session_id, "token": pending_update["token"]})
                st.session_state.pending_update = None
                st.rerun()

    # Chat input
    placeholder = "Nhập tên cột khóa, ví dụ employee_id." if st.session_state.pending_comparison else "Hỏi về dữ liệu hoặc nhắn cho Excel Assistant…"
    if prompt := st.chat_input(placeholder, disabled=not online, key="workspace_chat_input"):
        # Kiểm tra xem có đang chờ primary key không
        if st.session_state.pending_comparison:
            handle_pending_comparison(prompt)
        else:
            process_command(prompt)
        st.rerun()
