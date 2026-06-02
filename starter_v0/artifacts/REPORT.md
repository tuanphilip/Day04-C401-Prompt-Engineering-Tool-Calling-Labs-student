# Day 04 Lab v2 Report - Research Agent

> File này gồm 2 phần:
> - **PHẦN A - Giới thiệu agent**: mô tả ngắn gọn agent làm được gì, có tool nào, và câu hỏi mẫu để team khác thử.
> - **PHẦN B - Chi tiết / Bằng chứng**: bảng version, lỗi, eval, live chat và reflection dựa trên log thật trong `runs/`, `analysis/`, `transcripts/`.

## Team

- Team: Research Agent Team
- Members:
  - Nguyễn Danh Thành - 2A202600581
  - Vũ Tuấn Phương - 2A202600772
  - Vũ Ngọc Vinh - 2A202600864
- Provider/model: OpenRouter / `openai/gpt-4o-mini`

---

# PHẦN A - Giới thiệu agent

## A1. Agent này làm được gì

Research agent giúp người dùng tìm tin trên web, tìm bài đăng trên X/Twitter, đọc URL, tìm paper, tra cứu policy nội bộ, kiểm tra chất lượng citation/source và tạo bản tóm tắt/digest. Agent được tối ưu để chọn đúng tool, truyền đúng tham số, hỏi lại khi thiếu thông tin, và chỉ thực hiện hành động gửi Telegram sau khi có xác nhận rõ ràng.

**Link dùng thử (deploy):**

> URL local đã làm UI: `http://127.0.0.1:8501`
>
> Public URL: chưa ghi nhận link Cloudflare/Vercel cố định trong artifact. Có thể chạy `start_streamlit_ui.ps1` và `start_cloudflare_tunnel.ps1` để tạo link `https://*.trycloudflare.com` khi demo.

## A2. Tool agent có

| Tên tool | Làm được gì | Tool mới nhóm thêm? |
|---|---|---|
| `clarify` | Hỏi lại người dùng khi thiếu handle, URL, lựa chọn, hoặc cần xác nhận gửi/đăng. | Không |
| `timeline` | Lấy bài đăng gần đây của một tài khoản cụ thể trên X/Twitter, ví dụ `sama`, `elonmusk`, `karpathy`. | Không |
| `social_search` | Tìm bài đăng trên X/Twitter theo từ khóa/chủ đề; hỗ trợ `Latest` và `Top`. | Không |
| `lookup` | Tìm kiếm web công khai, tin mới, hoặc thông tin hiện tại; có `topic=general/news` và `timeframe`. | Không |
| `fetch` | Đọc và trích nội dung từ URL cụ thể mà người dùng cung cấp. | Không |
| `format` | Định dạng các item đã thu thập thành markdown digest, bullets, thread, hoặc daily briefing. | Không |
| `send` | Gửi text lên Telegram channel sau khi người dùng xác nhận nội dung. | Không, bonus action tool |
| `policy` | Tìm trong các file company policy nội bộ về citation, privacy, publish, tool usage, AI research. | Không, bonus/extension |
| `papers` | Tìm paper/preprint trên arXiv theo chủ đề nghiên cứu. | Không, bonus/extension |
| `paper_text` | Tải PDF arXiv và trích text để đọc/tóm tắt paper. | Không, bonus/extension |
| `source_audit` | Kiểm tra bản tin/digest có đủ URL, source domain và citation để publish hay chưa. | Có |

## A3. Câu hỏi mẫu để thử

1. Tin AI hôm nay có gì nổi bật?
2. Tóm tắt bài báo này: https://vietnamnet.vn/bi-thu-ha-noi-thanh-pho-tap-trung-nguon-luc-de-nguoi-dan-de-tiep-can-nha-o-2521750.html
3. Tìm 3 bài viết mới nhất của Elon Musk trên X.
4. Kiểm tra bản tin này đã đủ citation/source để publish chưa: OpenAI ra model mới. Anthropic cập nhật Claude. Chưa có link nguồn.
5. Tìm 5 paper mới về RAG evaluation trên arXiv.

