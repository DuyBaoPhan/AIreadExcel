# Excel Rule Engine — Hệ thống xử lý Excel bằng Rule-based Engine

> Chatbot Excel AI hoàn toàn bằng Python, hiểu câu lệnh tiếng Việt qua **Rule-based NLP** — không sử dụng LLM, không gọi API AI bên ngoài.

---

## 🏗️ Kiến trúc hệ thống

```
excel_rule_engine/
│
├── app/
│   ├── main.py              ← FastAPI backend
│   ├── chatbot.py           ← Streamlit UI
│   │
│   ├── core/
│   │   ├── intent_router.py     ← Rule-based NLP phân loại intent
│   │   ├── command_parser.py    ← Parser → ParsedCommand (Pydantic)
│   │   ├── entity_extractor.py  ← Trích xuất cột, toán tử, giá trị
│   │   └── response_generator.py← Tạo phản hồi thân thiện
│   │
│   ├── workflows/
│   │   ├── aggregation.py   ← Gộp nhiều file Excel
│   │   ├── filtering.py     ← Lọc dữ liệu theo điều kiện
│   │   ├── comparison.py    ← So sánh Root vs Update
│   │   └── report_export.py ← Tạo báo cáo tổng hợp
│   │
│   ├── services/
│   │   ├── excel_reader.py  ← Đọc file an toàn
│   │   ├── excel_writer.py  ← Ghi file với định dạng
│   │   └── file_manager.py  ← Quản lý file trong project
│   │
│   └── database/
│       ├── db.py            ← SQLite setup
│       └── task_repository.py← CRUD lịch sử tác vụ
│
├── projects/demo_project/
│   ├── input/               ← Đặt file Excel nguồn tại đây
│   └── output/              ← Kết quả xuất ra đây
│
└── tests/
    ├── test_system.py       ← Unit tests
    └── create_sample_data.py← Tạo dữ liệu mẫu
```

---

## ⚙️ Cài đặt

### Yêu cầu
- Python 3.12+
- Windows / Linux / macOS

### Bước 1: Clone và vào thư mục

```bash
cd excel_rule_engine
```

### Bước 2: Tạo môi trường ảo

```bash
python -m venv venv

# Windows
venv\Scripts\activate

# Linux/macOS
source venv/bin/activate
```

### Bước 3: Cài đặt dependencies

```bash
pip install -r requirements.txt
```

---

## 🚀 Chạy ứng dụng

### Terminal 1 — Khởi động FastAPI Backend

```bash
cd excel_rule_engine
uvicorn app.main:app --reload --port 8000
```

API docs tại: http://localhost:8000/docs

### Terminal 2 — Khởi động Streamlit Chatbot

```bash
cd excel_rule_engine
streamlit run app/chatbot.py
```

Giao diện tại: http://localhost:8501

---

## 📊 Tạo dữ liệu mẫu

```bash
cd excel_rule_engine
python tests/create_sample_data.py
```

Tạo ra 5 file Excel trong `projects/demo_project/input/`:
- `Employees_IT.xlsx` — Nhân viên phòng IT
- `Employees_HR_Accounting.xlsx` — Nhân viên HR & Kế toán
- `Sales_Data.xlsx` — Dữ liệu doanh thu
- `Root_Employees.xlsx` — File gốc cho so sánh
- `Update_Employees.xlsx` — File cập nhật cho so sánh

---

## 🧪 Chạy Unit Tests

```bash
cd excel_rule_engine
python -m pytest tests/test_system.py -v
```

---

## 💬 Ví dụ câu lệnh hỗ trợ

| Câu lệnh | Intent | Workflow |
|----------|--------|----------|
| "Gộp tất cả file Excel" | AGGREGATION | Merge → Master_Report.xlsx |
| "Tổng hợp dữ liệu từ các file" | AGGREGATION | Merge → Master_Report.xlsx |
| "Lọc nhân viên có lương trên 10 triệu" | FILTER | Filter salary > 10M |
| "Tìm nhân viên thuộc phòng IT" | FILTER | Filter department = IT |
| "Lấy những bản ghi đang làm việc" | FILTER | Filter status = active |
| "So sánh Root và Update" | COMPARISON | Diff → Change_Log.xlsx |
| "Kiểm tra thay đổi giữa hai file" | COMPARISON | Diff → Change_Log.xlsx |
| "Liệt kê các file Excel" | FILE_LIST | Danh sách file |
| "Có những file nào trong dự án?" | FILE_LIST | Danh sách file |
| "Tạo báo cáo tổng hợp" | EXPORT | Report → Report.xlsx |
| "Hướng dẫn sử dụng" | HELP | Hiển thị help |
| "Xóa tất cả dữ liệu" | DELETE | ⛔ Bị chặn |

---

## 🔒 Quy tắc an toàn

- ✅ **Không sử dụng LLM** hay API AI bên ngoài
- ✅ **Không ghi đè file gốc** — output luôn vào thư mục `output/`
- ✅ **Chặn path traversal** — chỉ truy cập trong phạm vi project
- ✅ **Không tự xóa dữ liệu** — lệnh DELETE bị chặn hoàn toàn
- ✅ **Không tự suy đoán Primary Key** — yêu cầu xác nhận từ người dùng
- ✅ **Kiểm tra file trước khi đọc** — validate extension, size, existence
- ✅ **Ghi log tất cả tác vụ** vào SQLite

---

## 📡 API Endpoints

| Method | Endpoint | Mô tả |
|--------|----------|-------|
| POST | `/api/command` | Nhận câu lệnh, trả kết quả |
| POST | `/api/execute/comparison` | Thực thi so sánh sau khi có primary key |
| GET | `/api/files` | Liệt kê file trong project |
| GET | `/api/download/{project}/{filename}` | Tải file output |
| GET | `/api/tasks/{session_id}` | Lịch sử tác vụ |
| GET | `/health` | Kiểm tra trạng thái |

---

## 🔧 Công nghệ sử dụng

| Thành phần | Công nghệ |
|------------|-----------|
| Backend API | FastAPI + Uvicorn |
| Chatbot UI | Streamlit |
| NLP Engine | Regex + RapidFuzz (Rule-based) |
| Data Processing | Pandas |
| Excel I/O | OpenPyXL |
| Validation | Pydantic v2 |
| Database | SQLite |
| Testing | unittest / pytest |

---

## 🗺️ Flow xử lý câu lệnh

```
Người dùng nhập câu lệnh
        ↓
[Intent Router] - Regex + Keyword + Fuzzy matching
        ↓
[Entity Extractor] - Cột, toán tử, giá trị, tên file
        ↓
[Command Parser] - Tạo ParsedCommand (Pydantic)
        ↓
[Workflow Engine] - Chọn workflow phù hợp
        ↓
[Excel Processing] - Pandas + OpenPyXL
        ↓
[Response Generator] - Trả kết quả + file output
```

