from __future__ import annotations

import json
import re
from datetime import datetime
from html import escape
from pathlib import Path
from typing import Any

import streamlit as st

from chat import now_iso, run_model_tool_loop, trim_history, write_transcript
from env_loader import load_lab_env
from providers import make_provider
from tools import load_tool_declarations, to_openai_tools
from versioning import artifact_version_dict, build_artifact_version


ROOT = Path(__file__).parent
ARTIFACTS_DIR = ROOT / "artifacts"
TRANSCRIPTS_DIR = ROOT / "transcripts"
load_lab_env(ROOT)


TOOL_GUIDE = {
    "clarify": "Ask for missing details or confirmation.",
    "timeline": "Recent posts from a specific account.",
    "social_search": "Search social posts by topic.",
    "lookup": "Search web/news.",
    "fetch": "Read a specific URL.",
    "format": "Format collected items.",
    "send": "Send to Telegram after confirmation.",
    "policy": "Search company policy.",
    "papers": "Search arXiv papers.",
    "paper_text": "Extract text from an arXiv paper.",
    "source_audit": "Check source/citation readiness.",
}


SAMPLE_PROMPTS = [
    "Tin AI hom nay co gi noi bat?",
    "Moi nguoi dang noi gi ve GPT-5 tren Twitter?",
    "Tom tat link nay: https://openai.com/research/",
    "Tim paper arXiv moi ve AI agent evaluation.",
    "Kiem tra ban tin nay da du citation/source de publish chua: OpenAI ra model moi. Chua co link nguon.",
]


def safe_slug(value: str) -> str:
    slug = re.sub(r"[^A-Za-z0-9_.-]+", "_", value.strip())
    return slug.strip("_") or "run"


def compact_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2, default=str)


def init_state() -> None:
    defaults = {
        "history": [],
        "turns": [],
        "trace": [],
        "turn_index": 0,
        "transcript_path": None,
        "transcript": None,
        "artifact_version": None,
        "pending_prompt": None,
    }
    for key, value in defaults.items():
        st.session_state.setdefault(key, value)


def reset_session() -> None:
    for key in ["history", "turns", "trace", "turn_index", "transcript_path", "transcript", "artifact_version"]:
        st.session_state.pop(key, None)
    init_state()


def ensure_transcript(provider_name: str, version: str, model: str | None, max_tool_rounds: int) -> None:
    if st.session_state.transcript is not None:
        return

    system_prompt_path = ARTIFACTS_DIR / "system_prompt.md"
    tools_path = ARTIFACTS_DIR / "tools.yaml"
    artifact = build_artifact_version(version, system_prompt_path, tools_path)
    timestamp = datetime.now().strftime("%Y%m%dT%H%M%S%f")
    transcript_id = "_".join([safe_slug(version), safe_slug(provider_name), "streamlit", timestamp])
    transcript_path = TRANSCRIPTS_DIR / f"{transcript_id}.transcript.json"
    transcript = {
        "transcript_id": transcript_id,
        **artifact_version_dict(artifact),
        "provider": provider_name,
        "model": model,
        "system_prompt": str(system_prompt_path),
        "tools": str(tools_path),
        "history_window": 5,
        "max_tool_rounds": max_tool_rounds,
        "created_at": now_iso(),
        "updated_at": now_iso(),
        "turns": [],
        "source": "streamlit_app",
    }
    st.session_state.artifact_version = artifact.artifact_version
    st.session_state.transcript = transcript
    st.session_state.transcript_path = transcript_path
    write_transcript(transcript_path, transcript)


