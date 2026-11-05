"""Explicit AI-only backend mode; credentials never leave the server."""
import os


def planner_mode():
    mode = os.getenv('REPORT_PLANNER', 'openai').strip().lower()
    if mode == 'rules':
        raise ValueError('Chế độ REPORT_PLANNER=rules đã ngừng hỗ trợ. Hãy đặt REPORT_PLANNER=openai và cấu hình OPENAI_API_KEY trên máy chủ.')
    if mode not in {'auto', 'openai'}:
        raise ValueError('REPORT_PLANNER không hợp lệ. Hãy dùng openai (hoặc auto, bí danh của openai).')
    return 'openai'


def planner_status():
    return {'planner': planner_mode(), 'configured': bool(os.getenv('OPENAI_API_KEY', '').strip()),
            'model': os.getenv('OPENAI_MODEL', 'gpt-4.1-mini'),
            'privacy': 'retrieved_excerpts_for_rag', 'retrieval': 'multilingual-e5-large + FAISS + BM25 + RRF'}
