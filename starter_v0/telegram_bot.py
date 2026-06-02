from __future__ import annotations

import argparse
import json
import os
import re
import time
from datetime import datetime
from pathlib import Path
from typing import Any

import requests

from chat import now_iso, run_model_tool_loop, trim_history, write_transcript
from env_loader import load_lab_env
from providers import make_provider
from tools import load_tool_declarations, to_openai_tools
from versioning import artifact_version_dict, build_artifact_version


ROOT = Path(__file__).parent
ARTIFACTS_DIR = ROOT / "artifacts"
TRANSCRIPTS_DIR = ROOT / "transcripts"
TELEGRAM_API = "https://api.telegram.org/bot{token}/{method}"
MAX_TELEGRAM_CHARS = 3900
load_lab_env(ROOT)


TOOL_GUIDE = {
    "clarify": "Ask for missing information or confirmation.",
    "timeline": "Recent posts from one specific account/person.",
    "social_search": "Search posts by topic or keyword.",
    "lookup": "Search web/news.",
    "fetch": "Read or summarize a specific URL.",
    "format": "Format already-collected items.",
    "send": "Post to configured Telegram channel after confirmation.",
    "policy": "Search internal company policy.",
    "papers": "Search arXiv papers.",
    "paper_text": "Extract text from an arXiv paper.",
    "source_audit": "Check citations/sources before publishing.",
}


def safe_slug(value: str) -> str:
    slug = re.sub(r"[^A-Za-z0-9_.-]+", "_", value.strip())
    return slug.strip("_") or "run"


def telegram_request(token: str, method: str, **payload: Any) -> dict[str, Any]:
    response = requests.post(TELEGRAM_API.format(token=token, method=method), json=payload, timeout=60)
    response.raise_for_status()
    data = response.json()
    if not data.get("ok"):
        raise RuntimeError(json.dumps(data, ensure_ascii=False))
    return data


def split_message(text: str, limit: int = MAX_TELEGRAM_CHARS) -> list[str]:
    text = text or ""
    if len(text) <= limit:
        return [text]
    chunks: list[str] = []
    remaining = text
    while len(remaining) > limit:
        cut = remaining.rfind("\n", 0, limit)
        if cut < limit // 2:
            cut = limit
        chunks.append(remaining[:cut].strip())
        remaining = remaining[cut:].strip()
    if remaining:
        chunks.append(remaining)
    return chunks


def send_message(token: str, chat_id: int | str, text: str) -> None:
    for chunk in split_message(text):
        telegram_request(token, "sendMessage", chat_id=chat_id, text=chunk, disable_web_page_preview=True)


def load_allowed_chat_ids() -> set[str]:
    raw = os.getenv("TELEGRAM_ALLOWED_CHAT_IDS", "").strip()
    if not raw:
        return set()
    return {item.strip() for item in raw.split(",") if item.strip()}


