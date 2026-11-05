<!-- Current architecture: OpenAI-only conversational understanding. -->
# Excel Studio - Excel AI & Reporting

> Excel chatbot with OpenAI-only natural-language understanding, validated Python execution, and hybrid local retrieval. An API key is required for conversational requests; there is no keyword/rules fallback.

---

## 🏗️ Kiến trúc hệ thống

See [Architecture](docs/architecture.md) for application layers and directory conventions.

```text
AIreadExcel/
|-- README.md                 # Start here
|-- main.py                   # Local launcher
|-- streamlit_app.py          # Streamlit Cloud
|-- requirements*.txt
|-- docs/                     # Guides and evaluation results
|-- scripts/                  # Demo generators and manual checks
`-- excel_rule_engine/
    |-- app/
    |   |-- main.py           # FastAPI
    |   |-- paths.py          # Shared filesystem paths
    |   |-- ui/               # Streamlit interface
    |   |-- services/         # ai, chat, excel, reports, sources, runtime
    |   |-- database/         # SQLite persistence
    |   `-- workflows/        # Deterministic data processing
    |-- legacy_nlp/           # Historical offline benchmarks only
    |-- tests/
    |-- examples/             # Report configuration samples
    `-- projects/             # Existing source files and report outputs
```

---

## ⚙️ Cài đặt

### Yêu cầu
- Python 3.12+
- Windows / Linux / macOS

### Bước 1: Clone và vào thư mục

```bash
cd AIreadExcel
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

Recommended: run from the repository root to launch both backend and UI:

```bash
python main.py
```

For separate development processes, open two terminals at the repository root:

### Terminal 1 — Khởi động FastAPI Backend

```bash
python -m uvicorn app.main:app --app-dir excel_rule_engine --reload --port 8000
```

API docs tại: http://localhost:8000/docs

### Terminal 2 — Khởi động Streamlit Chatbot

```bash
python -m streamlit run excel_rule_engine/app/ui/chatbot.py
```

Giao diện tại: http://localhost:8501

---

## 📊 Tạo dữ liệu mẫu

```bash
python scripts/create_sample_data.py
```

Tạo ra 6 file Excel trong `excel_rule_engine/projects/demo_project/input/`:
- `Employees_IT.xlsx` — Nhân viên phòng IT
- `Employees_Business.xlsx` - Sales, Marketing, HR, Finance
- `Employees_Operations.xlsx` - Warehouse, Production, Logistics
- `Sales_Data.xlsx` — Dữ liệu doanh thu
- `Root_Employees.xlsx` — File gốc cho so sánh
- `Update_Employees.xlsx` — File cập nhật cho so sánh

---

## 🧪 Chạy Unit Tests

