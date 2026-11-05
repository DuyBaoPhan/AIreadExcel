"""
Entity Extractor - Trích xuất thực thể từ câu lệnh tiếng Việt.
Sử dụng Regex và danh sách từ điển để lấy cột, giá trị, toán tử…
"""

from __future__ import annotations

import logging
import re
import unicodedata
from typing import Any

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────
#  Column alias mapping (Vietnamese → canonical)
# ─────────────────────────────────────────────

COLUMN_ALIASES: dict[str, str] = {
    # Nhân sự
    "lương": "salary",
    "mức lương": "salary",
    "thu nhập": "salary",
    "tên": "name",
    "họ tên": "name",
    "họ và tên": "name",
    "tên nhân viên": "name",
    "phòng": "department",
    "phòng ban": "department",
    "bộ phận": "department",
    "chức vụ": "position",
    "chức danh": "position",
    "vị trí": "position",
    "trạng thái": "status",
    "tình trạng": "status",
    "ngày vào làm": "start_date",
    "ngày gia nhập": "start_date",
    "mã nhân viên": "employee_id",
    "id": "employee_id",
    "email": "email",
    "số điện thoại": "phone",
    "điện thoại": "phone",
    # Tài chính
    "doanh thu": "revenue",
    "chi phí": "cost",
    "lợi nhuận": "profit",
    "số tiền": "amount",
    "giá": "price",
    "đơn giá": "unit_price",
    "số lượng": "quantity",
    "sản phẩm": "product",
    "danh mục": "category",
    "loại": "category",
    "khu vực": "region",
    "vùng": "region",
    "tháng": "month",
    "năm": "year",
    "ngày": "date",
}

# Operator mapping
OPERATOR_MAP: dict[str, str] = {
    "trên": ">",
    "lớn hơn": ">",
    "cao hơn": ">",
    "hơn": ">",
    "vượt": ">",
    "quá": ">",
    "dưới": "<",
    "nhỏ hơn": "<",
    "thấp hơn": "<",
    "ít hơn": "<",
    "bằng": "==",
    "là": "==",
    "bằng với": "==",
    "đúng bằng": "==",
    "không phải": "!=",
    "khác": "!=",
    "không bằng": "!=",
    "không là": "!=",
    "từ": ">=",
    "tối thiểu": ">=",
    "ít nhất": ">=",
    "tối đa": "<=",
    "nhiều nhất": "<=",
    "không quá": "<=",
}

# Status value aliases
STATUS_ALIASES: dict[str, str] = {
    "đang làm việc": "active",
    "đang làm": "active",
    "đang hoạt động": "active",
    "hoạt động": "active",
    "active": "active",
    "đã nghỉ": "inactive",
    "nghỉ việc": "inactive",
    "thôi việc": "inactive",
    "inactive": "inactive",
    "tạm nghỉ": "suspended",
    "suspended": "suspended",
}

# Department / entity name normalization
DEPARTMENT_ALIASES: dict[str, str] = {
    "it": "IT",
    "công nghệ thông tin": "IT",
    "cntt": "IT",
    "kế toán": "Accounting",
    "tài chính": "Finance",
    "kinh doanh": "Sales",
    "bán hàng": "Sales",
    "nhân sự": "HR",
    "hr": "HR",
    "marketing": "Marketing",
    "sản xuất": "Production",
    "kho": "Warehouse",
    "hành chính": "Admin",
    "kỹ thuật": "Engineering",
}

# Region aliases
REGION_ALIASES: dict[str, str] = {
    "miền bắc": "Miền Bắc",
    "bắc": "Miền Bắc",
    "miền nam": "Miền Nam",
    "nam": "Miền Nam",
    "miền trung": "Miền Trung",
    "trung": "Miền Trung",
}

# Product aliases
PRODUCT_ALIASES: dict[str, str] = {
    "laptop": "Laptop Pro X",
    "laptop pro": "Laptop Pro X",
    "màn hình": "Màn Hình 4K",
    "màn hình 4k": "Màn Hình 4K",
    "bàn phím": "Bàn Phím Cơ",
    "bàn phím cơ": "Bàn Phím Cơ",
    "chuột": "Chuột Không Dây",
    "chuột không dây": "Chuột Không Dây",
    "tai nghe": "Tai Nghe ANC",
    "tai nghe anc": "Tai Nghe ANC",
}


def _normalize(text: str) -> str:
    text = text.lower().strip()
    text = unicodedata.normalize("NFC", text)
    return re.sub(r"\s+", " ", text)


def extract_column(text: str) -> str | None:
    """Trích xuất tên cột từ câu lệnh."""
    normalized = _normalize(text)

    # Nếu câu lệnh nhắc đến tên vùng miền thì cột là region
    for r in REGION_ALIASES:
        if r in normalized and not re.search(r"\bphòng\b|\blương\b", normalized):
            return "region"

    # Nếu câu lệnh nhắc đến sản phẩm thì cột là product
    for p in PRODUCT_ALIASES:
        if p in normalized and not re.search(r"\bphòng\b|\blương\b", normalized):
            return "product"

    # Sắp xếp theo độ dài giảm dần để ưu tiên cụm từ dài hơn
    for vn, en in sorted(COLUMN_ALIASES.items(), key=lambda x: -len(x[0])):
        if vn in normalized:
            logger.debug("Column matched: %r → %r", vn, en)
            return en
    return None


