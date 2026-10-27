# Kế hoạch cá nhân hoàn thành SEMSYNTH Lite trước cuối tuần

**Cập nhật: 28/10/2026. Người thực hiện phần còn lại: Nguyễn Thành Đạt.**
Nhóm có ba người nhưng kế hoạch này không phụ thuộc việc Ty hoặc Bảo làm thêm.
Hạn người dùng cung cấp là cuối tuần này, chưa có giờ nộp: mục tiêu chốt bản nộp
vào **thứ Bảy 31/10**, dành **Chủ nhật 01/11** cho lỗi phát sinh và nộp bài.
Nếu trường yêu cầu nộp sớm hơn, ưu tiên các mục P0 dưới đây.

## 1. Bắt đầu từ đâu

Làm việc tại `D:\HK1_261\Đồ án tổng hợp ttnt`. Phần nghiên cứu trong
`D:\Research\implement` không thuộc phạm vi cần hoàn thiện tuần này.

Đã có: lõi sinh/lọc/hỏi, demo Streamlit, runner có checkpoint, 15 bài pilot,
32 ca tổng hợp thuộc 8 nhóm, báo cáo phase 1 và sơ đồ của Bảo. Bản tích hợp đã
được kiểm tra bằng **107 tests**, 3 demo offline và bộ thực nghiệm 32 ca × 3 cách chọn.
Xem [bằng chứng và quyết định tích hợp](TONG_HOP_DONG_GOP.md).

Còn thiếu để nộp: cấu hình và bằng chứng LLM thật; dữ liệu/mô tả được rà lại;
phân tích kết quả; báo cáo cuối; slide; video và hướng dẫn tái lập. **Không cần xây
lại hệ thống**. Phần lớn thời gian còn lại dành cho kiểm chứng và trình bày.

## 2. Phạm vi chốt cho môn học

Luồng phải demo được: mô tả hàm chuỗi/danh sách → K=3 ứng viên → tối đa 3 câu hỏi
Yes/No → lọc cứng → mã được chọn + lịch sử + lý do dừng. Một provider/model đã
kiểm tra truy cập. Mẫu ngữ nghĩa hiện hỗ trợ loại trùng và sắp xếp; có fallback I/O.

| Mức | Việc giữ lại / hoãn |
|---|---|
| P0 — bắt buộc | Demo chạy; một phiên LLM thật nếu có API; phép so sánh có dữ liệu; báo cáo, slide, video |
| P1 — khi P0 xong | Chạy thêm seed; 1–2 mẫu câu hỏi ngữ nghĩa cần cho demo; đo calls/tokens tốt hơn |
| Hoãn sau hạn nộp | Nhiều model, soft belief/noise study, Kaggle nhiều shard, XGBoost, 47 đặc trưng, React/FastAPI |

Không đặt điều kiện phải đạt 75–85% để được hoàn thành. Kết luận dựa trên số đo;
kết quả không cải thiện vẫn có giá trị nếu phân tích đúng nguyên nhân.

## 3. Kế hoạch theo ngày, có thời lượng và điểm dừng

Ngân sách dự kiến **20–24 giờ tập trung** từ 28–31/10, cộng 2–3 giờ dự phòng 01/11.
Thời gian API chạy có thể xen với viết báo cáo. Chỉ sửa lỗi có bằng chứng ảnh hưởng
demo hoặc phép đo; không dành cả ngày tối ưu thuật toán.

### Thứ Tư 28/10 — Chốt hệ thống, API và dữ liệu (5–6 giờ)

| ID | Việc làm theo thứ tự | Giờ | Sản phẩm / điều kiện hoàn thành |
|---|---|---:|---|
| W1 | Đọc README, tổng hợp đóng góp; chạy demo mặc định | 0,5 | Giải thích được luồng và 3 điều kiện dừng; có ảnh demo |
| W2 | Cài requirements, chọn đúng provider/model, tạo `.env` cục bộ | 0,5–1 | Một bài tạo ứng viên thật thành công; lưu model, cấu hình, không lưu khóa |
| W3 | Chạy smoke 1 bài với 3 phương pháp, xác nhận resume | 0,5 | Manifest và CSV đầy đủ; không dùng mock cho mục này |
| W4 | Rà 8 ca đầu tiên mỗi family của bộ synthetic; kiểm tra ý định đích và test | 1,5 | Bảng 8 bài: mô tả, hàm, ý định, số test độc lập và nguồn “tự biên soạn” |
| W5 | Rà 15 bài pilot: nguồn/id có thực không; chọn 3 bài phù hợp để minh họa | 1 | Đánh dấu bài đã xác minh; chưa xác minh thì gọi là bài biên soạn/adapted |
| W6 | Viết khung báo cáo và phần bài toán/phạm vi/kiến trúc | 1 | Bản thảo có đầy đủ đề mục và sơ đồ đúng phiên bản Lite |

