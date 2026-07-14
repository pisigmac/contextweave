"""Configuration management for ContextWeave."""
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import List


@dataclass
class WeaveConfig:
    """Application configuration."""

    # Database
    database_url: str = field(default_factory=lambda: os.getenv(
        "WEAVE_DATABASE_URL",
        "sqlite:///weave.db"
    ))

    # Workspace
    workspace_dir: Path = field(default_factory=lambda: Path(
        os.getenv("WEAVE_WORKSPACE_DIR", ".")
    ))

    # API
    api_host: str = field(default_factory=lambda: os.getenv("API_HOST", "0.0.0.0"))
    api_port: int = field(default_factory=lambda: int(os.getenv("API_PORT", "8000")))

    # Search
    search_limit: int = field(default_factory=lambda: int(os.getenv("SEARCH_LIMIT", "50")))

    # Sync
    sync_interval: int = field(default_factory=lambda: int(os.getenv("SYNC_INTERVAL", "30")))

    @property
    def is_sqlite(self) -> bool:
        return self.database_url.startswith("sqlite")

    def get_weave_files(self) -> List[Path]:
        """Find all .weave.md files in workspace."""
        if not self.workspace_dir.exists():
            return []
        return list(self.workspace_dir.rglob("*.weave.md"))


# Global config instance
config = WeaveConfig()