class TelegramAgentBot:
    def __init__(
        self,
        *,
        token: str,
        provider_name: str,
        version: str,
        model: str | None,
        max_tool_rounds: int,
    ) -> None:
        self.token = token
        self.provider_name = provider_name
        self.version = version
        self.model = model
        self.max_tool_rounds = max_tool_rounds
        self.allowed_chat_ids = load_allowed_chat_ids()
        self.sessions: dict[str, dict[str, Any]] = {}

    def session_for(self, chat_id: int | str) -> dict[str, Any]:
        sid = str(chat_id)
        if sid in self.sessions:
            return self.sessions[sid]

        system_prompt_path = ARTIFACTS_DIR / "system_prompt.md"
        tools_path = ARTIFACTS_DIR / "tools.yaml"
        artifact_version = build_artifact_version(self.version, system_prompt_path, tools_path)
        timestamp = datetime.now().strftime("%Y%m%dT%H%M%S%f")
        transcript_id = "_".join([safe_slug(self.version), safe_slug(self.provider_name), "telegram", safe_slug(sid), timestamp])
        transcript_path = TRANSCRIPTS_DIR / f"{transcript_id}.transcript.json"
        transcript = {
            "transcript_id": transcript_id,
            **artifact_version_dict(artifact_version),
            "provider": self.provider_name,
            "model": self.model,
            "system_prompt": str(system_prompt_path),
            "tools": str(tools_path),
            "history_window": 5,
            "max_tool_rounds": self.max_tool_rounds,
            "created_at": now_iso(),
            "updated_at": now_iso(),
            "turns": [],
            "source": "telegram_bot",
            "telegram_chat_id": sid,
        }
        session = {
            "history": [],
            "turn_index": 0,
            "transcript": transcript,
            "transcript_path": transcript_path,
            "artifact_version": artifact_version,
        }
        self.sessions[sid] = session
        write_transcript(transcript_path, transcript)
        return session

    def tool_help(self) -> str:
        names = [tool["name"] for tool in load_tool_declarations(ARTIFACTS_DIR / "tools.yaml")]
        lines = ["Available research tools:"]
        for name in names:
            lines.append(f"- {name}: {TOOL_GUIDE.get(name, 'Available tool.')}")
        lines += [
            "",
            "Examples:",
            "- Tin AI hom nay co gi noi bat?",
            "- Tom tat link nay: https://openai.com/research/",
            "- Moi nguoi noi gi ve GPT-5 tren Twitter?",
            "- Tim paper arXiv ve AI agent evaluation.",
            "- Kiem tra ban tin nay da du citation/source de publish chua: ...",
        ]
        return "\n".join(lines)

    def status_text(self) -> str:
        token_ok = ":" in self.token and len(self.token) >= 30
        keys = {
            "OPENROUTER_API_KEY": bool(os.getenv("OPENROUTER_API_KEY")),
            "TAVILY_API_KEY": bool(os.getenv("TAVILY_API_KEY")),
            "FIRECRAWL_API_KEY": bool(os.getenv("FIRECRAWL_API_KEY")),
            "RAPIDAPI_KEY": bool(os.getenv("RAPIDAPI_KEY")),
            "TELEGRAM_BOT_TOKEN": token_ok,
            "TELEGRAM_CHAT_ID": bool(os.getenv("TELEGRAM_CHAT_ID")),
        }
        return "\n".join([f"{name}: {'OK' if ok else 'missing/invalid'}" for name, ok in keys.items()])

    def handle_command(self, chat_id: int | str, text: str) -> bool:
        command = text.split()[0].split("@")[0].lower()
        if command in {"/start", "/help"}:
            send_message(
                self.token,
                chat_id,
                "Research Agent is ready.\n\n"
                "Commands:\n"
                "/tools - show available tools\n"
                "/status - check environment\n"
                "/reset - clear this chat memory\n"
                "/help - show this message\n\n"
                "Send any research question to chat with the agent.",
            )
            return True
        if command == "/tools":
            send_message(self.token, chat_id, self.tool_help())
            return True
        if command == "/status":
            send_message(self.token, chat_id, self.status_text())
            return True
        if command == "/reset":
            self.sessions.pop(str(chat_id), None)
            send_message(self.token, chat_id, "Memory reset for this chat.")
            return True
        return False

    def handle_message(self, message: dict[str, Any]) -> None:
        chat = message.get("chat") or {}
        chat_id = chat.get("id")
        text = (message.get("text") or "").strip()
        if not chat_id or not text:
            return

        sid = str(chat_id)
        if self.allowed_chat_ids and sid not in self.allowed_chat_ids:
            send_message(self.token, chat_id, "This chat is not allowed to use this bot.")
            return

        if text.startswith("/") and self.handle_command(chat_id, text):
            return

        session = self.session_for(chat_id)
        system_prompt = (ARTIFACTS_DIR / "system_prompt.md").read_text(encoding="utf-8")
        tool_declarations = load_tool_declarations(ARTIFACTS_DIR / "tools.yaml")
        openai_tools = to_openai_tools(tool_declarations)
        provider = make_provider(self.provider_name)

        messages = [
            {"role": "system", "content": system_prompt},
            *trim_history(session["history"], 5),
            {"role": "user", "content": text},
        ]

        session["turn_index"] += 1
        turn_record: dict[str, Any] = {
            "turn_index": session["turn_index"],
            "started_at": now_iso(),
            "user": text,
            "status": "started",
            "assistant_text": None,
            "rounds": [],
            "tool_events": [],
        }

        try:
            telegram_request(self.token, "sendChatAction", chat_id=chat_id, action="typing")
            result = run_model_tool_loop(
                provider=provider,
                messages=messages,
                tools=openai_tools,
                model=self.model,
                max_tool_rounds=self.max_tool_rounds,
            )
            turn_record.update(result)
            assistant_text = result.get("assistant_text") or ""
            tool_names = [
                call.get("name")
                for round_record in result.get("rounds", [])
                for call in round_record.get("tool_calls", [])
            ]
            prefix = f"Tools: {', '.join(tool_names)}\n\n" if tool_names else ""
            send_message(self.token, chat_id, prefix + assistant_text)
            session["history"].append({"role": "user", "content": text})
            session["history"].append({"role": "assistant", "content": assistant_text})
        except Exception as exc:
            turn_record.update({"status": "error", "error": f"{type(exc).__name__}: {exc}"})
            send_message(self.token, chat_id, f"Error: {type(exc).__name__}: {exc}")
        finally:
            turn_record["ended_at"] = now_iso()
            session["transcript"]["turns"].append(turn_record)
            write_transcript(session["transcript_path"], session["transcript"])

    def poll_forever(self) -> None:
        offset: int | None = None
        me = telegram_request(self.token, "getMe")["result"]
        print(f"Telegram bot running as @{me.get('username')} ({me.get('first_name')})")
        while True:
            try:
                data = telegram_request(self.token, "getUpdates", offset=offset, timeout=30, allowed_updates=["message"])
                for update in data.get("result", []):
                    offset = int(update["update_id"]) + 1
                    message = update.get("message")
                    if message:
                        self.handle_message(message)
            except KeyboardInterrupt:
                raise
            except Exception as exc:
                print(f"Polling error: {type(exc).__name__}: {exc}")
                time.sleep(5)


