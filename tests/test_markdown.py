from io import StringIO

import pytest
from rich.console import Console

import gemini_cli.markdown as markdown_module
from gemini_cli.markdown import Markdown


def render(markup: str, width: int = 100) -> str:
    output = StringIO()
    Console(file=output, color_system=None, width=width).print(Markdown(markup))
    return output.getvalue()


@pytest.mark.parametrize("fence", ["```", "~~~"])
def test_mermaid_flowchart_renders_nodes_and_arrows(fence: str) -> None:
    rendered = render(
        f"前文 **说明**\n\n{fence}mermaid\n"
        "flowchart TD\nA[开始] --> B{通过}\n"
        "B -->|是| C[完成]\nB -->|否| D[重试]\n"
        f"{fence}\n\n后文\n"
    )

    for text in ("前文 说明", "开始", "通过", "是", "否", "完成", "重试", "后文"):
        assert text in rendered
    assert "▼" in rendered
    assert "flowchart TD" not in rendered
    assert "-->" not in rendered
    assert "暂无法渲染" not in rendered


def test_mermaid_inside_blockquote_is_rendered() -> None:
    rendered = render(
        "> ```mermaid\n> graph LR\n> A[Start] --> B[End]\n> ```"
    )
    assert "Start" in rendered and "End" in rendered
    assert "graph LR" not in rendered
    assert "-->" not in rendered


def test_normal_code_and_inline_code_are_not_interpreted_as_diagrams() -> None:
    markup = "```text\ngraph LR; A --> B\n```\n\n`A --> B`"
    rendered = render(markup)
    assert "graph LR; A --> B" in rendered
    assert rendered.count("A --> B") == 2


def test_renderer_failure_preserves_source_and_following_text(monkeypatch) -> None:
    def fail(*args, **kwargs):
        raise ValueError("unsupported syntax")

    monkeypatch.setattr(markdown_module, "render_mermaid", fail)
    rendered = render("```mermaid\ngraph LR; A --> B\n```\n\n后续回答")
    assert "暂无法渲染" in rendered
    assert "graph LR; A --> B" in rendered
    assert "后续回答" in rendered


def test_wide_diagram_preserves_source_instead_of_clipping_nodes() -> None:
    rendered = render(
        "```mermaid\ngraph LR\nA[First] --> B[Second] --> C[Last]\n```",
        width=25,
    )
    assert "超出终端宽度" in rendered
    assert "First" in rendered and "Second" in rendered and "Last" in rendered
