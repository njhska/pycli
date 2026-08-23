import base64

import pytest

from gemini_cli.commands import normalize_mime_type, parse_attachment, parse_command


def test_parse_multiline_system_command() -> None:
    command = parse_command("/system 第一行\n第二行")
    assert command is not None
    assert command.name == "system"
    assert command.argument == "第一行\n第二行"


def test_non_command() -> None:
    assert parse_command("hello /model x") is None


def test_parse_attachment() -> None:
    encoded = base64.b64encode(b"image").decode()
    attachment = parse_attachment(f"--base64 {encoded} --type .png")
    assert attachment.data == b"image"
    assert attachment.mime_type == "image/png"


def test_invalid_attachment() -> None:
    with pytest.raises(ValueError, match="Base64"):
        parse_attachment("--base64 not-base64 --type image/png")


@pytest.mark.parametrize(
    ("value", "expected"),
    [("png", "image/png"), (".pdf", "application/pdf"), ("image/jpeg", "image/jpeg")],
)
def test_normalize_mime_type(value: str, expected: str) -> None:
    assert normalize_mime_type(value) == expected

