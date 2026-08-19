"""Writes data/manifest.json: list of harnesses with their latest record summary.

The static site fetches this first to know which harness files exist,
instead of hardcoding harness names in JS.
"""
from __future__ import annotations

import json
from pathlib import Path

from common import DATA_DIR, load_records

HARNESSES = ["claude-code", "codex-cli", "kimi-code", "opencode"]


def run() -> None:
    manifest = []
    for harness in HARNESSES:
        records = load_records(harness)
        if not records:
            continue
        latest = records[-1]
        manifest.append({
            "harness": harness,
            "version_count": len(records),
            "latest_version": latest["version"],
            "latest_token_count": latest["system_prompt_token_count"],
            "latest_confidence": latest["extraction_confidence"],
        })
    (DATA_DIR / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n"
    )


if __name__ == "__main__":
    run()
