#!/bin/bash
# Script khởi động nhanh Excel Rule Engine (Linux/macOS)

set -e
cd "$(dirname "$0")"

echo "========================================"
echo "   Excel Rule Engine - Quick Start"
echo "========================================"

# Tạo venv nếu chưa có
if [ ! -d "venv" ]; then
    echo "[INFO] Tạo virtual environment..."
    python3 -m venv venv
fi

source venv/bin/activate

# Cài dependencies
python -c "import fastapi" 2>/dev/null || pip install -r requirements.txt

# Tạo dữ liệu mẫu
if [ ! -f "projects/demo_project/input/Employees_IT.xlsx" ]; then
    echo "[INFO] Tạo dữ liệu mẫu..."
    python ../scripts/create_sample_data.py
fi

# Khởi tạo DB
python -c "from app.database.db import init_db; init_db()"

echo "[INFO] Khởi động FastAPI..."
uvicorn app.main:app --reload --port 8000 &
FASTAPI_PID=$!

sleep 2

echo "[INFO] Khởi động Streamlit..."
streamlit run app/ui/chatbot.py --server.port 8501 &
STREAMLIT_PID=$!

echo ""
echo "========================================"
echo "  FastAPI:   http://localhost:8000/docs"
echo "  Chatbot:   http://localhost:8501"
echo "========================================"
echo "Press Ctrl+C to stop all services"

trap "kill $FASTAPI_PID $STREAMLIT_PID 2>/dev/null; exit" INT
wait

