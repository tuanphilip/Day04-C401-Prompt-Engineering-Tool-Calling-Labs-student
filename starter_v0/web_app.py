from __future__ import annotations

import argparse
import json
import re
import threading
import uuid
from datetime import datetime
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from chat import now_iso, run_model_tool_loop, trim_history, write_transcript
from env_loader import load_lab_env
from providers import make_provider
from tools import load_tool_declarations, to_openai_tools
from versioning import artifact_version_dict, build_artifact_version


ROOT = Path(__file__).parent
ARTIFACTS_DIR = ROOT / "artifacts"
TRANSCRIPTS_DIR = ROOT / "transcripts"
load_lab_env(ROOT)


INDEX_HTML = r"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Research Agent</title>
  <style>
    :root {
      --bg: #f6f7f4;
      --panel: #ffffff;
      --panel-2: #f0f3ef;
      --ink: #17201a;
      --muted: #647067;
      --line: #d9dfd8;
      --accent: #0f766e;
      --accent-2: #164e63;
      --warn: #b45309;
      --danger: #b91c1c;
      --ok: #15803d;
      --shadow: 0 16px 40px rgba(23, 32, 26, 0.08);
      color-scheme: light;
      font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
    }

    * { box-sizing: border-box; }

    body {
      margin: 0;
      min-height: 100vh;
      color: var(--ink);
      background: var(--bg);
    }

    button, input, select, textarea {
      font: inherit;
    }

    .app {
      display: grid;
      grid-template-rows: 54px minmax(0, 1fr);
      min-height: 100vh;
    }

    header {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 16px;
      padding: 0 18px;
      border-bottom: 1px solid var(--line);
      background: rgba(255, 255, 255, 0.86);
      backdrop-filter: blur(12px);
    }

    .brand {
      display: flex;
      align-items: center;
      gap: 10px;
      min-width: 0;
    }

    .mark {
      width: 28px;
      height: 28px;
      border: 1px solid #0f766e;
      border-radius: 6px;
      display: grid;
      place-items: center;
      color: var(--accent);
      font-weight: 800;
      line-height: 1;
    }

    h1 {
      margin: 0;
      font-size: 17px;
      line-height: 1.2;
      font-weight: 760;
      letter-spacing: 0;
      white-space: nowrap;
      overflow: hidden;
      text-overflow: ellipsis;
    }

    .statusbar {
      display: flex;
      align-items: center;
      justify-content: flex-end;
      gap: 8px;
      min-width: 0;
      color: var(--muted);
      font-size: 13px;
    }

    .pill {
      display: inline-flex;
      align-items: center;
      gap: 6px;
      min-height: 26px;
      padding: 3px 8px;
      border: 1px solid var(--line);
      border-radius: 999px;
      background: var(--panel);
      color: var(--muted);
      white-space: nowrap;
    }

    .dot {
      width: 7px;
      height: 7px;
      border-radius: 999px;
      background: var(--warn);
    }

    .dot.ok { background: var(--ok); }
    .dot.err { background: var(--danger); }

    main {
      display: grid;
      grid-template-columns: minmax(220px, 280px) minmax(360px, 1fr) minmax(260px, 360px);
      gap: 12px;
      min-height: 0;
      padding: 12px;
    }

    aside, section {
      min-height: 0;
      border: 1px solid var(--line);
      border-radius: 8px;
      background: var(--panel);
      box-shadow: var(--shadow);
    }

    .left, .right {
      display: flex;
      flex-direction: column;
      overflow: hidden;
    }

    .pane-head {
      display: flex;
      align-items: center;
      justify-content: space-between;
      min-height: 42px;
      padding: 10px 12px;
      border-bottom: 1px solid var(--line);
      background: var(--panel-2);
      font-size: 13px;
      font-weight: 720;
    }

    .pane-body {
      padding: 12px;
      overflow: auto;
    }

    label {
      display: block;
      margin: 0 0 6px;
      color: var(--muted);
      font-size: 12px;
      font-weight: 680;
    }

    select, input[type="text"], input[type="number"] {
      width: 100%;
      height: 36px;
      border: 1px solid var(--line);
      border-radius: 6px;
      padding: 0 10px;
      background: #fff;
      color: var(--ink);
      outline: none;
    }

    select:focus, input:focus, textarea:focus {
      border-color: var(--accent);
      box-shadow: 0 0 0 3px rgba(15, 118, 110, 0.12);
    }

    .field { margin-bottom: 12px; }

    .metrics {
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 8px;
      margin-top: 12px;
    }

    .metric {
      border: 1px solid var(--line);
      border-radius: 6px;
      padding: 9px;
      background: #fbfcfa;
    }

    .metric strong {
      display: block;
      font-size: 18px;
      line-height: 1.1;
    }

    .metric span {
      color: var(--muted);
      font-size: 11px;
    }

    .tool-list {
      display: flex;
      flex-wrap: wrap;
      gap: 6px;
      margin-top: 8px;
    }

    .tool-chip {
      padding: 4px 7px;
      border: 1px solid var(--line);
      border-radius: 999px;
      color: var(--accent-2);
      background: #f8faf8;
      font-size: 12px;
      white-space: nowrap;
    }

    .chat {
      display: grid;
      grid-template-rows: minmax(0, 1fr) auto;
      overflow: hidden;
    }

    .messages {
      overflow: auto;
      padding: 18px;
    }

    .empty {
      height: 100%;
      display: grid;
      place-items: center;
      color: var(--muted);
      text-align: center;
    }

    .empty h2 {
      margin: 0 0 6px;
      color: var(--ink);
      font-size: 22px;
      letter-spacing: 0;
    }

    .empty p {
      max-width: 520px;
      margin: 0;
      font-size: 14px;
      line-height: 1.55;
    }

    .message {
      max-width: 880px;
      margin: 0 0 12px;
      display: flex;
      flex-direction: column;
      gap: 5px;
    }

    .message.user {
      margin-left: auto;
      align-items: flex-end;
    }

    .bubble {
      max-width: min(760px, 100%);
      padding: 10px 12px;
      border: 1px solid var(--line);
      border-radius: 8px;
      background: #fff;
      white-space: pre-wrap;
      line-height: 1.5;
      font-size: 14px;
    }

    .user .bubble {
      border-color: #0f766e;
      background: #e8f5f1;
    }

    .meta {
      color: var(--muted);
      font-size: 11px;
    }

    .composer {
      display: grid;
      grid-template-columns: minmax(0, 1fr) auto;
      gap: 10px;
      padding: 12px;
      border-top: 1px solid var(--line);
      background: var(--panel-2);
    }

    textarea {
      width: 100%;
      min-height: 46px;
      max-height: 180px;
      resize: vertical;
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 12px;
      background: #fff;
      color: var(--ink);
      outline: none;
      line-height: 1.45;
    }

    .actions {
      display: flex;
      flex-direction: column;
      gap: 8px;
    }

    button {
      min-width: 82px;
      height: 38px;
      border: 1px solid var(--line);
      border-radius: 6px;
      background: #fff;
      color: var(--ink);
      cursor: pointer;
      font-weight: 700;
    }

    button.primary {
      border-color: var(--accent);
      background: var(--accent);
      color: #fff;
    }

    button:disabled {
      cursor: wait;
      opacity: 0.65;
    }

    .trace-list {
      display: flex;
      flex-direction: column;
      gap: 8px;
    }

    details {
      border: 1px solid var(--line);
      border-radius: 6px;
      background: #fbfcfa;
      overflow: hidden;
    }

    summary {
      cursor: pointer;
      padding: 8px 10px;
      font-size: 13px;
      font-weight: 720;
      color: var(--accent-2);
    }

    pre {
      margin: 0;
      padding: 10px;
      overflow: auto;
      max-height: 280px;
      border-top: 1px solid var(--line);
      background: #17201a;
      color: #eef7ef;
      font-size: 12px;
      line-height: 1.5;
    }

    .notice {
      padding: 9px 10px;
      border: 1px solid #f1c27d;
      border-radius: 6px;
      background: #fff7ed;
      color: #7c2d12;
      font-size: 12px;
      line-height: 1.45;
      margin-top: 10px;
    }

    .muted {
      color: var(--muted);
      font-size: 12px;
      line-height: 1.45;
    }

    @media (max-width: 1080px) {
      main {
        grid-template-columns: 240px minmax(0, 1fr);
      }
      .right {
        display: none;
      }
    }

    @media (max-width: 760px) {
      .app {
        grid-template-rows: auto minmax(0, 1fr);
      }
      header {
        align-items: flex-start;
        flex-direction: column;
        padding: 12px;
      }
      .statusbar {
        width: 100%;
        justify-content: flex-start;
        flex-wrap: wrap;
      }
      main {
        grid-template-columns: 1fr;
        padding: 8px;
      }
      .left {
        max-height: 280px;
      }
      .composer {
        grid-template-columns: 1fr;
      }
      .actions {
        flex-direction: row;
      }
      button {
        flex: 1;
      }
    }
  </style>
