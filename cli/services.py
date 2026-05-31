from __future__ import annotations

from contextlib import redirect_stderr, redirect_stdout
from dataclasses import dataclass, field
from datetime import datetime
from io import StringIO
import os
from time import perf_counter

import asyncpg
from faker import Faker
import requests

from cli import bootstrap  # noqa: F401
from cli.constants import (
    DEFAULT_LLM_TIMEOUT_SECONDS,
    DEFAULT_LLM_URL,
    DEFAULT_OPENROUTER_MODEL,
)
from cli.action_dispatcher import execute_action
from infra.db_config import get_pg_connect_kwargs
from inserter import Inserter


def _run_llm_query(params: dict) -> ActionOutcome:
    started = datetime.now().isoformat(timespec="seconds")
    total_started = perf_counter()
    prompt = str(params.get("prompt", "")).strip()
    url = str(
        params.get(
            "url",
            DEFAULT_LLM_URL,
        )
    ).strip()
    model = str(
        params.get(
            "model",
            os.getenv("OPENROUTER_MODEL", DEFAULT_OPENROUTER_MODEL),
        )
    ).strip()
    timeout = DEFAULT_LLM_TIMEOUT_SECONDS

    if not prompt:
        return ActionOutcome(
            error="prompt is required",
            started_at=started,
            finished_at=datetime.now().isoformat(timespec="seconds"),
        )
    logs: list[str] = []
    error: str | None = None
    logs.append(f"Prompt: {prompt}")
    try:
        is_openrouter_direct = "openrouter.ai" in url
        if is_openrouter_direct:
            api_key = os.getenv("OPENROUTER_API_KEY", "").strip()
            if not api_key:
                return ActionOutcome(
                    error="OPENROUTER_API_KEY is not set",
                    started_at=started,
                    finished_at=datetime.now().isoformat(timespec="seconds"),
                )

            headers = {
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            }
            site_url = os.getenv("OPENROUTER_SITE_URL", "").strip()
            app_name = os.getenv("OPENROUTER_APP_NAME", "text2sql-db-cli").strip()
            if site_url:
                headers["HTTP-Referer"] = site_url
            if app_name:
                headers["X-Title"] = app_name

            payload = {
                "model": model,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.1,
                "max_tokens": 600,
            }
            resp = requests.post(url, headers=headers, json=payload, timeout=timeout)
        else:
            resp = requests.post(url, json={"prompt": prompt}, timeout=timeout)

        if resp.status_code != 200:
            body_preview = ""
            try:
                body_preview = resp.text[:400]
            except Exception:
                body_preview = ""
            logs.append(f"Response error body: {body_preview}")
            error = f"server returned status {resp.status_code}: {body_preview}"
        else:
            payload = resp.json()
            text = None
            if isinstance(payload, dict):
                choices = payload.get("choices", [])
                if choices and isinstance(choices[0], dict):
                    msg = choices[0].get("message", {})
                    if isinstance(msg, dict):
                        text = msg.get("content")
                if text is None:
                    text = payload.get("text") or payload.get("response")
            logs.append(f"Response: {str(text or '')}")
    except Exception as exc:
        error = f"request failed: {exc}"

    duration_ms = int((perf_counter() - total_started) * 1000)
    finished = datetime.now().isoformat(timespec="seconds")
    return ActionOutcome(
        inserted=None,
        logs=[line for line in logs if line.strip()],
        error=error,
        started_at=started,
        finished_at=finished,
        duration_ms=duration_ms,
        connect_ms=0,
        execute_ms=duration_ms,
        log_lines=len([line for line in logs if line.strip()]),
        throughput_rows_per_sec=None,
    )


@dataclass
class ActionOutcome:
    inserted: int | None = None
    logs: list[str] = field(default_factory=list)
    error: str | None = None
    started_at: str = ""
    finished_at: str = ""
    duration_ms: int = 0
    connect_ms: int = 0
    execute_ms: int = 0
    log_lines: int = 0
    throughput_rows_per_sec: float | None = None


async def run_seed_action(action: str, params: dict) -> ActionOutcome:
    if action == "llm_query":
        return _run_llm_query(params)

    started = datetime.now().isoformat(timespec="seconds")
    total_started = perf_counter()

    conn = None
    buffer = StringIO()
    inserted: int | None = None
    logs: list[str] = []
    error: str | None = None
    connect_ms = 0
    execute_ms = 0

    try:
        connect_started = perf_counter()
        conn = await asyncpg.connect(**get_pg_connect_kwargs())
        connect_ms = int((perf_counter() - connect_started) * 1000)

        fake = Faker()
        inserter = Inserter(conn)

        execute_started = perf_counter()
        try:
            with redirect_stdout(buffer), redirect_stderr(buffer):
                inserted = await execute_action(
                    action,
                    conn=conn,
                    inserter=inserter,
                    fake=fake,
                    **params,
                )
            error = None
        except Exception as exc:
            error = str(exc)
        finally:
            execute_ms = int((perf_counter() - execute_started) * 1000)

        logs = [line for line in buffer.getvalue().splitlines() if line.strip()]

    except Exception as exc:
        error = str(exc)
        logs = [line for line in buffer.getvalue().splitlines() if line.strip()]

    finally:
        if conn is not None:
            await conn.close()

    duration_ms = int((perf_counter() - total_started) * 1000)
    finished = datetime.now().isoformat(timespec="seconds")
    throughput = None
    if isinstance(inserted, int) and execute_ms > 0:
        throughput = inserted / (execute_ms / 1000)

    return ActionOutcome(
        inserted=inserted,
        logs=logs,
        error=error,
        started_at=started,
        finished_at=finished,
        duration_ms=duration_ms,
        connect_ms=connect_ms,
        execute_ms=execute_ms,
        log_lines=len(logs),
        throughput_rows_per_sec=throughput,
    )
