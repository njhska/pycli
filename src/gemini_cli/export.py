from __future__ import annotations

import re
from pathlib import Path

from .models import Conversation, Message


def safe_filename(title: str) -> str:
    name = re.sub(r"[\\/:*?\"<>|\r\n\x00-\x1f]", "_", title).strip(" .")
    return name or "未命名对话"


def export_markdown(
    save_dir: Path,
    conversation: Conversation,
    messages: list[Message],
) -> Path:
    save_dir.mkdir(parents=True, exist_ok=True)
    path = save_dir / f"{safe_filename(conversation.title)}.md"
    sections = [f"# {conversation.title}", ""]
    for message in messages:
        label = "用户" if message.role == "user" else "Gemini"
        sections.extend([f"## {label}", "", message.content, ""])
    path.write_text("\n".join(sections).rstrip() + "\n", encoding="utf-8")
    return path

