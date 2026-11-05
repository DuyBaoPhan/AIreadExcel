"""
Response Generator - Tạo phản hồi thân thiện bằng tiếng Việt cho chatbot.
Không sử dụng LLM; toàn bộ text được hard-code theo template.
"""

from __future__ import annotations

from typing import Any

from legacy_nlp.command_parser import ParsedCommand
from legacy_nlp.intent_router import Intent


HELP_TEXT = """
## 📖 Hướng dẫn sử dụng Excel AI System

### Các lệnh hỗ trợ:

| Chức năng | Ví dụ câu lệnh |
|-----------|---------------|
| 🗂️ Gộp file | "Gộp tất cả file Excel trong thư mục input" |
| 🔍 Lọc dữ liệu | "Lọc nhân viên có lương trên 10 triệu" |
| 🔍 Tìm kiếm | "Tìm nhân viên thuộc phòng IT" |
| 📊 So sánh | "So sánh Root và Update" |
| 📁 Liệt kê file | "Liệt kê các file Excel" |
| 📤 Xuất báo cáo | "Tạo báo cáo tổng hợp" |

### Lưu ý:
- Đặt file Excel nguồn vào thư mục `input/` của project
- Kết quả xuất ra thư mục `output/`
- Hệ thống **không hỗ trợ xóa dữ liệu tự động** vì lý do an toàn
"""


def generate_confirmation_prompt(command: ParsedCommand) -> str:
    """Tạo thông báo xác nhận trước khi thực thi."""
    intent = command.intent
    params = command.parameters

    if intent == Intent.FILTER:
        col = params.get("column", "?")
        op = params.get("operator", "?")
        val = params.get("value", "?")
        return (
            f"🔍 **Xác nhận lọc dữ liệu:**\n"
            f"- Cột: `{col}`\n"
            f"- Điều kiện: `{op} {val}`\n\n"
            f"Bạn có muốn thực hiện không?"
        )

    if intent == Intent.COMPARISON:
        files = params.get("file_names", [])
        file_str = ", ".join(files) if files else "tất cả file trong input"
        return (
            f"📊 **Xác nhận so sánh dữ liệu:**\n"
            f"- Files: `{file_str}`\n"
            f"- Primary key sẽ được hỏi ở bước tiếp theo\n\n"
            f"Bạn có muốn thực hiện không?"
        )

    if intent == Intent.DELETE:
        return (
            "⚠️ **CẢNH BÁO: Lệnh xóa dữ liệu**\n\n"
            "Hệ thống không hỗ trợ xóa file gốc tự động.\n"
            "Nếu bạn cần xóa file output, vui lòng thực hiện thủ công."
        )

    return "Bạn có muốn thực hiện thao tác này không? (yes/no)"


def generate_intent_display(command: ParsedCommand) -> str:
    """Tạo chuỗi mô tả intent đã nhận diện."""
    intent_labels = {
        "AGGREGATION": "🗂️ Gộp/Tổng hợp dữ liệu",
        "FILTER": "🔍 Lọc dữ liệu",
        "COMPARISON": "📊 So sánh dữ liệu",
        "EXPORT": "📤 Xuất báo cáo",
        "FILE_LIST": "📁 Liệt kê file",
        "HELP": "❓ Trợ giúp",
        "DELETE": "🗑️ Xóa dữ liệu (bị chặn)",
        "UNKNOWN": "❓ Không xác định",
    }
    label = intent_labels.get(command.intent, command.intent)
    conf_pct = int(command.confidence * 100)
    return f"{label} (độ tin cậy: {conf_pct}%)"


def generate_workflow_display(command: ParsedCommand) -> str:
    """Mô tả workflow sẽ được thực thi."""
    workflows = {
        "AGGREGATION": "Aggregation Workflow → đọc tất cả file → chuẩn hoá cột → gộp → xuất Master_Report.xlsx",
        "FILTER": "Filter Workflow → đọc file → áp dụng điều kiện → xuất Filtered_Result.xlsx",
        "COMPARISON": "Comparison Workflow → đọc Root & Update → so sánh → phân loại Added/Updated/Unchanged → xuất Change_Log.xlsx",
        "EXPORT": "Export Workflow → tổng hợp → tạo báo cáo → xuất file",
        "FILE_LIST": "File Manager → liệt kê file trong project",
        "HELP": "Hiển thị hướng dẫn sử dụng",
        "DELETE": "⛔ Không thực thi (lý do an toàn)",
        "UNKNOWN": "⛔ Không có workflow (intent không xác định)",
    }
    return workflows.get(command.intent, "N/A")


def generate_success_message(intent: str, output_info: dict[str, Any]) -> str:
    """Tạo thông báo thành công sau khi workflow hoàn thành."""
    if intent == "AGGREGATION":
        rows = output_info.get("total_rows", 0)
        files = output_info.get("files_merged", 0)
        path = output_info.get("output_path", "output/")
        return (
            f"✅ **Gộp dữ liệu thành công!**\n"
            f"- Đã gộp **{files}** file Excel\n"
            f"- Tổng cộng **{rows:,}** dòng dữ liệu\n"
            f"- Đầu ra: `{path}`"
        )

    if intent == "FILTER":
        rows = output_info.get("filtered_rows", 0)
        path = output_info.get("output_path", "output/")
        return (
            f"✅ **Lọc dữ liệu thành công!**\n"
            f"- Tìm thấy **{rows:,}** bản ghi khớp điều kiện\n"
            f"- Đầu ra: `{path}`"
        )

    if intent == "COMPARISON":
        added = output_info.get("added", 0)
        updated = output_info.get("updated", 0)
        unchanged = output_info.get("unchanged", 0)
        path = output_info.get("output_path", "output/")
        return (
            f"✅ **So sánh dữ liệu thành công!**\n"
            f"- Thêm mới: **{added}** bản ghi\n"
            f"- Thay đổi: **{updated}** bản ghi\n"
            f"- Không đổi: **{unchanged}** bản ghi\n"
            f"- Đầu ra: `{path}`"
        )

    if intent == "FILE_LIST":
        files = output_info.get("files", [])
        if not files:
            return "📁 Không tìm thấy file Excel nào trong thư mục."
        file_list = "\n".join(f"  - `{f}`" for f in files)
        return f"📁 **Danh sách file Excel:**\n{file_list}"

    if intent == "EXPORT":
        path = output_info.get("output_path", "output/")
        return f"✅ **Xuất báo cáo thành công!**\n- Đầu ra: `{path}`"

    return "✅ Thao tác hoàn thành."


def generate_error_message(intent: str, error: str) -> str:
    """Tạo thông báo lỗi thân thiện."""
    return f"❌ **Lỗi xử lý ({intent}):**\n{error}"


def generate_help() -> str:
    return HELP_TEXT

