# Research Agent Lab Playbook

## Goal

Build a research agent that can receive a user request, select the right tool, pass the right arguments, run real evaluations, save real logs, and improve the prompt/tool declarations across multiple versions.

The main lesson of this lab is not to create a chatbot that sounds fluent. The main lesson is to practice an evidence-driven loop:

1. Run a baseline.
2. Read the run JSON to understand what failed.
3. Edit `artifacts/system_prompt.md` or `artifacts/tools.yaml`.
4. Run the evaluation again.
5. Record evidence in `artifacts/version_log.csv`.
6. Write the report from real logs, not intuition.

## Submission Checklist

- `artifacts/system_prompt.md`
- `artifacts/tools.yaml`
- `artifacts/version_log.csv`
- `artifacts/REPORT.md`
- `data/eval_group.json`
- `runs/*.json`
- `transcripts/*.transcript.json`
- code for any new tool added by the team
- `TOOL.md` for any new tool

Do not submit `.env`. Do not include API keys in reports, transcripts, screenshots, or GitHub.

## Setup

Run all commands from `starter_v0/`.

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
```

Fill the minimum required keys in `.env`:

```text
OPENROUTER_API_KEY=...
TAVILY_API_KEY=...
FIRECRAWL_API_KEY=...
RAPIDAPI_KEY=...
RAPIDAPI_TWITTER_HOST=twitter-api45.p.rapidapi.com
```

Check the provider:

```powershell
python scripts/preflight_provider.py --provider openrouter
```

## Version Plan

### v0: Baseline

Run the base evaluation before changing the prompt or tool declarations.

```powershell
python run_eval.py --provider openrouter --version v0 --suite base --eval-cases data/eval_base.json
```

After the run, open the latest file in `runs/` and record:

- `summary.case_accuracy`
- `summary.tool_routing_accuracy`
- `summary.argument_accuracy`
- `summary.multiturn_accuracy`
- failed cases from `results[*].result.failures`

### v1: Improve the System Prompt

Edit `artifacts/system_prompt.md` so the agent has clear behavior rules.

Recommended rules:

- If the account or handle is missing, call `clarify`; do not guess.
- If the URL is missing, call `clarify`; do not invent a URL.
- If the user wants to send, post, publish, or write externally, ask for confirmation with `clarify` and `response_type=yes_no`.
- Only call `send` after the user has explicitly confirmed.
- For requests outside research, news, social search, web search, policy, or papers, do not call a tool.
- In multi-turn cases, answer only the latest user turn, but use earlier turns as context.
- If the latest turn corrects earlier information, prefer the latest information.

Run:

```powershell
python run_eval.py --provider openrouter --version v1 --suite base --eval-cases data/eval_base.json
```

### v2: Improve Tool Declarations

Edit `artifacts/tools.yaml` to make each tool description clearer.

Clarify:

- `timeline`: use for recent tweets/posts from a specific account or person.
- `social_search`: use for tweets/posts by topic or keyword.
- `lookup`: use for web search or news search.
- `fetch`: use when the user provides a specific URL and wants it read or summarized.
- `format`: only formats already-collected items; it does not fetch or search.
- `clarify`: use when required information or confirmation is missing.
- `send`: action tool; only use after explicit confirmation.
- `policy`: use for internal company policy questions.
- `papers`: use for paper or arXiv discovery.
- `paper_text`: use when the user provides an arXiv ID or URL and wants paper text.

Run:

```powershell
python run_eval.py --provider openrouter --version v2 --suite base --eval-cases data/eval_base.json
```

### v3: Fix Remaining Failures

Read the `v2` run JSON and choose one remaining failure pattern to fix.

Examples:

- Wrong `limit`.
- Wrong `timeframe`.
- Wrong `search_type`.
- Extra tool calls.
- Multi-turn context not carried forward.
- Multi-turn correction not applied.

Run:

```powershell
python run_eval.py --provider openrouter --version v3 --suite base --eval-cases data/eval_base.json
```

## Routing Rules

Use these rules in the prompt and tool descriptions.

| User intent | Tool |
|---|---|
| Latest tweets/posts from a specific person or account | `timeline` |
| Search tweets/posts by topic or keyword | `social_search` |
| Web search, news search, or fresh public information | `lookup` |
| Read or summarize a specific URL | `fetch` |
| Format already-collected results | `format` |
| Missing handle, URL, or required information | `clarify` |
| Send/post/publish request without confirmation | `clarify` |
| Send Telegram message after confirmation | `send` |
| Internal company policy question | `policy` |
| Search scientific papers or arXiv | `papers` |
| Read paper text from an arXiv ID or URL | `paper_text` |
| Out of scope for research/news/social/web/policy/papers | no tool |

## Argument Conventions

- `today`, `hôm nay` -> `timeframe=day`
- `this week`, `tuần này` -> `timeframe=week`
- `this month`, `tháng này` -> `timeframe=month`
- `popular`, `top`, `phổ biến` -> `search_type=Top`
- Default tweet/social search order -> `search_type=Latest`
- Sam Altman -> `screenname=sama`
- Elon Musk -> `screenname=elonmusk`
- Andrej Karpathy -> `screenname=karpathy`
- If the user gives a number of tweets/posts, preserve it as `limit`
- If the user corrects the number in a later turn, use the latest number

## New Tool Plan

The lab requires at least one new tool.

Recommended tool: `source_audit`.

Purpose:

- Check whether a list of items or a markdown digest has citations/source URLs.
- Report items missing URLs.
- Report weak or suspicious sources.
- Produce a pre-publish checklist for research outputs.

Files to create:

- `tools/source_audit/tool.py`
- `tools/source_audit/TOOL.md`

Required registration:

- Add the import and key to `tools/__init__.py`.
- Add the tool declaration to `artifacts/tools.yaml`.
- Add related evaluation cases to `data/eval_group.json`.

## Group Evaluation Plan

`data/eval_group.json` should contain at least 10 cases:

- 5 single-turn cases.
- 5 multi-turn cases.

Suggested single-turn cases:

1. Missing account in a latest-tweets request -> `clarify`.
2. Missing URL in an article-summary request -> `clarify`.
3. Two URLs in one request -> call `fetch` twice.
4. Top tweets about a topic -> `social_search` with `search_type=Top`.
5. Check citations/sources before publishing -> `source_audit`.

Suggested multi-turn cases:

1. User asks for 5 tweets, then provides the account -> `timeline` with `limit=5`.
2. User changes the account from Sam Altman to Karpathy -> `timeline` with `screenname=karpathy`.
3. User changes the limit from 10 to 3 -> `timeline` with `limit=3`.
4. User switches from Twitter to web news -> `lookup`.
5. User asks to publish, agent asks for confirmation, user confirms -> `send` with `confirmed=true`.

Run the group evaluation:

```powershell
python run_eval.py --provider openrouter --version v3 --suite group --eval-cases data/eval_group.json
```

## Live Chat Plan

Run:

```powershell
python chat.py --provider openrouter --version v3
```

Create transcript evidence for at least 3 scenarios:

1. A normal research request.
2. A request with missing information where the agent asks a clarification question.
3. A send/post/publish request where the agent asks for confirmation before sending.

Transcripts are saved to `transcripts/*.transcript.json`.

## Web UI

Run from `starter_v0/`:

```powershell
powershell -ExecutionPolicy Bypass -File .\start_streamlit_ui.ps1
```

Then open:

```text
http://127.0.0.1:8501
```

The web UI uses the same prompt, tool declarations, provider adapters, tool loop,
and transcript format as `chat.py`. Web transcripts are saved under
`transcripts/*.transcript.json`.

To expose the Streamlit UI for other teams with Cloudflare Tunnel:

```powershell
powershell -ExecutionPolicy Bypass -File .\start_cloudflare_tunnel.ps1
```

Copy the generated `https://*.trycloudflare.com` URL into
`artifacts/REPORT.md` Part A and keep the terminal open while others test.

## Telegram Bot

The Telegram bot token from BotFather must stay as one value:

```text
TELEGRAM_BOT_TOKEN=123456789:AAExampleTokenCharacters
```

Do not split the `id:characters` token into two variables. `TELEGRAM_CHAT_ID` is
different: it is the chat, user, group, or channel ID used by the `send` action
tool. The polling chatbot can reply to the current Telegram chat without
`TELEGRAM_CHAT_ID`, but the `send` tool still needs it.

Optional access control:

```text
TELEGRAM_ALLOWED_CHAT_IDS=123456789,-1001234567890
```

Run from `starter_v0/`:

```powershell
.\.venv\Scripts\python.exe telegram_bot.py --check-env
powershell -ExecutionPolicy Bypass -File .\start_telegram_bot.ps1
```

Telegram commands:

```text
/start - show help
/help - show help
/tools - list available research tools and examples
/status - check environment readiness
/reset - clear this chat memory
```

Tools shown by `/tools`:

- `clarify`: ask for missing information or confirmation.
- `timeline`: recent posts from one specific account/person.
- `social_search`: search posts by topic or keyword.
- `lookup`: search web/news.
- `fetch`: read or summarize a specific URL.
- `format`: format already-collected items.
- `send`: post to the configured Telegram channel after confirmation.
- `policy`: search internal company policy.
- `papers`: search arXiv papers.
- `paper_text`: extract text from an arXiv paper.
- `source_audit`: check citations/sources before publishing.

## Version Log

After each evaluation run, fill `artifacts/version_log.csv`.

Use information from the run JSON:

- `version`
- `artifact_version`
- `prompt_hash`
- `tools_hash`
- `summary.case_accuracy`
- run file path

Each version should have a clear hypothesis.

Examples:

```text
v1: If the prompt forbids guessing and requires clarification for missing information, missing_info cases should improve.
v2: If tool descriptions explain routing boundaries clearly, wrong_tool cases should decrease.
v3: If timeframe/search_type/multi-turn conventions are explicit, argument_accuracy should improve.
```

## How to Read Run JSON

In each `runs/*.json` file, inspect:

- `summary`: overall metrics.
- `results[*].id`: case ID.
- `results[*].expect`: expected tool calls and arguments.
- `results[*].result.actual_tool_calls`: actual tool calls from the agent.
- `results[*].result.failures`: exact failure details.
- `results[*].result.observed_mismatch`: observed mismatch type.

Do not edit `data/eval_base.json`, except to synchronize tool names if the team intentionally renames a tool.

## Report Plan

Fill `artifacts/REPORT.md` with real evidence.

Include:

- Provider/model.
- Final version.
- Best base run file.
- Base case accuracy.
- Base routing accuracy.
- Base argument accuracy.
- Group evaluation run file.
- Group evaluation accuracy.
- Chat transcript file.
- Version evidence table.
- Failure analysis table.
- Team evaluation cases.
- Live chat evidence.
- Bonus evidence if applicable.

## Working Principles

- Change one hypothesis at a time.
- Prefer prompt and tool declaration changes before changing agent code.
- Add the new tool after the base evaluation is reasonably stable.
- Write the report from run JSON and transcript JSON, not from memory.
- Never include API keys in any artifact.
