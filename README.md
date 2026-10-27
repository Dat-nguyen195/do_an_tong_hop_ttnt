# SEMSYNTH Lite

Đồ án tổng hợp hướng Trí tuệ nhân tạo: sinh các hàm Python nhỏ từ mô tả tự nhiên,
hỏi người dùng Yes/No về các hành vi khác nhau, rồi thu hẹp tập chương trình ứng viên.
Phạm vi chính là xử lý chuỗi và danh sách; giao diện dùng Streamlit.

## Tài liệu làm việc

- [Kế hoạch hoàn thành đồ án](docs/KE_HOACH_HOAN_THANH.md): phạm vi, phân công, mốc và tiêu chí nghiệm thu.
- [Tổng hợp đóng góp và quyết định tích hợp](docs/TONG_HOP_DONG_GOP.md).
- [Báo cáo giai đoạn 1](docs/phase1_report.md): khảo sát và mục tiêu ban đầu; các tỷ lệ kỳ vọng chưa phải kết quả đo.
- [Hướng dẫn Kaggle](notebooks/KAGGLE_QUICKSTART.md): lựa chọn bổ sung khi cần chạy trên cloud.

## Cài đặt và chạy trên Windows

Yêu cầu Python 3.10 trở lên; môi trường tích hợp dùng Python 3.12.

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m streamlit run app.py
```

Linux/macOS: dùng `.venv/bin/python` thay cho `.\.venv\Scripts\python.exe`.
Trên giao diện, chọn **Offline demo (no API key)** để thử trước. Ba tình huống có
ứng viên mẫu là xóa phần tử trùng, sắp xếp và tìm phần tử chung. Các mô tả khác
cần chọn **Real LLM** để sinh chương trình theo yêu cầu.

Để dùng API, sao chép `.env.example` thành `.env`, điền khóa của provider đã chọn
và model mà tài khoản thực sự truy cập được. Có adapter OpenAI, OpenRouter và
Gemini. Chạy thử một bài trước khi chạy hàng loạt. Kiểm thử offline không xác nhận
một model/khóa API còn hoạt động. Không lưu khóa trong notebook hoặc Git.

## Luồng tối thiểu

1. Sinh tối đa K ứng viên, loại bản trùng, sai cú pháp và sai tên hàm.
2. Chạy ứng viên trên đầu vào thăm dò nhỏ để tìm khác biệt.
3. Chọn câu hỏi chia tập ứng viên gần cân bằng nhất.
4. Nhận Yes/No và loại ứng viên không phù hợp.
5. Dừng khi còn một ứng viên, hết ngân sách câu hỏi hoặc không tìm được khác biệt.

Mẫu ngữ nghĩa hiện hỗ trợ thứ tự khi loại trùng và chiều sắp xếp. Câu hỏi gắn
với đầu vào quan sát được; trường hợp khác dùng câu hỏi I/O. Một ứng viên còn lại
không bảo đảm đúng trên mọi đầu vào. Giao diện ghi rõ khi lựa chọn còn tạm thời.

| Thành phần | File |
|---|---|
| Sinh ứng viên, API và mock | `src/llm_client.py` |
| Kiểm tra và lọc ứng viên | `src/candidate_manager.py` |
| Chạy hàm trong tiến trình riêng | `src/code_executor.py` |
| Probe và câu hỏi Yes/No | `src/question_generator.py` |
| Điều phối phiên, log, điều kiện dừng | `src/semsynth_controller.py` |
| Demo tương tác | `app.py` |
| Direct-1 / Oracle Best-of-K | `src/baseline_cot.py` |
| Thực nghiệm có checkpoint | `run_experiments.py` |

Đồ án mặc định dùng lọc cứng và Top-K nhỏ. Cập nhật xác suất mềm, mô phỏng trả lời
sai, explanation trace và chạy nhiều shard là phần mở rộng tùy chọn.

## Kiểm thử và thực nghiệm

Các lệnh sau dùng Python của môi trường đã kích hoạt; có thể thay `python`
bằng đường dẫn `.venv\Scripts\python.exe`.

```powershell
python -m pytest -q
python scripts/preflight.py --mode offline
python kaggle_run.py --offline-suite
python -m src.baseline_cot --dry-run --limit 3
python run_experiments.py --mode offline --quick --methods direct1,first_valid,balanced --require-complete
```

- `config/dataset_sample.json`: 15 bài pilot biên soạn theo HumanEval/MBPP;
  cần đối chiếu nguồn và test trước khi dùng làm kết quả cuối kỳ.
- `config/ambiguity_benchmark.json`: 32 ca tổng hợp thuộc 8 nhóm mẫu. Đây là bộ
  kiểm tra có kiểm soát, không phải 32 bài thực tế độc lập.
- Runner dùng cùng pool ứng viên cho các cách chọn, tách đầu vào đánh giá khỏi
  toàn bộ probe làm rõ, ghi số đầu vào bị loại do trùng trong manifest.
- `direct1` của runner là ứng viên đầu trong pool đã sinh. Đo một lần sinh độc
  lập bằng `src.baseline_cot`; không coi sinh cả pool là một API call.
- `oracle_upper_bound` / Oracle Best-of-K dùng đáp án để chọn chương trình,
  chỉ thể hiện cận trên và không phải baseline có thể triển khai cho người dùng.
- `success` của phiên nghĩa là còn ứng viên; `passed_all` đo vượt qua test đánh
  giá. Báo cáo riêng hai đại lượng này.

Kết quả trong `results/` gồm manifest, checkpoint, CSV và `SEMSYNTH_RESULTS.zip`.
Resume chỉ dùng lại cùng cấu hình, model, tập phương pháp và dữ liệu. Để ghép shard:

```powershell
python scripts/merge_shards.py path/to/shard0.zip path/to/shard1.zip --output-dir results/merged
```

Script đọc phương pháp từ manifest và từ chối dữ liệu không khớp.

## Giới hạn

Executor có kiểm tra AST, timeout và tiến trình riêng, phù hợp demo cục bộ với hàm
nhỏ. Nó chưa phải môi trường chạy mã đối kháng cho dịch vụ công cộng.

Mock/offline chỉ xác nhận pipeline và tình huống kiểm thử. Đồ án còn cần LLM thật,
dữ liệu đã rà nguồn, phân tích lỗi và diễn tập demo. Chưa đo với người dùng thì
không suy ra mức giảm tải nhận thức.

`IMPROVEMENT_REPORT.md`, `PATCH_*` và notebook cũ là tài liệu bàn giao lịch sử;
số test trong đó phản ánh thời điểm viết. Dùng kế hoạch và tổng hợp đóng góp làm
trạng thái hiện tại.
