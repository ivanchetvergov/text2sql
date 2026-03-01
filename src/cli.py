from __future__ import annotations

import argparse
import sys
import requests


def main() -> int:
    p = argparse.ArgumentParser(description="CLI client for text2sql FastAPI generate endpoint")
    p.add_argument("--url", default="http://localhost:8000/generate", help="Full generate endpoint URL (default: http://localhost:8000/generate)")
    args = p.parse_args()

    url = args.url.rstrip()
    print("Text2SQL CLI client. Type /help for commands.")

    while True:
        try:
            prompt = input("> ").strip()
        except (KeyboardInterrupt, EOFError):
            print()
            return 0

        if not prompt:
            continue
        if prompt.startswith("/"):
            cmd = prompt[1:].strip().lower()
            if cmd in ("exit", "quit"):
                return 0
            if cmd == "help":
                print("Commands:\n  /exit - quit\n  /help - show this help")
                continue
            print("Unknown command. Type /help.")
            continue

        try:
            resp = requests.post(url, json={"prompt": prompt}, timeout=180)
        except Exception as exc:
            print(f"Error: request failed: {exc}", file=sys.stderr)
            continue

        if resp.status_code != 200:
            print(f"Error: server returned status {resp.status_code}", file=sys.stderr)
            continue

        try:
            j = resp.json()
        except Exception as exc:
            print(f"Error: invalid JSON response: {exc}", file=sys.stderr)
            continue

        out = j.get("text") if isinstance(j, dict) else None
        if out is None:
            out = j.get("response") if isinstance(j, dict) else None
        if out is None:
            print("", end="")
        else:
            print(out)


if __name__ == "__main__":
    raise SystemExit(main())
