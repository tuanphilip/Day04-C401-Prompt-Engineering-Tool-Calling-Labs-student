from __future__ import annotations

import json
import re
from datetime import datetime
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
            --bg: #071013;
            --panel: rgba(16, 27, 32, .92);
            --panel-strong: rgba(20, 35, 42, .96);
            --ink: #e7f6f2;
            --muted: #94a9b0;
            --line: rgba(148, 169, 176, .22);
            --teal: #2dd4bf;
            --cyan: #38bdf8;
            --indigo: #8b5cf6;
            --amber: #fbbf24;
            --rose: #fb7185;
            --shadow: 0 24px 80px rgba(0, 0, 0, .32);
        }
        .stApp {
            background:
                radial-gradient(circle at top left, rgba(45, 212, 191, .20), transparent 28rem),
                radial-gradient(circle at 78% 8%, rgba(139, 92, 246, .18), transparent 26rem),
                radial-gradient(circle at bottom right, rgba(56, 189, 248, .13), transparent 30rem),
                var(--bg);
            color: var(--ink);
        }
        [data-testid="stSidebar"] {
            background: rgba(5, 13, 16, .94);
            border-right: 1px solid var(--line);
        }
        [data-testid="stSidebar"] * {
            color: var(--ink);
        }
        [data-testid="stSidebar"] .stCaption, [data-testid="stSidebar"] p {
            color: var(--muted);
        }
        .main .block-container {
            max-width: 1180px;
            padding-top: 1.4rem;
            padding-bottom: 2rem;
        }
        h1, h2, h3 {
            letter-spacing: 0;
        }
        .hero {
            border: 1px solid var(--line);
            border-radius: 8px;
            padding: 18px 20px;
            background:
                linear-gradient(135deg, rgba(20, 35, 42, .96), rgba(9, 18, 22, .92)),
                var(--panel);
            box-shadow: var(--shadow);
            margin-bottom: 14px;
        }
        .hero-title {
            margin: 0;
            font-size: 28px;
            font-weight: 780;
            line-height: 1.15;
        }
        .hero-copy {
            margin: 8px 0 0;
            max-width: 820px;
            color: var(--muted);
            font-size: 15px;
            line-height: 1.5;
        }
        .metric-row {
            display: grid;
            grid-template-columns: repeat(4, minmax(0, 1fr));
            gap: 10px;
            margin: 12px 0 18px;
        }
        .metric-card {
            border: 1px solid var(--line);
            border-radius: 8px;
            padding: 12px;
            background: var(--panel);
            box-shadow: 0 12px 40px rgba(0, 0, 0, .18);
        }
        .metric-card strong {
            display: block;
            font-size: 23px;
            line-height: 1;
            color: var(--cyan);
            text-shadow: 0 0 22px rgba(56, 189, 248, .28);
        }
        .metric-card span {
            display: block;
            margin-top: 5px;
            color: var(--muted);
            font-size: 12px;
        }
        .tool-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
            gap: 8px;
        }
        .tool-card {
            border: 1px solid var(--line);
            border-radius: 8px;
            padding: 10px;
            background: var(--panel);
            min-height: 76px;
        }
        .tool-card b {
            color: var(--teal);
        }
        .tool-card p {
            margin: 4px 0 0;
            color: var(--muted);
            font-size: 12px;
            line-height: 1.35;
        }
        .trace-box {
            border: 1px solid var(--line);
            border-radius: 8px;
            background: var(--panel);
            padding: 10px 12px;
            margin-bottom: 10px;
        }
        .small-muted {
            color: var(--muted);
            font-size: 12px;
        }
        div[data-testid="stChatMessage"] {
            border: 1px solid var(--line);
            border-radius: 8px;
            background: rgba(16, 27, 32, .78);
            box-shadow: 0 12px 38px rgba(0, 0, 0, .16);
        }
        div[data-testid="stChatMessage"] p {
            color: var(--ink);
        }
        .stTextInput input,
        .stSelectbox [data-baseweb="select"],
        .stNumberInput input,
        .stTextArea textarea {
            background: rgba(7, 16, 19, .86) !important;
            color: var(--ink) !important;
            border-color: var(--line) !important;
        }
        .stButton > button {
            background: linear-gradient(135deg, rgba(45, 212, 191, .18), rgba(56, 189, 248, .12));
            border: 1px solid rgba(45, 212, 191, .38);
            color: var(--ink);
        }
        .stButton > button:hover {
            border-color: var(--teal);
            color: #ffffff;
        }
        .stAlert {
            background: rgba(20, 35, 42, .88);
            color: var(--ink);
            border: 1px solid var(--line);
        }
        pre, code {
            background: #02070a !important;
            color: #d8fff7 !important;
            border-color: var(--line) !important;
        }
        .stButton > button {
            border-radius: 6px;
            font-weight: 700;
        }
        .stChatMessage {
            border-radius: 8px;
        }
        @media (max-width: 900px) {
            .metric-row { grid-template-columns: repeat(2, minmax(0, 1fr)); }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def render_sidebar() -> tuple[str, str, str | None, int]:
    st.sidebar.title("Run")
    provider_name = st.sidebar.selectbox("Provider", ["openrouter", "openai", "anthropic", "gemini"], index=0)
    version = st.sidebar.text_input("Version", value="v3")
    model_value = st.sidebar.text_input("Model override", value="")
    max_tool_rounds = st.sidebar.slider("Tool rounds", 1, 8, 4)

    if st.sidebar.button("Reset chat", use_container_width=True):
        reset_session()
        st.rerun()

    st.sidebar.divider()
    st.sidebar.subheader("Environment")
    for key, ok in env_status().items():
        st.sidebar.write(f"{key}: {'OK' if ok else 'missing'}")

    st.sidebar.divider()
    st.sidebar.subheader("Transcript")
    if st.session_state.transcript_path:
        st.sidebar.code(str(st.session_state.transcript_path), language="text")
    else:
        st.sidebar.caption("Transcript starts after the first message.")

    return provider_name, version, model_value.strip() or None, max_tool_rounds


def render_header(tool_count: int) -> None:
    st.markdown(
        f"""
        <section class="hero">
          <h1 class="hero-title">Research Agent Workbench</h1>
          <p class="hero-copy">
            A tool-calling research agent for live web lookup, social search, URL reading,
            paper discovery, internal policy lookup, source audits, and publish-safe workflows.
          </p>
        </section>
        <div class="metric-row">
          <div class="metric-card"><strong>1.00</strong><span>base case accuracy</span></div>
          <div class="metric-card"><strong>1.00</strong><span>group eval accuracy</span></div>
          <div class="metric-card"><strong>{tool_count}</strong><span>available tools</span></div>
          <div class="metric-card"><strong>{len(st.session_state.turns) // 2}</strong><span>chat turns</span></div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_tools(tool_declarations: list[dict[str, Any]]) -> None:
    cards = []
    for tool in tool_declarations:
        name = tool["name"]
        cards.append(
            f'<div class="tool-card"><b>{name}</b><p>{TOOL_GUIDE.get(name, tool.get("description", "Available tool."))}</p></div>'
        )
    st.markdown('<div class="tool-grid">' + "".join(cards) + "</div>", unsafe_allow_html=True)


def render_trace() -> None:
    if not st.session_state.trace:
        st.info("Tool trace will appear after the first agent turn.")
        return
    for item in reversed(st.session_state.trace[-6:]):
        tool_names = [
            call.get("name")
            for round_item in item.get("rounds", [])
            for call in round_item.get("tool_calls", [])
        ]
        st.markdown(
            f'<div class="trace-box"><b>Turn {item["turn"]}</b><br><span class="small-muted">Tools: {", ".join(tool_names) if tool_names else "none"}</span></div>',
            unsafe_allow_html=True,
        )
        with st.expander(f"Trace JSON for turn {item['turn']}"):
            st.code(compact_json({"rounds": item["rounds"], "tool_events": item["tool_events"]}), language="json")


def main() -> None:
    st.set_page_config(page_title="Research Agent", page_icon=None, layout="wide")
    init_state()
    apply_styles()

    provider_name, version, model, max_tool_rounds = render_sidebar()
    tool_declarations = load_tool_declarations(ARTIFACTS_DIR / "tools.yaml")

    render_header(len(tool_declarations))

    left, right = st.columns([0.66, 0.34], gap="large")

    with right:
        st.subheader("Tools")
        render_tools(tool_declarations)
        st.subheader("Try These")
        for prompt in SAMPLE_PROMPTS:
            if st.button(prompt, use_container_width=True):
                st.session_state.pending_prompt = prompt
                st.rerun()
        st.subheader("Trace")
        render_trace()

    with left:
        st.subheader("Chat")
        if not st.session_state.turns:
            st.caption("Start with a research request. Use /tools in Telegram, or the sample prompts here, for the same tool set.")
        for turn in st.session_state.turns:
            with st.chat_message(turn["role"]):
                st.caption(turn.get("meta", turn["role"]))
                st.write(turn["content"])

        prompt = st.chat_input("Ask the research agent...")
        if st.session_state.pending_prompt:
            prompt = st.session_state.pending_prompt
            st.session_state.pending_prompt = None

        if prompt:
            with st.spinner("Running agent and tools..."):
                run_agent_turn(prompt, provider_name, version, model, max_tool_rounds)
            st.rerun()


if __name__ == "__main__":
    main()
