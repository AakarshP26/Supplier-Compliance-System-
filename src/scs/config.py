"""Central runtime configuration.

Loaded once on import; reads from environment with sane defaults so the
project still runs without a .env file (using mock LLM + bundled data).
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:  # pragma: no cover - dev convenience only
    pass


def _bool_env(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class Config:
    anthropic_api_key: str | None
    use_mock_llm: bool
    data_dir: Path

    @property
    def news_dir(self) -> Path:
        return self.data_dir / "news"

    @property
    def reference_dir(self) -> Path:
        return self.data_dir / "reference"

    @property
    def suppliers_file(self) -> Path:
        return self.data_dir / "seed_suppliers.json"


def _resolve_data_dir() -> Path:
    raw = os.getenv("SCS_DATA_DIR", "./data")
    p = Path(raw).expanduser().resolve()
    return p


CONFIG = Config(
    anthropic_api_key=os.getenv("ANTHROPIC_API_KEY") or None,
    use_mock_llm=_bool_env("USE_MOCK_LLM", default=True),
    data_dir=_resolve_data_dir(),
)
