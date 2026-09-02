from __future__ import annotations

import sys
from dataclasses import dataclass, field

import psycopg
from prompt_toolkit import PromptSession
from prompt_toolkit.formatted_text import HTML
from prompt_toolkit.key_binding import KeyBindings
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.table import Table

from .commands import Command, parse_attachment, parse_command
from .config import Settings
from .database import Database
from .export import export_markdown
from .gemini import GeminiService
from .models import Conversation, Message, PendingAttachment


console = Console()


@dataclass
class SessionState:
    model: str
    system_prompt: str | None
    websearch: bool
    conversation: Conversation | None = None
    attachments: list[PendingAttachment] = field(default_factory=list)


def make_prompt_session() -> PromptSession[str]:
    bindings = KeyBindings()

    @bindings.add("escape", "enter")
    def submit(event) -> None:
        event.current_buffer.validate_and_handle()

    return PromptSession(
        multiline=True,
        key_bindings=bindings,
        prompt_continuation=lambda width, line_number, is_soft_wrap: "... ",
    )


class Application:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.database = Database(settings.database_kwargs)
        self.gemini = GeminiService(settings)
        self.prompt = make_prompt_session()
        self.state = SessionState(
            model=settings.default_model,
            system_prompt=None,
            websearch=settings.websearch_default,
        )

    def run(self) -> None:
        self.database.initialize()
        console.print(
            f"Gemini CLI · 模型 [cyan]{self.state.model}[/cyan] · "
            f"Web Search [cyan]{'on' if self.state.websearch else 'off'}[/cyan]"
        )
        console.print("Enter 换行，Esc+Enter 发送，Ctrl+C 清空输入，Ctrl+D 退出。")

        try:
            while True:
                try:
                    text = self.prompt.prompt(HTML("<ansigreen>你 › </ansigreen>"))
                except KeyboardInterrupt:
                    continue
                except EOFError:
                    break
                if not text.strip():
                    continue

                command = parse_command(text)
                if command:
                    self.handle_command(command)
                else:
                    self.chat(text)
        finally:
            self.gemini.close()

    def _persist_settings(self) -> None:
        if self.state.conversation:
            self.database.update_conversation_settings(
                self.state.conversation.id,
                model=self.state.model,
                system_prompt=self.state.system_prompt,
                websearch=self.state.websearch,
            )
            refreshed = self.database.get_conversation(self.state.conversation.id)
            if refreshed:
                self.state.conversation = refreshed

    def handle_command(self, command: Command) -> None:
        try:
            if command.name == "system":
                self.state.system_prompt = command.argument or None
                self._persist_settings()
                console.print("[green]System prompt 已更新。[/green]")
            elif command.name == "websearch":
                value = command.argument.strip().lower()
                if value not in {"on", "off"}:
                    raise ValueError("用法: /websearch on|off")
                self.state.websearch = value == "on"
                self._persist_settings()
                console.print(f"[green]Web Search 已{('开启' if self.state.websearch else '关闭')}。[/green]")
            elif command.name == "model":
                model = command.argument.strip()
                if not model:
                    raise ValueError("用法: /model <模型名称>")
                self.state.model = model
                self._persist_settings()
                console.print(f"[green]模型已切换为 {model}。[/green]")
            elif command.name == "file":
                attachment = parse_attachment(command.argument)
                self.state.attachments.append(attachment)
                console.print(
                    f"[green]附件已暂存：{attachment.mime_type}，"
                    f"{len(attachment.data)} bytes。[/green]"
                )
            elif command.name == "resume":
                self.resume(command.argument.strip())
            elif command.name == "new":
                if command.argument.strip():
                    raise ValueError("用法: /new")
                self.new_conversation()
            elif command.name == "save":
                self.save()
            elif command.name in {"help", "?"}:
                self.show_help()
            else:
                raise ValueError(f"未知命令: /{command.name}，输入 /help 查看帮助")
        except ValueError as exc:
            console.print(f"[red]{exc}[/red]")
        except Exception as exc:
            console.print(f"[red]命令执行失败：{exc}[/red]")

    def resume(self, argument: str) -> None:
        if not argument:
            conversations = self.database.list_conversations()
            if not conversations:
                console.print("[yellow]还没有历史对话。[/yellow]")
                return
            table = Table("ID", "主题", "模型", "Web", "更新时间")
            for item in conversations:
                table.add_row(
                    str(item.id),
                    item.title,
                    item.model,
                    "on" if item.websearch else "off",
                    item.updated_at.astimezone().strftime("%Y-%m-%d %H:%M:%S"),
                )
            console.print(table)
            return

        if argument == "last":
            conversation = self.database.get_last_conversation()
        else:
            try:
                conversation_id = int(argument)
            except ValueError as exc:
                raise ValueError("用法: /resume、/resume <id> 或 /resume last") from exc
            conversation = self.database.get_conversation(conversation_id)

        if conversation is None:
            raise ValueError("没有找到指定对话")
        self.state.conversation = conversation
        self.state.model = conversation.model
        self.state.system_prompt = conversation.system_prompt
        self.state.websearch = conversation.websearch
        self.state.attachments.clear()
        console.print(
            f"[green]已恢复 #{conversation.id}：{conversation.title}[/green]"
        )
        messages = self.database.get_messages(conversation.id)
        self.display_history(conversation, messages)

    def new_conversation(self) -> None:
        self.state.conversation = None
        self.state.model = self.settings.default_model
        self.state.system_prompt = None
        self.state.websearch = self.settings.websearch_default
        self.state.attachments.clear()
        console.print(
            f"[green]已启动新对话。[/green] 模型 [cyan]{self.state.model}[/cyan] · "
            f"Web Search [cyan]{'on' if self.state.websearch else 'off'}[/cyan]"
        )

    @staticmethod
    def display_user_message(content: str) -> None:
        console.print(
            Panel(
                Markdown(content),
                title="[bold cyan]你（Markdown）[/bold cyan]",
                title_align="left",
                border_style="cyan",
                padding=(0, 1),
            )
        )

    @staticmethod
    def display_history(
        conversation: Conversation,
        messages: list[Message],
    ) -> None:
        console.rule(f"[bold]#{conversation.id} {conversation.title}[/bold]")
        console.print(
            f"[dim]模型：{conversation.model} · "
            f"Web Search：{'on' if conversation.websearch else 'off'}[/dim]"
        )
        if conversation.system_prompt:
            console.print("\n[bold yellow]System prompt[/bold yellow]")
            console.print(Markdown(conversation.system_prompt))

        if not messages:
            console.print("[yellow]该对话还没有消息。[/yellow]")
            return

        for message in messages:
            if message.role == "user":
                console.print()
                Application.display_user_message(message.content)
                continue
            elif message.role == "assistant":
                console.print("\n[bold magenta]Gemini（Markdown）[/bold magenta]")
            else:
                console.print("\n[bold yellow]System[/bold yellow]")
            console.print(Markdown(message.content))

            if message.role == "assistant":
                tokens = (
                    f"输入 {message.prompt_tokens if message.prompt_tokens is not None else '-'} · "
                    f"输出 {message.completion_tokens if message.completion_tokens is not None else '-'} · "
                    f"总计 {message.total_tokens if message.total_tokens is not None else '-'}"
                )
                search = "是" if message.websearch_used else "否"
                console.print(
                    f"[dim]Token：{tokens} · 调用 Web Search：{search}[/dim]"
                )
        console.rule("[dim]历史记录结束[/dim]")

    def save(self) -> None:
        conversation = self.state.conversation
        if not conversation:
            raise ValueError("当前还没有可保存的对话")
        messages = self.database.get_messages(conversation.id)
        path = export_markdown(self.settings.save_dir, conversation, messages)
        console.print(f"[green]已保存到 {path}[/green]")

    def chat(self, user_text: str) -> None:
        console.print()
        self.display_user_message(user_text)
        console.print("\n[bold magenta]Gemini（流式）[/bold magenta]")

        history = []
        if self.state.conversation:
            history = self.database.get_messages(self.state.conversation.id)

        def write_chunk(chunk: str) -> None:
            console.print(chunk, end="", markup=False, highlight=False, soft_wrap=True)

        try:
            result = self.gemini.stream_reply(
                model=self.state.model,
                history=history,
                user_text=user_text,
                system_prompt=self.state.system_prompt,
                websearch=self.state.websearch,
                attachments=self.state.attachments,
                on_text=write_chunk,
            )
        except Exception as exc:
            console.print(f"\n[red]请求失败：{exc}[/red]")
            console.print("[yellow]附件仍保留，可直接重试。[/yellow]")
            return

        console.print()
        if not result.text:
            console.print("[yellow]模型没有返回文本内容。[/yellow]")

        console.print("\n[bold magenta]Gemini（Markdown）[/bold magenta]")
        console.print(Markdown(result.text))

        if self.state.conversation is None:
            self.state.conversation = self.database.create_conversation(
                title=user_text[:20],
                model=self.state.model,
                system_prompt=self.state.system_prompt,
                websearch=self.state.websearch,
            )
            console.print(
                f"[dim]已创建对话 #{self.state.conversation.id}："
                f"{self.state.conversation.title}[/dim]"
            )

        self.database.save_turn(
            self.state.conversation.id,
            user_text=user_text,
            assistant_text=result.text,
            model=self.state.model,
            websearch_enabled=self.state.websearch,
            result=result,
        )
        self.state.attachments.clear()

        tokens = (
            f"输入 {result.prompt_tokens if result.prompt_tokens is not None else '-'} · "
            f"输出 {result.completion_tokens if result.completion_tokens is not None else '-'} · "
            f"总计 {result.total_tokens if result.total_tokens is not None else '-'}"
        )
        search = "是" if result.websearch_used else "否"
        console.print(f"[dim]Token：{tokens} · 调用 Web Search：{search}[/dim]")

    @staticmethod
    def show_help() -> None:
        console.print(
            """
[bold]/system <内容>[/bold]       设置当前对话的 system prompt
[bold]/websearch on|off[/bold]    开启或关闭当前对话的 Google Search
[bold]/file --base64 X --type T[/bold]  为下一轮暂存附件
[bold]/resume[/bold]              列出历史对话
[bold]/resume <id>|last[/bold]    恢复历史对话
[bold]/new[/bold]                 启动新对话
[bold]/model <名称>[/bold]        切换当前对话模型
[bold]/save[/bold]                覆盖保存当前对话 Markdown
[bold]/help[/bold]                显示帮助
""".strip()
        )


def main() -> None:
    try:
        settings = Settings.from_env()
        Application(settings).run()
    except (ValueError, OSError) as exc:
        console.print(f"[red]启动失败：{exc}[/red]")
        sys.exit(1)
    except psycopg.Error as exc:
        console.print(f"[red]数据库错误：{exc}[/red]")
        sys.exit(1)


if __name__ == "__main__":
    main()
