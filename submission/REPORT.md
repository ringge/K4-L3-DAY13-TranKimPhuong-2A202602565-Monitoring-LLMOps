# Báo cáo cá nhân — K4-L3B Day 13 Monitoring & LLMOps

> Mỗi học viên hoàn thiện một file duy nhất này. Khi dẫn evidence, dùng đường dẫn tương đối, ví dụ `evidence/07-trace-waterfall.png`.

## 1. Thông tin học viên

- **Họ và tên:** Trần Kim Phương
- **MSSV:** 2A202602565
- **Lớp:** K4-L3B
- **Repository URL:** https://github.com/ringge/K4-L3-DAY13-TranKimPhuong-2A202602565-Monitoring-LLMOps
- **Commit SHA cuối:** 20becd3d64390c8b19ca525869ae4982f281e2f4
- **Challenge ID:** day13-k4-l3b-monitoring-llmops-v1
- **Tên project Langfuse cá nhân:** `day13-k4-l3b-2A202602565`

## 2. Evidence index

Điền đúng đường dẫn tới evidence thực tế. Có thể đổi tên hoặc dùng nhiều ảnh nếu cần.

| Evidence | Đường dẫn |
|---|---|
| Pytest cuối | `evidence/01-pytest.png` |
| Log validator | `evidence/02-log-validator.png` |
| Dashboard validator | `evidence/03-dashboard-validator.png` |
| Structured log | `evidence/04-structured-log.png` |
| PII redaction | `evidence/05-pii-redaction.png` |
| Trace list | `evidence/06-trace-list.png` |
| Trace waterfall | `evidence/07-trace-waterfall.png` |
| Trace metadata | `evidence/08-trace-metadata.png` |
| Prompt versions | `evidence/09-prompt-versions.png` |
| Prompt rollback | `evidence/10-prompt-rollback.png` |
| Dashboard runtime | `evidence/11-dashboard-overview.png` |
| Incident metric | `evidence/12-incident-metric.png` |
| Incident log | `evidence/13-incident-log.png` |
| Incident trace | `evidence/14-incident-trace.png` |

## 3. Kết quả kỹ thuật

| Nội dung | Baseline | Kết quả cuối | Nhận xét |
|---|---|---|---|
| `validate_logs.py` | 30/100 | 100/100 | |
| `validate_dashboard.py` | 6/6 | 6/6 | |
| `pytest` | 22 passed | 22 passed | |
| Số traces hợp lệ | 10 | 10 | Trong Langfuse. |
| Số PII leak | 0 | 0 | |
| Latency P95 / TTFT P95 | 1,370 ms / 55 ms | 536,7 ms / 55 ms | Tính từ 10 bản ghi `response_sent` khớp với 10 correlation ID của lần load test mới, dùng percentile nội suy trong `dashboard_metrics.py`. Log ghi latency từ 156 đến 844 ms; lần đo đầu là 844 ms và chín lần còn lại từ 156 đến 161 ms. P95 round-trip từ terminal là 587,6 ms (đo nội suy trên 10 kết quả). |
| Retrieval success rate | 100% (10/10) | 100% (10/10) | Cả 10 response có `tool_success=true`; load test trả HTTP 200 cho 10/10 request. Chỉ phản ánh lời gọi retriever hoàn tất. |

## 4. Logging và PII

- **Cách tạo/nhận và truyền correlation ID:** `CorrelationIdMiddleware` nhận `x-request-id` từ request; nếu header không có, middleware tạo ID dạng `req-` kèm 8 ký tự hex từ UUID. Middleware gắn ID vào structlog context và `request.state`, rồi trả lại trong response header `x-request-id`. Các log event kế thừa ID qua `merge_contextvars`; `app/agent.py` cũng truyền ID vào metadata của trace Langfuse để nối trace với log.
- **Các metadata được ghi vào structured log:** Mỗi dòng JSONL có timestamp UTC (`ts`), `level`, `service`, `event`, `correlation_id`, `env`, `model`, `session_id`, `feature` và `user_id_hash`. Log `request_received` có `message_preview`; log `response_sent` có `answer_preview`, latency, TTFT, token input/output, chi phí, quality score và trạng thái retriever. `user_id_hash` là 12 ký tự đầu của SHA-256 trên user ID.
- **Cách bảo đảm PII được scrub trước khi ghi:** `summarize_text` scrub nội dung trước khi cắt preview tối đa 80 ký tự. `scrub_text` thay email, số điện thoại Việt Nam, CCCD 12 chữ số và số thẻ thanh toán bằng nhãn `[REDACTED_...]`. Processor `scrub_event` chạy trước `JsonlFileProcessor`, scrub tên event và các giá trị chuỗi trong `payload` trước khi ghi `data/logs.jsonl`.
- **Cách kiểm chứng kết quả:** `tests/test_pii.py` kiểm tra các định dạng email, điện thoại, CCCD và thẻ thanh toán. Ảnh [PII redaction](evidence/05-pii-redaction.png) cho thấy preview đã che cả bốn loại dữ liệu. `scripts/validate_logs.py` quét log bằng các detector riêng; bằng chứng [log validator](evidence/02-log-validator.png) ghi nhận 20 log records, 10 correlation ID, 0 trường bắt buộc bị thiếu, 0 trường enrichment bị thiếu, 0 PII leak và điểm 100/100. Ảnh [structured log](evidence/04-structured-log.png) cho thấy ID giống nhau ở `request_received` và `response_sent`.

