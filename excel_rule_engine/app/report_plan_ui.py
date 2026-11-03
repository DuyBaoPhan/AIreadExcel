"""Explicit approval and clarification UI for schema-aware chat report plans."""
import streamlit as st


def render_pending_report(call_api, add_message):
    pending = st.session_state.get('pending_report')
    if not pending:
        return
    with st.container(border=True):
        st.subheader('Kế hoạch xử lý yêu cầu')
        st.write(pending.get('text', ''))
        for line in pending.get('explanation', []):
            st.write(f'• {line}')
        for line in pending.get('warnings', []):
            st.warning(line)
        for line in pending.get('questions', []) + pending.get('unsupported', []):
            st.info(line)
        source = pending.get('source')
        if source:
            st.caption(f'Nguồn: {source}')
        if pending.get('status') != 'ready':
            names = pending.get('available_sources', [])
            if names:
                selected = st.selectbox('Chọn nguồn để phân tích lại', names, key='plan_source_choice')
                if st.button('Dùng nguồn này', key='replan_source'):
                    result = call_api('/api/report/preview', {
                        'text': pending['text'], 'project': pending['project'], 'source_name': selected,
                    })
                    if result and not result.get('error'):
                        st.session_state.pending_report = {**result, 'text': pending['text'], 'project': pending['project']}
                        st.rerun()
                    else:
                        st.error((result or {}).get('error', 'Không nhận được kế hoạch.'))
            st.caption('Bạn có thể gửi lại câu đầy đủ đã chỉnh sửa. Không xuất file khi điều kiện còn mơ hồ.')
        if pending.get('config'):
            with st.expander('Điều kiện và phép tính sẽ thực hiện'):
                st.json(pending['config'])
        c1, c2 = st.columns(2)
        if c1.button('Xác nhận và tạo báo cáo', type='primary', key='confirm_report_plan',
                     disabled=pending.get('status') != 'ready'):
            with st.spinner('Kiểm tra lại nguồn và tính toán...'):
                response = call_api('/api/report/confirm', {
                    'text': pending['text'], 'project': pending['project'],
                    'source_name': source, 'fingerprint': pending['fingerprint'],
                })
            if response and response.get('result'):
                result = response['result']
                add_message('assistant', '**Báo cáo đã được tính theo kế hoạch xác nhận.**', {
                    'output_path': result['output_path'], 'project': pending['project'],
                    'summary': result.get('summary', []), 'warnings': result.get('warnings', []),
                })
                st.session_state.pending_report = None
                st.rerun()
            else:
                st.error((response or {}).get('error', 'Không nhận được kết quả. Hãy phân tích lại yêu cầu.'))
        if c2.button('Hủy kế hoạch', key='cancel_report_plan'):
            st.session_state.pending_report = None
            st.rerun()
