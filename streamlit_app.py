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
            return
    except Exception:
        pass

    backend_cmd = [
        sys.executable, "-m", "uvicorn", "app.main:app",
        "--host", "127.0.0.1", "--port", "8000"
    ]
    subprocess.Popen(backend_cmd, cwd=str(PROJECT_DIR))
    time.sleep(2)

start_fastapi()

# Chạy nội dung Chatbot UI
chatbot_path = PROJECT_DIR / "app" / "chatbot.py"
with open(chatbot_path, encoding="utf-8") as f:
    code = compile(f.read(), str(chatbot_path), "exec")
    exec(code, globals())

