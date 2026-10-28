# Báo cáo LaTeX SEMSYNTH

Báo cáo chính là `SEMSYNTH_Report_CO3101.pdf`, được biên dịch từ `main.tex` và các file `sections/`, `tables/`, `references.bib`. Định dạng IEEEtran hai cột theo mẫu được cung cấp; nội dung tiếng Anh, tác giả/GVHD có dấu tiếng Việt. Báo cáo hiện có 8 trang. Không tự coi mẫu 6 trang hoặc thông tin 6–10 trang trong tài liệu cũ là xác nhận quy định chính thức của môn.

Bộ trình chiếu hiện hành là `SEMSYNTH_Slides_CO3101.pdf` (12 trang), source chỉnh sửa tại `slides/slides.tex`. Slides giữ cấu trúc Beamer 16:9, dùng cùng thiết kế và phạm vi kết luận với báo cáo. Video không thuộc gói bàn giao.

## Nội dung và nguồn

Giữ nguyên bài toán và thiết kế SEMSYNTH: 47 features, M(h,q), IG, atomic/diversity, Bayesian revision, tiered management, AGA và regeneration. Phần Implementation Scope phân biệt các module chưa tích hợp với trường hợp giới hạn đã code. Phần kết quả chỉ có số đo của đồ án, không mang số 250 bài/SOTA của bản nghiên cứu sang.

Bản `.tex` tham chiếu nguyên byte tại `reference/paper_icse2027.tex`; `reference/source.json` ghi hash/đường dẫn gốc. Nó là bản thảo do người dùng cung cấp, không được gán là bài đã công bố ICSE. Bibliography hoạt động đã đối chiếu nguồn primary; xem `../docs/evidence/final/reference_audit.json`.

## Source và bảng

Main include Introduction, Method, Experimental Setup, Results, Discussion/Limitations, Conclusion và Acknowledgment/Contributions. Tên, email chưa có bằng chứng và tuyên bố chưa đo đã được rà lại. Các bảng được sinh bằng:

```bash
.venv/bin/python scripts/build_report_tables.py
```

Chạy lệnh trên từ root. Script dùng các run cố định ghi trong `../docs/evidence/final/report_runs.json`; không gọi API và không sửa checkpoint. Catalog pilot đã được audit nguồn và 46 test cục bộ, không phải benchmark chính.

## Build

Từ root:

```bash
latexmk -cd -pdf -interaction=nonstopmode -halt-on-error -outdir=build report/main.tex
```

Hoặc trong thư mục `report/`:

```bash
latexmk -pdf -interaction=nonstopmode -halt-on-error -outdir=build main.tex
```

Cần TeX Live với IEEEtran, vntex/T5, amsmath/amsthm, algorithm/algpseudocode, tabularx, microtype, balance và BibTeX. PDF build ở `build/main.pdf`; bản bàn giao được chép thành `SEMSYNTH_Report_CO3101.pdf`. Các chỉnh sửa LaTeX cần được build và mở kiểm tra từng trang trước khi cập nhật bản bàn giao.

## Giới hạn số liệu

Offline: 13/32, 13/32, 32/32; Balanced trung bình 1,4688 câu hỏi. Hai pilot lưu đủ 24 task-method outcomes/run, Balanced 8/8 nhưng còn 6 và 5 phiên unresolved. Tất cả là finite-suite agreement trên synthetic tasks, noiseless reference oracle. Original API generation không được gọi lại khi kiểm tra; pool lưu được replay và đối chiếu hash/metric. Không khẳng định đúng mọi input, SOTA, significant gain, noise recovery hoặc cognitive-load reduction.

## Slides

Từ root:

```bash
.venv/bin/python scripts/build_slide_tables.py
latexmk -cd -pdf -interaction=nonstopmode -halt-on-error -outdir=build report/slides/slides.tex
```

Cần thêm Beamer. Bảng được sinh từ cùng checkpoint cố định của báo cáo, không gọi API. Kiểm tra PDF `slides/build/slides.pdf` trước khi chép thành `SEMSYNTH_Slides_CO3101.pdf`. Các file kế hoạch, review và bản nháp cũ đã được dọn; phạm vi triển khai nằm trong báo cáo, slides và README. Log build/test/replay trong `../docs/evidence/final/`; gói nộp và manifest hash ở `../dist/`.
