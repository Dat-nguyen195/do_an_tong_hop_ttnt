# SEMSYNTH Lite — Interactive Program Synthesis via Semantic Clarification

SEMSYNTH Lite là hệ thống tổng hợp chương trình tương tác người dùng, giải quyết rào cản **Cognitive Friction Gap** bằng cách chủ động đặt các câu hỏi làm rõ ở mức ngữ nghĩa dưới dạng **Đúng/Sai (Yes/No)**.

## 🚀 Cấu trúc dự án

```
semsynth-lite/
├── docs/
│   └── phase1_report.md          # Báo cáo giai đoạn 1
├── config/
│   └── dataset_sample.json       # Tập dữ liệu 15 bài toán mẫu
├── src/
│   ├── __init__.py               # Package init
│   ├── llm_client.py             # Wrapper gọi LLM API
│   ├── baseline_cot.py           # Baseline CoT (0-interaction)
│   ├── candidate_manager.py      # Quản lý chương trình ứng viên
│   ├── question_generator.py     # Sinh câu hỏi Đúng/Sai
│   ├── code_executor.py          # Sandbox chạy mã an toàn
│   └── semsynth_controller.py    # Controller chính SEMSYNTH
├── tests/
│   ├── __init__.py               # Package init
│   └── test_baseline.py          # Test cho Baseline CoT
├── .env.example                  # Template biến môi trường
├── .gitignore                    # Git ignore rules
├── app.py                        # Giao diện Web Demo (Streamlit)
├── requirements.txt              # Thư viện Python
└── README.md                     # File này
```

### Mô tả thư mục

- `docs/` — Báo cáo các giai đoạn của đồ án (Phase 1, Phase 2...).
- `config/` — Tập dữ liệu benchmark mẫu (HumanEval/MBPP).
- `src/` — Mã nguồn cốt lõi (LLM Client, Baseline CoT, Candidate Manager, Question Generator).
- `tests/` — Kịch bản kiểm thử tự động với pytest.
- `app.py` — Giao diện Web Demo (Streamlit).

## 🛠️ Hướng dẫn cài đặt

### 1. Tạo môi trường ảo và cài đặt thư viện

```bash
python -m venv venv
source venv/bin/activate  # Trên Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Cấu hình file `.env`

```bash
cp .env.example .env
# Điền API Key vào file .env
```

### 3. Chạy thử Baseline CoT

```bash
# Chế độ dry-run (không cần API key)
python src/baseline_cot.py --dry-run

# Chế độ đầy đủ (cần API key)
python src/baseline_cot.py
```

### 4. Chạy test

```bash
pytest tests/ -v
```

### 5. Chạy Web Demo

```bash
streamlit run app.py
```

## 📊 Benchmark Datasets

Dự án sử dụng bài toán trích từ 2 bộ benchmark chuẩn:

| Benchmark | Mô tả | Nguồn |
|---|---|---|
| **HumanEval** | 164 bài Python (OpenAI) | [openai/human-eval](https://github.com/openai/human-eval) |
| **MBPP** | 974 bài Python cơ bản (Google) | [google-research-datasets/mbpp](https://github.com/google-research-datasets/mbpp) |

## 📝 License

Dự án phục vụ mục đích học thuật — Đồ án tổng hợp AI (HK1/2026–2027).
