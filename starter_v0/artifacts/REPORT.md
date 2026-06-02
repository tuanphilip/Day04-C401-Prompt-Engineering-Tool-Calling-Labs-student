# Day 04 Lab v2 Report - Research Agent

> File nay gom 2 phan:
> - **PHAN A - Gioi thieu agent**: mo ta ngan gon agent lam duoc gi, co tool nao, va cau hoi mau de team khac thu.
> - **PHAN B - Chi tiet / Bang chung**: bang version, loi, eval, live chat va reflection dua tren log that trong `runs/`, `analysis/`, `transcripts/`.

## Team

- Team: Research Agent Team
- Members:
  - Nguyen Danh Thanh - 2A202600581
  - Vu Tuan Phuong - 2A202600772
  - Vu Ngoc Vinh - 2A202600864
- Provider/model: OpenRouter / `openai/gpt-4o-mini`

---

# PHAN A - Gioi thieu agent

## A1. Agent nay lam duoc gi

Research agent giup nguoi dung tim tin tren web, tim bai dang tren X/Twitter, doc URL, tim paper, tra cuu policy noi bo, kiem tra chat luong citation/source va tao ban tom tat/digest. Agent duoc toi uu de chon dung tool, truyen dung tham so, hoi lai khi thieu thong tin, va chi thuc hien hanh dong gui Telegram sau khi co xac nhan ro rang.

**Link dung thu (deploy):**

> URL local da lam UI: `http://127.0.0.1:8501`
>
> Public URL: chua ghi nhan link Cloudflare/Vercel co dinh trong artifact. Co the chay `start_streamlit_ui.ps1` va `start_cloudflare_tunnel.ps1` de tao link `https://*.trycloudflare.com` khi demo.

## A2. Tool agent co

| Ten tool | Lam duoc gi | Tool moi nhom them? |
|---|---|---|
| `clarify` | Hoi lai nguoi dung khi thieu handle, URL, lua chon, hoac can xac nhan gui/dang. | Khong |
| `timeline` | Lay bai dang gan day cua mot tai khoan cu the tren X/Twitter, vi du `sama`, `elonmusk`, `karpathy`. | Khong |
| `social_search` | Tim bai dang tren X/Twitter theo tu khoa/chu de; ho tro `Latest` va `Top`. | Khong |
| `lookup` | Tim kiem web cong khai, tin moi, hoac thong tin hien tai; co `topic=general/news` va `timeframe`. | Khong |
| `fetch` | Doc va trich noi dung tu URL cu the ma nguoi dung cung cap. | Khong |
| `format` | Dinh dang cac item da thu thap thanh markdown digest, bullets, thread, hoac daily briefing. | Khong |
| `send` | Gui text len Telegram channel sau khi nguoi dung xac nhan noi dung. | Khong, bonus action tool |
| `policy` | Tim trong cac file company policy noi bo ve citation, privacy, publish, tool usage, AI research. | Khong, bonus/extension |
| `papers` | Tim paper/preprint tren arXiv theo chu de nghien cuu. | Khong, bonus/extension |
| `paper_text` | Tai PDF arXiv va trich text de doc/tom tat paper. | Khong, bonus/extension |
| `source_audit` | Kiem tra ban tin/digest co du URL, source domain va citation de publish hay chua. | Co |

## A3. Cau hoi mau de thu

1. Tin AI hom nay co gi noi bat?
2. Tom tat bai bao nay: https://vietnamnet.vn/bi-thu-ha-noi-thanh-pho-tap-trung-nguon-luc-de-nguoi-dan-de-tiep-can-nha-o-2521750.html
3. Tim 3 bai viet moi nhat cua Elon Musk tren X.
4. Kiem tra ban tin nay da du citation/source de publish chua: OpenAI ra model moi. Anthropic cap nhat Claude. Chua co link nguon.
5. Tim 5 paper moi ve RAG evaluation tren arXiv.

---

# PHAN B - Chi tiet / Bang chung

## B1. Version Evidence

Du lieu lay tu `artifacts/version_log.csv`, `analysis/run-analysis.csv`, va `runs/*.json`.

| Version | Changed Artifact | Hypothesis | Metric Before | Metric After | Run File |
|---|---|---|---:|---:|---|
| v0 | baseline | Baseline se de lo cac loi routing, thieu clarify, va action boundary chua chat. | N/A | 0.70 | `runs/v0_B_base_openrouter_20260602T142350788386.json` |
| v1 | `system_prompt.md` | Neu prompt cam doan thong tin thieu va yeu cau clarify, accuracy se tang. | 0.70 | 0.90 | `runs/v1_B_base_openrouter_20260602T142522428245.json` |
| v2 | `tools.yaml` | Neu tool declarations noi ro boundary va argument convention, loi wrong-tool/URL routing se giam. | 0.90 | 0.95 | `runs/v2_B_base_openrouter_20260602T142656224351.json` |
| v3 | `system_prompt.md` + `tools.yaml` | Neu missing-info rule cho timeline ro hon va dang ky `source_audit`, base va group eval se dat full accuracy. | 0.95 | 1.00 | `runs/v3_B_base_openrouter_20260602T142827784188.json` |