**Gate cuối ngày:** demo offline ổn, ít nhất một API smoke thật; chốt config và
dataset trước khi chạy đo chính. Nếu API chưa chạy sau 60 phút xử lý, dừng thử
provider mới, chuyển sang W4–W6 và ghi phần LLM thật đang bị chặn.

### Thứ Năm 29/10 — Thực nghiệm và phân tích lỗi (5–6 giờ)

| ID | Việc làm | Giờ | Sản phẩm / điều kiện hoàn thành |
|---|---|---:|---|
| T1 | Chạy LLM thật trên 8 bài, cùng K=3, 3 câu hỏi, cùng pool cho 3 cách chọn | 1–2 + chờ API | 24 checkpoint hoàn chỉnh; ghi rõ người dùng giả lập bằng reference |
| T2 | Nếu ổn và còn ngân sách, chạy seed thứ hai; chỉ đổi seed, giữ protocol | 0,5 + chờ API | Hai run riêng; không ghi đè hoặc trộn cấu hình |
| T3 | Tổng hợp tỷ lệ pass theo bài, số câu hỏi, trạng thái dừng và thời gian | 1 | CSV + một bảng báo cáo, có tử/mẫu và model cụ thể |
| T4 | Đọc 3–5 ca lỗi hoặc mọi ca lỗi nếu ít hơn 3; lưu một ví dụ thành công | 1–1,5 | Phân loại thiếu ứng viên đúng / probe kém / hỏi khó hiểu / runtime / lọc sai |
| T5 | Sửa tối đa 1–2 lỗi P0 có ảnh hưởng trực tiếp, chạy test liên quan | 1 | Test hồi quy; nếu sửa phương pháp/dữ liệu thì chạy lại phép đo bị ảnh hưởng |

**Gate cuối ngày:** đủ kết quả để viết. Nếu LLM thật không thành công, dùng kết quả
synthetic đã kiểm chứng và demo offline, nói rõ giới hạn; không trình bày chúng như
độ chính xác trên HumanEval/MBPP hoặc người dùng thực. Không cố làm benchmark lớn.

### Thứ Sáu 30/10 — Hoàn thành báo cáo và slide (5–6 giờ)

| ID | Việc làm | Giờ | Sản phẩm / điều kiện hoàn thành |
|---|---|---:|---|
| F1 | Viết thuật toán và thiết kế, nêu cách chọn câu hỏi và điều kiện dừng | 1 | Pseudocode hoặc sơ đồ, ví dụ có partition Yes/No cụ thể |
| F2 | Viết phần thực nghiệm từ CSV; tách synthetic và LLM thật | 1,5 | Cấu hình, bộ bài, baseline, metric, kết quả, phân tích lỗi |
| F3 | Rà khảo sát 3–5 nguồn đã dùng và các tuyên bố trong phase 1 | 1 | Nguồn thực sự đọc; không giữ tỷ lệ không có bằng chứng |
| F4 | Hoàn thiện giới hạn và đóng góp từng thành viên theo GitHub | 0,5 | Phân biệt phần Đạt, Ty, Bảo và phần sửa tích hợp; không suy % từ commit |
| F5 | Làm slide 10–12 trang từ báo cáo | 1–1,5 | Bài toán → kiến trúc → demo → kết quả → giới hạn |

**Gate cuối ngày:** báo cáo có thể đọc liền mạch; không còn mục “sẽ thực hiện” ở
phần kết quả, không còn số liệu kỳ vọng lẫn với số đã đo.

### Thứ Bảy 31/10 — Đóng gói và diễn tập (4–5 giờ)

