"""Explicit backend planner mode; credentials never leave the server."""
import os


def planner_mode():
    mode = os.getenv('REPORT_PLANNER', 'auto').strip().lower()
    if mode not in {'auto', 'openai', 'rules'}:
        raise ValueError('REPORT_PLANNER must be auto, openai or rules.')
    return ('openai' if os.getenv('OPENAI_API_KEY', '').strip() else 'rules') if mode == 'auto' else mode


def planner_status():
    mode = planner_mode()
    return {'planner': mode, 'configured': bool(os.getenv('OPENAI_API_KEY', '').strip()) if mode == 'openai' else True,
            'model': os.getenv('OPENAI_MODEL', 'gpt-4.1-mini') if mode == 'openai' else None,
            'privacy': 'retrieved_excerpts_for_rag', 'retrieval': 'multilingual-e5-large + FAISS + BM25 + RRF'}
