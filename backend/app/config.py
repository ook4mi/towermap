"""Application configuration loaded from environment variables and .env."""

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

_ROOT_ENV = Path(__file__).resolve().parents[2] / ".env"


class Settings(BaseSettings):
    """TowerMap runtime configuration."""

    model_config = SettingsConfigDict(
        env_file=(str(_ROOT_ENV), ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # General
    app_env: str = "development"
    mock_mode: bool = True
    cache_ttl_seconds: int = 15
    default_domain: str = "ook4mi.ovh"
    tower_host_ips: str = "192.168.68.62,127.0.0.1,localhost,tower"
    suggest_port_start: int = 4010
    suggest_port_end: int = 4099
    http_timeout_seconds: float = 5.0
    static_dir: str | None = None

    # Docker (used when MOCK_MODE=false)
    docker_host: str | None = None

    # Gluetun (optional)
    gluetun_url: str | None = None
    gluetun_api_key: str | None = None

    # Nginx Proxy Manager (optional)
    npm_url: str | None = None
    npm_identity: str | None = None
    npm_secret: str | None = None

    # Technitium DNS (optional)
    technitium_url: str | None = None
    technitium_api_token: str | None = None

    @property
    def tower_hosts(self) -> set[str]:
        """Normalized set of hostnames/IPs considered local to tower."""
        return {
            item.strip().lower()
            for item in self.tower_host_ips.split(",")
            if item.strip()
        }

    @property
    def mode_label(self) -> str:
        return "mock" if self.mock_mode else "live"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return cached Settings instance."""
    return Settings()
