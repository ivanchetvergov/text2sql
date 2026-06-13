from __future__ import annotations

import logging
import os
import yaml
from pathlib import Path
from typing import Any, Dict, List, Optional


class YamlReader:
    _DEFAULT = Path(__file__).resolve().parent.parent / "docs" / "custom" / "rag.yaml"

    @staticmethod
    def load(path: Optional[Path] = None) -> List[Dict[str, Any]]:
        src = Path(path) if path else YamlReader._DEFAULT
        with src.open(encoding="utf-8") as f:
            schema = yaml.safe_load(f)

        tables = schema.get("tables", {}) if isinstance(schema, dict) else {}
        return [
            {
                "table":          tbl,
                "retrieval_text": (cfg.get("retrieval_text") or "").strip(),
                "context_text":   (cfg.get("context_text")   or "").strip(),
                "relations":      cfg.get("relations") or [],
                "columns":        cfg.get("columns")   or {},
                "examples":       cfg.get("examples")  or [],
            }
            for tbl, cfg in tables.items()
        ]


class GraphReader:
    _DEFAULT = Path(__file__).resolve().parent.parent / "docs" / "custom" / "graph.yaml"

    @staticmethod
    def load(path: Optional[Path] = None) -> Dict[str, Any]:
        src = Path(path) if path else GraphReader._DEFAULT
        with src.open(encoding="utf-8") as f:
            data = yaml.safe_load(f)
        if not isinstance(data, dict):
            raise ValueError("graph.yaml root must be a mapping")
        return {
            "algorithms": data.get("algorithms") or {},
            "tables":     data.get("tables")     or {},
        }


class Logger:
    @staticmethod
    def get_logger(name: str = "text2sql", filename: str = "app.log", level: int = logging.INFO) -> logging.Logger:
        logs_dir = Path(__file__).resolve().parent.parent / "logs"
        logs_dir.mkdir(parents=True, exist_ok=True)

        logger = logging.getLogger(name)
        if not logger.handlers:
            fh = logging.FileHandler(logs_dir / filename, encoding="utf-8")
            fh.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
            logger.addHandler(fh)
        logger.setLevel(level)
        return logger


def load_env(root: Path | None = None) -> None:
    """Load .env from project root into os.environ (setdefault — won't override existing vars)."""
    env_path = (root or Path(__file__).resolve().parent.parent) / ".env"
    if not env_path.exists():
        return
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


__all__ = ["YamlReader", "GraphReader", "Logger", "load_env"]