---

# PHẦN B - Chi tiết / Bằng chứng

## B1. Version Evidence

Dữ liệu lấy từ `artifacts/version_log.csv`, `analysis/run-analysis.csv`, và `runs/*.json`.

| Version | Changed Artifact | Hypothesis | Metric Before | Metric After | Run File |
|---|---|---|---:|---:|---|
| v0 | baseline | Baseline sẽ để lộ các lỗi routing, thiếu clarify, và action boundary chưa chặt. | N/A | 0.70 | `runs/v0_B_base_openrouter_20260602T142350788386.json` |
| v1 | `system_prompt.md` | Nếu prompt cấm đoán thông tin thiếu và yêu cầu clarify, accuracy sẽ tăng. | 0.70 | 0.90 | `runs/v1_B_base_openrouter_20260602T142522428245.json` |
| v2 | `tools.yaml` | Nếu tool declarations nói rõ boundary và argument convention, lỗi wrong-tool/URL routing sẽ giảm. | 0.90 | 0.95 | `runs/v2_B_base_openrouter_20260602T142656224351.json` |
| v3 | `system_prompt.md` + `tools.yaml` | Nếu missing-info rule cho timeline rõ hơn và đăng ký `source_audit`, base và group eval sẽ đạt full accuracy. | 0.95 | 1.00 | `runs/v3_B_base_openrouter_20260602T142827784188.json` |

Kết quả tổng hợp:

| Suite | Version | Passed / Total | Case Accuracy | Routing Accuracy | Argument Accuracy | Multiturn Accuracy |
|---|---|---:|---:|---:|---:|---:|
| base | v0 | 14 / 20 | 0.70 | 0.80 | 0.70 | 1.00 |
| base | v1 | 18 / 20 | 0.90 | 0.90 | 0.90 | 1.00 |
| base | v2 | 19 / 20 | 0.95 | 0.95 | 0.95 | 1.00 |
| base | v3 | 20 / 20 | 1.00 | 1.00 | 1.00 | 1.00 |
| group | v3 | 10 / 10 | 1.00 | 1.00 | 1.00 | 1.00 |

## B2. Failure Analysis

Use actual failures from `results[*].result.failures`.

| Case ID | Failure Type | Actual Tool Calls | What Failed | Fix |
|---|---|---|---|---|
| `R03_web_news_routing` in v0 | wrong arg value | `lookup(query="AI news", topic="news", timeframe="day")` | Agent thêm từ "news" vào query, trong khi expected query là `AI`. | Thêm convention: news request dùng `topic=news`, giữ query gọn theo chủ đề chính. |
| `R08_out_of_scope` in v0 | out of scope | `send` | Agent gọi action tool cho request ngoài phạm vi/chưa cần tool. | Prompt nói rõ out-of-scope thì trả lời ngắn, không gọi tool. |
| `R10_missing_handle` in v0 | missing info | `timeline` | User muốn lấy tweet nhưng chưa nói account; agent đoán và gọi timeline. | Thêm rule: thiếu account cho timeline thì `clarify(response_type=text)`. |
| `R11_missing_url` in v0 | missing info | `fetch` | User nói "bài này/link này" nhưng không có URL; agent vẫn gọi fetch. | Thêm rule: thiếu URL thì hỏi lại, không tự chế URL. |
| `R12_confirm_before_send` in v0 | wrong boundary | `send` | Agent gửi Telegram trước khi có xác nhận rõ ràng. | Thêm publish boundary: send/post/publish phải `clarify(response_type=yes_no)` trước. |
| `R13_parallel_web_and_tweets` in v0 | wrong arg value | `lookup` + `social_search` | Routing đúng nhiều tool nhưng query/topic bị sai: `AI news` và thiếu `topic=news`. | Bổ sung rule cho parallel requests: mỗi tool giữ đúng boundary và args riêng. |
| `R04_read_url_routing` in v1 | wrong tool | `clarify` | User đã đưa URL nhưng agent hỏi lại thay vì fetch. | Sửa mô tả `fetch`: có URL thì dùng `fetch`, nhiều URL thì gọi nhiều lần. |
| `R10_missing_handle` in v1/v2 | missing info | `social_search` | Request timeline thiếu account bị route sang topic search. | v3 bổ sung rule cụ thể: "tweets/posts from an account but no account -> clarify". |
| `G10_multiturn_confirm_send` in group run đầu | wrong arg value | `send` | Lần chạy đầu sai dấu chấm trong `text`: expected `AI briefing da san sang.`, got `AI briefing da san sang`. | Điều chỉnh/kiểm tra lại action boundary và nội dung gửi; group run sau đạt 10/10. |

