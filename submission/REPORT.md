# Báo cáo cá nhân — K4-L3B Day 13 Monitoring & LLMOps

> Mỗi học viên hoàn thiện một file duy nhất này. Khi dẫn evidence, dùng đường dẫn tương đối, ví dụ `evidence/07-trace-waterfall.png`.

## 1. Thông tin học viên

- **Họ và tên:** Trần Kim Phương
- **MSSV:** 2A202602565
- **Lớp:** K4-L3B
- **Repository URL:** https://github.com/ringge/K4-L3-DAY13-TranKimPhuong-2A202602565-Monitoring-LLMOps
- **Commit SHA cuối:**
- **Challenge ID:**
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
| `validate_logs.py` | 30/100 | | |
| `validate_dashboard.py` | 6/6 | | |
| `pytest` | 22 passed | | |
| Số traces hợp lệ | 10 | | Trong Langfuse. |
| Số PII leak | 0 | | |
| Latency P95 / TTFT P95 | 1,370 ms / 55 ms | | Tính từ 10 bản ghi `response_sent` trong `data/logs.jsonl`, theo cách tính percentile của ứng dụng. |
| Retrieval success rate | 100% (10/10) | | Cả 10 bản ghi `response_sent` đều có `tool_success=true`; chỉ phản ánh lời gọi retriever hoàn tất. |

## 4. Logging và PII

- **Cách tạo/nhận và truyền correlation ID:**
- **Các metadata được ghi vào structured log:**
- **Cách bảo đảm PII được scrub trước khi ghi:**
- **Cách kiểm chứng kết quả:**

## 5. Tracing và prompt versioning

- **Cách xác nhận traces do chính tôi tạo trong project cá nhân:**
- **Cấu trúc root/retrieval/generation observations:**
- **Cách nối trace với log:**
- **Prompt name:**
- **Version/label baseline:**
- **Version/label candidate:**
- **Trace ID của mỗi version:**
- **Cách promote và rollback `production`:**

## 6. Dashboard, SLO và alerts

- **Dashboard và sáu panel:**
- **SLO và lý do chọn:**
- **Cách tính error budget:**
- **Ba alert và runbook tương ứng:**

> Ví dụ cách viết error budget: "SLO 99.5% trong 28 ngày nghĩa là error budget 0.5%. Nếu workload có 10,000 request thì tối đa 50 request được phép lỗi hoặc chậm hơn ngưỡng SLO."

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

- **Một quyết định kỹ thuật quan trọng và lý do:**
- **Một lỗi/blocker đã gặp:**
- **Cách tìm nguyên nhân và xử lý:**
- **Cách hiểu luồng Metrics → Logs → Traces:**
- **Vai trò của prompt version, token/cost, SLO hoặc rollback trong vận hành LLM:**
- **Điều quan trọng nhất đã học:**
- **Hạn chế hoặc phần chưa hoàn thành, nếu có:**

## 9. Checklist trước khi nộp

- [ ] Kết quả và evidence thuộc commit SHA cuối.
- [ ] Tất cả ảnh/output mở được bằng đường dẫn tương đối.
- [ ] Incident evidence nối đúng metric → log → trace.
- [ ] Trace/prompt evidence thuộc project Langfuse cá nhân và ảnh không lộ key/secret.
- [ ] Repository chạy lại được theo README.
- [ ] Không có secret, API key, PII thô hoặc evidence của người khác/lớp khác.
- [ ] URL repo và commit SHA cuối đã được nộp trên LMS/Codelabs.