## 5. Tracing và prompt versioning

- **Cách xác nhận traces do chính tôi tạo trong project cá nhân:** Danh sách trace hiển thị project Langfuse cá nhân `day13-k4-l3b-2A202602565` và nhiều trace `lab-agent-run` do workload của repo tạo. Ảnh [trace list](evidence/06-trace-list.png) cho thấy project và danh sách trace.
- **Cấu trúc root/retrieval/generation observations:** `LabAgent.run` tạo root observation `lab-agent-run` với trace name `day13-agent-request`; root tắt capture input/output thô. Hai child observation là `retrieval` loại `retriever` và `generation` loại `generation`. Generation ghi model, preview đã scrub, usage token và cost. Ảnh [trace waterfall](evidence/07-trace-waterfall.png) cho thấy cây root/child.
- **Cách nối trace với log:** Middleware gắn `correlation_id` vào log context, rồi `app/agent.py` truyền cùng ID vào metadata trace. Ví dụ incident ở mục 7 dùng `req-7ce1b8f9` trong log và metadata trace `ba0cad6baafb3c9b87f899f81a256c0d`.
- **Prompt name:** `day13-chat`.
- **Version/label baseline:** Version `1`, có label `baseline` và `production` trước khi chuyển label. Trace baseline `54976328e4eb7db1b67dbf22f0971a57` ghi `prompt_version=1`, `prompt_label=baseline`.
- **Version/label candidate:** Version `2`, label `candidate`. Trace candidate `5b6983222d8c2ba0534bdd3c399f1a1d` ghi `prompt_version=2`, `prompt_label=candidate`.
- **Trace ID của mỗi version:** Baseline v1: `54976328e4eb7db1b67dbf22f0971a57`. Candidate v2: `5b6983222d8c2ba0534bdd3c399f1a1d`. Metadata của mỗi trace cũng ghi `prompt_name`, `prompt_version`, `prompt_label` và `prompt_source=langfuse`; xem [trace metadata](evidence/08-trace-metadata.png) và [prompt rollback](evidence/10-prompt-rollback.png).
- **Cách promote và rollback `production`:** Ứng dụng lấy prompt theo `LANGFUSE_PROMPT_NAME` và `LANGFUSE_PROMPT_LABEL`; mặc định là `day13-chat` và `production`. Để promote, chuyển label `production` từ v1 sang v2 trong Langfuse. Để rollback, chuyển label `production` về v1. Không cần sửa code; trace mới ghi lại version và label thực tế đã dùng. Ảnh [prompt versions](evidence/09-prompt-versions.png) và [prompt rollback](evidence/10-prompt-rollback.png) lưu các version, label và trace tương ứng.

## 6. Dashboard, SLO và alerts

