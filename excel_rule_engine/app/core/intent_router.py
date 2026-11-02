"""
Intent Router - Rule-based NLP engine for Vietnamese command classification.
Sử dụng Regex, Keyword Matching và RapidFuzz để nhận diện ý định người dùng.
"""

from __future__ import annotations

import logging
import re
import unicodedata
from enum import Enum
from dataclasses import dataclass, field

from rapidfuzz import fuzz, process

logger = logging.getLogger(__name__)


class Intent(str, Enum):
    AGGREGATION = "AGGREGATION"
    FILTER = "FILTER"
    COMPARISON = "COMPARISON"
    EXPORT = "EXPORT"
    FILE_LIST = "FILE_LIST"
    HELP = "HELP"
    DELETE = "DELETE"          # Nhận diện nhưng yêu cầu xác nhận
    UNKNOWN = "UNKNOWN"


@dataclass
class IntentResult:
    intent: Intent
    confidence: float            # 0.0 – 1.0
    matched_keywords: list[str] = field(default_factory=list)
    raw_text: str = ""


# ─────────────────────────────────────────────
#  Keyword dictionaries  (tiếng Việt + English)
# ─────────────────────────────────────────────

INTENT_KEYWORDS: dict[Intent, list[str]] = {
    Intent.AGGREGATION: [
        "gộp", "tổng hợp", "hợp nhất", "combine", "merge",
        "kết hợp", "nhập", "tập hợp", "ghép", "gom",
        "tổng kết", "tổng hợp dữ liệu", "gộp file",
    ],
    Intent.FILTER: [
        "lọc", "tìm", "lấy dữ liệu", "filter", "search",
        "tìm kiếm", "lấy", "tìm những", "lấy những",
        "truy vấn", "query", "chọn", "select",
        "hiển thị", "xem dữ liệu",
    ],
    Intent.COMPARISON: [
        "so sánh", "đối chiếu", "kiểm tra thay đổi",
        "compare", "diff", "khác biệt", "sự khác nhau",
        "thay đổi", "bản ghi mới", "bản ghi thay đổi",
        "cập nhật nào", "khác gì",
    ],
    Intent.EXPORT: [
        "xuất file", "tạo báo cáo", "export", "xuất báo cáo",
        "tạo report", "generate report", "xuất excel",
    ],
    Intent.FILE_LIST: [
        "danh sách file", "có những file nào", "liệt kê",
        "danh sách các file", "có file gì", "có những file",
    ],
    Intent.HELP: [
        "hướng dẫn", "trợ giúp", "chỉ dẫn",
        "làm thế nào", "cách dùng", "sử dụng như thế nào",
    ],
    Intent.DELETE: [
        "xóa", "delete", "remove", "xoá",
        "xóa dữ liệu", "xóa tất cả", "xóa file",
        "loại bỏ", "bỏ đi", "xóa hết",
    ],
}

# Regex patterns for quick detection
INTENT_PATTERNS: dict[Intent, list[str]] = {
    Intent.AGGREGATION: [
        r"\bgộp\b",
        r"\btổng\s*hợp\b",
        r"\bhợp\s*nhất\b",
        r"\bmerge\b",
        r"\bcombine\b",
        r"\bghép\b",
        r"\bgom\b",
    ],
    Intent.FILTER: [
        r"\blọc\b",
        r"\btìm\s+(?:kiếm\s+)?(?:nhân\s+viên|dữ\s+liệu|bản\s+ghi|những)\b",
        r"\blấy\s+(?:dữ\s+liệu|những|các)\b",
        r"\bfilter\b",
        r"\bchọn\b.*\bcó\b",
        r"\bhiển\s*thị\b",
        r"(?:\blương\b|\bdoanh\s*thu\b|\blợi\s*nhuận\b|\bchi\s*phí\b|\bsố\s*lượng\b).*(?:\btrên\b|\bdưới\b|\blớn\s*hơn\b|\bnhỏ\s*hơn\b|\bcao\s*hơn\b|\bthấp\s*hơn\b|\bhơn\b|\bbằng\b)",
        r"(?:\bnhân\s*viên\b|\bdữ\s*liệu\b|\bbán\s*hàng\b).*(?:\btrên\b|\bdưới\b|\blớn\s*hơn\b|\bnhỏ\s*hơn\b|\bcao\s*hơn\b|\bthấp\s*hơn\b|\bhơn\b)",
    ],
    Intent.COMPARISON: [
        r"\bso\s*sánh\b",
        r"\bđối\s*chiếu\b",
        r"\bkiểm\s*tra\s*thay\s*đổi\b",
        r"\bcompare\b",
        r"\bdiff\b",
        r"\bkhác\s*biệt\b",
    ],
    Intent.EXPORT: [
        r"\bxuất\s*(?:file|báo\s*cáo|excel|report)\b",
        r"\btạo\s*(?:báo\s*cáo|file|report|excel)\b",
        r"\bexport\b",
        r"\bgenerate\s*report\b",
    ],
    Intent.FILE_LIST: [
        r"\bdanh\s*sách\s*file\b",
        r"\bcó\s*(?:những|các)\s*file\b",
        r"\bliệt\s*kê\b",
        r"\blist\s*file\b",
        r"\bfile\s*nào\b",
    ],
    Intent.HELP: [
        r"\bhướng\s*dẫn\b",
        r"\btrợ\s*giúp\b",
        r"\bhelp\b",
        r"\bgiúp\s+đỡ\b",
        r"\bcách\s*dùng\b",
    ],
    Intent.DELETE: [
        r"\bxóa\b",
        r"\bxoá\b",
        r"\bdelete\b",
        r"\bremove\b",
        r"\bloại\s*bỏ\b",
    ],
}

