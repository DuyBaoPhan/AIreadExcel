"""
Entry point duy nhất của toàn bộ hệ thống Excel Rule Engine.
Chạy: python main.py
Tự động kích hoạt cả Backend API và Giao diện Chatbot Streamlit.
"""

from __future__ import annotations

import os
import subprocess
import sys
import time
from pathlib import Path

# Đảm bảo thư mục dự án được thêm vào sys.path
PROJECT_DIR = Path(__file__).resolve().parent
os.chdir(PROJECT_DIR)
sys.path.insert(0, str(PROJECT_DIR))


def main():
    # Fix encoding cho console Windows
    if sys.platform == "win32":
        try:
            sys.stdout.reconfigure(encoding="utf-8")
            sys.stderr.reconfigure(encoding="utf-8")
        except Exception:
            pass

    print("\n" + "=" * 60)
    print("      EXCEL RULE ENGINE - KHOI DONG HE THONG")
    print("=" * 60)

    # 1. Khởi tạo DB nếu chưa có
    from app.database.db import init_db
    init_db()

    # 2. Tạo dữ liệu mẫu nếu chưa có
    sample_marker = PROJECT_DIR / "projects" / "demo_project" / "input" / "Employees_IT.xlsx"
    if not sample_marker.exists():
        print("[*] Dang tao du lieu Excel mau...")
        import tests.create_sample_data as sample_gen
        sample_gen.OUTPUT_DIR = sample_marker.parent
        sample_gen.create_employees_it()
        sample_gen.create_employees_hr()
        sample_gen.create_sales_data()
        sample_gen.create_root_file()
        sample_gen.create_update_file()

    # 3. Khởi động Streamlit Chatbot (chạy nền)
    chatbot_script = PROJECT_DIR / "app" / "chatbot.py"
    streamlit_cmd = [
        sys.executable, "-m", "streamlit", "run",
        str(chatbot_script),
        "--server.port=8501",
        "--server.headless=false",
    ]

    print("[1/2] Dang khoi dong Giao dien Chatbot Streamlit...")
    st_proc = subprocess.Popen(streamlit_cmd)

    time.sleep(2)

    print("[2/2] Dang khoi dong Backend API FastAPI...")
    print("\n" + "-" * 60)
    print("  -> Giao dien Chatbot : http://localhost:8501")
    print("  -> Swagger API Docs  : http://localhost:8000/docs")
    print("  (Nhan Ctrl+C de dung toan bo chuong trinh)")
    print("-" * 60 + "\n")

    # 4. Chạy FastAPI qua Uvicorn trực tiếp
    try:
        import uvicorn
        uvicorn.run("app.main:app", host="127.0.0.1", port=8000, reload=False)
    except KeyboardInterrupt:
        print("\n[!] Đang tắt hệ thống...")
    finally:
        st_proc.terminate()
        st_proc.wait()
        print("[✓] Đã tắt toàn bộ chương trình thành công.")


if __name__ == "__main__":
    main()

