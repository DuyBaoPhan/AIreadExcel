"""Readable source-edit preview; does not perform writes or authorize proposals."""
import math
import streamlit as st

LABELS = {'name': 'Họ tên', 'employee_id': 'Mã nhân viên',
          'salary': 'Lương', 'department': 'Phòng ban', 'position': 'Chức vụ',
          'status': 'Trạng thái', 'email': 'Email', 'start_date': 'Ngày bắt đầu'}


def format_value(value):
    """Format presentation only; identifiers/strings retain their exact content."""
    if value is None:
        return '(Trống)'
    if isinstance(value, bool):
        return 'True' if value else 'False'
    if isinstance(value, (int, float)) and math.isfinite(value):
        if isinstance(value, int) or value.is_integer():
            return format(value, ',.0f').replace(',', '.')
        # Vietnamese separators without rounding away changed fractional values.
        whole, fraction = str(value).split('.') if 'e' not in str(value).lower() else (None, None)
        if whole is not None:
            sign = '-' if whole.startswith('-') else ''
            return sign + format(abs(int(whole)), ',').replace(',', '.') + ',' + fraction
    return str(value)


def render_update_preview(preview):
    """Show the exact proposed record and before/after values, not raw JSON."""
    st.subheader('Xác nhận thay đổi dữ liệu')
    st.caption('Kiểm tra nội dung bên dưới trước khi cập nhật tệp gốc.')
    st.text('Tệp nguồn: ' + str(preview.get('source', '')))
    key = str(preview.get('key_column', ''))
    column = str(preview.get('column', ''))
    # Text widgets avoid interpreting untrusted cell values as HTML/Markdown.
    st.text(LABELS.get(key, key) + ': ' + str(preview.get('key_value', '')))
    st.text('Cột cập nhật: ' + LABELS.get(column, column) + ' (' + column + ')')
    before, after = st.columns(2)
    with before:
        st.caption('GIÁ TRỊ HIỆN TẠI')
        st.text(format_value(preview.get('old_value')))
    with after:
        st.caption('GIÁ TRỊ MỚI')
        st.text(format_value(preview.get('new_value')))
    st.warning('Thay đổi này sửa trực tiếp tệp nguồn. Chỉ ghi sau khi bạn xác nhận; hệ thống sẽ lưu bản sao lưu trước khi thay thế tệp.')