def run_agent_turn(user_text: str, provider_name: str, version: str, model: str | None, max_tool_rounds: int) -> None:
    ensure_transcript(provider_name, version, model, max_tool_rounds)

    system_prompt = (ARTIFACTS_DIR / "system_prompt.md").read_text(encoding="utf-8")
    tool_declarations = load_tool_declarations(ARTIFACTS_DIR / "tools.yaml")
    openai_tools = to_openai_tools(tool_declarations)
    provider = make_provider(provider_name)
    messages = [
        {"role": "system", "content": system_prompt},
        *trim_history(st.session_state.history, 5),
        {"role": "user", "content": user_text},
    ]

    st.session_state.turn_index += 1
    turn_record: dict[str, Any] = {
        "turn_index": st.session_state.turn_index,
        "started_at": now_iso(),
        "user": user_text,
        "status": "started",
        "assistant_text": None,
        "rounds": [],
        "tool_events": [],
    }

    try:
        result = run_model_tool_loop(
            provider=provider,
            messages=messages,
            tools=openai_tools,
            model=model,
            max_tool_rounds=max_tool_rounds,
        )
        turn_record.update(result)
        assistant_text = result.get("assistant_text") or ""
        tool_names = [
            call.get("name")
            for round_item in result.get("rounds", [])
            for call in round_item.get("tool_calls", [])
        ]
        st.session_state.turns.append({
            "role": "user",
            "content": user_text,
            "meta": "You",
        })
        st.session_state.turns.append({
            "role": "assistant",
            "content": assistant_text,
            "meta": f"Agent · {', '.join(tool_names) if tool_names else 'direct answer'}",
        })
        st.session_state.history.append({"role": "user", "content": user_text})
        st.session_state.history.append({"role": "assistant", "content": assistant_text})
        st.session_state.trace.append({
            "turn": st.session_state.turn_index,
            "user": user_text,
            "rounds": result.get("rounds", []),
            "tool_events": result.get("tool_events", []),
        })
    except Exception as exc:
        turn_record.update({"status": "error", "error": f"{type(exc).__name__}: {exc}"})
        st.session_state.turns.append({"role": "user", "content": user_text, "meta": "You"})
        st.session_state.turns.append({"role": "assistant", "content": f"{type(exc).__name__}: {exc}", "meta": "Error"})
    finally:
        turn_record["ended_at"] = now_iso()
        st.session_state.transcript["turns"].append(turn_record)
        write_transcript(st.session_state.transcript_path, st.session_state.transcript)


def env_status() -> dict[str, bool]:
    import os

    return {
        "OPENROUTER_API_KEY": bool(os.getenv("OPENROUTER_API_KEY")),
        "TAVILY_API_KEY": bool(os.getenv("TAVILY_API_KEY")),
        "FIRECRAWL_API_KEY": bool(os.getenv("FIRECRAWL_API_KEY")),
        "RAPIDAPI_KEY": bool(os.getenv("RAPIDAPI_KEY")),
        "RAPIDAPI_TWITTER_HOST": bool(os.getenv("RAPIDAPI_TWITTER_HOST")),
        "TELEGRAM_BOT_TOKEN": bool(os.getenv("TELEGRAM_BOT_TOKEN")),
    }


