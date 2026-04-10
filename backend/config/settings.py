"""Configuration settings from environment."""

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass
class Settings:
    """Application settings."""

    vt_api_key: str
    offline_only: bool
    nmap_path: str


def get_settings() -> Settings:
    """Load settings from environment variables."""
    # Try to load .env file if it exists
    try:
        from dotenv import load_dotenv

        env_path = Path(".env")
        if env_path.exists():
            load_dotenv(env_path)
    except ImportError:
        pass

    return Settings(
        vt_api_key=os.getenv("VT_API_KEY", ""),
        offline_only=os.getenv("OFFLINE_ONLY", "false").lower() == "true",
        nmap_path=os.getenv("NMAP_PATH", ""),
    )
