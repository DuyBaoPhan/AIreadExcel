"""
Entry point gốc: Chuyển hướng và chạy Excel Rule Engine.
Chạy: python main.py ngay từ D:\AIreadExcel
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

ENGINE_DIR = Path(__file__).resolve().parent / "excel_rule_engine"

if ENGINE_DIR.exists():
    os.chdir(ENGINE_DIR)
    sys.path.insert(0, str(ENGINE_DIR))
    import main as engine_main
    engine_main.main()
else:
    print(f"[!] Không tìm thấy thư mục {ENGINE_DIR}")