</head>
<body>
  <div class="app">
    <header>
      <div class="brand">
        <div class="mark">R</div>
        <h1>Research Agent</h1>
      </div>
      <div class="statusbar">
        <span class="pill"><span id="envDot" class="dot"></span><span id="envText">Checking env</span></span>
        <span class="pill" id="artifactText">version</span>
        <span class="pill" id="transcriptText">transcript</span>
      </div>
    </header>

    <main>
      <aside class="left">
        <div class="pane-head">Run</div>
        <div class="pane-body">
          <div class="field">
            <label for="provider">Provider</label>
            <select id="provider">
              <option value="openrouter" selected>OpenRouter</option>
              <option value="openai">OpenAI</option>
              <option value="anthropic">Anthropic</option>
              <option value="gemini">Gemini</option>
            </select>
          </div>
          <div class="field">
            <label for="version">Version</label>
            <input id="version" type="text" value="v3">
          </div>
          <div class="field">
            <label for="model">Model</label>
            <input id="model" type="text" placeholder="provider default">
          </div>
          <div class="field">
            <label for="rounds">Tool rounds</label>
            <input id="rounds" type="number" min="1" max="8" value="4">
          </div>
          <button id="resetBtn">Reset</button>

          <div class="metrics">
            <div class="metric"><strong id="toolCount">0</strong><span>tools</span></div>
            <div class="metric"><strong id="turnCount">0</strong><span>turns</span></div>
          </div>

          <div class="notice" id="envNotice" hidden></div>

          <div class="field" style="margin-top: 14px;">
            <label>Tools</label>
            <div id="tools" class="tool-list"></div>
          </div>
        </div>
      </aside>

      <section class="chat">
        <div id="messages" class="messages">
          <div class="empty">
            <div>
              <h2>Ready</h2>
              <p>Ask for web research, social search, URL summaries, policy lookup, paper search, source audit, or publication confirmation.</p>
            </div>
          </div>
        </div>
        <form id="composer" class="composer">
          <textarea id="message" placeholder="Ask the research agent..." required></textarea>
          <div class="actions">
            <button class="primary" id="sendBtn" type="submit">Send</button>
            <button id="clearBtn" type="button">Clear</button>
          </div>
        </form>
      </section>

      <aside class="right">
        <div class="pane-head">Trace</div>
        <div class="pane-body">
          <div id="trace" class="trace-list">
            <div class="muted">No tool calls yet.</div>
          </div>
        </div>
      </aside>
    </main>
  </div>

  <script>
    const state = {
      sessionId: localStorage.getItem("researchAgentSession") || "",
      turns: 0,
      busy: false
    };

    const els = {
      messages: document.getElementById("messages"),
      trace: document.getElementById("trace"),
      composer: document.getElementById("composer"),
      message: document.getElementById("message"),
      sendBtn: document.getElementById("sendBtn"),
      clearBtn: document.getElementById("clearBtn"),
      resetBtn: document.getElementById("resetBtn"),
      provider: document.getElementById("provider"),
      version: document.getElementById("version"),
      model: document.getElementById("model"),
      rounds: document.getElementById("rounds"),
      envDot: document.getElementById("envDot"),
      envText: document.getElementById("envText"),
      envNotice: document.getElementById("envNotice"),
      artifactText: document.getElementById("artifactText"),
      transcriptText: document.getElementById("transcriptText"),
      toolCount: document.getElementById("toolCount"),
      turnCount: document.getElementById("turnCount"),
      tools: document.getElementById("tools")
    };

    function escapeHtml(value) {
      return String(value)
        .replaceAll("&", "&amp;")
        .replaceAll("<", "&lt;")
        .replaceAll(">", "&gt;")
        .replaceAll('"', "&quot;")
        .replaceAll("'", "&#039;");
    }

    function pretty(value) {
      return JSON.stringify(value, null, 2);
    }

    function setBusy(busy) {
      state.busy = busy;
      els.sendBtn.disabled = busy;
      els.message.disabled = busy;
      els.sendBtn.textContent = busy ? "Running" : "Send";
    }

    function appendMessage(role, text, meta) {
      const empty = els.messages.querySelector(".empty");
      if (empty) empty.remove();

      const item = document.createElement("div");
      item.className = `message ${role}`;
      item.innerHTML = `
        <div class="meta">${escapeHtml(meta || role)}</div>
        <div class="bubble">${escapeHtml(text || "")}</div>
      `;
      els.messages.appendChild(item);
      els.messages.scrollTop = els.messages.scrollHeight;
    }

    function renderTrace(rounds, events) {
      els.trace.innerHTML = "";
      if ((!rounds || !rounds.length) && (!events || !events.length)) {
        els.trace.innerHTML = '<div class="muted">No tool calls yet.</div>';
        return;
      }
      (rounds || []).forEach((round) => {
        const details = document.createElement("details");
        details.open = true;
        details.innerHTML = `
          <summary>Round ${round.round}: ${(round.tool_calls || []).map((c) => c.name).join(", ") || "answer"}</summary>
          <pre>${escapeHtml(pretty(round))}</pre>
        `;
        els.trace.appendChild(details);
      });
      if (events && events.length) {
        const details = document.createElement("details");
        details.innerHTML = `<summary>Tool events</summary><pre>${escapeHtml(pretty(events))}</pre>`;
        els.trace.appendChild(details);
      }
    }

    async function loadStatus() {
      const resp = await fetch("/api/status");
      const data = await resp.json();

      els.toolCount.textContent = data.tools.length;
      els.tools.innerHTML = data.tools.map((name) => `<span class="tool-chip">${escapeHtml(name)}</span>`).join("");
      els.artifactText.textContent = data.artifact_version || "v3";

      const missing = Object.entries(data.env || {}).filter(([, ok]) => !ok).map(([key]) => key);
      if (missing.length) {
        els.envDot.className = "dot";
        els.envText.textContent = "Env partial";
        els.envNotice.hidden = false;
        els.envNotice.textContent = "Missing optional or provider keys: " + missing.join(", ");
      } else {
        els.envDot.className = "dot ok";
        els.envText.textContent = "Env ready";
        els.envNotice.hidden = true;
      }
    }

    async function sendMessage(text) {
      setBusy(true);
      appendMessage("user", text, "You");
      try {
        const resp = await fetch("/api/chat", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            session_id: state.sessionId,
            message: text,
            provider: els.provider.value,
            version: els.version.value,
            model: els.model.value,
            max_tool_rounds: Number(els.rounds.value || 4)
          })
        });
        const data = await resp.json();
        if (!resp.ok) throw new Error(data.error || "Request failed");

        state.sessionId = data.session_id;
        localStorage.setItem("researchAgentSession", state.sessionId);
        state.turns = data.turn_index;
        els.turnCount.textContent = state.turns;
        els.artifactText.textContent = data.artifact_version;
        els.transcriptText.textContent = data.transcript_file ? data.transcript_file.split(/[\\/]/).pop() : "transcript";
        appendMessage("assistant", data.assistant_text || "", data.status || "Agent");
        renderTrace(data.rounds, data.tool_events);
      } catch (error) {
        appendMessage("assistant", error.message, "Error");
      } finally {
        setBusy(false);
        els.message.focus();
      }
    }

    async function resetSession() {
      if (state.sessionId) {
        await fetch("/api/reset", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ session_id: state.sessionId })
        });
      }
      state.sessionId = "";
      state.turns = 0;
      localStorage.removeItem("researchAgentSession");
      els.turnCount.textContent = "0";
      els.transcriptText.textContent = "transcript";
      els.messages.innerHTML = `
        <div class="empty">
          <div>
            <h2>Ready</h2>
            <p>Ask for web research, social search, URL summaries, policy lookup, paper search, source audit, or publication confirmation.</p>
          </div>
        </div>`;
      renderTrace([], []);
      els.message.focus();
    }

    els.composer.addEventListener("submit", (event) => {
      event.preventDefault();
      const text = els.message.value.trim();
      if (!text || state.busy) return;
      els.message.value = "";
      sendMessage(text);
    });

    els.clearBtn.addEventListener("click", () => { els.message.value = ""; els.message.focus(); });
    els.resetBtn.addEventListener("click", resetSession);

    els.message.addEventListener("keydown", (event) => {
      if (event.key === "Enter" && (event.ctrlKey || event.metaKey)) {
        els.composer.requestSubmit();
      }
    });

    loadStatus().catch((error) => {
      els.envDot.className = "dot err";
      els.envText.textContent = "Status error";
      els.envNotice.hidden = false;
      els.envNotice.textContent = error.message;
    });
  </script>
