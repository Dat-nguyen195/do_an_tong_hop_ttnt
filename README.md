# SEMSYNTH — đồ án tổng hợp trí tuệ nhân tạo

Dự án triển khai một phần của thiết kế SEMSYNTH do nhóm cung cấp. Báo cáo giữ ý tưởng và hệ thuật toán gốc, đối chiếu rõ phần đã tích hợp, và chỉ dùng số liệu của prototype. Bàn giao gồm **source, báo cáo LaTeX/PDF, slides LaTeX/PDF và bằng chứng tái lập**. Video không thuộc gói nộp.

## Tài liệu và gói nộp

- [Nguồn và cách build LaTeX](report/README.md).
- [Báo cáo PDF](report/SEMSYNTH_Report_CO3101.pdf).
- [Slides PDF (12 trang)](report/SEMSYNTH_Slides_CO3101.pdf) và [source LaTeX](report/slides/slides.tex).
- [Ôn tập 10 câu bảo vệ](docs/ON_TAP_BAO_VE_10_CAU_HOI.md).
- [Catalog dữ liệu pilot](docs/dataset_catalog.csv).

`dist/` có `semsynth_source.zip`, `semsynth_evidence.zip`, `SEMSYNTH_Report_CO3101.pdf`, `SEMSYNTH_Slides_CO3101.pdf` và `DELIVERABLES_PROVENANCE.json`. Mỗi ZIP có `MANIFEST.json` kiểm tra SHA-256 từng file. Gói có source chỉnh sửa slides; không chứa `.env`, virtualenv, cache hoặc video.

## Cài đặt và kiểm tra

Môi trường kiểm tra là Linux, Python 3.12.3. Tạo môi trường mới và dùng lockfile để tái lập đúng phiên bản:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.lock.txt
.venv/bin/python -m pytest -q
.venv/bin/python scripts/preflight.py --mode offline
.venv/bin/python kaggle_run.py --offline-suite
.venv/bin/python scripts/verify_evidence.py
```

Windows: thay `.venv/bin/python` bằng `.venv\Scripts\python.exe`. `requirements.txt` ghi phụ thuộc mức ứng dụng; `requirements.lock.txt` khóa cả phụ thuộc gián tiếp đã kiểm tra. Không dùng venv tạo trên hệ điều hành khác.

## Demo Streamlit

```bash
.venv/bin/python -m streamlit run app.py
```

Chọn Offline demo trước; không cần API key. Ba ví dụ:

| Task description | Function name | Parameters |
|---|---|---|
| Remove duplicate elements from a list. | remove_duplicates | xs |
| Sort the numbers in a list. | sort_numbers | xs |
| Return the common elements of two lists. | common_elements | xs, ys |

Probe mặc định suy kiểu từ tên tham số; dùng `xs, ys` thay vì `a, b` cho demo danh sách. Có thể còn nhiều ứng viên không phân biệt được trên probe, khi đó UI báo tentative. Một ứng viên còn lại cũng chưa chứng minh đúng mọi input.

Muốn tạo code bằng LLM thật, tạo `.env` theo `.env.example` và chọn provider/model thực sự truy cập được. Model tag trong code hoặc artifact lịch sử không đảm bảo khả năng truy cập hiện tại. OpenAI-compatible endpoint được cấu hình bằng `OPENAI_BASE_URL` hoặc `--base-url`; không đưa khóa vào source, notebook hoặc gói nộp.

## Thực nghiệm và dữ liệu

`config/ambiguity_benchmark.json` là bộ 32 ca tổng hợp/8 họ dùng trong runner. `config/dataset_sample.json` là 15 bài pilot dùng bởi baseline và audit, có schema khác; không đưa trực tiếp vào runner tương tác. Pilot có 13 contract đối chiếu nguồn và 2 ca local/adapted; không tuyên bố đây là benchmark HumanEval/MBPP chuẩn.

```bash
.venv/bin/python run_experiments.py --mode offline --methods direct1,first_valid,balanced --top-k 3 --max-questions 3 --max-probes 8 --seed 3101 --require-complete --output-dir results/offline_new
```

Offline đã lưu: Direct-1 13/32, First-valid 13/32, Balanced 32/32; Balanced trung bình 1,4688 câu hỏi. Các phương pháp dùng chung pool; evaluation inputs trùng probe đã được loại. Đây là chọn từ bank có đáp án tham chiếu với noiseless oracle, không phải 100% chất lượng sinh code LLM.

Hai pilot lưu dưới `results/real_pilot_gemini/` và `results/real_pilot_qwen/`: mỗi run 8 bài/24 checkpoint. `scripts/verify_evidence.py` replay toàn bộ 150 outcomes của run offline, hai pilot và hai smoke; không gọi lại API. Replay xác nhận selection/evaluation của pool lưu, không xác thực độc lập dịch vụ/model đã sinh ra chúng hoặc đo generation latency/tokens.

## Báo cáo và đóng gói

```bash
.venv/bin/python scripts/build_report_tables.py
latexmk -cd -pdf -interaction=nonstopmode -halt-on-error -outdir=build report/main.tex
.venv/bin/python scripts/build_slide_tables.py
latexmk -cd -pdf -interaction=nonstopmode -halt-on-error -outdir=build report/slides/slides.tex
```

Mở kiểm tra từng trang PDF, sau đó chép `report/build/main.pdf` thành `report/SEMSYNTH_Report_CO3101.pdf` và `report/slides/build/slides.pdf` thành `report/SEMSYNTH_Slides_CO3101.pdf`. Sau đó:

```bash
.venv/bin/python scripts/package_deliverables.py
```

Trình đóng gói tạo virtualenv độc lập, cài lockfile, kiểm tra test bằng JUnit, preflight, demo, offline rerun, evidence replay và build báo cáo/slides LaTeX từ source giải nén. Kết quả ở `docs/evidence/final/FINAL_VERIFICATION.json`; số test đọc từ công cụ, không hard-code.

Chạy lại audit nguồn pilot cần mạng nhưng không cần API LLM:

```bash
.venv/bin/python scripts/audit_dataset_sources.py
```

Kaggle và nhiều shard là phần mở rộng tùy chọn, chưa thuộc nghiệm thu bản nộp này. Giữ `scripts/merge_shards.py` và [notebook duy nhất](notebooks/KAGGLE_QUICKSTART.md) khi cần dùng.

## Phạm vi triển khai

`src/llm_client.py` cung cấp adapters/mock; `candidate_manager.py` admission/lọc; `code_executor.py` thực thi tiến trình riêng; `question_generator.py` probe/entropy; `semsynth_controller.py` điều phối; `app.py` giao diện; `run_experiments.py` runner. `baseline_cot.py` hiện là Direct-1/Oracle Best-of-K, không phải chứng cứ đã chạy CoT.

Cấu hình đo dùng hard filtering. Soft belief/noise/explanation có tùy chọn hoặc unit test nhưng chưa được đánh giá đầy đủ. XGBoost 47 features, atomic/diversity, AGA/regeneration và hierarchy vẫn thuộc thiết kế gốc/hướng phát triển. Executor phục vụ demo cục bộ, chưa là sandbox chạy code đối kháng cho dịch vụ công cộng.
