# Chạy SEMSYNTH trên Kaggle

Kaggle là lựa chọn bổ sung khi cần môi trường cloud; chạy local theo README vẫn là đường chính để hoàn thành đồ án.

Chỉ giữ một notebook: `kaggle_quickstart.ipynb`. Nó dùng source project đầy đủ qua GitHub hoặc một ZIP, không cần patch ZIP hay marker.

1. Tạo Kaggle notebook, bật Internet; CPU đủ, không yêu cầu GPU.
2. Mở `kaggle_quickstart.ipynb`. Điền `REPO_URL` tới repository chứa bản source hiện tại; nếu chưa đồng bộ GitHub, upload ZIP source đầy đủ vào Kaggle Inputs.
3. Giữ `MODE="offline"` để thử 32 ca tổng hợp; `QUICK=True` chạy một bài mỗi họ. Các phương pháp chính là `direct1,first_valid,balanced`.
4. Nếu chạy thật, tạo Kaggle Secret theo provider: `GEMINI_API_KEY`, `OPENAI_API_KEY` hoặc `OPENROUTER_API_KEY`; cho notebook quyền dùng secret. Đặt `MODE="real"`, điền `MODEL` đã kiểm tra truy cập, dùng `QUICK=True, MAX_TASKS=1` để smoke trước.
5. Khi smoke thành công, dùng `QUICK=True, MAX_TASKS=None` để chạy 8 họ, cùng K=3/Q=3/seed 3101. Không coi đây là benchmark HumanEval/MBPP vì bộ bài vẫn là synthetic.
6. Download `SEMSYNTH_RESULTS.zip` trong `/kaggle/working/semsynth_results/<run_id>/`. Kiểm tra `completeness.json` và lưu pool/checkpoint/CSV/manifest trước khi kết thúc session.

ZIP source cần chứa `run_experiments.py` và `config/ambiguity_benchmark.json`. Không đưa `.venv`, cache, khóa hoặc backup dọn dẹp vào ZIP. Source ở GitHub phải có cùng thay đổi với local nếu dùng đường clone.

Resume chỉ phù hợp cùng source/data/config/model/methods. Session mới cần khôi phục output nếu muốn tiếp tục checkpoint. Không có fallback tự động từ LLM thật về mock khi API lỗi.

Soft belief, explanation và sharding còn trong code như phần mở rộng; chỉ thêm chúng vào thực nghiệm sau khi đã xong cấu hình chính. `scripts/merge_shards.py` giữ lại cho nhu cầu này.
