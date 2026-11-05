@echo off
REM Script khởi động nhanh Excel Rule Engine (Windows)
REM Chạy script này để start cả FastAPI và Streamlit

title Excel Rule Engine Launcher

echo ========================================
echo    Excel Rule Engine - Quick Start
echo ========================================
echo.

REM Kiểm tra Python
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python chua duoc cai dat hoac khong trong PATH.
    pause
    exit /b 1
)

REM Vào thư mục project
cd /d "%~dp0"

REM Kiểm tra venv
if not exist "venv\Scripts\activate.bat" (
    echo [INFO] Tao virtual environment...
    python -m venv venv
)

REM Activate venv
call venv\Scripts\activate.bat

REM Cài dependencies nếu chưa có
python -c "import fastapi" >nul 2>&1
if errorlevel 1 (
    echo [INFO] Cai dependencies...
    pip install -r requirements.txt
)

REM Tạo dữ liệu mẫu nếu chưa có
if not exist "projects\demo_project\input\Employees_IT.xlsx" (
    echo [INFO] Tao du lieu mau...
    python ..\scripts\create_sample_data.py
)

REM Khởi tạo DB
python -c "from app.database.db import init_db; init_db()"

echo.
echo [INFO] Khoi dong FastAPI backend...
start "FastAPI Server" cmd /k "call venv\Scripts\activate.bat && uvicorn app.main:app --reload --port 8000"

timeout /t 3 /nobreak >nul

echo [INFO] Khoi dong Streamlit chatbot...
start "Streamlit Chatbot" cmd /k "call venv\Scripts\activate.bat && streamlit run app\ui\chatbot.py --server.port 8501"

echo.
echo ========================================
echo  FastAPI:   http://localhost:8000/docs
echo  Chatbot:   http://localhost:8501
echo ========================================
echo.
pause