def check_env() -> int:
    token = os.getenv("TELEGRAM_BOT_TOKEN", "")
    checks = {
        "TELEGRAM_BOT_TOKEN set": bool(token),
        "TELEGRAM_BOT_TOKEN contains colon": ":" in token,
        "OPENROUTER_API_KEY set": bool(os.getenv("OPENROUTER_API_KEY")),
        "TAVILY_API_KEY set": bool(os.getenv("TAVILY_API_KEY")),
        "FIRECRAWL_API_KEY set": bool(os.getenv("FIRECRAWL_API_KEY")),
        "RAPIDAPI_KEY set": bool(os.getenv("RAPIDAPI_KEY")),
    }
    for name, ok in checks.items():
        print(f"{name}: {'OK' if ok else 'FAIL'}")
    if os.getenv("TELEGRAM_CHAT_ID"):
        print("TELEGRAM_CHAT_ID set: OK")
    else:
        print("TELEGRAM_CHAT_ID set: optional for chat replies, required for send tool")
    return 0 if all(checks.values()) else 1


def main() -> None:
    parser = argparse.ArgumentParser(description="Telegram interface for the research agent.")
    parser.add_argument("--provider", choices=["openrouter", "openai", "anthropic", "gemini"], default="openrouter")
    parser.add_argument("--model", default=None)
    parser.add_argument("--version", default="v3")
    parser.add_argument("--max-tool-rounds", type=int, default=4)
    parser.add_argument("--check-env", action="store_true")
    args = parser.parse_args()

    if args.check_env:
        raise SystemExit(check_env())

    token = os.getenv("TELEGRAM_BOT_TOKEN", "")
    if not token:
        raise SystemExit("Missing TELEGRAM_BOT_TOKEN in .env")
    if ":" not in token:
        raise SystemExit("Invalid TELEGRAM_BOT_TOKEN: keep the BotFather token as one value in the form id:characters.")

    bot = TelegramAgentBot(
        token=token,
        provider_name=args.provider,
        version=args.version,
        model=args.model,
        max_tool_rounds=max(1, min(args.max_tool_rounds, 8)),
    )
    bot.poll_forever()


if __name__ == "__main__":
    main()
