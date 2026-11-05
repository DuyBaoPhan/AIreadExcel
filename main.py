r"""
Entry point gốc: Chuyển hướng và chạy Excel Rule Engine.
Chạy: python main.py ngay từ D:\AIreadExcel
"""

from __future__ import annotations

import runpy
import os
import sys
from pathlib import Path

ENGINE_DIR = Path(__file__).resolve().parent / "excel_rule_engine"

if ENGINE_DIR.exists():
    os.chdir(ENGINE_DIR)
    sys.path.insert(0, str(ENGINE_DIR))
    runpy.run_path(str(ENGINE_DIR / "main.py"), run_name="__main__")
else:
    print(f"[!] Không tìm thấy thư mục {ENGINE_DIR}")

