"""Runs every scraper. A failure in one harness never stops the others."""
from __future__ import annotations

import json
import sys
import traceback
from datetime import UTC, datetime
from pathlib import Path

import build_manifest
import claude_code
import codex_cli
import kimi_code
import opencode

SCRAPERS = {
    "claude-code": claude_code.run,
    "codex-cli": codex_cli.run,
    "kimi-code": kimi_code.run,
    "opencode": opencode.run,
}

STATUS_PATH = Path(__file__).resolve().parent.parent / "data" / "status.json"


def main() -> None:
    status = {}
    had_failure = False
    for harness, fn in SCRAPERS.items():
        try:
            fn()
            status[harness] = {"ok": True, "checked_at": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")}
        except Exception as exc:
            had_failure = True
            print(f"[{harness}] FAILED: {exc}", file=sys.stderr)
            traceback.print_exc()
            status[harness] = {
                "ok": False,
                "checked_at": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
                "error": str(exc),
            }

    STATUS_PATH.write_text(json.dumps(status, ensure_ascii=False, indent=2) + "\n")
    build_manifest.run()
    if had_failure:
        sys.exit(1)


if __name__ == "__main__":
    main()