Ket qua tong hop:

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
| `R03_web_news_routing` in v0 | wrong arg value | `lookup(query="AI news", topic="news", timeframe="day")` | Agent them tu "news" vao query, trong khi expected query la `AI`. | Them convention: news request dung `topic=news`, giu query gon theo chu de chinh. |
| `R08_out_of_scope` in v0 | out of scope | `send` | Agent goi action tool cho request ngoai pham vi/chua can tool. | Prompt noi ro out-of-scope thi tra loi ngan, khong goi tool. |
| `R10_missing_handle` in v0 | missing info | `timeline` | User muon lay tweet nhung chua noi account; agent doan va goi timeline. | Them rule: thieu account cho timeline thi `clarify(response_type=text)`. |
| `R11_missing_url` in v0 | missing info | `fetch` | User noi "bai nay/link nay" nhung khong co URL; agent van goi fetch. | Them rule: thieu URL thi hoi lai, khong tu che URL. |
| `R12_confirm_before_send` in v0 | wrong boundary | `send` | Agent gui Telegram truoc khi co xac nhan ro rang. | Them publish boundary: send/post/publish phai `clarify(response_type=yes_no)` truoc. |
| `R13_parallel_web_and_tweets` in v0 | wrong arg value | `lookup` + `social_search` | Routing dung nhieu tool nhung query/topic bi sai: `AI news` va thieu `topic=news`. | Bo sung rule cho parallel requests: moi tool giu dung boundary va args rieng. |
| `R04_read_url_routing` in v1 | wrong tool | `clarify` | User da dua URL nhung agent hoi lai thay vi fetch. | Sua mo ta `fetch`: co URL thi dung `fetch`, nhieu URL thi goi nhieu lan. |
| `R10_missing_handle` in v1/v2 | missing info | `social_search` | Request timeline thieu account bi route sang topic search. | v3 bo sung rule cu the: "tweets/posts from an account but no account -> clarify". |
| `G10_multiturn_confirm_send` in group run dau | wrong arg value | `send` | Lan chay dau sai dau cham trong `text`: expected `AI briefing da san sang.`, got `AI briefing da san sang`. | Dieu chinh/kiem tra lai action boundary va noi dung gui; group run sau dat 10/10. |

## B3. Team Eval Cases

List 10 cases added to `data/eval_group.json` (5 single turn + 5 multi turn).

| Case ID | What It Tests | Expected Tool/Behavior | Result |
|---|---|---|---|
| `G01_missing_account_for_timeline` | Timeline request thieu account phai hoi lai, khong doan. | `clarify(response_type=text)` | Pass |
| `G02_missing_url_for_article` | Tom tat bai viet nhung chua co URL phai hoi lai URL. | `clarify(response_type=text)` | Pass |
| `G03_two_urls_parallel_fetch` | Hai URL ro rang phai tao hai lan fetch, khong web search. | `fetch` + `fetch` | Pass |
| `G04_top_social_search` | "Top/pho bien" tren social phai dung `search_type=Top`. | `social_search(query="AI agents", search_type="Top")` | Pass |
| `G05_source_audit_before_publish` | Kiem tra citation/source phai route den tool moi cua nhom. | `source_audit` | Pass |
| `G06_multiturn_fill_account_keep_limit` | Multi-turn giu limit 5 va dien account Sam Altman. | `timeline(screenname="sama", limit=5)` | Pass |
| `G07_multiturn_correct_account` | Turn sau sua account phai override account cu. | `timeline(screenname="karpathy", limit=4)` | Pass |
| `G08_multiturn_correct_limit` | Turn sau sua limit tu 10 sang 3 phai lay limit moi. | `timeline(screenname="elonmusk", limit=3)` | Pass |
| `G09_multiturn_switch_social_to_web` | Turn sau doi Twitter sang web news, giu chu de OpenAI. | `lookup(query="OpenAI", topic="news", timeframe="week")` | Pass |
| `G10_multiturn_confirm_send` | Sau xac nhan ro rang moi duoc goi send. | `send(confirmed=true)` | Pass |

Evidence run: `runs/v3_B_group_openrouter_20260602T142921831209.json`, passed 10/10.

## B4. Live Chat Evidence

Use `transcripts/*.transcript.json`.

