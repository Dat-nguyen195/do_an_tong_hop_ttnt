# Mười câu ôn tập bảo vệ SEMSYNTH

Tài liệu hỗ trợ giải thích bản nộp hiện tại. Slides hiện hành gồm 12 trang tại `report/SEMSYNTH_Slides_CO3101.pdf`; video không thuộc gói nộp. Không dùng kết quả finite-suite hoặc số câu hỏi để suy ra độ đúng tổng quát hay giảm cognitive load.

1. **Bài toán và ba trụ cột của thiết kế gốc là gì?** Mô tả tự nhiên có thể mơ hồ. Thiết kế SEMSYNTH dùng semantic information gain/atomic questions, Bayesian belief revision cùng quản lý giả thuyết, và AGA/regeneration để làm rõ hoặc bổ sung pool.

2. **M(h,q) gốc khác mapping trong code thế nào?** Thiết kế gốc dùng 47 features và XGBoost dự đoán satisfaction. Code được đo chạy ứng viên trên probe và phân nhóm output; không có model 47-feature đã train trong prototype.

3. **Vì sao balanced entropy liên hệ với IG gốc?** Với prior đồng đều, mapping tất định và câu trả lời chính xác, xác suất Yes là p=|H_yes|/|H|. Thay vào entropy kỳ vọng sau hỏi cho IG=-p log2(p)-(1-p)log2(1-p). Giới hạn này áp dụng trên các partition có sẵn, không bảo đảm probe luôn phân biệt được mọi chương trình.

4. **Hard filtering liên hệ với Bayes thế nào?** Likelihood của ứng viên hợp câu trả lời bằng 1, không hợp bằng 0. Nhân prior rồi chuẩn hoá tương ứng giữ partition. Soft update 1-epsilon/epsilon là tùy chọn khác; chưa chứng minh full consistency recovery của thiết kế gốc.

5. **Đã triển khai những gì?** Adapters/mock, admission, execution/probe, binary entropy, hard filtering, dừng/log, UI và runner. 47-feature/XGBoost, atomic/diversity đầy đủ, AGA, regeneration và hierarchy chưa tích hợp; không gọi việc sinh code nhiều lần là AGA hai bước.

6. **Một ứng viên còn lại và pass test khác nhau thế nào?** Một ứng viên nghĩa là hội tụ trong pool. Pass nghĩa là đúng trên các test giữ lại. Có thể còn nhiều ứng viên mà chương trình được chọn vẫn pass; cũng có thể hội tụ vào chương trình sai trên input chưa kiểm tra. No distinguishing question chỉ nói các probe hiện tại không phân biệt được, không chứng minh equivalence toàn miền.

7. **100% trên synthetic chứng minh điều gì?** Balanced chọn mã pass tất cả test giữ lại trong 32 ca có kiểm soát, reference có trong bank, oracle noiseless. Không chứng minh 100% sinh code của LLM, độ đúng tổng quát, noise robustness, scale lớn hay lợi ích nhận thức. Bốn variant cùng họ liên quan nhau.

8. **Direct-1 khác CoT và oracle thế nào?** Direct-1 lấy ứng viên đầu của pool dùng chung, không phải một API call độc lập. First-valid lấy ứng viên đầu qua admission. Oracle Best-of-K dùng nhãn đánh giá để chọn, chỉ là cận trên. File tên baseline_cot.py không đồng nghĩa đã thực nghiệm CoT.

9. **LLM, reference và evidence được dùng ở đâu?** Model sinh code được ghi bằng identifier trong manifest; reference trả lời câu hỏi và tạo nhãn đánh giá, không được đưa vào prompt sinh. Probe/evaluation tách exact inputs. Final verification replay pool lưu, không gọi lại API và không xác thực độc lập request lịch sử. Model weight revision/token usage chưa lưu nên không cam kết sinh lại đúng pool.

10. **Nếu triển khai tiếp sẽ làm gì?** Thêm bài độc lập và protocol; feature extractor/M(h,q) có calibration; atomic/diversity; noisy consistency/recovery; AGA/regeneration; hierarchy/scale; cuối cùng user assessment. Mỗi bước cần dữ liệu, test và phép đo riêng trước khi nhận kết luận.

Số cần nhớ: offline 13/32, 13/32, 32/32; 47 câu, TB 1,4688; 29 single và 3 unresolved; 127 evaluation inputs. Gemini-labeled 7/8 → 8/8, 0,25 câu; Qwen-labeled 6/8 → 8/8, 0,50 câu. Hai pilot vẫn là các bài synthetic, mỗi pilot chỉ 8 ca/31 input giữ lại. Tăng tỷ lệ offline là 59,375 **điểm phần trăm**.
