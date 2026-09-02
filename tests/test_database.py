from gemini_cli.database import Database


class FakeCursor:
    def __init__(self) -> None:
        self.query = ""
        self.parameters: tuple[object, ...] = ()

    def __enter__(self):
        return self

    def __exit__(self, *args) -> None:
        pass

    def execute(self, query: str, parameters: tuple[object, ...]) -> None:
        self.query = " ".join(query.split())
        self.parameters = parameters

    def fetchall(self) -> list[object]:
        return []


class FakeConnection:
    def __init__(self, cursor: FakeCursor) -> None:
        self.test_cursor = cursor

    def __enter__(self):
        return self

    def __exit__(self, *args) -> None:
        pass

    def cursor(self, **kwargs) -> FakeCursor:
        return self.test_cursor


def test_list_conversations_orders_by_id_ascending(monkeypatch) -> None:
    database = Database({})
    cursor = FakeCursor()
    monkeypatch.setattr(database, "connect", lambda: FakeConnection(cursor))

    assert database.list_conversations(limit=25) == []
    assert "ORDER BY id ASC" in cursor.query
    assert cursor.parameters == (25,)
