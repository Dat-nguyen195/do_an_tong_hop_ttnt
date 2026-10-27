# Tổng hợp đóng góp và quyết định tích hợp

Kiểm tra ngày 28/10/2026 cho [Dat-nguyen195/do_an_tong_hop_ttnt](https://github.com/Dat-nguyen195/do_an_tong_hop_ttnt).
Chuẩn đánh giá là SEMSYNTH Lite phục vụ môn học, chạy được và dễ tiếp cận.
Thông tin dưới đây dựa trên lịch sử GitHub đã tải, nội dung diff, review mã và
kiểm thử cục bộ; không đánh giá công việc ngoài Git hoặc quy đổi số commit thành công sức.

## 1. Thành viên và bằng chứng trên GitHub

| Thành viên | Tài khoản được xác nhận từ tác giả commit | Nhánh / mốc | Kết quả thấy trong mã | Quyết định |
|---|---|---|---|---|
| Nguyễn Thành Đạt | [Dat-nguyen195](https://github.com/Dat-nguyen195) | `main`, `9d9ccf0`, 16/09 | Khởi tạo Lite: khảo sát phase 1, 15 bài pilot, baseline, khung module và UI | Dùng làm nền; controller/UI ban đầu vẫn là scaffold |
| Nguyễn Tiến Vũ Bảo | [tienbao-stack](https://github.com/tienbao-stack) | `propose-from-bao`, `cda756d`, 19/09; 1 commit riêng | Sửa cách diễn đạt cognitive load và thêm sơ đồ cho mục 3.4; 2 file thay đổi | Tích hợp; chỉnh link ảnh và chú thích các điều kiện dừng thực tế |
| Đặng Bá Ty | [tydeptrai21042004](https://github.com/tydeptrai21042004) | `tydeptrai`, đến `34670f6`, 27/10; 5 commit riêng | Pipeline hoạt động, API/mock, probe/hỏi/lọc, executor, demo, test, benchmark và Kaggle; 36 file thay đổi so với main gốc | Tích hợp sau các sửa lỗi tại mục 3; phần mở rộng giữ dạng tùy chọn |

Đối chiếu tên đầy đủ với danh sách nhóm trong `proposal_semsynth_doan-v2.pdf`.
Ba tài khoản được xác nhận trực tiếp qua metadata commit GitHub:
[Đạt](https://github.com/Dat-nguyen195/do_an_tong_hop_ttnt/commit/9d9ccf0497825d3ed2d83e1cd72b690da2fb9300),
[Bảo](https://github.com/Dat-nguyen195/do_an_tong_hop_ttnt/commit/cda756d29cdcaecb76220cba7936b48faea42b69),
[Ty](https://github.com/Dat-nguyen195/do_an_tong_hop_ttnt/commit/34670f6006d18acd39010cff81216f7fa6f7ba6a).
Tìm kiếm PR không trả về PR trong repository tại thời điểm review.

## 2. Chi tiết phần Ty đã thực hiện

| Commit | Ngày | Sản phẩm chính |
|---|---|---|
| `944570b` | 29/09 | Thay scaffold bằng controller hỏi–đáp, chọn câu hỏi theo khác biệt hành vi, quản lý ứng viên; cải tiến executor/client/baseline; UI trạng thái; dữ liệu và test |
| `b8a5454` | 01/10 | Adapter Gemini, demo offline nhiều tình huống, thêm kiểm thử; bổ sung giới hạn executor và lý do dừng |
| `d744453` | 17/10 | 32 ca synthetic/8 nhóm, runner/checkpoint/shard, cache/batch execution, soft belief tùy chọn, notebook và preflight |
| `bc33b17` | 27/10 | Explanation trace, xuất kết quả khi chạy lỗi, Kaggle one-cell và các test tương ứng |
| `34670f6` | 27/10 | Sửa đường dẫn import khi chạy trực tiếp `scripts/preflight.py` |

Đánh giá: phần Ty giúp dự án đi từ khung giai đoạn 1 sang prototype có thể chạy.
Đã có giá trị sử dụng rõ ràng, nên giữ. Các notebook, soft belief, nhiễu và shard
không phải yêu cầu bắt buộc để Đạt hoàn tất đồ án cuối tuần.

Không thấy kết quả đo LLM thật được kiểm chứng trong các bằng chứng đã review.
Các nội dung “verified” trong `IMPROVEMENT_REPORT.md` là báo cáo lịch sử của nhánh,
được đối chiếu lại bằng test trong lần tích hợp này.

## 3. Vấn đề phát hiện và phần sửa khi tích hợp

| Vấn đề có thể tái hiện | Ảnh hưởng | Xử lý |
|---|---|---|
| Executor dùng encoding mặc định của Windows | Đầu vào tiếng Việt gây `UnicodeEncodeError` ở cấu hình code page cũ | Cố định UTF-8 ở parent pipe và child Python; test cả single/batch với UTF-8 mode của parent bị tắt |
| Client loại trùng bằng cách gộp mọi whitespace | Có thể gộp nhầm chương trình trả `'a b'` với `'a  b'`, hoặc khác cấu trúc thụt lề | So sánh AST, giữ ý nghĩa string/indentation; thêm regression |
| Demo không dùng kiểm tra admission của controller | Một mã lỗi hoặc sai tên hàm có thể thành “best candidate”; hết câu hỏi bị trình bày như thành công | Chia sẻ kiểm tra ứng viên; phân biệt rỗng/một ứng viên/tạm thời; xóa phiên cũ khi sinh thất bại |
| Đầu vào đánh giá trùng probe dùng để hỏi | “Held-out” chưa đúng, kết quả có thể lạc quan | Loại trùng trước khi tính output, dùng cùng test còn lại cho mọi phương pháp, ghi manifest và test disjoint |
| Run ID không chứa tập phương pháp | Chạy lại cùng thư mục với methods khác có thể đọc lẫn checkpoint rồi lỗi aggregate | Đưa methods vào danh tính run; đóng băng model đã resolve vào manifest |
| Script ghép shard không chạy được trực tiếp | `ModuleNotFoundError: run_experiments` | Thêm project root; kiểm tra CLI |
| Ghép shard mặc định thiếu `proposed_explain`, không xác minh dataset hash | Không khớp phương pháp hoặc ghép với bộ dữ liệu khác | Đọc methods từ manifest; kiểm tra cấu hình/dataset trước khi ghi; kiểm thử ghép hai shard |
| First-valid chỉ kiểm tra AST mà chưa kiểm tra tên hàm | Có thể chọn hàm không đúng interface bài toán | Dùng kiểm tra admission chung |
| Preflight tìm `google.genai` khi chưa có namespace `google` | Traceback thay cho thông báo thiếu package | Bắt `ModuleNotFoundError` và báo thiếu dependency |
| Link ảnh `/image/01.png`, tài liệu cũ và một bản Excel tên mã hóa bị trùng | Khó mở local, khó xác định trạng thái hiện hành | Link tương đối; viết README theo Lite; bỏ bản Excel trùng byte, giữ bản gốc và thay đổi cục bộ |

Giữ lịch sử commit của hai thành viên qua merge commit. Những sửa lỗi tích hợp
được ghi riêng, không ghi đè hoặc đổi tác giả các commit trước đó.

## 4. Kết quả xác minh

Môi trường: Windows, Python 3.12.14. Kiểm thử adapter API dùng fake/mock; **không gọi
API thật trong lần review này**. Workflow CI đã được thêm nhưng chưa có bằng chứng
CI trên GitHub tại thời điểm ghi tài liệu.

| Kiểm tra | Kết quả |
|---|---|
| Snapshot nguyên trạng nhánh Ty `34670f6` | 96 tests passed, 45,94 giây |
| Bản tích hợp, gồm regression và Streamlit AppTest | 107 tests passed, 78,10 giây |
| Preflight offline | PASS; đọc đủ 32 bài, 8 nhóm và ghi được output |
| Demo offline | 3 ca chạy; sort/intersection còn 1 ứng viên; dedup còn 2 ứng viên tương đương trên probe và báo đúng chưa hội tụ |
| Runner offline, seed 3101, K=3, max questions=3, max probes=8 | Đủ 96/96 checkpoint, `all_complete=true` |

Kết quả synthetic của run `e6a84cf2098af752`:

| Cách chọn | Bài pass / 32 | Tỷ lệ | Câu hỏi TB |
|---|---:|---:|---:|
| Ứng viên đầu (`direct1`) | 13/32 | 40,625% | 0 |
| Ứng viên hợp lệ đầu (`first_valid`) | 13/32 | 40,625% | 0 |
| Lọc bằng câu hỏi cân bằng (`balanced`) | 32/32 | 100% | 1,4688 |

**Giới hạn diễn giải:** pool là mã dựng sẵn, có đáp án tham chiếu; người trả lời là
reference hoàn hảo; 32 ca chỉ gồm 8 họ mẫu. 100% xác nhận cơ chế chọn trên bộ có
kiểm soát, không chứng minh 100% độ chính xác LLM hoặc thành công với người dùng.
Runner đã loại tổng cộng 33 evaluation inputs trùng probe (tính theo các bài),
còn 2–5 test/bài; bộ cuối kỳ nên bổ sung test nếu muốn kết luận mạnh hơn.

Bằng chứng được lưu tại [evidence/2026-10-28](evidence/2026-10-28/):
`verification.json`, `summary.csv`, `per_task.csv`, `manifest.json`,
`completeness.json`, `offline-environment.txt`. Toàn bộ checkpoint/pool và ZIP ở
`results/integration_review/e6a84cf2098af752/` (thư mục kết quả không được Git theo dõi).

## 5. Thư mục và bảo toàn dữ liệu

- Repository làm việc đúng: `D:\HK1_261\Đồ án tổng hợp ttnt`, remote trỏ đúng GitHub.
- File Excel gốc có thay đổi chưa commit trước review; đã giữ nguyên từng byte,
  có backup trong `.git/codex-review/original-local-assignment.xlsx` và stash
  `Preserve local assignment workbook before team integration 2026-10-27`.
  Thay đổi cá nhân này không được đưa vào commit tích hợp.
- Bản Excel tên chứa `#U...` do nhánh Ty bổ sung trùng byte với bản local, đã loại
  khỏi phiên bản tích hợp để tránh nhầm bản. Có thể truy hồi qua lịch sử nhánh Ty.
- Bản clone phụ `D:\Research\do_an_tong_hop_ttnt` không có dữ liệu riêng và đã
  được kiểm tra refs khớp. Thao tác xóa bị hệ thống kiểm duyệt chặn với “blocked
  by policy”; bản này vẫn tồn tại. Mọi sửa đổi được thực hiện trong thư mục gốc.

## 6. Việc còn lại trước khi nộp

Ưu tiên một phiên LLM thật, pilot nhỏ, phân tích lỗi và báo cáo. Kiểm tra model
hiện có trong tài khoản; không coi default model trong nhánh là đã được xác minh.
Tài liệu phase 1 vẫn chứa mục tiêu kỳ vọng và mô tả CoT cần chỉnh trong báo cáo cuối.
Các mẫu câu hỏi ngữ nghĩa chỉ phủ một phần, probing vẫn heuristic, executor chưa
phù hợp dịch vụ chạy mã đối kháng. Trình bày đúng các giới hạn này là đủ cho phạm vi Lite.

Lịch làm một mình, lệnh chạy, sản phẩm từng ngày và phương án giảm tải ở
[KE_HOACH_HOAN_THANH.md](KE_HOACH_HOAN_THANH.md).
