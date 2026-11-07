import os
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlsplit

from dotenv import load_dotenv


@dataclass(frozen=True)
class Settings:
    mode: str = "demo"
    database_path: str = "data/waste_sorting.sqlite3"
    recognition_url: str = ""
    guidance_url: str = ""
    recognition_key: str = ""
    guidance_key: str = ""
    recognition_timeout: float = 15
    guidance_timeout: float = 10

    @classmethod
    def from_env(cls):
        load_dotenv(Path(__file__).resolve().parents[2] / ".env")
        mode = os.getenv("SERVICE_MODE", "demo")
        if mode not in {"demo", "http"}:
            raise ValueError("SERVICE_MODE must be demo or http.")
        settings = cls(
            mode=mode,
            database_path=os.getenv("DATABASE_PATH", "data/waste_sorting.sqlite3"),
            recognition_url=os.getenv("RECOGNITION_API_URL", "").rstrip("/"),
            guidance_url=os.getenv("GUIDANCE_API_URL", "").rstrip("/"),
            recognition_key=os.getenv("RECOGNITION_API_KEY", ""),
            guidance_key=os.getenv("GUIDANCE_API_KEY", ""),
            recognition_timeout=float(os.getenv("RECOGNITION_TIMEOUT_SECONDS", "15")),
            guidance_timeout=float(os.getenv("GUIDANCE_TIMEOUT_SECONDS", "10")),
        )
        if min(settings.recognition_timeout, settings.guidance_timeout) <= 0:
            raise ValueError("Service timeouts must be positive.")
        allow_http = os.getenv("ALLOW_INSECURE_LOCAL_HTTP", "false").lower() == "true"
        if mode == "http":
            for url in [settings.recognition_url, settings.guidance_url]:
                parsed = urlsplit(url)
                if not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment:
                    raise ValueError("Configure valid service URLs without credentials, queries or fragments.")
                if parsed.scheme != "https" and not (allow_http and parsed.scheme == "http"):
                    raise ValueError("Configure HTTPS URLs, or explicitly enable local development HTTP.")
        return settings
