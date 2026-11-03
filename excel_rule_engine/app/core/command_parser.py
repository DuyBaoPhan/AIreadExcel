"""
Command Parser - Chuyển đổi câu lệnh tự nhiên thành ParsedCommand (Pydantic model).
Không sử dụng LLM; chỉ dùng Rule-based Intent + Entity extraction.
"""

from __future__ import annotations

import logging
from typing import Any

from pydantic import BaseModel, Field

from app.core.intent_router import Intent, IntentResult, classify_intent
from app.core.entity_extractor import extract_entities, extract_source_folder

logger = logging.getLogger(__name__)


class ParsedCommand(BaseModel):
    """Cấu trúc lệnh đã được phân tích."""

    intent: str
    confidence: float = Field(ge=0.0, le=1.0)
    parameters: dict[str, Any] = Field(default_factory=dict)
    requires_confirmation: bool = False
    error_message: str | None = None
    raw_text: str = ""

    def is_valid(self) -> bool:
        return self.error_message is None

    def to_dict(self) -> dict[str, Any]:
        return self.model_dump()


def _build_aggregation(text: str, entities: dict[str, Any]) -> tuple[dict[str, Any], bool]:
    params: dict[str, Any] = {
        "source": entities.get("source", "input"),
        "file_type": ".xlsx",
        "specific_files": entities.get("file_names", []),
    }
    return params, False


def _build_filter(text: str, entities: dict[str, Any]) -> tuple[dict[str, Any], bool, str | None]:
    column = entities.get("column")
    operator = entities.get("operator")
    value = entities.get("value")

    # Mặc định toán tử so sánh bằng '==' nếu có cột và giá trị mà thiếu operator (ví dụ 'tháng 4', 'phòng IT')
    if column is not None and value is not None and operator is None:
        operator = "=="

    error: str | None = None
    if column is None:
        error = (
            "Không xác định được cột cần lọc. "
            "Vui lòng chỉ rõ, ví dụ: 'lọc nhân viên có lương trên 10 triệu'."
        )
    elif operator is None:
        error = (
            "Không xác định được điều kiện lọc (lớn hơn, nhỏ hơn, bằng, …). "
            "Vui lòng bổ sung điều kiện."
        )
    elif value is None:
        error = (
            "Không xác định được giá trị để lọc. "
            "Vui lòng bổ sung giá trị, ví dụ: '10 triệu' hoặc 'IT'."
        )

    params: dict[str, Any] = {
        "source": entities.get("source", "input"),
        "column": column,
        "operator": operator,
        "value": value,
    }
    requires_confirmation = column is not None and operator is not None and value is not None
    return params, requires_confirmation, error


def _build_comparison(text: str, entities: dict[str, Any]) -> tuple[dict[str, Any], bool]:
    file_names = entities.get("file_names", [])
    params: dict[str, Any] = {
        "source": entities.get("source", "input"),
        "file_names": file_names,
        "primary_key": None,   # sẽ hỏi người dùng ở bước sau
        "treat_as_full_snapshot": False,
    }
    return params, True  # luôn yêu cầu xác nhận primary key


def _build_export(text: str, entities: dict[str, Any]) -> tuple[dict[str, Any], bool]:
    params: dict[str, Any] = {
        "source": entities.get("source", "input"),
        "output_folder": "output",
    }
    return params, False


def _build_file_list(text: str, entities: dict[str, Any]) -> tuple[dict[str, Any], bool]:
    params: dict[str, Any] = {
        "folder": entities.get("source", "input"),
    }
    return params, False


def _build_help(_text: str, _entities: dict[str, Any]) -> tuple[dict[str, Any], bool]:
    return {}, False


def _build_delete(_text: str, _entities: dict[str, Any]) -> tuple[dict[str, Any], bool]:
    return {}, True  # luôn yêu cầu xác nhận


def parse_command(raw_text: str) -> ParsedCommand:
    """
    Phân tích câu lệnh đầu vào thành ParsedCommand.

    Raises không có ngoại lệ; thay vào đó trả về ParsedCommand.error_message
    khi thiếu thông tin.
    """
    from app.workflows.revenue_report import is_revenue_request, parse_revenue_request
    if is_revenue_request(raw_text) and classify_intent(raw_text).intent != Intent.DELETE:
        try:
            parse_revenue_request(raw_text)
            error = None
        except ValueError as exc:
            error = str(exc)
        return ParsedCommand(intent="EXPORT", confidence=1.0,
                             parameters={"report_type": "revenue"},
                             error_message=error, raw_text=raw_text)
    intent_result: IntentResult = classify_intent(raw_text)
    intent = intent_result.intent
    entities = extract_entities(raw_text)

    logger.info(
        "Intent=%s confidence=%.3f entities=%s",
        intent, intent_result.confidence, entities,
    )

    if intent == Intent.UNKNOWN:
        return ParsedCommand(
            intent=Intent.UNKNOWN,
            confidence=0.0,
            error_message=(
                "Tôi không hiểu yêu cầu của bạn. "
                "Vui lòng diễn đạt lại, ví dụ:\n"
                "• 'Gộp tất cả file Excel trong thư mục input'\n"
                "• 'Lọc nhân viên có lương trên 10 triệu'\n"
                "• 'So sánh Root và Update'\n"
                "• 'Liệt kê các file Excel'\n"
                "Gõ 'hướng dẫn' để xem thêm ví dụ."
            ),
            raw_text=raw_text,
        )

    params: dict[str, Any] = {}
    requires_confirmation = False
    error_message: str | None = None

    if intent == Intent.AGGREGATION:
        params, requires_confirmation = _build_aggregation(raw_text, entities)

    elif intent == Intent.FILTER:
        params, requires_confirmation, error_message = _build_filter(raw_text, entities)

    elif intent == Intent.COMPARISON:
        params, requires_confirmation = _build_comparison(raw_text, entities)

    elif intent == Intent.EXPORT:
        params, requires_confirmation = _build_export(raw_text, entities)

    elif intent == Intent.FILE_LIST:
        params, requires_confirmation = _build_file_list(raw_text, entities)

    elif intent == Intent.HELP:
        params, requires_confirmation = _build_help(raw_text, entities)

    elif intent == Intent.DELETE:
        params, requires_confirmation = _build_delete(raw_text, entities)
        error_message = (
            "⚠️ Lệnh XÓA DỮ LIỆU được phát hiện.\n"
            "Hệ thống không hỗ trợ xóa file gốc tự động vì lý do an toàn.\n"
            "Nếu bạn muốn xóa file output cụ thể, hãy thực hiện thủ công."
        )

    return ParsedCommand(
        intent=intent.value,
        confidence=intent_result.confidence,
        parameters=params,
        requires_confirmation=requires_confirmation,
        error_message=error_message,
        raw_text=raw_text,
    )

