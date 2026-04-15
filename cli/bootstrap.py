import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
SEED_DIR = ROOT_DIR / "seed"


def ensure_paths() -> None:
    for path in (ROOT_DIR, SEED_DIR):
        path_str = str(path)
        if path_str not in sys.path:
            sys.path.append(path_str)


ensure_paths()