</body>
</html>
"""


def safe_slug(value: str) -> str:
    slug = re.sub(r"[^A-Za-z0-9_.-]+", "_", value.strip())
    return slug.strip("_") or "run"


def json_response(handler: BaseHTTPRequestHandler, payload: Any, status: int = 200) -> None:
    body = json.dumps(payload, ensure_ascii=False, default=str).encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Content-Length", str(len(body)))
    handler.end_headers()
    handler.wfile.write(body)


def text_response(handler: BaseHTTPRequestHandler, body: str, status: int = 200, content_type: str = "text/html; charset=utf-8") -> None:
    data = body.encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", content_type)
    handler.send_header("Content-Length", str(len(data)))
    handler.end_headers()
    handler.wfile.write(data)


def read_json(handler: BaseHTTPRequestHandler) -> dict[str, Any]:
    length = int(handler.headers.get("Content-Length", "0") or "0")
    if length <= 0:
        return {}
    raw = handler.rfile.read(length)
    return json.loads(raw.decode("utf-8"))


class SessionStore:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._sessions: dict[str, dict[str, Any]] = {}

    def get_or_create(self, session_id: str | None, *, provider_name: str, version: str, model: str | None, max_tool_rounds: int) -> dict[str, Any]:
        with self._lock:
            if session_id and session_id in self._sessions:
                return self._sessions[session_id]

            sid = session_id or uuid.uuid4().hex
            system_prompt_path = ARTIFACTS_DIR / "system_prompt.md"
            tools_path = ARTIFACTS_DIR / "tools.yaml"
            artifact_version = build_artifact_version(version, system_prompt_path, tools_path)
            timestamp = datetime.now().strftime("%Y%m%dT%H%M%S%f")
            transcript_id = "_".join([safe_slug(version), safe_slug(provider_name), "web", timestamp])
            transcript_path = TRANSCRIPTS_DIR / f"{transcript_id}.transcript.json"
            transcript = {
                "transcript_id": transcript_id,
                **artifact_version_dict(artifact_version),
                "provider": provider_name,
                "model": model,
                "system_prompt": str(system_prompt_path),
                "tools": str(tools_path),
                "history_window": 5,
                "max_tool_rounds": max_tool_rounds,
                "created_at": now_iso(),
                "updated_at": now_iso(),
                "turns": [],
                "source": "web_app",
            }
            session = {
                "session_id": sid,
                "history": [],
                "turn_index": 0,
                "transcript": transcript,
                "transcript_path": transcript_path,
                "artifact_version": artifact_version,
            }
            self._sessions[sid] = session
            write_transcript(transcript_path, transcript)
            return session

    def remove(self, session_id: str | None) -> bool:
        if not session_id:
            return False
        with self._lock:
            return self._sessions.pop(session_id, None) is not None


class WebApp:
    def __init__(self) -> None:
        self.sessions = SessionStore()

    def status(self) -> dict[str, Any]:
        tool_declarations = load_tool_declarations(ARTIFACTS_DIR / "tools.yaml")
        artifact = build_artifact_version("v3", ARTIFACTS_DIR / "system_prompt.md", ARTIFACTS_DIR / "tools.yaml")
        env = {
            "OPENROUTER_API_KEY": bool(__import__("os").getenv("OPENROUTER_API_KEY")),
            "TAVILY_API_KEY": bool(__import__("os").getenv("TAVILY_API_KEY")),
            "FIRECRAWL_API_KEY": bool(__import__("os").getenv("FIRECRAWL_API_KEY")),
            "RAPIDAPI_KEY": bool(__import__("os").getenv("RAPIDAPI_KEY")),
            "RAPIDAPI_TWITTER_HOST": bool(__import__("os").getenv("RAPIDAPI_TWITTER_HOST")),
        }
        return {
            "artifact_version": artifact.artifact_version,
            "tools": [tool["name"] for tool in tool_declarations],
            "env": env,
        }

    def chat(self, payload: dict[str, Any]) -> dict[str, Any]:
        user_text = str(payload.get("message") or "").strip()
        if not user_text:
            raise ValueError("Message is required.")

        provider_name = str(payload.get("provider") or "openrouter")
        version = str(payload.get("version") or "v3")
        model = str(payload.get("model") or "").strip() or None
        max_tool_rounds = max(1, min(int(payload.get("max_tool_rounds") or 4), 8))
        session = self.sessions.get_or_create(
            str(payload.get("session_id") or "") or None,
            provider_name=provider_name,
            version=version,
            model=model,
            max_tool_rounds=max_tool_rounds,
        )

        system_prompt = (ARTIFACTS_DIR / "system_prompt.md").read_text(encoding="utf-8")
        tool_declarations = load_tool_declarations(ARTIFACTS_DIR / "tools.yaml")
        openai_tools = to_openai_tools(tool_declarations)
        provider = make_provider(provider_name)

        messages = [
            {"role": "system", "content": system_prompt},
            *trim_history(session["history"], 5),
            {"role": "user", "content": user_text},
        ]

        session["turn_index"] += 1
        turn_record: dict[str, Any] = {
            "turn_index": session["turn_index"],
            "started_at": now_iso(),
            "user": user_text,
            "status": "started",
            "assistant_text": None,
            "rounds": [],
            "tool_events": [],
        }

        result = run_model_tool_loop(
            provider=provider,
            messages=messages,
            tools=openai_tools,
            model=model,
            max_tool_rounds=max_tool_rounds,
        )
        turn_record.update(result)
        turn_record["ended_at"] = now_iso()

        assistant_text = result["assistant_text"]
        session["history"].append({"role": "user", "content": user_text})
        session["history"].append({"role": "assistant", "content": assistant_text})
        session["transcript"]["turns"].append(turn_record)
        write_transcript(session["transcript_path"], session["transcript"])

        return {
            "session_id": session["session_id"],
            "turn_index": session["turn_index"],
            "artifact_version": session["artifact_version"].artifact_version,
            "transcript_file": str(session["transcript_path"]),
            **result,
        }


APP = WebApp()


class Handler(BaseHTTPRequestHandler):
    server_version = "ResearchAgentWeb/1.0"

    def log_message(self, fmt: str, *args: Any) -> None:
        print(f"{self.address_string()} - {fmt % args}")

    def do_GET(self) -> None:
        path = urlparse(self.path).path
        if path == "/":
            text_response(self, INDEX_HTML)
            return
        if path == "/api/status":
            json_response(self, APP.status())
            return
        text_response(self, "Not found", HTTPStatus.NOT_FOUND, "text/plain; charset=utf-8")

    def do_POST(self) -> None:
        path = urlparse(self.path).path
        try:
            payload = read_json(self)
            if path == "/api/chat":
                json_response(self, APP.chat(payload))
                return
            if path == "/api/reset":
                json_response(self, {"removed": APP.sessions.remove(payload.get("session_id"))})
                return
            json_response(self, {"error": "Not found"}, HTTPStatus.NOT_FOUND)
        except Exception as exc:
            json_response(self, {"error": f"{type(exc).__name__}: {exc}"}, HTTPStatus.INTERNAL_SERVER_ERROR)


def main() -> None:
    parser = argparse.ArgumentParser(description="Research Agent web UI.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=7860)
    args = parser.parse_args()

    server = ThreadingHTTPServer((args.host, args.port), Handler)
    print(f"Research Agent web UI running at http://{args.host}:{args.port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print()
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