FUZZY_THRESHOLD = 75   # RapidFuzz score threshold (0–100)


def normalize_text(text: str) -> str:
    """Chuẩn hoá: lowercase, strip dấu kép, rút gọn khoảng trắng."""
    text = text.lower().strip()
    # Chuẩn hoá dấu Unicode NFC
    text = unicodedata.normalize("NFC", text)
    # Rút gọn khoảng trắng
    text = re.sub(r"\s+", " ", text)
    return text


def _keyword_score(text: str, intent: Intent) -> tuple[float, list[str]]:
    """Trả về điểm khớp từ khoá và danh sách keyword đã match."""
    keywords = INTENT_KEYWORDS[intent]
    matched: list[str] = []

    for kw in keywords:
        if kw in text:
            matched.append(kw)

    # Fuzzy matching cho các từ khoá chưa khớp trực tiếp
    for kw in keywords:
        if kw not in matched:
            score = fuzz.partial_ratio(kw, text)
            if score >= FUZZY_THRESHOLD:
                matched.append(f"~{kw}")

    score = min(1.0, len(matched) / 2.0)  # normalize: 1 match = 0.5, 2 matches = 1.0
    return score, matched


def _regex_score(text: str, intent: Intent) -> float:
    """Trả về điểm dựa trên số regex pattern khớp."""
    patterns = INTENT_PATTERNS.get(intent, [])
    hits = sum(1 for p in patterns if re.search(p, text))
    if hits > 0:
        return min(1.0, 0.5 + hits * 0.3)
    return 0.0


def classify_intent(raw_text: str) -> IntentResult:
    """
    Phân loại ý định từ văn bản đầu vào.

    Returns:
        IntentResult với intent, confidence và các keyword đã match.
    """
    normalized = normalize_text(raw_text)
    logger.debug("Normalized text: %r", normalized)

    scores: dict[Intent, float] = {}
    all_matched: dict[Intent, list[str]] = {}

    for intent in Intent:
        if intent == Intent.UNKNOWN:
            continue
        kw_score, matched = _keyword_score(normalized, intent)
        re_score = _regex_score(normalized, intent)
        combined = kw_score * 0.5 + re_score * 0.5
        scores[intent] = combined
        all_matched[intent] = matched
        logger.debug("  %s → kw=%.2f re=%.2f combined=%.2f", intent, kw_score, re_score, combined)

    # Nếu câu có điều kiện lọc cụ thể (ví dụ 'tháng 4', 'lương trên', 'phòng...') mà có từ 'tổng hợp/lấy'
    # thì ưu tiên FILTER hơn AGGREGATION thông thường
    if re.search(r"\btháng\s*\d+\b|\blương\b|\bphòng\b", normalized):
        if scores[Intent.FILTER] > 0 or scores[Intent.AGGREGATION] > 0:
            scores[Intent.FILTER] = max(scores[Intent.FILTER], scores[Intent.AGGREGATION] + 0.1)

    best_intent = max(scores, key=lambda i: scores[i])
    best_score = scores[best_intent]

    if best_score < 0.25:
        logger.info("No intent matched (best_score=%.2f)", best_score)
        return IntentResult(
            intent=Intent.UNKNOWN,
            confidence=0.0,
            raw_text=raw_text,
        )

    return IntentResult(
        intent=best_intent,
        confidence=round(best_score, 3),
        matched_keywords=all_matched[best_intent],
        raw_text=raw_text,
    )

