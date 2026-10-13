from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse


PROJECT_ROOT = Path(__file__).resolve().parent.parent


def load_dotenv(path: Path) -> None:
    if not path.exists():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        os.environ.setdefault(key, value)


def _project_path(root: Path, name: str, default: str) -> Path:
    configured = Path(os.getenv(name, default))
    return configured if configured.is_absolute() else root / configured


@dataclass(frozen=True, slots=True)
class Settings:
    project_root: Path
    proxy_url: str
    proxy_check_url: str
    lookback_hours: int
    max_items_per_source: int
    feed_config: Path
    social_inbox: Path
    database_path: Path
    output_root: Path

    def validate(self) -> None:
        parsed = urlparse(self.proxy_url)
        if parsed.scheme not in {"http", "https"} or not parsed.hostname or not parsed.port:
            raise ValueError("AI_NEWS_PROXY 必须是包含主机和端口的 HTTP/HTTPS URL")
        if self.lookback_hours < 1:
            raise ValueError("AI_NEWS_LOOKBACK_HOURS 必须大于 0")
        if self.max_items_per_source < 1:
            raise ValueError("AI_NEWS_MAX_ITEMS_PER_SOURCE 必须大于 0")


def get_settings(project_root: Path | None = None) -> Settings:
    root = (project_root or PROJECT_ROOT).resolve()
    load_dotenv(root / ".env")
    settings = Settings(
        project_root=root,
        proxy_url=os.getenv("AI_NEWS_PROXY", "http://127.0.0.1:7897"),
        proxy_check_url=os.getenv("AI_NEWS_PROXY_CHECK_URL", "https://api.ipify.org?format=json"),
        lookback_hours=int(os.getenv("AI_NEWS_LOOKBACK_HOURS", "72")),
        max_items_per_source=int(os.getenv("AI_NEWS_MAX_ITEMS_PER_SOURCE", "25")),
        feed_config=root / "config" / "feeds.json",
        social_inbox=_project_path(
            root,
            "AI_NEWS_SOCIAL_INBOX",
            "input/social-links.md",
        ),
        database_path=_project_path(root, "AI_NEWS_DATABASE_PATH", "data/ai_news.db"),
        output_root=root / "output",
    )
    settings.validate()
    return settings
