from datetime import datetime, timezone
from io import StringIO

from rich.console import Console

import gemini_cli.app as app_module
from gemini_cli.app import Application
from gemini_cli.models import Conversation, Message


def test_display_history_renders_all_messages(monkeypatch) -> None:
    output = StringIO()
    test_console = Console(file=output, color_system=None, width=100)
    monkeypatch.setattr(app_module, "console", test_console)
    now = datetime.now(timezone.utc)
    conversation = Conversation(
        id=7,
        title="测试主题",
        model="gemini-2.5-flash",
        system_prompt="你是助手",
        websearch=True,
        created_at=now,
        updated_at=now,
    )
    messages = [
        Message(
            id=1,
            conversation_id=7,
            role="user",
            content="# 用户问题",
            sequence_no=1,
        ),
        Message(
            id=2,
            conversation_id=7,
            role="assistant",
            content="**完整回答**",
            sequence_no=2,
            prompt_tokens=10,
            completion_tokens=5,
            total_tokens=15,
            websearch_used=True,
        ),
    ]

    Application.display_history(conversation, messages)

    rendered = output.getvalue()
    assert "#7 测试主题" in rendered
    assert "你是助手" in rendered
    assert "用户问题" in rendered
    assert "完整回答" in rendered
    assert "总计 15" in rendered
    assert "调用 Web Search：是" in rendered

