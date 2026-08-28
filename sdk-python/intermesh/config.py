import os
import sys
from pathlib import Path
from typing import Optional

def load_env_file(dotenv_path: Optional[Path] = None) -> None:
    """Charge un fichier .env de maniere robuste et sans dependances externes."""
    if dotenv_path is None:
        intermesh_home = os.environ.get("INTERMESH_HOME")
        if intermesh_home:
            dotenv_path = Path(intermesh_home) / ".env"
        else:
            dotenv_path = Path.cwd() / ".env"
            if not dotenv_path.is_file():
                dotenv_path = Path(__file__).resolve().parents[2] / ".env"

    if dotenv_path.is_file():
        try:
            with open(dotenv_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith("#"):
                        continue
                    if "=" in line:
                        key, val = line.split("=", 1)
                        key = key.strip()
                        val = val.strip()
                        if (val.startswith('"') and val.endswith('"')) or (val.startswith("'") and val.endswith("'")):
                            val = val[1:-1]
                        if key not in os.environ:
                            os.environ[key] = val
        except Exception as e:
            print(f"Erreur lors du chargement de {dotenv_path} : {e}", file=sys.stderr)

load_env_file()

class Settings:
    """Configuration unifiee et typee pour le Hub et les SDK InterMesh."""

    @property
    def intermesh_home(self) -> Path:
        base = os.environ.get("INTERMESH_HOME")
        return Path(base) if base else Path.home() / ".intermesh"

    @property
    def hub_host(self) -> str:
        return os.environ.get("INTERMESH_HUB_HOST", "0.0.0.0")

    @property
    def hub_port(self) -> int:
        try:
            return int(os.environ.get("INTERMESH_HUB_PORT", "8765"))
        except ValueError:
            return 8765

    @property
    def default_org(self) -> str:
        return os.environ.get("INTERMESH_DEFAULT_ORG", "default")

    @property
    def token_expiry(self) -> int:
        try:
            return int(os.environ.get("INTERMESH_TOKEN_EXPIRY", "3600"))
        except ValueError:
            return 3600

    @property
    def default_rate_limit(self) -> float:
        try:
            return float(os.environ.get("INTERMESH_RATE_LIMIT", "15.0"))
        except ValueError:
            return 15.0

    @property
    def default_rate_burst(self) -> float:
        try:
            return float(os.environ.get("INTERMESH_RATE_BURST", "20.0"))
        except ValueError:
            return 20.0

    @property
    def default_hub_url(self) -> str:
        return os.environ.get("INTERMESH_HUB_URL", "ws://localhost:8765")

    @property
    def default_timeout_who_is(self) -> float:
        try:
            return float(os.environ.get("INTERMESH_TIMEOUT_WHO_IS", "5.0"))
        except ValueError:
            return 5.0

    @property
    def default_timeout_ask(self) -> float:
        try:
            return float(os.environ.get("INTERMESH_TIMEOUT_ASK", "10.0"))
        except ValueError:
            return 10.0

    @property
    def default_timeout_submit_task(self) -> float:
        try:
            return float(os.environ.get("INTERMESH_TIMEOUT_SUBMIT_TASK", "15.0"))
        except ValueError:
            return 15.0

    @property
    def default_timeout_discover(self) -> float:
        try:
            return float(os.environ.get("INTERMESH_TIMEOUT_DISCOVER", "5.0"))
        except ValueError:
            return 5.0

    @property
    def default_timeout_admin(self) -> float:
        try:
            return float(os.environ.get("INTERMESH_TIMEOUT_ADMIN", "10.0"))
        except ValueError:
            return 10.0

    @property
    def default_timeout_key_fetch(self) -> float:
        try:
            return float(os.environ.get("INTERMESH_TIMEOUT_KEY_FETCH", "3.0"))
        except ValueError:
            return 3.0

    @property
    def default_encrypt(self) -> bool:
        val = os.environ.get("INTERMESH_ENCRYPT", "true").lower()
        return val in ("true", "1", "yes", "on")

    @property
    def log_level(self) -> str:
        return os.environ.get("INTERMESH_LOG_LEVEL", "INFO").upper()

    @property
    def log_format(self) -> str:
        return os.environ.get("INTERMESH_LOG_FORMAT", "text").lower()

    @property
    def allow_cross_tenant(self) -> bool:
        val = os.environ.get("INTERMESH_ALLOW_CROSS_TENANT", "false").lower()
        return val in ("true", "1", "yes", "on")

settings = Settings()
