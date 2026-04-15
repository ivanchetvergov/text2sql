from __future__ import annotations

import json
import logging
import yaml
from pathlib import Path
from typing import Any, Dict, List, Optional


class JsonLoader:
    @staticmethod
    def load(path: Optional[Path] = None) -> List[Dict[str, Any]]:
        if path is None:
            path = Path(__file__).resolve().parent.parent / "docs/schema.json"
        try:
            with Path(path).open(encoding="utf-8") as f:
                data = json.load(f)
            if not isinstance(data, list):
                raise ValueError("JSON root must be a list of schema entries")
            return data
        except Exception:
            raise


class YamlReader:
    _DEFAULT = Path(__file__).resolve().parent.parent / "docs" / "rag.yaml"

    @staticmethod
    def load(path: Optional[Path] = None) -> List[Dict[str, Any]]:
        src = Path(path) if path else YamlReader._DEFAULT
        with src.open(encoding="utf-8") as f:
            schema = yaml.safe_load(f)

        tables = schema.get("tables", {}) if isinstance(schema, dict) else {}
        entries = []
        for tbl, cfg in tables.items():
            entries.append({
                "table":          tbl,
                "retrieval_text": (cfg.get("retrieval_text") or "").strip(),
                "context_text":   (cfg.get("context_text")   or "").strip(),
                "relations":      cfg.get("relations") or [],
                "columns":        cfg.get("columns") or {},
                "examples":       cfg.get("examples") or [],
            })
        return entries


class GraphReader:
    _DEFAULT = Path(__file__).resolve().parent.parent / "docs" / "graph.yaml"

    @staticmethod
    def load(path: Optional[Path] = None) -> Dict[str, Any]:
        src = Path(path) if path else GraphReader._DEFAULT
        with src.open(encoding="utf-8") as f:
            data = yaml.safe_load(f)
        if not isinstance(data, dict):
            raise ValueError("graph.yaml root must be a mapping")
        return {
            "algorithms": data.get("algorithms") or {},
            "tables":     data.get("tables") or {},
        }


class Logger:
    @staticmethod
    def get_logger(name: str = "text2sql", filename: str = "app.log", level: int = logging.INFO) -> logging.Logger:
        logs_dir = Path(__file__).resolve().parent.parent / "logs"
        logs_dir.mkdir(parents=True, exist_ok=True)

        logger = logging.getLogger(name)
        if not logger.handlers:
            fh = logging.FileHandler(logs_dir / filename, encoding="utf-8")
            fmt = logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s")
            fh.setFormatter(fmt)
            logger.addHandler(fh)
        logger.setLevel(level)
        return logger


__all__ = ["JsonLoader", "YamlReader", "GraphReader", "Logger"]