| ID | Việc làm | Giờ | Sản phẩm / điều kiện hoàn thành |
|---|---|---:|---|
| S1 | Chạy lần cuối theo README từ môi trường đã chốt | 0,5–1 | Test pass, demo khởi động, đường dẫn dữ liệu/kết quả đúng |
| S2 | Quay demo 3–5 phút: loại trùng, sắp xếp và một ca chưa phân biệt được | 1 | Video có đầu vào, câu hỏi, lọc, kết quả và giải thích giới hạn |
| S3 | Luyện trình bày, trả lời mục 8 dưới đây | 1 | Tự giải thích được code/method mà không dựa vào người khác |
| S4 | Xuất báo cáo PDF, slide; kiểm tra ảnh, font, bảng, link | 0,5–1 | Không lỗi hiển thị; số liệu khớp CSV |
| S5 | Đóng gói source + kết quả + môi trường + README; lưu commit nộp | 0,5–1 | Gói nộp không chứa khóa hoặc `.venv`; có manifest và hướng dẫn |

**Chủ nhật 01/11:** 2–3 giờ dự phòng, chỉ sửa lỗi nộp/hiển thị/khởi động. Giữ bản
đã chốt thứ Bảy làm phương án quay lại. Xác nhận giờ nộp trên kênh môn học sớm.

## 4. Lệnh chạy cho các mốc

```powershell
Set-Location 'D:\HK1_261\Đồ án tổng hợp ttnt'
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m streamlit run app.py
```

Demo không cần API và kiểm tra môi trường:

```powershell
.\.venv\Scripts\python.exe scripts/preflight.py --mode offline
.\.venv\Scripts\python.exe kaggle_run.py --offline-suite
```

Bộ synthetic 32 ca đã chạy trong lần tích hợp; chạy lại chỉ khi thay đổi ảnh hưởng kết quả:

```powershell
.\.venv\Scripts\python.exe run_experiments.py --mode offline --methods direct1,first_valid,balanced --require-complete --output-dir results/integration_review
```

Để chạy thật, cấu hình `.env` theo provider. Trong lệnh dưới, thay `MODEL_DA_KIEM_TRA`
bằng model mà tài khoản đã thử thành công; đổi provider nếu dùng OpenAI/OpenRouter.

```powershell
# Smoke 1 bài trước, tối đa 9 lần thử sinh ở tầng wrapper với K=3
.\.venv\Scripts\python.exe run_experiments.py --mode real --provider gemini --model MODEL_DA_KIEM_TRA --quick --max-tasks 1 --top-k 3 --max-questions 3 --methods direct1,first_valid,balanced --output-dir results/real_smoke
# Pilot: một bài mỗi nhóm, 8 bài, tối đa 72 lần thử ở tầng wrapper
.\.venv\Scripts\python.exe run_experiments.py --mode real --provider gemini --model MODEL_DA_KIEM_TRA --quick --top-k 3 --max-questions 3 --methods direct1,first_valid,balanced --require-complete --output-dir results/real_pilot
```

SDK có thể retry nội bộ; các con số 9/72 không phải bảo đảm về số request tính phí.
Kiểm tra log/provider usage sau smoke trước khi chạy pilot. Run lưu pool để các
phương pháp dùng chung; chạy lại cùng lệnh sẽ resume. Nếu đổi code/phương pháp
ngoài cấu hình đã băm, dùng output directory mới và ghi lại commit để tránh dùng
checkpoint cũ. Seed thứ hai: thêm `--seed 3102` và lưu run riêng.

## 5. Protocol và cách đọc kết quả

- **Ba cách chọn:** `direct1` là ứng viên đầu của pool; `first_valid` là ứng viên
  đầu qua kiểm tra cú pháp/tên hàm; `balanced` dùng hỏi–đáp và lọc cứng.
- **Cùng ngân sách chọn:** cả ba dùng chung pool, cùng test đánh giá. Không coi
  `direct1` trong runner là thí nghiệm chỉ tốn đúng một API call.
- **Oracle:** reference mô phỏng câu trả lời; thuật toán chọn không đọc đáp án test
  đánh giá. Nếu bổ sung Oracle Best-of-K, ghi là cận trên dùng nhãn chuẩn.
- **Tách dữ liệu:** runner loại mọi evaluation input trùng seed/mutation dùng để
  hỏi; số test còn lại khác nhau theo bài, được lưu trong log. Bài còn quá ít test
  cần bổ sung test mới nếu dùng làm kết luận cuối kỳ.