def extract_operator(text: str) -> str | None:
    """Trích xuất toán tử so sánh."""
    normalized = _normalize(text)
    for vn, op in sorted(OPERATOR_MAP.items(), key=lambda x: -len(x[0])):
        if vn in normalized:
            logger.debug("Operator matched: %r → %r", vn, op)
            return op
    return None


def extract_numeric_value(text: str) -> float | None:
    """
    Trích xuất giá trị số từ văn bản.
    Hỗ trợ: '10 triệu', '5.5 triệu', '10,000,000', '10000000'.
    """
    normalized = _normalize(text)

    # Dạng: X triệu / X tỷ / X tr / X k / X trđ
    m = re.search(r"([\d,.]+)\s*(?:triệu|tr\b|trđ)", normalized)
    if m:
        raw = m.group(1).replace(",", ".")
        try:
            return float(raw) * 1_000_000
        except ValueError:
            pass

    m = re.search(r"([\d,.]+)\s*(?:tỷ|ty\b)", normalized)
    if m:
        raw = m.group(1).replace(",", ".")
        try:
            return float(raw) * 1_000_000_000
        except ValueError:
            pass

    m = re.search(r"([\d,.]+)\s*(?:nghìn|ngàn|k\b)", normalized)
    if m:
        raw = m.group(1).replace(",", ".")
        try:
            return float(raw) * 1_000
        except ValueError:
            pass

    # Số thường (có thể có dấu phẩy phân cách hàng nghìn)
    m = re.search(r"\b([\d]{1,3}(?:[,.][\d]{3})*(?:[.,][\d]+)?)\b", normalized)
    if m:
        raw = m.group(1).replace(",", "")
        try:
            return float(raw)
        except ValueError:
            pass

    return None


def extract_string_value(text: str, column: str | None = None) -> str | None:
    """Trích xuất giá trị chuỗi (phòng ban, trạng thái, tháng, vùng miền, sản phẩm…)."""
    normalized = _normalize(text)

    # Nếu đang cần tìm cột Region
    if column == "region":
        for vn, canonical in sorted(REGION_ALIASES.items(), key=lambda x: -len(x[0])):
            if vn in normalized:
                return canonical

    # Nếu đang cần tìm cột Product
    if column == "product":
        for vn, canonical in sorted(PRODUCT_ALIASES.items(), key=lambda x: -len(x[0])):
            if vn in normalized:
                return canonical

    # Nhận diện tháng dạng 'tháng 4', 'tháng 04', 'tháng 4/2024', 'tháng 2024-04'
    m_month = re.search(r"tháng\s*(\d{1,2})(?:[/-](\d{4}))?", normalized)
    if m_month:
        month_num = int(m_month.group(1))
        year = m_month.group(2) if m_month.group(2) else "2024"
        return f"{year}-{month_num:02d}"

    # Region
    for vn, canonical in sorted(REGION_ALIASES.items(), key=lambda x: -len(x[0])):
        if vn in normalized:
            return canonical

    # Product
    for vn, canonical in sorted(PRODUCT_ALIASES.items(), key=lambda x: -len(x[0])):
        if vn in normalized:
            return canonical

    # Status
    for vn, canonical in sorted(STATUS_ALIASES.items(), key=lambda x: -len(x[0])):
        if vn in normalized:
            return canonical

    # Department
    for vn, canonical in sorted(DEPARTMENT_ALIASES.items(), key=lambda x: -len(x[0])):
        if vn in normalized:
            return canonical

    # Chuỗi trong ngoặc kép / ngoặc đơn
    m = re.search(r'["\']([^"\']+)["\']', text)
    if m:
        return m.group(1)

    return None


def extract_filter_value(text: str, column: str | None) -> Any:
    """Thử extract giá trị chuỗi trước nếu là cột chuỗi, ngược lại thử số trước."""
    if column in ("month", "department", "status", "region", "product"):
        str_val = extract_string_value(text, column)
        if str_val is not None:
            return str_val

    num = extract_numeric_value(text)
    if num is not None:
        return num
    return extract_string_value(text, column)


def extract_file_names(text: str) -> list[str]:
    """Trích xuất tên file từ câu lệnh (có phần mở rộng hoặc không)."""
    # Pattern: file có đuôi .xlsx/.xls/.csv
    names = re.findall(r"[\w\-áàảãạăắằẳẵặâấầẩẫậéèẻẽẹêếềểễệíìỉĩịóòỏõọôốồổỗộơớờởỡợúùủũụưứừửữựýỳỷỹỵđÁÀẢÃẠĂẮẰẲẴẶÂẤẦẨẪẬÉÈẺẼẸÊẾỀỂỄỆÍÌỈĨỊÓÒỎÕỌÔỐỒỔỖỘƠỚỜỞỠỢÚÙỦŨỤƯỨỪỬỮỰÝỲỶỸỴĐ]+\.(?:xlsx|xls|csv)\b",
                       text, flags=re.IGNORECASE)
    return names


def extract_source_folder(text: str) -> str:
    """Trích xuất tên thư mục nguồn ('input' mặc định)."""
    normalized = _normalize(text)
    if re.search(r"\boutput\b", normalized):
        return "output"
    return "input"  # mặc định


def extract_entities(text: str) -> dict[str, Any]:
    """
    Entry-point tổng hợp: trả về dict chứa tất cả entity đã trích xuất.
    """
    column = extract_column(text)
    operator = extract_operator(text)
    value = extract_filter_value(text, column)
    file_names = extract_file_names(text)
    source = extract_source_folder(text)

    return {
        "column": column,
        "operator": operator,
        "value": value,
        "file_names": file_names,
        "source": source,
    }

