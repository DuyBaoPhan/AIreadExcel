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


## Tạo báo cáo từ file upload

Trên giao diện Streamlit, mở mục **Tạo báo cáo từ file của bạn**:

1. Upload một file `.xlsx` hoặc `.csv` (tối đa 20 MB, 100.000 dòng dữ liệu).
2. Chọn sheet và dòng tiêu đề (đánh số từ 1). Kiểm tra bản xem trước 50 dòng.
3. Chọn mẫu Tổng hợp, Nhân sự hoặc Doanh thu / bán hàng.
4. Điền tên đơn vị, tiêu đề, kỳ báo cáo và người lập. Kỳ báo cáo chỉ là nhãn hiển thị, không lọc dữ liệu.
5. Với mẫu Nhân sự, chọn cột phòng ban và tùy chọn cột lương dạng số. Mẫu bán hàng cần cột phân nhóm và cột doanh thu dạng số.
6. Bấm **Tạo báo cáo Excel**, sau đó **Tải báo cáo Excel**.

Báo cáo chỉ sử dụng sheet đã chọn, không trộn với file demo. Dữ liệu được xử lý trong bộ nhớ và không ghi vào thư mục input/output dùng chung. File upload không được tự thêm vào nguồn của chatbot. Tải file về trước khi đóng hoặc khởi động lại ứng dụng; đây không phải kho lưu trữ bền vững.

Mỗi dòng là một bản ghi, không tự loại trùng hay suy luận mã nhân viên. Người dùng phải chọn đúng cột tiền; không chọn mã định danh hoặc cộng các loại tiền tệ khác nhau. Ô tiền trống không được suy đoán; kiểm tra cảnh báo chất lượng trước khi sử dụng số liệu.

## Báo cáo nâng cao không cần LLM

Mục **Báo cáo nâng cao** dùng bộ tính toán xác định, không gửi dữ liệu sang AI/API bên ngoài. Mỗi lần làm việc hỗ trợ một nguồn chính và một nguồn phụ để nối, chọn sheet và dòng tiêu đề riêng. Dữ liệu nằm trong phiên Streamlit; đây không phải hệ thống đăng nhập hay kho lưu trữ bền vững.

### Khả năng
- Lọc nhiều điều kiện AND/OR: bằng/khác, so sánh số/ngày, chứa văn bản (không regex), danh sách, khoảng, ô trống.
- Kiểu lọc được chọn rõ: text/number/date. Văn bản so sánh phân biệt hoa thường. Chuỗi ngày dùng ngày/tháng/năm; giá trị không chuyển kiểu được sẽ báo lỗi, không tự loại bỏ.
- Nhóm theo nhiều cột và ngày/tháng/quý/năm. Chỉ tiêu: tổng, trung bình, min/max, đếm dòng, đếm giá trị không trống, đếm duy nhất (không tính null).
- Pivot và top/bottom N; pivot là chế độ riêng, không kết hợp chỉ tiêu nhóm hoặc so sánh kỳ trong cùng cấu hình.
- So sánh hai khoảng thời gian không giao nhau: giá trị hiện tại, kỳ trước, chênh lệch và % thay đổi. Không có nhóm ở một kỳ giữ null, không tự suy luận bằng 0; kỳ trước bằng 0 không tính phần trăm. Cận thời gian bao gồm hai đầu; khi nhập ngày cuối phải dùng hết ngày nếu dữ liệu có giờ.
- Nối trái/trong/ngoài bằng khóa rõ ràng và kiểm tra quan hệ 1–1, nhiều–1 hoặc 1–nhiều. Không hỗ trợ nhiều–nhiều; từ chối khóa null và khóa trùng vi phạm quan hệ. Nối 1–nhiều có thể lặp giá trị từ bảng trái: phải chọn đúng chỉ tiêu trước khi cộng.
- Tải/lấy lại cấu hình JSON phiên bản 1. Cấu hình chỉ chứa phép toán cho phép, không có Python, SQL hay eval. Cấu hình không kèm dữ liệu nguồn hoặc cấu hình nối; chọn lại nguồn/khóa khi chạy lại.
- Excel gồm Report, Summary, Data, Quality và Configuration. Trang Report là trích tối đa 15 dòng; Summary chứa toàn bộ kết quả. Top N tác động vào bảng tổng hợp nếu có, nếu không thì vào dữ liệu chi tiết.

### Giới hạn và tính đúng
Tối đa mỗi file 20 MB, workbook giải nén 200 MB, 100.000 dòng, 200 cột; bảng tổng hợp tối đa 1 triệu ô; cấu hình 100 KiB. Không tự đoán cột tiền, đơn vị tiền tệ, công thức nghiệp vụ hay loại trùng. Excel công thức được đọc theo giá trị cache có sẵn, không được tính lại; hãy tính/lưu workbook trong Excel trước khi upload. CSV phải là UTF-8, dấu phân cách phẩy. Chưa hỗ trợ biểu thức tùy ý, PDF, lập lịch, dữ liệu ngoài hoặc mọi yêu cầu ngôn ngữ tự nhiên.