- **Metric chính:** số bài pass toàn bộ / tổng bài; kèm số câu hỏi trung bình,
  số ca không còn ứng viên/không tìm được câu hỏi và thời gian.
- **Giới hạn:** 32 ca là 8 họ mẫu, không độc lập; 8 bài LLM thật vẫn là bài synthetic.
  Gọi kết quả đúng tên, không suy rộng thành benchmark chuẩn hay đánh giá người dùng.
- **Không đạt ưu thế cũng báo cáo:** nếu không sinh được ứng viên đúng thì việc
  chọn câu hỏi không thể sửa được; đây là kết quả cần phân tích.

| Bảng cần có trong báo cáo | Cột tối thiểu |
|---|---|
| Cấu hình | Commit, Python, provider/model, K, số câu hỏi/probe, seed, loại dữ liệu |
| Kết quả | Phương pháp, số bài, bài pass, tỷ lệ, câu hỏi TB, thời gian |
| Lỗi | ID bài, hành vi mong muốn, mã được chọn, nguyên nhân, hướng xử lý |
| Đóng góp | Thành viên, nhánh/commit, sản phẩm có bằng chứng, phần đã tích hợp |

## 6. Dàn ý báo cáo và slide

Báo cáo: (1) bài toán và phạm vi Lite; (2) khảo sát 3–5 công trình; (3) kiến trúc và
thuật toán; (4) triển khai; (5) dữ liệu/protocol/metric; (6) kết quả và lỗi; (7) giới
hạn, kết luận, hướng tiếp; (8) đóng góp, tài liệu tham khảo, cách chạy.

Slide 10–12 trang: tên đề tài/nhóm; vấn đề; ví dụ mơ hồ; kiến trúc; cách chọn câu
hỏi; demo; cấu hình đánh giá; bảng kết quả; phân tích lỗi; giới hạn/kết luận; dự phòng.

Đề xuất PDF cũ còn XGBoost, 47 đặc trưng và React/FastAPI: ghi rõ đã điều chỉnh
phạm vi theo môn học. Tên file `baseline_cot.py` được giữ để tương thích, nhưng
baseline đang triển khai là Direct-1, chưa phải bằng chứng về CoT.

## 7. Checklist gói nộp

- [ ] Kiểm tra hạn/giờ nộp và mẫu báo cáo trên kênh môn học.
- [ ] Demo offline và video dự phòng chạy được; có bằng chứng API thật hoặc ghi rõ chưa có.
- [ ] Source sạch + commit/tag; requirements và phiên bản môi trường đã kiểm tra.
- [ ] Dataset/config/pool/kết quả cần tái lập, không có khóa API.
- [ ] CSV, manifest và completeness đi kèm; không chỉ chụp một bảng tỷ lệ.
- [ ] Báo cáo PDF và slide khớp cấu hình, số liệu, điều kiện dừng trong code.
- [ ] Có ví dụ thất bại và giới hạn, không dùng số kỳ vọng làm số đo.
- [ ] README có lệnh cài, test, demo và vị trí kết quả.

## 8. Các câu phải tự giải thích được

1. Vì sao cần nhiều ứng viên? Nếu không có ứng viên đúng thì sao?
2. Vì sao chia gần 50/50 hữu ích? Khi nào phải dừng dù còn nhiều ứng viên?
3. Câu hỏi ngữ nghĩa hiện hỗ trợ đến đâu; lúc nào trở về câu I/O?
4. Còn một ứng viên khác gì với mã đúng trên mọi đầu vào?
5. Đã ngăn trùng probe/test thế nào? Oracle có được dùng để chọn không?
6. Vì sao kết quả synthetic tốt không chứng minh chất lượng LLM/người dùng thực?
7. Phần nào của Đạt, Ty, Bảo; phần nào được sửa khi tích hợp?

## 9. Nếu chỉ còn 8–10 giờ

Giữ 1h demo/API smoke, 1h kiểm tra dữ liệu và lấy bảng đã có, 3h báo cáo, 1h slide,
1h video và 1–2h đóng gói/diễn tập. Hoãn seed thứ hai, mở rộng dataset và mẫu câu
hỏi mới. Nếu API chặn, nộp prototype offline và ghi giới hạn rõ ràng; không bịa
kết quả hoặc ghi “LLM thật” cho dữ liệu mock.
