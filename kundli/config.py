"""Centralized configuration — all tunables in one place.

Values are read from environment variables with sensible defaults.
For production, set these in .env or your deployment environment.
"""

import os
from dataclasses import dataclass, field


def _env(key: str, default: str) -> str:
    return os.environ.get(key, default)


def _env_int(key: str, default: int) -> int:
    return int(os.environ.get(key, str(default)))


def _env_float(key: str, default: float) -> float:
    return float(os.environ.get(key, str(default)))


def _env_bool(key: str, default: bool) -> bool:
    val = os.environ.get(key, str(default)).lower()
    return val in ("1", "true", "yes")


@dataclass(frozen=True)
class ServerConfig:
    host: str = field(default_factory=lambda: _env("KUNDLI_HOST", "0.0.0.0"))
    port: int = field(default_factory=lambda: _env_int("KUNDLI_PORT", 8000))
    reload: bool = field(default_factory=lambda: _env_bool("KUNDLI_RELOAD", False))
    workers: int = field(default_factory=lambda: _env_int("KUNDLI_WORKERS", 1))
    log_level: str = field(default_factory=lambda: _env("KUNDLI_LOG_LEVEL", "info"))


@dataclass(frozen=True)
class AppConfig:
    debug: bool = field(default_factory=lambda: _env_bool("KUNDLI_DEBUG", False))
    default_lang: str = field(default_factory=lambda: _env("KUNDLI_DEFAULT_LANG", "mr"))
    default_utc_offset: float = field(default_factory=lambda: _env_float("KUNDLI_DEFAULT_UTC_OFFSET", 5.5))
    cors_origins: list[str] = field(default_factory=lambda: _env("KUNDLI_CORS_ORIGINS", "*").split(","))


@dataclass(frozen=True)
class LimitsConfig:
    max_year_range: int = field(default_factory=lambda: _env_int("KUNDLI_MAX_YEAR_RANGE", 20))
    min_year: int = field(default_factory=lambda: _env_int("KUNDLI_MIN_YEAR", 1900))
    max_year: int = field(default_factory=lambda: _env_int("KUNDLI_MAX_YEAR", 2100))
    rate_limit_per_minute: int = field(default_factory=lambda: _env_int("KUNDLI_RATE_LIMIT", 60))


@dataclass(frozen=True)
class Settings:
    server: ServerConfig = field(default_factory=ServerConfig)
    app: AppConfig = field(default_factory=AppConfig)
    limits: LimitsConfig = field(default_factory=LimitsConfig)


# Singleton — import this everywhere
settings = Settings()