Cấu hình mẫu ở `examples/hr_report.json`, `examples/payroll_pivot.json`, `examples/period_comparison.json`; thay tên cột và khoảng ngày theo nguồn thực tế. Mẫu so sánh dùng ngày bắt đầu làm việc chỉ để minh họa kỹ thuật, không phải so sánh quỹ lương tháng thực tế.

Giới hạn xuất Excel có định dạng: tổng Data + Summary tối đa 1.000.000 ô. Ô chữ/tiêu đề dài hơn giới hạn Excel 32.767 ký tự UTF-16 sẽ bị từ chối, không cắt ngầm. Sheet Configuration lưu JSON thành các đoạn; ghép các ô theo thứ tự, không thêm dấu phân cách, để khôi phục JSON. Nút tải cấu hình JSON là cách dùng lại cấu hình trực tiếp.

## Giao diện Excel Studio

Thanh bên chia ba không gian độc lập: **Chatbot**, **Tạo báo cáo** và **Báo cáo nâng cao**. Chỉ công cụ đang chọn được dựng, giảm tải và tránh nhầm nguồn. Chatbot sử dụng file dự án; công cụ báo cáo sử dụng file upload riêng trong phiên. Khi backend mất kết nối, chatbot tạm khóa nhưng hai công cụ báo cáo vẫn dùng được.

Thư viện file dự án chỉ tải khi bật **Mở thư viện file dự án**; chọn một kết quả để tải thay vì nạp tất cả file. Hội thoại có thể lưu thành văn bản, xóa cần xác nhận. Chuyển công cụ không xóa lịch sử chat. Tác vụ đối chiếu đang chờ có nút hủy riêng.

Theme dark/cyan tự chứa, không gọi font/CDN ngoài; có trạng thái focus bàn phím và hỗ trợ giảm chuyển động. Theme Streamlit ở `.streamlit/config.toml` tại thư mục gốc và thư mục engine để chạy từ cả hai vị trí. Khởi động lại Streamlit sau khi đổi cấu hình theme. Không có thay đổi thuật toán tính toán hoặc quyền truy cập dữ liệu trong lần thiết kế giao diện này.

## Vệ sinh repository và cài thư viện

Danh sách thư viện dùng chung nằm tại `requirements.txt` ở gốc repository. Bản `excel_rule_engine/requirements.txt` tham chiếu danh sách đó bằng `-r ../requirements.txt`, nên có thể tiếp tục cài từ cả hai thư mục mà không duy trì hai bộ phiên bản khác nhau. Giữ nguyên chính sách khoảng phiên bản của bản gốc; đây chưa phải lockfile tái lập môi trường.

File sinh trong `excel_rule_engine/projects/*/output/` được Git bỏ qua, ngoại trừ `.gitkeep`. Các báo cáo cũ đã được bỏ theo dõi trong index, không xóa file trên máy thực hiện dọn dẹp và không viết lại lịch sử Git. Sau khi commit/pull thay đổi này ở máy khác, các bản output từng được theo dõi có thể bị Git xóa tại đó; sao lưu báo cáo cần giữ trước khi cập nhật. Có thể tạo lại mẫu bằng `python tests/create_advanced_reports.py` từ thư mục engine.

## Chatbot hiểu yêu cầu báo cáo theo dữ liệu (không LLM)

Yêu cầu phân tích cụ thể được chuyển sang bộ lập kế hoạch dựa trên tên cột và giá trị thật của file, không còn chỉ bắt từ “báo cáo” rồi gộp toàn bộ nguồn. Chatbot hiển thị nguồn, chỉ tiêu, nhóm và điều kiện; người dùng phải bấm **Xác nhận và tạo báo cáo**. Khi có nhiều nguồn phù hợp, chọn nguồn và phân tích lại; khi câu còn mơ hồ, gửi lại câu đầy đủ đã làm rõ. Đây chưa phải hội thoại suy luận tự do.

Các mẫu câu trong phạm vi hỗ trợ:
- “Báo cáo doanh thu của Laptop Pro X năm 2024 là bao nhiêu?”
- “Tổng doanh thu theo sản phẩm năm 2024”
- “Lợi nhuận theo khu vực”
- “Doanh thu trung bình theo sản phẩm”
- “Lương trung bình theo phòng ban IT”
- “Đếm nhân viên theo phòng ban” (đếm mã nhân viên duy nhất)
- “Đếm dòng doanh thu từ 10 đến 30 triệu”
- “Top 5 sản phẩm doanh thu cao nhất”

Tên sản phẩm/phòng ban/khu vực/trạng thái được khớp từ dữ liệu thật, không hard-code. Tên cột có thể Việt/Anh theo từ điển `SCHEMA_ALIASES` trong `app/core/report_planner.py`. Chuẩn hóa dấu chỉ dùng khi nhận diện; bộ lọc giữ giá trị gốc. Nhiều cột đồng nghĩa hoặc nhiều nguồn đều cần làm rõ. Giá trị tháng YYYY-MM có thể lọc năm; tháng không có năm không được tự suy đoán, trừ khi nguồn xác định duy nhất một năm (hiển thị kế hoạch để kiểm tra).

