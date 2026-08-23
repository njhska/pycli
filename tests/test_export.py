from gemini_cli.export import safe_filename


def test_safe_filename() -> None:
    assert safe_filename('问题/回答:\n"测试"') == "问题_回答___测试_"


def test_safe_filename_fallback() -> None:
    assert safe_filename("...") == "未命名对话"

