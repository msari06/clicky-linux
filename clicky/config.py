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

    # --- Claude Code (Code mode) -----------------------------------------------
    claude_code_path: str = Field(
        default="claude",
        description="Path to the `claude` CLI. Override if not on PATH.",
    )
    claude_code_workspace: str = Field(
        default=str(PROJECT_ROOT),
        description=(
            "Default working directory for Code mode. Override per-prompt with "
            "an `@/path/to/dir` prefix in the input. Defaults to the Clicky repo "
            "itself so Clicky can hack on its own source out of the box."
        ),
    )
    claude_code_model: str = Field(
        default="",
        description="Optional model alias (e.g. 'sonnet', 'opus'). Empty = Claude Code default.",
    )
    claude_code_max_turns: int = Field(
        default=0,
        description="Hard cap on agent turns per prompt. 0 = no cap (let Claude Code decide).",
    )

    def chat_endpoint(self) -> str:
        return f"{self.worker_url.rstrip('/')}/chat"


settings = Settings()