| Turn | User Request | Tool Calls | Version Evidence | Outcome |
|---|---|---|---|---|
| CLI transcript turn 1 | "Tin AI hom nay co gi noi bat?" | `lookup(query="AI", topic="news", timeframe="day")` | `v3+p575c57ef8434+t67c6e3325411` | Tra ve 5 tin AI trong ngay kem URL/source. |
| CLI transcript turn 2 | "Tom tat 5 tweet moi nhat giup minh" | `social_search(query="AI", search_type="Latest", limit=5)` | `v3+p575c57ef8434+t67c6e3325411` | Routing den social search dung, nhung API Twitter/RapidAPI tra 403 nen agent bao loi truy cap. |
| CLI transcript turn 3 | "Kiem tra ban tin nay da du citation/source de publish chua..." | `source_audit(markdown=..., min_sources=2)` | `v3+p575c57ef8434+t67c6e3325411` | Tool moi phat hien 0 source domain, status `needs_review`. |
| Web UI transcript turn 2 | "tim ra 3 bai viet moi nhat cua elon musk tren X" | `timeline(screenname="elonmusk", limit=3)` | `v3+p575c57ef8434+t67c6e3325411` | Routing dung timeline, API Twitter tra 403 va agent bao khong truy cap duoc. |
| Web UI transcript turn 5 | "tom tat bai bao nay: https://vietnamnet.vn/..." | `fetch(url=...)` | `v3+p575c57ef8434+t67c6e3325411` | Doc URL VietNamNet va tom tat bai viet. |
| Telegram transcript turn 4 | "Tom tat bai nay cho toi: https://vietnamnet.vn/..." | `fetch(url=...)` | `v3+p575c57ef8434+t67c6e3325411` | Bot Telegram nhan request, goi fetch va tra loi tom tat. |
| Streamlit transcript turn 1 | "xin chao" | No tool | `v3+p575c57ef8434+t67c6e3325411` | UI Streamlit hoat dong, meta/casual question khong goi tool. |

Evidence files:

- `transcripts/v3_openrouter_20260602T143250148565.transcript.json`
- `transcripts/v3_openrouter_web_20260602T144227135350.transcript.json`
- `transcripts/v3_openrouter_telegram_6947373058_20260602T144958357685.transcript.json`
- `transcripts/v3_openrouter_streamlit_20260602T162236454964.transcript.json`

## B5. Bonus Evidence

| Bonus | Evidence File | What Worked | Risk / Guardrail |
|---|---|---|---|
| send (Telegram) | `tools/send/TOOL.md`, `telegram_bot.py`, `runs/v3_B_group_openrouter_20260602T142921831209.json` | Co action tool gui Telegram va group case `G10` dat pass khi da co xac nhan. | `send` chi duoc goi khi latest user turn xac nhan ro noi dung; neu chua xac nhan thi `clarify(response_type=yes_no)`. |
| arXiv/company policy | `tools/policy/`, `tools/papers/`, `tools/paper_text/`, `artifacts/tools.yaml` | Agent co the route policy noi bo, tim arXiv paper va doc text PDF arXiv. | Khong dung web search cho policy noi bo; `paper_text` chi doc khi co arXiv ID/URL. |
| UI | `app.py`, `web_app.py`, `telegram_bot.py`, `artifacts/poster.html`, Streamlit transcript | Co Streamlit UI, web app, Telegram bot va poster demo; transcript Streamlit/web/Telegram da duoc luu. | Khong commit `.env`/API keys; public Cloudflare link la tam thoi, can tao lai khi demo. |
| custom source audit | `tools/source_audit/TOOL.md`, `tools/source_audit/tool.py`, `data/eval_group.json`, group run v3 | Tool moi kiem tra URL/source domain va tra status `pass` hoac `needs_review`; case `G05` pass. | Tool chi audit evidence da co, khong tu fetch them nguon; draft thieu source can manual review. |

## B6. Reflection

- Fix thuoc `system_prompt.md`: routing rules, missing-info behavior, multi-turn correction, out-of-scope behavior, publish boundary va quy tac khong doan URL/handle/confirmation.
- Fix thuoc `tools.yaml`: mo ta ro tung tool, required args, default/enum values, convention nhu `topic=news`, `timeframe=day/week/month`, `search_type=Top`, va boundary cua `fetch`, `send`, `source_audit`.
- Failure can manual review: cac loi API 403 cua Twitter/RapidAPI trong live chat. Agent chon dung tool va args, nhung external API bi tu choi nen khong nen tinh nhu loi prompt/tool routing.
- Dieu se cai tien tiep: them retry/fallback khi Twitter API 403, lam sach HTML/noise khi `fetch` trang bao, them eval cho `policy`, `papers`, `paper_text`, va ghi public deploy URL vao report/poster khi demo.
