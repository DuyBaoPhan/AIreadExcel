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

# ──────────────────────────────────────────────────────────────
#  Config
# ──────────────────────────────────────────────────────────────
API_BASE = "http://localhost:8000"
DEFAULT_PROJECT = "demo_project"

st.set_page_config(
    page_title="Excel AI Chatbot",
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
    add_message("user", user_text)

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

with st.sidebar:
    st.title("⚙️ Cài đặt")

    project = st.selectbox(
        "Project",
        options=["demo_project"],
        index=0,
    )
    st.session_state.project = project

    st.divider()
    st.subheader("📁 File trong Input")
    if st.button("🔄 Làm mới danh sách"):
        st.rerun()

    input_files = get_file_list("input")
    if input_files:
        for f in input_files:
            st.text(f"📄 {f.get('name')} ({f.get('size')})")
    else:
        st.info("Không có file nào trong input/")

    st.divider()
    st.subheader("📤 File Output")
    output_files = get_file_list("output")
    if output_files:
        for f in output_files:
            fname = f.get("name", "")
            project_name = st.session_state.project
            _render_download_button(
                fname, project=project_name, key=f"sidebar_download_{project_name}_{fname}",
            )
            st.caption(f.get("size", ""))
    else:
        st.info("Chưa có file output.")

    st.divider()
    st.caption(f"Session: `{st.session_state.session_id[:8]}...`")
    if st.button("🗑️ Xoá lịch sử chat"):
        st.session_state.messages = []
        st.session_state.pending_comparison = None
        st.rerun()


# ──────────────────────────────────────────────────────────────
#  MAIN AREA
# ──────────────────────────────────────────────────────────────

st.title("📊 Excel AI Chatbot")
st.markdown(
    "_Hệ thống xử lý Excel bằng Rule-based Engine — **không sử dụng LLM**_"
)

# Hiển thị trạng thái API
try:
    health = requests.get(f"{API_BASE}/health", timeout=3)
    if health.status_code == 200:
        st.success("✅ API Server đang hoạt động")
    else:
        st.error("❌ API Server gặp sự cố")
except Exception:
    st.error("❌ Không kết nối được API Server. Chạy: `uvicorn app.main:app --reload`")

st.divider()

render_report_wizard()

st.divider()

# Gợi ý nhanh
st.markdown("**💡 Thử ngay:**")
quick_cols = st.columns(3)
quick_commands = [
    "Liệt kê các file Excel",
    "Gộp tất cả file Excel",
    "Lọc nhân viên có lương trên 10 triệu",
    "So sánh Root và Update",
    "Tạo báo cáo tổng hợp",
    "Hướng dẫn",
]
for i, cmd in enumerate(quick_commands):
    col = quick_cols[i % 3]
    if col.button(cmd, key=f"quick_{i}"):
        process_command(cmd)
        st.rerun()

st.divider()

# Hiển thị lịch sử chat
for message_index, msg in enumerate(st.session_state.messages):
    render_message(msg, message_index)

# Chat input
if prompt := st.chat_input("Nhập câu lệnh bằng tiếng Việt..."):
    # Kiểm tra xem có đang chờ primary key không
    if st.session_state.pending_comparison:
        handle_pending_comparison(prompt)
    else:
        process_command(prompt)
    st.rerun()