```bash
python -m pytest
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

- OpenAI handles conversational understanding; requests/metadata or RAG evidence excerpts are sent to the provider as documented. Manual report configuration still runs locally.
- Report exports write into `output/`. Explicit source-update requests can modify a source only after the separate confirmation flow; a backup is retained.
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
| Natural-language understanding | OpenAI structured outputs; no keyword routing |
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
[OpenAI agent] - Structured action and report configuration
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

Cấu hình mẫu ở `excel_rule_engine/examples/hr_report.json`, `excel_rule_engine/examples/payroll_pivot.json`, `excel_rule_engine/examples/period_comparison.json`; thay tên cột và khoảng ngày theo nguồn thực tế. Mẫu so sánh dùng ngày bắt đầu làm việc chỉ để minh họa kỹ thuật, không phải so sánh quỹ lương tháng thực tế.

Giới hạn xuất Excel có định dạng: tổng Data + Summary tối đa 1.000.000 ô. Ô chữ/tiêu đề dài hơn giới hạn Excel 32.767 ký tự UTF-16 sẽ bị từ chối, không cắt ngầm. Sheet Configuration lưu JSON thành các đoạn; ghép các ô theo thứ tự, không thêm dấu phân cách, để khôi phục JSON. Nút tải cấu hình JSON là cách dùng lại cấu hình trực tiếp.

## Giao diện Excel Studio

Thanh bên chia ba không gian độc lập: **Chatbot**, **Tạo báo cáo** và **Báo cáo nâng cao**. Chỉ công cụ đang chọn được dựng, giảm tải và tránh nhầm nguồn. Chatbot sử dụng file dự án; công cụ báo cáo sử dụng file upload riêng trong phiên. Khi backend mất kết nối, chatbot tạm khóa nhưng hai công cụ báo cáo vẫn dùng được.

Thư viện file dự án chỉ tải khi bật **Mở thư viện file dự án**; chọn một kết quả để tải thay vì nạp tất cả file. Hội thoại có thể lưu thành văn bản, xóa cần xác nhận. Chuyển công cụ không xóa lịch sử chat. Tác vụ đối chiếu đang chờ có nút hủy riêng.

Theme dark/cyan tự chứa, không gọi font/CDN ngoài; có trạng thái focus bàn phím và hỗ trợ giảm chuyển động. Theme Streamlit ở `.streamlit/config.toml` tại thư mục gốc và thư mục engine để chạy từ cả hai vị trí. Khởi động lại Streamlit sau khi đổi cấu hình theme. Không có thay đổi thuật toán tính toán hoặc quyền truy cập dữ liệu trong lần thiết kế giao diện này.

## Vệ sinh repository và cài thư viện

Danh sách thư viện dùng chung nằm tại `requirements.txt` ở gốc repository. Bản `excel_rule_engine/requirements.txt` tham chiếu danh sách đó bằng `-r ../requirements.txt`, nên có thể tiếp tục cài từ cả hai thư mục mà không duy trì hai bộ phiên bản khác nhau. Giữ nguyên chính sách khoảng phiên bản của bản gốc; đây chưa phải lockfile tái lập môi trường.

File sinh trong `excel_rule_engine/projects/*/output/` được Git bỏ qua, ngoại trừ `.gitkeep`. Các báo cáo cũ đã được bỏ theo dõi trong index, không xóa file trên máy thực hiện dọn dẹp và không viết lại lịch sử Git. Sau khi commit/pull thay đổi này ở máy khác, các bản output từng được theo dõi có thể bị Git xóa tại đó; sao lưu báo cáo cần giữ trước khi cập nhật. Có thể tạo lại mẫu bằng `python scripts/create_advanced_reports.py` from the repository root.

## Chatbot hiểu yêu cầu báo cáo theo dữ liệu (không LLM)

> Historical offline implementation/benchmark only. This is not the production chatbot routing path. Current requests require OpenAI; these older scores do not measure OpenAI accuracy.

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

Tên sản phẩm/phòng ban/khu vực/trạng thái được khớp từ dữ liệu thật, không hard-code. Tên cột có thể Việt/Anh theo từ điển `SCHEMA_ALIASES` trong `excel_rule_engine/app/services/reports/schema_matching.py`. Chuẩn hóa dấu chỉ dùng khi nhận diện; bộ lọc giữ giá trị gốc. Nhiều cột đồng nghĩa hoặc nhiều nguồn đều cần làm rõ. Giá trị tháng YYYY-MM có thể lọc năm; tháng không có năm không được tự suy đoán, trừ khi nguồn xác định duy nhất một năm (hiển thị kế hoạch để kiểm tra).

Chưa hỗ trợ qua câu tự nhiên: dự báo, nối nhiều nguồn, so sánh kỳ, điều kiện OR/loại trừ phức tạp, công thức nghiệp vụ tùy ý hoặc nối tiếp ngữ cảnh kiểu “còn tháng trước?”. Sử dụng Báo cáo nâng cao cho các phép toán có giao diện tương ứng. Nếu còn cụm điều kiện chưa nhận diện, chatbot phải hỏi/từ chối, không xuất thay bằng báo cáo tổng hợp. Các câu xuất tổng hợp chung rõ ràng vẫn dùng luồng cũ.

Xác nhận gắn với dấu kiểm tra SHA-256 của yêu cầu, nguồn và cấu hình. Dữ liệu thay đổi cần xem/xác nhận lại; đây là kiểm tra tính nhất quán, **không phải đăng nhập hoặc phân quyền**. Tối đa 20 nguồn/40 MB tổng; chatbot đọc sheet đầu, muốn chọn sheet khác dùng công cụ upload báo cáo. Không có bản ghi phù hợp hoặc không có bằng chứng số liệu thì không tạo báo cáo bằng 0 giả. Kết quả bảng được hiển thị trong hội thoại và xuất Excel có cấu hình.

Kiểm thử toàn bộ (bao gồm tập câu tiếng Việt): cài `pip install -r requirements-dev.txt` từ gốc, chạy `python -m pytest`. Không thêm pytest vào phụ thuộc chạy Cloud.


## Kiểm thử ngôn ngữ tự nhiên diện rộng

> Historical offline implementation/benchmark only. This is not the production chatbot routing path. Current requests require OpenAI; these older scores do not measure OpenAI accuracy.

Bộ kiểm thử cố định có 596 trường hợp (572 câu khác nhau), gồm câu có dấu/không dấu, phép tổng/trung bình/đếm/min/max, nhóm nhiều chiều, xếp hạng, lọc số và thời gian, nguồn mơ hồ và điều kiện chưa hỗ trợ. Kết quả kỳ vọng được viết độc lập và đối chiếu số liệu, không chỉ kiểm tra trạng thái “đã hiểu”.

- Kết quả và giới hạn: `docs/nlp_campaign_results.md`.
- Lỗi ban đầu và từng câu: `docs/nlp_benchmark_baseline.json`; so sánh cùng bộ mở rộng: `docs/nlp_benchmark_expanded_before.json`, `docs/nlp_benchmark_current.json`.
- Chạy từ thư mục gốc repository: `python -m pytest -q`.
- Xuất nhật ký từng câu: `python excel_rule_engine/tests/test_nlp_benchmark.py --audit docs/nlp_benchmark_current.json`. Chế độ audit luôn lưu cả lỗi và trả mã 0; pytest mới là cổng kiểm tra bắt buộc.

Đây là phạm vi đã kiểm thử, không phải cam kết hiểu mọi câu tiếng Việt. Trường hợp phạm vi tính toán mơ hồ sẽ hỏi lại, không tự bỏ điều kiện hoặc chuyển sang gộp file. Khởi động lại cả backend sau khi cập nhật mã nguồn.

## Tự động tạo báo cáo khi yêu cầu rõ ràng

Chatbot mặc định bật **Tự động tạo báo cáo**: chọn nguồn dựa trên cột nghiệp vụ, giá trị và thời gian phù hợp rồi tạo kết quả ngay, không yêu cầu xác nhận lần hai. Có thể tắt tùy chọn này ở thanh bên để xem và xác nhận kế hoạch theo cách thủ công.

- Không chọn nguồn chỉ vì tên tệp, thứ tự, số dòng hoặc vì một nguồn dễ phân tích hơn nguồn khác.
- Nếu nhiều nguồn cùng phù hợp, chỉ hiển thị những nguồn liên quan để người dùng chọn; ở chế độ tự động, chọn xong sẽ chạy ngay. Không tự gộp các tệp nhân sự.
- Kết quả ghi rõ nguồn, lý do chọn và số dòng phù hợp. Luồng tự động lập kế hoạch và chạy trên cùng một bản chụp dữ liệu, không ghi đè tệp đầu vào.
- “Đứng top 2” trả hai đối tượng dẫn đầu; “đứng thứ 2” trả một đối tượng tại vị trí thứ hai. Các giá trị bằng nhau được giữ thứ tự ổn định, không dùng hạng đồng hạng dày đặc.
- Điều kiện chưa hiểu hoặc không có bằng chứng dữ liệu sẽ không được thay bằng báo cáo tổng hợp/gộp file.

**Streamlit Cloud:** đưa toàn bộ mã mới lên đúng repository/branch của app, sau đó chọn **Reboot app** trong phần quản lý ứng dụng. Backend cần có cả các tuyến lập kế hoạch, xác nhận và `POST /api/report/auto`; chỉ tải lại trang trình duyệt không bảo đảm backend cũ đã được thay. Không chuyển sang gộp file khi gặp HTTP 404.

Kết quả kiểm thử và giới hạn của đợt nâng cấp: [automatic_reporting_results.md](docs/automatic_reporting_results.md).

### Quy tắc ưu tiên nguồn theo phòng ban

Dự án có thể khai báo `source_policy.json` cạnh thư mục `input`, với `version: 1` và bảng `department_sources` ánh xạ tên phòng ban sang tên tệp chính xác. Đây là cấu hình nghiệp vụ rõ ràng, không phải suy đoán tên tệp. Dự án demo đã khai báo IT → Employees_IT.xlsx; HR/Accounting/Sales/Marketing/Finance → Employees_Business.xlsx; Warehouse/Production/Admin/Engineering → Employees_Operations.xlsx.

Quy tắc chỉ áp dụng khi câu hỏi đã được phân tích thành điều kiện phòng ban bằng chính xác và nguồn được cấu hình nằm trong các nguồn phù hợp. Người dùng chỉ rõ tệp sẽ ghi đè ưu tiên này. Cấu hình thiếu hoặc tệp không còn tồn tại không dẫn đến tự gộp/chọn nguồn khác; cấu hình hỏng được báo lỗi. Câu hỏi toàn công ty vẫn cần một nguồn chính được xác định riêng; không tự coi Root hoặc Update là nguồn chính.

## OpenAI agent — understanding without keyword routing

All chatbot requests go to OpenAI, not a keyword intent parser. `REPORT_PLANNER=openai` is the supported setting; `auto` is a compatibility alias for OpenAI, never an offline fallback. Python still executes validated reports; the model cannot run code, access arbitrary files or calculate authoritative results itself.

### Streamlit Cloud

In **Manage app → Settings → Secrets**, add:

```toml
OPENAI_API_KEY = "your-key-here"
OPENAI_MODEL = "gpt-4.1-mini"
REPORT_PLANNER = "openai"
```

Never commit the real key or send it in chat. Publish the code to the app branch and **Reboot app**. The entrypoint passes only these documented settings to the backend subprocess. The sidebar shows AI configuration status. Missing keys and provider failures stop safely rather than activating offline keyword matching. The model must support strict JSON-schema structured outputs; change `OPENAI_MODEL` if needed for your account.

Local PowerShell: set these as environment variables in the terminal used to launch the application. The repository-root `.env` is loaded automatically at startup using python-dotenv; existing process environment variables take precedence. Copy `.env.example` to `.env` when setting up a new checkout.

- `REPORT_PLANNER=auto`: compatibility alias for OpenAI; a key is still required.
- `REPORT_PLANNER=openai`: require the key, never silently fall back if API fails.
- `REPORT_PLANNER=rules`: no longer supported by production; change this setting to `openai`.

### Privacy, boundaries and reliability

OpenAI receives the current request, source filenames, row counts, column names/types and configured department priorities. **No cell values or sample rows are uploaded.** Text the user enters may itself contain personal information; do not enter secrets or sensitive details into requests. Filenames and column names can also be sensitive metadata. There is no multi-turn conversational memory in this version: include all required conditions in each request.

The agent supports filters, aggregation, grouping, date grouping and ranking through a strict structured plan. Other operations (joins, arbitrary formulas, forecasts, destructive changes) are not silently approximated. It asks when source authority or intent is unclear. Metadata-only mode cannot discover values or infer date coverage from rows; an unknown value can produce no matches, not an invented result.

Every ready plan is checked for schema, available source/columns, safe config and numeric evidence. The engine enforces resource limits. There is one bounded API call per planning request, no automatic retries; 45-second provider timeout, output token limit 4,000. Provider billing applies. Manual approval caches the exact validated plan server-side for 15 minutes (up to 128 entries); confirmation rereads/verifies the source snapshot without a second AI plan. Backend restart expires pending AI approvals.

Automated tests mock the provider and verify local contracts/privacy/error handling; they do **not** measure a real model's language accuracy. Before production, run a separately reviewed evaluation with your configured key/model and representative data. Structural validation cannot prove that every user condition was interpreted correctly.

### Conversational mode and direct updates

In OpenAI mode the main chatbot now uses `/api/chat`: greetings/advice return conversation, data questions return locally computed tables without creating a workbook, and only an explicit export action creates a file. The server keeps up to 12 message entries per session for one hour (128 sessions maximum). Resolved requests, not computed rows, are sent as context for follow-ups. Planning a data turn can make two provider calls (routing and validated report planning), unlike the legacy one-call reporting endpoint. Provider billing applies to each call.

Direct updates are opt-in per operation: the assistant proposes one cell change identified by exact source and record key; the UI displays old/new values. **Only the confirmation button writes the source**. Text such as “yes” never confirms a write. XLSX first-sheet updates preserve other sheets and ordinary formatting using openpyxl; CSV updates require string cell values. Formulas, key changes, duplicate keys, unknown columns, bulk updates, row insertion/deletion and unsupported formats are rejected. A source byte fingerprint is checked before replacement; an exact original backup is created before an atomic file replacement. Pending tokens expire after five minutes or backend restart.

The backup is kept alongside the source with a non-input backup extension. Backups contain sensitive source data: protect them like originals and define a retention policy. Excel workbooks with advanced features may not round-trip perfectly in openpyxl; validate compatibility before enabling production edits. Cloud filesystem changes/backups are not durable storage and may disappear on reboot/redeploy.

**Deployment security:** the current app has no user authentication/authorization. Confirmation and session tokens are consistency safeguards, not user identity or access control. Do not publish a source-editing app with sensitive data to untrusted users; add authentication, project-level write permissions and durable audit/storage before production multi-user deployment. The local backend remains bound to loopback. No source data was modified during implementation; tests use isolated fixtures.

## Hybrid RAG over uploaded spreadsheets

The AI router distinguishes factual/qualitative lookup (`retrieve`) from full-table calculation (`query`). Retrieval combines local **intfloat/multilingual-e5-large** embeddings with **FAISS** cosine search and **BM25** lexical ranking, fused by reciprocal rank fusion. Exact record codes benefit from lexical search; paraphrases benefit from multilingual embeddings. Retrieval is not a completeness guarantee.

`requirements.txt` includes `requirements-rag.txt`. The embedding model is loaded lazily; the first lookup downloads model weights through the normal Hugging Face mechanism. This is a large model: allow several GB for download/runtime, expect CPU startup latency, and verify your hosting RAM before deploying. `RAG_MODEL_PATH` may point to a predownloaded local model. No lightweight substitute is silently selected. Streamlit Cloud resources may be insufficient; use a backend with adequate RAM if needed.

Indexing scans the project's chatbot `input` directory, not unrelated files processed privately in report wizards. Supported workbooks include every sheet. Records are tied to exact source/sheet/row provenance. Limits reject unsupported or excessive inputs explicitly rather than claim an incomplete index is complete. Index snapshots are project-isolated, bounded, in memory, and fingerprinted from input bytes. Add/change/delete source files and subsequent searches rebuild the index; direct edits are not answered using the previous index. No pickle deserialization or external vector service is used.

**Privacy change:** retrieval embeddings remain local, but the relevant cell excerpts and source references ARE sent to OpenAI to produce a grounded answer. This supersedes the schema-only promise for retrieval turns; structured report planning still uses metadata only. Treat source cells as untrusted data, not instructions. Do not use sensitive workbooks with this path unless provider processing is approved. Access control must be enforced before indexing/retrieval in a production multi-user deployment.

Answers are concise and cited to retrieved evidence. Unknown citation IDs / claims without references are rejected; missing evidence is reported rather than replaced by generic advice. Citation validation checks references, not semantic truth: the model may still misinterpret evidence. Top-k retrieval cannot establish full-dataset totals, counts, maxima or exhaustive lists; those stay in the Python report engine. Conflicting snapshots are not automatically merged or assigned authority.

### Adding files to the chatbot knowledge base

Use sidebar **Thêm Excel làm nguồn chatbot / RAG → Lưu làm nguồn chatbot**. This is explicit upload into the project input directory, refuses overwriting an existing name, and validates file type/size. Files uploaded earlier only to report wizards are not automatically retained as chatbot sources; upload them here to make them searchable. Existing project input files are indexed automatically on lookup.

Current retrieval limits: 20 input files, 40 MB total raw bytes, 200 MB expanded XLSX bytes, 20,000 data rows, 256 columns, 12,000 characters per row and 512 actual E5 tokens including prefix. A long row/query is explicitly rejected rather than silently truncated. Convert legacy XLS to XLSX. Formula cells are indexed as formula text (not freshly calculated results). The first row of each sheet is treated as a header; verify irregular worksheets before use. Indexes are in-memory FAISS stores and rebuild on process restart; model weights use the normal local model cache.

## Contextual report filenames

Conversational exports use concise business names from validated config: `Doanh_thu_2024-10.xlsx`, `Top5_doanh_thu_san_pham_2024.xlsx`, or `Nhan_vien_IT.xlsx`. Names keep the main measure, a grouping dimension where useful, ranking and reporting period; multi-measure reports use a short summary title. Query-only turns do not create files. Downloads retain the actual filename.

Names are ASCII/Windows-safe and length-bounded; device names and separators are excluded. No UUID is appended. If the name already exists, the writer tries `_2`, `_3`, and so on using exclusive file creation, which also prevents overwrites during simultaneous exports. The descriptive stem is bounded to 90 characters (plus a numeric collision suffix and extension). Names do not use arbitrary model aliases, source filenames or row-level personal/salary filter values. Unknown columns use a generic business label. This does not add free-form user-specified names or change legacy standalone wizard naming.

## Sidebar conversation history

The sidebar now lists conversations (title from first user message, newest activity first), supports creating a new conversation and restoring individual message/agent-session context. Tools, upload and settings are under a collapsed section. Switching conversations cancels pending writes and never restores approval tokens. Clearing a conversation removes its active archive entry. Copies prevent edits in one loaded thread from mutating another.

History is isolated in Streamlit browser-session state, not a permanent account archive. Closing/reconnecting the session or restarting the app can lose it. Agent context expires separately after its existing server TTL. Download the conversation to retain a copy. Durable cross-device history requires authenticated user-owned storage; this implementation does not expose all users' chats from a shared database.
