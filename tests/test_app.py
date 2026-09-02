from datetime import datetime, timezone
from io import StringIO

from rich.console import Console

import gemini_cli.app as app_module
from gemini_cli.app import Application, SessionState
from gemini_cli.commands import Command
from gemini_cli.models import Conversation, Message, PendingAttachment


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


def test_display_user_message_renders_markdown_in_panel(monkeypatch) -> None:
    output = StringIO()
    test_console = Console(file=output, color_system=None, width=60)
    monkeypatch.setattr(app_module, "console", test_console)

    Application.display_user_message("# 标题\n\n- 第一项\n- 第二项")

    rendered = output.getvalue()
    assert "你（Markdown）" in rendered
    assert "标题" in rendered
    assert "• 第一项" in rendered
    assert "• 第二项" in rendered
    assert "╭" in rendered


def test_new_command_resets_conversation_to_defaults() -> None:
    application = Application.__new__(Application)
    application.settings = type(
        "Settings", (), {"default_model": "default-model", "websearch_default": False}
    )()
    application.state = SessionState(
        model="other-model",
        system_prompt="old prompt",
        websearch=True,
        conversation=object(),  # type: ignore[arg-type]
        attachments=[PendingAttachment(data=b"data", mime_type="text/plain")],
    )

    application.handle_command(Command("new"))

    assert application.state.conversation is None
    assert application.state.model == "default-model"
    assert application.state.system_prompt is None
    assert application.state.websearch is False
    assert application.state.attachments == []
