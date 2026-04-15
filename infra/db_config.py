import os
from pathlib import Path


def load_env_file(env_path: Path | None = None) -> None:
    if env_path is None:
        env_path = Path(__file__).resolve().parents[1] / ".env"

    if not env_path.exists():
        return

    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue

        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        os.environ.setdefault(key, value)


def get_pg_connect_kwargs() -> dict[str, str | int]:
    load_env_file()

    host = os.getenv("DB_HOST", "127.0.0.1")
    port_str = os.getenv("DB_PORT", "5436")

    return {
        "user": os.getenv("POSTGRES_USER", "competition_user"),
        "password": os.getenv("POSTGRES_PASSWORD", "competition_pass"),
        "database": os.getenv("POSTGRES_DB", "competition_db"),
        "host": host,
        "port": int(port_str),
    }
