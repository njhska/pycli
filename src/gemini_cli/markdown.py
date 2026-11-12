from __future__ import annotations

from rich.cells import cell_len
from rich.console import Console, ConsoleOptions, RenderResult
from rich.markdown import CodeBlock, Markdown as RichMarkdown
from rich.text import Text
from termaid import render as render_mermaid


class DiagramCodeBlock(CodeBlock):
    """Render Mermaid fences as terminal diagrams; keep other code unchanged."""

    def __rich_console__(
        self, console: Console, options: ConsoleOptions
    ) -> RenderResult:
        if self.lexer_name.lower() != "mermaid":
            yield from super().__rich_console__(console, options)
            return

        try:
            diagram = render_mermaid(
                self.text.plain, padding_x=1, padding_y=0, gap=2
            )
            if not diagram.strip():
                raise ValueError("empty diagram")
        except Exception:
            # A malformed / unsupported diagram must not hide the rest of a reply.
            yield Text("Mermaid 图暂无法渲染，以下保留源码。", style="yellow")
            yield from super().__rich_console__(console, options)
            return

        if max(map(cell_len, diagram.splitlines()), default=0) > options.max_width:
            yield Text("Mermaid 图超出终端宽度，请加宽窗口；以下保留源码。", style="yellow")
            yield from super().__rich_console__(console, options)
            return

        yield Text(diagram, no_wrap=True, overflow="crop")


class Markdown(RichMarkdown):
    """Rich Markdown with local Mermaid rendering, including nested fences."""

    elements = {**RichMarkdown.elements, "fence": DiagramCodeBlock}
