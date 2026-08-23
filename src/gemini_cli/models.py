from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class Conversation:
    id: int
    title: str
    model: str
    system_prompt: str | None
    websearch: bool
    created_at: datetime
    updated_at: datetime


@dataclass
class Message:
    id: int
    conversation_id: int
    role: str
    content: str
    sequence_no: int
    model: str | None = None
    websearch_enabled: bool | None = None
    websearch_used: bool | None = None
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    total_tokens: int | None = None
    created_at: datetime | None = None


@dataclass
class PendingAttachment:
    data: bytes
    mime_type: str


@dataclass
class GenerationResult:
    text: str
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    total_tokens: int | None = None
    websearch_used: bool = False
    search_queries: list[str] = field(default_factory=list)