def apply_styles() -> None:
    st.markdown(
        """
        <style>
        :root {
            --bg: #0b0f14;
            --panel: #111827;
            --panel-soft: #151f2e;
            --panel-strong: #0f172a;
            --ink: #e5e7eb;
            --muted: #94a3b8;
            --line: rgba(148, 163, 184, .22);
            --accent: #22c55e;
            --accent-strong: #86efac;
            --blue: #60a5fa;
            --amber: #fbbf24;
            --danger: #fb7185;
            --shadow: 0 18px 48px rgba(0, 0, 0, .35);
        }
        .stApp {
            background:
                linear-gradient(180deg, rgba(15, 23, 42, .72), rgba(11, 15, 20, 0) 220px),
                var(--bg);
            color: var(--ink);
        }
        header[data-testid="stHeader"],
        [data-testid="stSidebar"] {
            display: none;
        }
        [data-testid="stSidebar"] {
            background: var(--panel);
            border-right: 1px solid var(--line);
        }
        .main .block-container {
            max-width: 100%;
            padding: .75rem 1rem 6.8rem;
        }
        h1, h2, h3 {
            letter-spacing: 0;
        }
        .app-title {
            display: flex;
            align-items: center;
            justify-content: space-between;
            gap: 12px;
            min-height: 42px;
            padding: 0 2px 10px;
            border-bottom: 1px solid var(--line);
            margin-bottom: 12px;
        }
        .app-title h1 {
            margin: 0;
            color: var(--ink);
            font-size: 20px;
            line-height: 1.2;
            font-weight: 760;
        }
        .app-title span {
            color: var(--muted);
            font-size: 13px;
        }
        .panel-label {
            margin: 0 0 10px;
            color: var(--ink);
            font-size: 13px;
            font-weight: 760;
        }
        .panel-note {
            color: var(--muted);
            font-size: 12px;
            line-height: 1.45;
            margin: 0 0 10px;
        }
        .stat-grid {
            display: grid;
            grid-template-columns: repeat(2, minmax(0, 1fr));
            gap: 8px;
            margin: 10px 0 12px;
        }
        .stat {
            border: 1px solid var(--line);
            border-radius: 8px;
            padding: 9px 10px;
            background: linear-gradient(180deg, rgba(30, 41, 59, .88), rgba(17, 24, 39, .96));
            box-shadow: var(--shadow);
        }
        .stat strong {
            display: block;
            color: var(--ink);
            font-size: 20px;
            line-height: 1.05;
        }
        .stat span {
            color: var(--muted);
            font-size: 11px;
        }
        .chat-welcome {
            min-height: 45vh;
            display: grid;
            place-items: center;
            color: var(--muted);
            text-align: center;
            padding: 24px;
        }
        .chat-welcome h2 {
            margin: 0;
            color: var(--ink);
            font-size: 24px;
            line-height: 1.15;
        }
        .chat-welcome p {
            margin: 8px auto 0;
            max-width: 520px;
            color: var(--muted);
            font-size: 14px;
            line-height: 1.5;
        }
        .sample-strip {
            display: grid;
            grid-template-columns: repeat(2, minmax(0, 1fr));
            gap: 8px;
            margin: 8px 0 12px;
        }
        .sample-strip .stButton button {
            min-height: 42px;
            justify-content: flex-start;
            text-align: left;
            white-space: normal;
        }
        .tool-pill-row {
            display: flex;
            flex-wrap: wrap;
            gap: 6px;
            margin: 8px 0 0;
        }
        .tool-pill {
            border: 1px solid var(--line);
            border-radius: 999px;
            padding: 4px 8px;
            color: var(--blue);
            background: rgba(96, 165, 250, .10);
            font-size: 12px;
            white-space: nowrap;
        }
        .tool-card {
            border: 1px solid var(--line);
            border-radius: 8px;
            padding: 9px 10px;
            background: rgba(17, 24, 39, .82);
            margin-bottom: 8px;
        }
        .tool-card b {
            display: block;
            color: var(--ink);
            font-size: 13px;
        }
        .tool-card p {
            margin: 3px 0 0;
            color: var(--muted);
            font-size: 12px;
            line-height: 1.35;
        }
        .thought-box {
            border: 1px solid var(--line);
            border-radius: 8px;
            background: rgba(17, 24, 39, .84);
            padding: 10px;
            margin-bottom: 8px;
            box-shadow: var(--shadow);
        }
        .thought-box b {
            color: var(--ink);
            font-size: 13px;
        }
        .thought-box p,
        .thought-box li {
            color: var(--muted);
            font-size: 12px;
            line-height: 1.45;
        }
        .thought-box ul {
            margin: 4px 0 0;
            padding-left: 18px;
        }
        .status-ok,
        .status-warn,
        .status-miss {
            display: inline-flex;
            align-items: center;
            gap: 5px;
            min-height: 24px;
            padding: 2px 7px;
            border-radius: 999px;
            border: 1px solid var(--line);
            font-size: 12px;
        }
        .status-ok { color: #bbf7d0; background: rgba(34, 197, 94, .12); border-color: rgba(34, 197, 94, .28); }
        .status-warn { color: #fde68a; background: rgba(251, 191, 36, .12); border-color: rgba(251, 191, 36, .28); }
        .status-miss { color: #fecdd3; background: rgba(251, 113, 133, .12); border-color: rgba(251, 113, 133, .30); }
        .small-muted {
            color: var(--muted);
            font-size: 12px;
        }
        [data-testid="stChatInput"] {
            border-top: 1px solid var(--line);
            background: rgba(11, 15, 20, .94);
            backdrop-filter: blur(10px);
            padding: .85rem 24%;
        }
        [data-testid="stChatInput"] textarea {
            background: #111827 !important;
            color: var(--ink) !important;
            border: 1px solid var(--line) !important;
            border-radius: 10px !important;
            box-shadow: 0 14px 40px rgba(0, 0, 0, .34) !important;
        }
        [data-testid="stChatInput"] textarea::placeholder {
            color: #64748b !important;
        }
        div[data-testid="stChatMessage"] {
            border-radius: 8px;
            border: 1px solid transparent;
            padding: 14px 18px;
            background: rgba(15, 23, 42, .34);
            margin: 0 0 8px;
        }
        div[data-testid="stChatMessage"]:has([data-testid="stChatMessageAvatarUser"]) {
            background: rgba(30, 41, 59, .78);
            border-color: rgba(148, 163, 184, .16);
        }
        div[data-testid="stChatMessage"]:has([data-testid="stChatMessageAvatarAssistant"]) {
            background: rgba(17, 24, 39, .82);
            border-color: rgba(34, 197, 94, .12);
        }
        div[data-testid="stChatMessage"] p,
        div[data-testid="stChatMessage"] li {
            color: var(--ink);
            font-size: 14px;
            line-height: 1.55;
        }
        [data-testid="stChatMessageAvatarUser"],
        [data-testid="stChatMessageAvatarAssistant"] {
            border-radius: 6px;
        }
        [data-testid="stChatMessageAvatarUser"] {
            background: var(--accent) !important;
        }
        [data-testid="stChatMessageAvatarAssistant"] {
            background: var(--panel-strong) !important;
        }
        .stTextInput input,
        .stSelectbox [data-baseweb="select"],
        .stNumberInput input,
        .stTextArea textarea {
            background: #0f172a !important;
            color: var(--ink) !important;
            border-color: var(--line) !important;
            border-radius: 6px !important;
            box-shadow: none !important;
        }
        .stTextInput input::placeholder,
        .stTextArea textarea::placeholder {
            color: #64748b !important;
        }
        .stSlider [data-baseweb="slider"] {
            color: var(--accent);
        }
        .stButton > button {
            background: #111827;
            border: 1px solid var(--line);
            color: var(--ink);
            border-radius: 6px;
            font-weight: 680;
        }
        .stButton > button:hover {
            border-color: var(--accent);
            color: var(--accent-strong);
            background: rgba(34, 197, 94, .10);
        }
        .stAlert {
            background: #111827;
            color: var(--ink);
            border: 1px solid var(--line);
        }
        pre, code {
            background: #020617 !important;
            color: #dbeafe !important;
            border-color: var(--line) !important;
        }
        .stTabs [data-baseweb="tab-list"] {
            gap: 4px;
            border-bottom: 1px solid var(--line);
        }
        .stTabs [data-baseweb="tab"] {
            height: 36px;
            padding: 0 10px;
            font-size: 13px;
            color: var(--muted);
        }
        .stTabs [aria-selected="true"] {
            color: var(--accent-strong) !important;
        }
        @media (max-width: 980px) {
            [data-testid="stChatInput"] { padding: .85rem 1rem; }
            .sample-strip { grid-template-columns: 1fr; }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def render_status_badges() -> None:
    env = env_status()
    ready = all(env.values())
    cls = "status-ok" if ready else "status-warn"
    label = "Env ready" if ready else "Env partial"
    st.markdown(
        f"""
        <div>
          <span class="{cls}">{label}</span>
          <span class="status-ok">{len(st.session_state.turns) // 2} turns</span>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_parameter_panel(tool_declarations: list[dict[str, Any]]) -> tuple[str, str, str | None, int]:
    settings_tab, tools_tab = st.tabs(["Thong so", "Cong cu"])
    with settings_tab:
        st.markdown('<p class="panel-note">Chinh provider, version prompt va so vong goi tool cho moi lan hoi.</p>', unsafe_allow_html=True)
        provider_name = st.selectbox("Provider", ["openrouter", "openai", "anthropic", "gemini"], index=0)
        version = st.text_input("Version", value="v3")
        model_value = st.text_input("Model override", value="")
        max_tool_rounds = st.slider("Tool rounds", 1, 8, 4)

        if st.button("Reset chat", use_container_width=True):
            reset_session()
            st.rerun()

        st.markdown(
            f"""
            <div class="stat-grid">
              <div class="stat"><strong>{len(tool_declarations)}</strong><span>tools</span></div>
              <div class="stat"><strong>{len(st.session_state.turns) // 2}</strong><span>turns</span></div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        st.markdown('<p class="panel-label">Environment</p>', unsafe_allow_html=True)
        for key, ok in env_status().items():
            cls = "status-ok" if ok else "status-miss"
            value = "OK" if ok else "missing"
            st.markdown(f'<span class="{cls}">{escape(key)}: {value}</span>', unsafe_allow_html=True)

        st.markdown('<p class="panel-label" style="margin-top:12px;">Transcript</p>', unsafe_allow_html=True)
        if st.session_state.transcript_path:
            st.code(str(st.session_state.transcript_path), language="text")
        else:
            st.caption("Transcript starts after the first message.")

    with tools_tab:
        st.markdown('<p class="panel-note">Danh sach tool agent co the goi khi can tim kiem, doc link, audit source hoac format ket qua.</p>', unsafe_allow_html=True)
        render_tools(tool_declarations)

    return provider_name, version, model_value.strip() or None, max_tool_rounds


def render_header() -> None:
    st.markdown(
        """
        <div class="app-title">
          <div>
            <h1>Research Agent</h1>
            <span>Chat UI voi input co dinh, thong so ben trai, log ben phai.</span>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_tools(tool_declarations: list[dict[str, Any]], *, compact: bool = False) -> None:
    if compact:
        pills = "".join(f'<span class="tool-pill">{escape(tool["name"])}</span>' for tool in tool_declarations)
        st.markdown(f'<div class="tool-pill-row">{pills}</div>', unsafe_allow_html=True)
        return

    for tool in tool_declarations:
        name = escape(tool["name"])
        description = escape(TOOL_GUIDE.get(tool["name"], tool.get("description", "Available tool.")))
        st.markdown(f'<div class="tool-card"><b>{name}</b><p>{description}</p></div>', unsafe_allow_html=True)


def thought_steps(item: dict[str, Any]) -> list[str]:
    steps = [f"Nhan yeu cau: {item.get('user', '')}"]
    rounds = item.get("rounds", [])
    if not rounds:
        steps.append("Tra loi truc tiep, khong can goi tool.")
        return steps

    for round_item in rounds:
        round_no = round_item.get("round")
        calls = round_item.get("tool_calls", [])
        if not calls:
            steps.append(f"Round {round_no}: model chot cau tra loi.")
            continue
        names = ", ".join(str(call.get("name", "tool")) for call in calls)
        steps.append(f"Round {round_no}: goi tool {names}.")

    events = item.get("tool_events", [])
    if events:
        steps.append(f"Ghi nhan {len(events)} tool event de lap transcript.")
    return steps


def render_thought_log() -> None:
    if not st.session_state.trace:
        st.info("Log tu duy se hien sau khi agent chay. Phan nay tom tat hoat dong/tool trace, khong hien chuoi suy luan rieng tu cua model.")
        return

    for item in reversed(st.session_state.trace[-8:]):
        steps = thought_steps(item)
        lis = "".join(f"<li>{escape(step)}</li>" for step in steps)
        st.markdown(
            f"""
            <div class="thought-box">
              <b>Turn {item["turn"]}</b>
              <ul>{lis}</ul>
            </div>
            """,
            unsafe_allow_html=True,
        )


def render_trace_json() -> None:
    if not st.session_state.trace:
        st.info("Trace JSON se hien sau turn dau tien.")
        return
    for item in reversed(st.session_state.trace[-8:]):
        with st.expander(f"Turn {item['turn']} trace", expanded=item["turn"] == st.session_state.turn_index):
            st.code(compact_json({"rounds": item["rounds"], "tool_events": item["tool_events"]}), language="json")


def render_samples() -> None:
    st.markdown('<p class="panel-label">Thu nhanh</p>', unsafe_allow_html=True)
    first_row = st.columns(2)
    second_row = st.columns(2)
    rows = [*first_row, *second_row]
    for index, prompt in enumerate(SAMPLE_PROMPTS[:4]):
        with rows[index]:
            if st.button(prompt, use_container_width=True, key=f"sample_{index}"):
                st.session_state.pending_prompt = prompt
                st.rerun()


def render_chat() -> None:
    if not st.session_state.turns:
        st.markdown(
            """
            <div class="chat-welcome">
              <div>
                <h2>Ban muon nghien cuu gi?</h2>
                <p>Nhap cau hoi o thanh input co dinh ben duoi. Agent se tra loi nhu chat va cap nhat log tool o ben phai.</p>
              </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        return

    for turn in st.session_state.turns:
        with st.chat_message(turn["role"]):
            st.caption(turn.get("meta", turn["role"]))
            st.write(turn["content"])


def handle_prompt(provider_name: str, version: str, model: str | None, max_tool_rounds: int) -> None:
    prompt = st.chat_input("Nhap cau hoi cho Research Agent...")
    if st.session_state.pending_prompt:
        prompt = st.session_state.pending_prompt
        st.session_state.pending_prompt = None

    if prompt:
        with st.spinner("Agent dang chay tool va tong hop cau tra loi..."):
            run_agent_turn(prompt, provider_name, version, model, max_tool_rounds)
        st.rerun()


def main() -> None:
    st.set_page_config(page_title="Research Agent", page_icon=None, layout="wide")
    init_state()
    apply_styles()

    tool_declarations = load_tool_declarations(ARTIFACTS_DIR / "tools.yaml")
    left_col, chat_col, right_col = st.columns([0.23, 0.52, 0.25], gap="medium")

    with left_col:
        st.markdown('<p class="panel-label">Control</p>', unsafe_allow_html=True)
        provider_name, version, model, max_tool_rounds = render_parameter_panel(tool_declarations)

    with chat_col:
        render_header()
        render_status_badges()
        render_samples()
        render_chat()

    with right_col:
        st.markdown('<p class="panel-label">Log ben phai</p>', unsafe_allow_html=True)
        thought_tab, trace_tab = st.tabs(["Log tu duy", "Trace JSON"])
        with thought_tab:
            render_thought_log()
        with trace_tab:
            render_trace_json()

    handle_prompt(provider_name, version, model, max_tool_rounds)


if __name__ == "__main__":
    main()
