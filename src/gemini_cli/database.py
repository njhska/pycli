from __future__ import annotations

from collections.abc import Sequence

import psycopg
from psycopg.rows import class_row

from .models import Conversation, GenerationResult, Message


SCHEMA = """
CREATE TABLE IF NOT EXISTS conversations (
    id SERIAL PRIMARY KEY,
    title VARCHAR(255) NOT NULL,
    model VARCHAR(100) NOT NULL,
    system_prompt TEXT,
    websearch BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_conversations_updated_at
    ON conversations (updated_at DESC);

CREATE TABLE IF NOT EXISTS messages (
    id SERIAL PRIMARY KEY,
    conversation_id INTEGER NOT NULL
        REFERENCES conversations(id) ON DELETE CASCADE,
    role VARCHAR(20) NOT NULL,
    content TEXT NOT NULL,
    model VARCHAR(100),
    websearch_enabled BOOLEAN,
    websearch_used BOOLEAN,
    prompt_tokens INTEGER,
    completion_tokens INTEGER,
    total_tokens INTEGER,
    sequence_no INTEGER NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT chk_messages_role CHECK (role IN ('user', 'assistant', 'system')),
    CONSTRAINT uq_messages_sequence UNIQUE (conversation_id, sequence_no)
);

CREATE INDEX IF NOT EXISTS idx_messages_conversation
    ON messages (conversation_id, sequence_no);
"""


class Database:
    def __init__(self, connection_kwargs: dict[str, object]) -> None:
        self.connection_kwargs = connection_kwargs

    def connect(self) -> psycopg.Connection:
        return psycopg.connect(**self.connection_kwargs)

    def initialize(self) -> None:
        with self.connect() as conn:
            conn.execute(SCHEMA)

    def create_conversation(
        self,
        title: str,
        model: str,
        system_prompt: str | None,
        websearch: bool,
    ) -> Conversation:
        with self.connect() as conn:
            with conn.cursor(row_factory=class_row(Conversation)) as cursor:
                cursor.execute(
                    """
                    INSERT INTO conversations (title, model, system_prompt, websearch)
                    VALUES (%s, %s, %s, %s)
                    RETURNING *
                    """,
                    (title, model, system_prompt, websearch),
                )
                conversation = cursor.fetchone()
        assert conversation is not None
        return conversation

    def get_conversation(self, conversation_id: int) -> Conversation | None:
        with self.connect() as conn:
            with conn.cursor(row_factory=class_row(Conversation)) as cursor:
                cursor.execute(
                    "SELECT * FROM conversations WHERE id = %s", (conversation_id,)
                )
                return cursor.fetchone()

    def get_last_conversation(self) -> Conversation | None:
        with self.connect() as conn:
            with conn.cursor(row_factory=class_row(Conversation)) as cursor:
                cursor.execute(
                    "SELECT * FROM conversations ORDER BY updated_at DESC, id DESC LIMIT 1"
                )
                return cursor.fetchone()

    def list_conversations(self, limit: int = 100) -> list[Conversation]:
        with self.connect() as conn:
            with conn.cursor(row_factory=class_row(Conversation)) as cursor:
                cursor.execute(
                    """
                    SELECT * FROM conversations
                    ORDER BY updated_at DESC, id DESC
                    LIMIT %s
                    """,
                    (limit,),
                )
                return list(cursor.fetchall())

    def get_messages(self, conversation_id: int) -> list[Message]:
        with self.connect() as conn:
            with conn.cursor(row_factory=class_row(Message)) as cursor:
                cursor.execute(
                    """
                    SELECT * FROM messages
                    WHERE conversation_id = %s
                    ORDER BY sequence_no
                    """,
                    (conversation_id,),
                )
                return list(cursor.fetchall())

    def save_turn(
        self,
        conversation_id: int,
        user_text: str,
        assistant_text: str,
        model: str,
        websearch_enabled: bool,
        result: GenerationResult,
    ) -> None:
        with self.connect() as conn:
            next_sequence = conn.execute(
                """
                SELECT COALESCE(MAX(sequence_no), 0) + 1
                FROM messages WHERE conversation_id = %s
                """,
                (conversation_id,),
            ).fetchone()[0]
            conn.execute(
                """
                INSERT INTO messages
                    (conversation_id, role, content, sequence_no)
                VALUES (%s, 'user', %s, %s)
                """,
                (conversation_id, user_text, next_sequence),
            )
            conn.execute(
                """
                INSERT INTO messages (
                    conversation_id, role, content, model,
                    websearch_enabled, websearch_used,
                    prompt_tokens, completion_tokens, total_tokens,
                    sequence_no
                )
                VALUES (%s, 'assistant', %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    conversation_id,
                    assistant_text,
                    model,
                    websearch_enabled,
                    result.websearch_used,
                    result.prompt_tokens,
                    result.completion_tokens,
                    result.total_tokens,
                    next_sequence + 1,
                ),
            )
            conn.execute(
                "UPDATE conversations SET updated_at = NOW() WHERE id = %s",
                (conversation_id,),
            )

    def update_conversation_settings(
        self,
        conversation_id: int,
        *,
        model: str,
        system_prompt: str | None,
        websearch: bool,
    ) -> None:
        with self.connect() as conn:
            conn.execute(
                """
                UPDATE conversations
                SET model = %s, system_prompt = %s, websearch = %s,
                    updated_at = NOW()
                WHERE id = %s
                """,
                (model, system_prompt, websearch, conversation_id),
            )

