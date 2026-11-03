"""Recognize analytical requests without confusing report plans with legacy actions."""
import re
import unicodedata


def is_analytical_request(text: str) -> bool:
    value = ''.join(c for c in unicodedata.normalize('NFD', text.lower().replace('đ', 'd'))
                    if unicodedata.category(c) != 'Mn')
    if re.search(r'\b(xoa|delete|remove)\b', value):
        return False  # Preserve destructive-command safeguards.
    # Generic legacy export remains explicit; specialized requests cannot fall back.
    generic = {'tao bao cao tong hop', 'xuat file excel ket qua', 'tao bao cao', 'xuat bao cao'}
    if value.strip(' .?!') in generic:
        return False
    return bool(re.search(
        r'\b(doanh thu|doanh so|loi nhuan|chi phi|revenue|profit|cost|top|trung binh|'
        r'bao cao|tong luong|quy luong|dem|bao nhieu|theo thang|theo quy|theo nam)\b', value))
