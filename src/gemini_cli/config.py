from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


def _as_bool(value: str) -> bool:
    normalized = value.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    raise ValueError(f"无法识别的布尔值: {value}")


@dataclass(frozen=True)
class Settings:
    gemini_api_key: str
    gemini_base_url: str | None
    gemini_api_version: str
    default_model: str
    websearch_default: bool
    save_dir: Path
    db_host: str
    db_port: int
    db_user: str
    db_password: str
    db_name: str
    db_sslmode: str

    @classmethod
    def from_env(cls) -> "Settings":
        load_dotenv()
        key = os.getenv("GEMINI_API_KEY", "").strip()
        if not key:
            raise ValueError("缺少 GEMINI_API_KEY 环境变量")

        base_url = os.getenv("GEMINI_BASE_URL", "").strip() or None
        return cls(
            gemini_api_key=key,
            gemini_base_url=base_url,
            gemini_api_version=os.getenv("GEMINI_API_VERSION", "v1beta").strip(),
            default_model=os.getenv(
                "PYCLI_DEFAULT_MODEL", "gemini-2.5-flash"
            ).strip(),
            websearch_default=_as_bool(
                os.getenv("PYCLI_WEBSEARCH_DEFAULT", "true")
            ),
            save_dir=Path(os.getenv("PYCLI_SAVE_DIR", "./conversations"))
            .expanduser()
            .resolve(),
            db_host=os.getenv("PYCLI_DB_HOST", "127.0.0.1"),
            db_port=int(os.getenv("PYCLI_DB_PORT", "5432")),
            db_user=os.getenv("PYCLI_DB_USER", "postgres"),
            db_password=os.getenv("PYCLI_DB_PASSWORD", ""),
            db_name=os.getenv("PYCLI_DB_NAME", "postgres"),
            db_sslmode=os.getenv("PYCLI_DB_SSLMODE", "prefer"),
        )

    @property
    def database_kwargs(self) -> dict[str, object]:
        return {
            "host": self.db_host,
            "port": self.db_port,
            "user": self.db_user,
            "password": self.db_password,
            "dbname": self.db_name,
            "sslmode": self.db_sslmode,
        }