- **Dashboard và sáu panel:** Dashboard Streamlit đọc `data/logs.jsonl`, mặc định xem 60 phút gần nhất và refresh mỗi 30 giây; có thể chuyển sang toàn bộ lịch sử. Sáu panel là latency P50/P95/P99 và TTFT P95, request traffic, error rate và retrieval success, cost, input/output tokens, và quality score trung bình. Contract đặt các ngưỡng chính: latency P95 ≤ 3.000 ms, error rate ≤ 2%, retrieval success ≥ 90%, cost ≤ 2,5 USD, tổng token ≤ 50.000 và quality ≥ 0,75. Validator báo hợp lệ 6/6 panel trong [dashboard validator](evidence/03-dashboard-validator.png). Ảnh [incident metric](evidence/12-incident-metric.png) ghi P95 2.672 ms, P50 2.667 ms, P99 2.673 ms và TTFT P95 55 ms.
- **SLO và lý do chọn:** SLO `fast_successful_requests` là 99,5% trong cửa sổ 28 ngày. Một request đạt SLI khi có `response_sent` với `latency_ms ≤ 3000`; mẫu số là các event `request_received`. Chọn ngưỡng 3.000 ms vì baseline P95 là 1.370 ms trên 10 response. Cỡ mẫu này nhỏ, nên đây là mục tiêu của lab, chưa phải cam kết production.
- **Cách tính error budget:** Error budget là `100% - 99,5% = 0,5%` số request trong cửa sổ 28 ngày. Với 10.000 request, ngân sách là `10.000 × 0,005 = 50` request không đạt. Request lỗi, không có response hoặc có latency trên 3.000 ms đều dùng ngân sách.
- **Ba alert và runbook tương ứng:** Các rule có owner `student-2A202602565`, duration 5 phút và đích Slack `#k4-l3b-alerts` trong [`config/alert_rules.yaml`](../config/alert_rules.yaml).
  - `HighLatencyP95`: P95 > 3.000 ms, mức `warning`; runbook [Alert 1](../docs/alerts.md#alert-1) kiểm tra latency/TTFT, lọc log theo `correlation_id`, mở trace và xử lý retrieval chậm hoặc rollback prompt nếu cần.
  - `HighRequestErrorRate`: tỷ lệ `request_failed` trên `request_received` > 2%, mức `critical`; runbook [Alert 2](../docs/alerts.md#alert-2) kiểm tra `error_type` và trace, tắt scenario `tool_fail` nếu đang chạy practice hoặc khôi phục cấu hình thành phần lỗi.
  - `LowRetrievalSuccess`: retrieval success < 90%, mức `warning`; runbook [Alert 3](../docs/alerts.md#alert-3) lọc log `tool_success=false`, kiểm tra span retrieval và khôi phục kết nối/cấu hình retriever nếu cần. Repo khai báo rule và runbook nhưng chưa tích hợp thành phần gửi thông báo Slack.

## 7. Điều tra challenge

- **Challenge ID:** `day13-k4-l3b-monitoring-llmops-v1`.
- **Khoảng thời gian điều tra:** 30/09/2026, 12:39:50–12:40:16 ICT (05:39:50–05:40:16 UTC), từ lúc log ghi `incident_enabled` đến response cuối của 5 request challenge.
- **Triệu chứng từ metrics:** Dữ liệu cho panel latency trong `data/logs.jsonl` cho P95 = 2.672,4 ms, P50 = 2.667 ms. Cả 5/5 request có `latency_ms` từ 2.662 đến 2.673 ms, vượt ngưỡng 2.000 ms của challenge. TTFT chỉ 52–55 ms, error rate 0% và retrieval success 100%. P95 vẫn dưới ngưỡng 3.000 ms của dashboard và alert hiện tại, nên chưa đủ điều kiện kích hoạt `HighLatencyP95`.
- **Log line và correlation ID liên quan:** `incident_enabled` lúc 05:39:50 UTC ghi `name=rag_slow`. Request `req-7ce1b8f9` có `request_received` lúc 05:40:03.437 UTC và `response_sent` lúc 05:40:06.109 UTC với `latency_ms=2670`, `ttft_ms=52`, `tool_name=retrieval`, `tool_success=true`. Hai dòng cùng `correlation_id=req-7ce1b8f9` trong `data/logs.jsonl`.
- **Trace ID và span gây ảnh hưởng:** Trace Langfuse `ba0cad6baafb3c9b87f899f81a256c0d` có metadata `correlation_id=req-7ce1b8f9`. Span `retrieval` (`bdf76609054ef41a`) kéo dài 2.509 ms, chiếm khoảng 94% root `lab-agent-run` (2.670 ms); span `generation` chỉ 158 ms.
- **Root cause:** Incident `rag_slow` được bật trước workload. Nhánh này gọi `time.sleep(2.5)` trong `retrieve()` tại [`app/mock_rag.py`](../app/mock_rag.py), khiến span retrieval chậm khoảng 2,5 giây dù trả kết quả thành công. `chat()` gọi agent đồng bộ trong async handler, nên 5 request gửi với concurrency 5 vẫn lần lượt đi qua đoạn chặn này.
- **Fix action:** Tắt incident bằng `python scripts/inject_incident.py --disable` để khôi phục retrieval; chạy lại challenge workload và kiểm tra P95 cùng thời lượng span `retrieval` giảm dưới 2.000 ms. Với retrieval thật, thay lời gọi chặn event loop bằng I/O bất đồng bộ hoặc chạy tác vụ đồng bộ trong thread pool.
- **Preventive measure:** Thêm cảnh báo P95 latency hoặc P95 span `retrieval` vượt 2.000 ms trong cửa sổ có đủ mẫu, vì alert hiện tại chỉ báo khi P95 > 3.000 ms liên tục 5 phút. Bổ sung kiểm thử tải đồng thời và runbook lọc log theo `correlation_id`, rồi so sánh các span trong trace trước khi xử lý.

## 8. Giải thích và tự đánh giá

- **Một quyết định kỹ thuật quan trọng và lý do:** Mình truyền cùng một `correlation_id` từ middleware vào structured log và metadata trace. Root trace không capture input/output thô; log và child observations chỉ lưu preview đã scrub. Cách này giúp điều tra request mà không cần ghi prompt và câu trả lời nguyên văn.
- **Một lỗi/blocker đã gặp:** Trong challenge, cả 5 request đều chậm hơn ngưỡng 2.000 ms của challenge, nhưng P95 là 2.672,4 ms nên chưa vượt ngưỡng 3.000 ms của rule `HighLatencyP95`. Vì vậy, điều kiện của rule chưa đạt dù độ trễ vượt tiêu chí challenge.
- **Cách tìm nguyên nhân và xử lý:** Mình dùng metrics để xác nhận độ trễ, lọc log theo `correlation_id=req-7ce1b8f9`, rồi mở trace `ba0cad6baafb3c9b87f899f81a256c0d`. Trace cho thấy span `retrieval` mất 2.509 ms; đọc `app/mock_rag.py` xác nhận scenario `rag_slow` gọi `time.sleep(2.5)`. Cách khắc phục đề xuất là tắt scenario bằng `python scripts/inject_incident.py --scenario rag_slow --disable`, chạy lại workload và kiểm tra P95 dưới 2.000 ms.
- **Cách hiểu luồng Metrics → Logs → Traces:** Metrics cho biết triệu chứng và phạm vi ảnh hưởng. Log giúp chọn đúng request bằng `correlation_id` và xem kết quả, lỗi, latency. Trace chia request thành các span để tìm bước gây chậm hoặc lỗi.
- **Vai trò của prompt version, token/cost, SLO hoặc rollback trong vận hành LLM:** Prompt version và label cho biết request đã dùng prompt nào, đồng thời cho phép chuyển `production` về version ổn định nếu candidate gây hồi quy. Token và cost cho thấy mức tiêu thụ tài nguyên theo request. SLO định nghĩa mức dịch vụ cần đạt; error budget lượng hóa số request có thể không đạt trước khi vượt mục tiêu.
- **Điều quan trọng nhất đã học:** Request có thể hoàn tất retrieval và trả câu trả lời nhưng vẫn chậm. Vì vậy, cần theo dõi latency cùng error rate, rồi dùng log và trace để tìm bước gây ảnh hưởng.
- **Hạn chế hoặc phần chưa hoàn thành, nếu có:** SLO được chọn từ baseline chỉ có 10 response nên phù hợp với lab, chưa đủ để đại diện tải production. Repo có alert rules và runbooks nhưng chưa gửi thông báo Slack. Evidence `11-dashboard-overview.png` chưa có trong `submission/evidence/`; các ô kết quả cuối ở mục 3 và commit SHA ở mục 1 cũng còn trống.

## 9. Checklist trước khi nộp

- [ x ] Kết quả và evidence thuộc commit SHA cuối.
- [ x ] Tất cả ảnh/output mở được bằng đường dẫn tương đối.
- [ x ] Incident evidence nối đúng metric → log → trace.
- [ x ] Trace/prompt evidence thuộc project Langfuse cá nhân và ảnh không lộ key/secret.
- [ x ] Repository chạy lại được theo README.
- [ x ] Không có secret, API key, PII thô hoặc evidence của người khác/lớp khác.
- [ x ] URL repo và commit SHA cuối đã được nộp trên LMS/Codelabs.
