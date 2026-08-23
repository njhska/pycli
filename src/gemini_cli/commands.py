from __future__ import annotations

import base64
import binascii
import mimetypes
import shlex
from dataclasses import dataclass

from .models import PendingAttachment


@dataclass(frozen=True)
class Command:
    name: str
    argument: str = ""


def parse_command(text: str) -> Command | None:
    if not text.startswith("/"):
        return None
    head, separator, tail = text.partition(" ")
    return Command(head[1:].strip().lower(), tail if separator else "")


def parse_attachment(argument: str) -> PendingAttachment:
    try:
        tokens = shlex.split(argument)
    except ValueError as exc:
        raise ValueError(f"附件命令格式错误: {exc}") from exc

    base64_value: str | None = None
    file_type: str | None = None
    index = 0
    while index < len(tokens):
        flag = tokens[index]
        if flag not in {"--base64", "--type"}:
            raise ValueError(f"未知参数: {flag}")
        if index + 1 >= len(tokens):
            raise ValueError(f"{flag} 后缺少值")
        if flag == "--base64":
            base64_value = tokens[index + 1]
        else:
            file_type = tokens[index + 1]
        index += 2

    if not base64_value or not file_type:
        raise ValueError("用法: /file --base64 <字符串> --type <类型>")

    mime_type = normalize_mime_type(file_type)
    try:
        data = base64.b64decode(base64_value, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise ValueError("Base64 内容无效") from exc
    if not data:
        raise ValueError("附件内容不能为空")
    return PendingAttachment(data=data, mime_type=mime_type)


def normalize_mime_type(file_type: str) -> str:
    value = file_type.strip().lower()
    if "/" in value:
        return value
    suffix = value if value.startswith(".") else f".{value}"
    guessed, _ = mimetypes.guess_type(f"attachment{suffix}")
    if not guessed:
        raise ValueError(f"无法识别文件类型: {file_type}")
    return guessed

