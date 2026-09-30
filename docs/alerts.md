# Runbooks cho cảnh báo

[`config/alert_rules.yaml`](../config/alert_rules.yaml) khai báo ba alert và đích Slack `#k4-l3b-alerts`. Repo lưu policy và hướng dẫn xử lý, nhưng chưa có thành phần gửi thông báo tới Slack. Hãy cấu hình channel trong hệ thống alerting đang dùng.

Mỗi runbook dùng cùng thứ tự kiểm tra: xác nhận triệu chứng trên dashboard, tìm request trong `data/logs.jsonl` bằng `correlation_id`, rồi mở trace tương ứng trên Langfuse.

## Alert 1

- **Tên:** `HighLatencyP95`
- **Điều kiện:** `p95(latency_ms) > 3000` trong `5m`.
- **Severity:** `warning`.
- **Owner:** `student-2A202602565`.
- **Kênh Slack:** `#k4-l3b-alerts`.
- **Ảnh hưởng:** Người dùng phải chờ lâu hơn trước khi nhận câu trả lời.

### Kiểm tra

1. Mở panel Latency. Xác nhận P95, P99 và TTFT trong cùng khoảng thời gian.
2. Lọc `data/logs.jsonl` theo `event == "response_sent"` và `latency_ms > 3000`. Ghi lại một `correlation_id`.
3. Mở trace có cùng `correlation_id`. So sánh thời lượng của `retrieval` và `generation`, rồi kiểm tra `prompt_version`.

### Giảm ảnh hưởng

- Nếu `rag_slow` đang bật trong practice, tắt scenario bằng `python scripts/inject_incident.py --scenario rag_slow --disable`.
- Nếu trace cho thấy prompt version mới làm tăng latency, chuyển label `production` về version gần nhất có kết quả tốt.
- Chạy lại workload practice và xác nhận P95 giảm dưới 3,000 ms.

## Alert 2

- **Tên:** `HighRequestErrorRate`
- **Điều kiện:** Tỷ lệ `request_failed` trên `request_received` vượt `2%` trong `5m`.
- **Severity:** `critical`.
- **Owner:** `student-2A202602565`.
- **Kênh Slack:** `#k4-l3b-alerts`.
- **Ảnh hưởng:** Một số request không trả được câu trả lời và API trả lỗi `500`.

### Kiểm tra

1. Mở panel Errors. Xác nhận error rate và loại lỗi tăng trong khoảng thời gian nào.
2. Lọc `data/logs.jsonl` theo `event == "request_failed"` trong khoảng đó. Ghi lại `error_type` và `correlation_id`.
3. Mở trace có cùng `correlation_id`. Kiểm tra observation nào có trạng thái lỗi.

### Giảm ảnh hưởng

- Nếu `tool_fail` đang bật trong practice, tắt scenario bằng `python scripts/inject_incident.py --scenario tool_fail --disable`.
- Nếu lỗi vẫn còn, kiểm tra quyền truy cập và trạng thái của thành phần được nêu trong trace. Khôi phục cấu hình gần nhất đã hoạt động.
- Gửi một request mới và xác nhận error rate xuống dưới `2%`.

## Alert 3

- **Tên:** `LowRetrievalSuccess`
- **Điều kiện:** Tỷ lệ `tool_success == true` trên các log có `tool_success` thấp hơn `90%` trong `5m`.
- **Severity:** `warning`.
- **Owner:** `student-2A202602565`.
- **Kênh Slack:** `#k4-l3b-alerts`.
- **Ảnh hưởng:** Request có thể lỗi khi retriever không hoàn tất, nên ứng dụng không trả được câu trả lời.

`tool_success` đo việc lời gọi retriever hoàn tất. Nó không đo độ liên quan của tài liệu trả về.

### Kiểm tra

1. Mở panel Errors. Xác nhận retrieval success rate dưới `90%` trong cùng khoảng thời gian.
2. Lọc `data/logs.jsonl` theo `tool_name == "retrieval"` và `tool_success == false`. Ghi lại `error_type` và `correlation_id`.
3. Mở trace có cùng `correlation_id`. Kiểm tra trạng thái và thời lượng của observation `retrieval`.

### Giảm ảnh hưởng

- Nếu `tool_fail` đang bật trong practice, tắt scenario bằng `python scripts/inject_incident.py --scenario tool_fail --disable`.
- Nếu không phải practice, kiểm tra kết nối và cấu hình của nguồn retrieval. Khôi phục quyền truy cập hoặc cấu hình trước đó nếu chúng vừa thay đổi.
- Gửi request mới và xác nhận retrieval success rate trở lại ít nhất `90%`.
