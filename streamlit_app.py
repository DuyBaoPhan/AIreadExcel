"""
Streamlit App Entrypoint cho Streamlit Community Cloud.
Tự động kích hoạt Backend API nếu cần và chạy Chatbot.
"""

import sys
import os
import subprocess
import time
from pathlib import Path

# Thiết lập đường dẫn thư mục dự án
CURRENT_DIR = Path(__file__).resolve().parent
PROJECT_DIR = CURRENT_DIR / "excel_rule_engine"

if str(PROJECT_DIR) not in sys.path:
    sys.path.insert(0, str(PROJECT_DIR))

from app.services.runtime.environment import load_environment
load_environment()

# Đảm bảo database được khởi tạo
try:
    from app.database.db import init_db
    init_db()
except Exception:
    pass

# Chạy FastAPI ngầm (port 8000) trên Cloud nếu chưa chạy
def start_fastapi():
    try:
        import requests
        res = requests.get("http://localhost:8000/health", timeout=1)
        if res.status_code == 200:
            from app.services.runtime.backend_capabilities import check_report_api
            compatible, diagnostic = check_report_api()
            if not compatible:
                import streamlit as st
                st.error(diagnostic + '. Backend đang chạy không tương thích. Local: dừng phiên cũ bằng Ctrl+C rồi chạy lại. Streamlit Cloud: cập nhật mã và Reboot app. Không tự tắt tiến trình đang chiếm cổng.')
                st.stop()
            return
    except Exception:
        pass

    backend_cmd = [
        sys.executable, "-m", "uvicorn", "app.main:app",
        "--host", "127.0.0.1", "--port", "8000"
    ]
    subprocess.Popen(backend_cmd, cwd=str(PROJECT_DIR))
    time.sleep(2)

# Only documented application secrets are inherited by the backend child.
import streamlit as st
for name in ("OPENAI_API_KEY", "OPENAI_MODEL", "REPORT_PLANNER", "RAG_MODEL_PATH"):
    try:
        value = st.secrets.get(name)
    except (FileNotFoundError, KeyError):
        value = None
    if value is not None:
        os.environ[name] = str(value)

start_fastapi()

# Chạy nội dung Chatbot UI
chatbot_path = PROJECT_DIR / "app" / "ui" / "chatbot.py"
with open(chatbot_path, encoding="utf-8") as f:
    code = compile(f.read(), str(chatbot_path), "exec")
    exec(code, globals())