## B3. Team Eval Cases

List 10 cases added to `data/eval_group.json` (5 single turn + 5 multi turn).

| Case ID | What It Tests | Expected Tool/Behavior | Result |
|---|---|---|---|
| `G01_missing_account_for_timeline` | Timeline request thiếu account phải hỏi lại, không đoán. | `clarify(response_type=text)` | Pass |
| `G02_missing_url_for_article` | Tóm tắt bài viết nhưng chưa có URL phải hỏi lại URL. | `clarify(response_type=text)` | Pass |
| `G03_two_urls_parallel_fetch` | Hai URL rõ ràng phải tạo hai lần fetch, không web search. | `fetch` + `fetch` | Pass |
| `G04_top_social_search` | "Top/phổ biến" trên social phải dùng `search_type=Top`. | `social_search(query="AI agents", search_type="Top")` | Pass |
| `G05_source_audit_before_publish` | Kiểm tra citation/source phải route đến tool mới của nhóm. | `source_audit` | Pass |
| `G06_multiturn_fill_account_keep_limit` | Multi-turn giữ limit 5 và điền account Sam Altman. | `timeline(screenname="sama", limit=5)` | Pass |
| `G07_multiturn_correct_account` | Turn sau sửa account phải override account cũ. | `timeline(screenname="karpathy", limit=4)` | Pass |
| `G08_multiturn_correct_limit` | Turn sau sửa limit từ 10 sang 3 phải lấy limit mới. | `timeline(screenname="elonmusk", limit=3)` | Pass |
| `G09_multiturn_switch_social_to_web` | Turn sau đổi Twitter sang web news, giữ chủ đề OpenAI. | `lookup(query="OpenAI", topic="news", timeframe="week")` | Pass |
| `G10_multiturn_confirm_send` | Sau xác nhận rõ ràng mới được gọi send. | `send(confirmed=true)` | Pass |

Evidence run: `runs/v3_B_group_openrouter_20260602T142921831209.json`, passed 10/10.

## B4. Live Chat Evidence

Use `transcripts/*.transcript.json`.

