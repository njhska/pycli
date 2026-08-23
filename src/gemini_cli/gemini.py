from __future__ import annotations

from collections.abc import Callable, Sequence

from google import genai
from google.genai import types

from .config import Settings
from .models import GenerationResult, Message, PendingAttachment


class GeminiService:
    def __init__(self, settings: Settings) -> None:
        options = types.HttpOptions(api_version=settings.gemini_api_version)
        if settings.gemini_base_url:
            options.base_url = settings.gemini_base_url
        self.client = genai.Client(
            api_key=settings.gemini_api_key,
            http_options=options,
        )

    def close(self) -> None:
        self.client.close()

    def stream_reply(
        self,
        *,
        model: str,
        history: Sequence[Message],
        user_text: str,
        system_prompt: str | None,
        websearch: bool,
        attachments: Sequence[PendingAttachment],
        on_text: Callable[[str], None],
    ) -> GenerationResult:
        contents: list[types.Content] = []
        for message in history:
            role = "model" if message.role == "assistant" else "user"
            contents.append(
                types.Content(
                    role=role,
                    parts=[types.Part.from_text(text=message.content)],
                )
            )

        current_parts: list[types.Part] = [
            types.Part.from_bytes(data=item.data, mime_type=item.mime_type)
            for item in attachments
        ]
        current_parts.append(types.Part.from_text(text=user_text))
        contents.append(types.Content(role="user", parts=current_parts))

        config = types.GenerateContentConfig(system_instruction=system_prompt)
        if websearch:
            config.tools = [types.Tool(google_search=types.GoogleSearch())]

        chunks: list[str] = []
        prompt_tokens = None
        completion_tokens = None
        total_tokens = None
        websearch_used = False
        search_queries: list[str] = []

        for chunk in self.client.models.generate_content_stream(
            model=model,
            contents=contents,
            config=config,
        ):
            text = chunk.text or ""
            if text:
                chunks.append(text)
                on_text(text)

            usage = chunk.usage_metadata
            if usage:
                prompt_tokens = usage.prompt_token_count or prompt_tokens
                completion_tokens = usage.candidates_token_count or completion_tokens
                total_tokens = usage.total_token_count or total_tokens

            for candidate in chunk.candidates or []:
                grounding = candidate.grounding_metadata
                if grounding:
                    queries = list(grounding.web_search_queries or [])
                    if queries or grounding.grounding_chunks:
                        websearch_used = True
                    for query in queries:
                        if query not in search_queries:
                            search_queries.append(query)

        return GenerationResult(
            text="".join(chunks),
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens,
            websearch_used=websearch_used,
            search_queries=search_queries,
        )

