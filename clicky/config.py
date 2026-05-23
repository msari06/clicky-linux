from __future__ import annotations

from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


PROJECT_ROOT = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=PROJECT_ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    worker_url: str = Field(
        default="http://localhost:8787",
        description="Cloudflare Worker proxy base URL (no trailing slash).",
    )
    openai_model: str = Field(default="gpt-4o-mini")
    hotkey: str = Field(
        default="<ctrl>+<alt>+<space>",
        description=(
            "pynput-style global hotkey to open the input overlay. "
            "Examples: '<ctrl>+<alt>+<space>', '<ctrl>+<shift>+c', '<f12>'. "
            "Modifier-only combos (just ctrl+alt) are not supported reliably on Linux."
        ),
    )

    max_tokens: int = Field(default=1024)

    def chat_endpoint(self) -> str:
        return f"{self.worker_url.rstrip('/')}/chat"


settings = Settings()