| Turn | User Request | Tool Calls | Version Evidence | Outcome |
|---|---|---|---|---|
| CLI transcript turn 1 | "Tin AI hom nay co gi noi bat?" | `lookup(query="AI", topic="news", timeframe="day")` | `v3+p575c57ef8434+t67c6e3325411` | Trả về 5 tin AI trong ngày kèm URL/source. |
| CLI transcript turn 2 | "Tom tat 5 tweet moi nhat giup minh" | `social_search(query="AI", search_type="Latest", limit=5)` | `v3+p575c57ef8434+t67c6e3325411` | Routing đến social search đúng, nhưng API Twitter/RapidAPI trả 403 nên agent báo lỗi truy cập. |
| CLI transcript turn 3 | "Kiem tra ban tin nay da du citation/source de publish chua..." | `source_audit(markdown=..., min_sources=2)` | `v3+p575c57ef8434+t67c6e3325411` | Tool mới phát hiện 0 source domain, status `needs_review`. |
| Web UI transcript turn 2 | "tim ra 3 bai viet moi nhat cua elon musk tren X" | `timeline(screenname="elonmusk", limit=3)` | `v3+p575c57ef8434+t67c6e3325411` | Routing đúng timeline, API Twitter trả 403 và agent báo không truy cập được. |
| Web UI transcript turn 5 | "tom tat bai bao nay: https://vietnamnet.vn/..." | `fetch(url=...)` | `v3+p575c57ef8434+t67c6e3325411` | Đọc URL VietNamNet và tóm tắt bài viết. |
| Telegram transcript turn 4 | "Tom tat bai nay cho toi: https://vietnamnet.vn/..." | `fetch(url=...)` | `v3+p575c57ef8434+t67c6e3325411` | Bot Telegram nhận request, gọi fetch và trả lời tóm tắt. |
| Streamlit transcript turn 1 | "xin chao" | No tool | `v3+p575c57ef8434+t67c6e3325411` | UI Streamlit hoạt động, meta/casual question không gọi tool. |

Evidence files:

- `transcripts/v3_openrouter_20260602T143250148565.transcript.json`
- `transcripts/v3_openrouter_web_20260602T144227135350.transcript.json`
- `transcripts/v3_openrouter_telegram_6947373058_20260602T144958357685.transcript.json`
- `transcripts/v3_openrouter_streamlit_20260602T162236454964.transcript.json`

## B5. Bonus Evidence

| Bonus | Evidence File | What Worked | Risk / Guardrail |
|---|---|---|---|
| send (Telegram) | `tools/send/TOOL.md`, `telegram_bot.py`, `runs/v3_B_group_openrouter_20260602T142921831209.json` | Có action tool gửi Telegram và group case `G10` đạt pass khi đã có xác nhận. | `send` chỉ được gọi khi latest user turn xác nhận rõ nội dung; nếu chưa xác nhận thì `clarify(response_type=yes_no)`. |
| arXiv/company policy | `tools/policy/`, `tools/papers/`, `tools/paper_text/`, `artifacts/tools.yaml` | Agent có thể route policy nội bộ, tìm arXiv paper và đọc text PDF arXiv. | Không dùng web search cho policy nội bộ; `paper_text` chỉ đọc khi có arXiv ID/URL. |
| UI | `app.py`, `web_app.py`, `telegram_bot.py`, `artifacts/poster.html`, Streamlit transcript | Có Streamlit UI, web app, Telegram bot và poster demo; transcript Streamlit/web/Telegram đã được lưu. | Không commit `.env`/API keys; public Cloudflare link là tạm thời, cần tạo lại khi demo. |
| custom source audit | `tools/source_audit/TOOL.md`, `tools/source_audit/tool.py`, `data/eval_group.json`, group run v3 | Tool mới kiểm tra URL/source domain và trả status `pass` hoặc `needs_review`; case `G05` pass. | Tool chỉ audit evidence đã có, không tự fetch thêm nguồn; draft thiếu source cần manual review. |

## B6. Reflection

- Fix thuộc `system_prompt.md`: routing rules, missing-info behavior, multi-turn correction, out-of-scope behavior, publish boundary và quy tắc không đoán URL/handle/confirmation.
- Fix thuộc `tools.yaml`: mô tả rõ từng tool, required args, default/enum values, convention như `topic=news`, `timeframe=day/week/month`, `search_type=Top`, và boundary của `fetch`, `send`, `source_audit`.
- Failure cần manual review: các lỗi API 403 của Twitter/RapidAPI trong live chat. Agent chọn đúng tool và args, nhưng external API bị từ chối nên không nên tính như lỗi prompt/tool routing.
- Điều sẽ cải tiến tiếp: thêm retry/fallback khi Twitter API 403, làm sạch HTML/noise khi `fetch` trang báo, thêm eval cho `policy`, `papers`, `paper_text`, và ghi public deploy URL vào report/poster khi demo.