Chưa hỗ trợ qua câu tự nhiên: dự báo, nối nhiều nguồn, so sánh kỳ, điều kiện OR/loại trừ phức tạp, công thức nghiệp vụ tùy ý hoặc nối tiếp ngữ cảnh kiểu “còn tháng trước?”. Sử dụng Báo cáo nâng cao cho các phép toán có giao diện tương ứng. Nếu còn cụm điều kiện chưa nhận diện, chatbot phải hỏi/từ chối, không xuất thay bằng báo cáo tổng hợp. Các câu xuất tổng hợp chung rõ ràng vẫn dùng luồng cũ.

Xác nhận gắn với dấu kiểm tra SHA-256 của yêu cầu, nguồn và cấu hình. Dữ liệu thay đổi cần xem/xác nhận lại; đây là kiểm tra tính nhất quán, **không phải đăng nhập hoặc phân quyền**. Tối đa 20 nguồn/40 MB tổng; chatbot đọc sheet đầu, muốn chọn sheet khác dùng công cụ upload báo cáo. Không có bản ghi phù hợp hoặc không có bằng chứng số liệu thì không tạo báo cáo bằng 0 giả. Kết quả bảng được hiển thị trong hội thoại và xuất Excel có cấu hình.

Kiểm thử toàn bộ (bao gồm tập câu tiếng Việt): cài `pip install -r requirements-dev.txt` từ gốc, chạy `python -m pytest`. Không thêm pytest vào phụ thuộc chạy Cloud.


## Kiểm thử ngôn ngữ tự nhiên diện rộng

Bộ kiểm thử cố định có 596 trường hợp (572 câu khác nhau), gồm câu có dấu/không dấu, phép tổng/trung bình/đếm/min/max, nhóm nhiều chiều, xếp hạng, lọc số và thời gian, nguồn mơ hồ và điều kiện chưa hỗ trợ. Kết quả kỳ vọng được viết độc lập và đối chiếu số liệu, không chỉ kiểm tra trạng thái “đã hiểu”.

- Kết quả và giới hạn: `../docs/nlp_campaign_results.md`.
- Lỗi ban đầu và từng câu: `../docs/nlp_benchmark_baseline.json`; so sánh cùng bộ mở rộng: `../docs/nlp_benchmark_expanded_before.json`, `../docs/nlp_benchmark_current.json`.
- Chạy từ thư mục gốc repository: `excel_rule_engine\venv\Scripts\python.exe -m pytest -q`.
- Xuất nhật ký từng câu: `excel_rule_engine\venv\Scripts\python.exe excel_rule_engine/tests/test_nlp_benchmark.py --audit docs/nlp_benchmark_current.json`. Chế độ audit luôn lưu cả lỗi và trả mã 0; pytest mới là cổng kiểm tra bắt buộc.

Đây là phạm vi đã kiểm thử, không phải cam kết hiểu mọi câu tiếng Việt. Trường hợp phạm vi tính toán mơ hồ sẽ hỏi lại, không tự bỏ điều kiện hoặc chuyển sang gộp file. Khởi động lại cả backend sau khi cập nhật mã nguồn.

## Tự động tạo báo cáo khi yêu cầu rõ ràng

Chatbot mặc định bật **Tự động tạo báo cáo**: chọn nguồn dựa trên cột nghiệp vụ, giá trị và thời gian phù hợp rồi tạo kết quả ngay, không yêu cầu xác nhận lần hai. Có thể tắt tùy chọn này ở thanh bên để xem và xác nhận kế hoạch theo cách thủ công.

- Không chọn nguồn chỉ vì tên tệp, thứ tự, số dòng hoặc vì một nguồn dễ phân tích hơn nguồn khác.
- Nếu nhiều nguồn cùng phù hợp, chỉ hiển thị những nguồn liên quan để người dùng chọn; ở chế độ tự động, chọn xong sẽ chạy ngay. Không tự gộp các tệp nhân sự.
- Kết quả ghi rõ nguồn, lý do chọn và số dòng phù hợp. Luồng tự động lập kế hoạch và chạy trên cùng một bản chụp dữ liệu, không ghi đè tệp đầu vào.
- “Đứng top 2” trả hai đối tượng dẫn đầu; “đứng thứ 2” trả một đối tượng tại vị trí thứ hai. Các giá trị bằng nhau được giữ thứ tự ổn định, không dùng hạng đồng hạng dày đặc.
- Điều kiện chưa hiểu hoặc không có bằng chứng dữ liệu sẽ không được thay bằng báo cáo tổng hợp/gộp file.

**Streamlit Cloud:** đưa toàn bộ mã mới lên đúng repository/branch của app, sau đó chọn **Reboot app** trong phần quản lý ứng dụng. Backend cần có cả các tuyến lập kế hoạch, xác nhận và `POST /api/report/auto`; chỉ tải lại trang trình duyệt không bảo đảm backend cũ đã được thay. Không chuyển sang gộp file khi gặp HTTP 404.

Kết quả kiểm thử và giới hạn của đợt nâng cấp: [automatic_reporting_results.md](../docs/automatic_reporting_results.md).
