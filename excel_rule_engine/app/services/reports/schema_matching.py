"""Column-schema aliases and normalization, not natural-language request routing."""
import re
import unicodedata

SCHEMA_ALIASES = {
    'revenue': ('doanh so', 'doanh thu', 'revenue', 'sales', 'thanh tien'),
    'profit': ('loi nhuan', 'profit'),
    'cost': ('chi phi', 'cost', 'expense', 'expenses'),
    'quantity': ('so luong', 'quantity', 'qty'),
    'salary': ('quy luong', 'luong', 'salary', 'payroll', 'tien luong'),
    'product': ('san pham', 'product', 'product name', 'ten san pham'),
    'department': ('bo phan', 'phong ban', 'department', 'phong'),
    'region': ('khu vuc', 'region', 'vung', 'mien'),
    'status': ('trang thai', 'status'),
    'employee_name': ('ten nhan vien', 'ho ten', 'ho va ten', 'employee name', 'employee_name', 'name'),
    'employee_id': ('ma nhan vien', 'employee id', 'employee_id', 'manv'),
    'order_id': ('ma don hang', 'order id', 'order_id', 'ma don'),
    'date': ('ngay', 'date', 'ngay ban', 'ngay giao dich', 'order date', 'thang', 'month', 'period'),
}


def normalize(text: str) -> str:
    """Accent-insensitive matching; never applied to returned data values."""
    text = unicodedata.normalize('NFD', str(text).lower().replace('đ', 'd'))
    return re.sub(r'\s+', ' ', ''.join(c for c in text if not unicodedata.combining(c)).replace('_', ' ')).strip()

