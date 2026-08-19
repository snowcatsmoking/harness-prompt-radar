"""Scraper for Kimi Code CLI (@moonshot-ai/kimi-code).

Unlike Claude Code, this npm package still ships an unminified JS bundle
(dist/main.mjs) with the system prompt as a plain quoted string literal
(`system_default$1 = "..."`). We locate that literal with a regex anchored
on the assignment target, then unescape it via JSON parsing (the JS string
escape grammar used here is a subset compatible with JSON's).
"""
from __future__ import annotations

import json
import re
import subprocess
import tempfile
from pathlib import Path

from common import Record, save_record

HARNESS = "kimi-code"
NPM_PACKAGE = "@moonshot-ai/kimi-code"
BUNDLE_RELATIVE_PATH = "package/dist/main.mjs"

PROMPT_VAR_PATTERN = re.compile(r'system_default\$1\s*=\s*"((?:[^"\\]|\\.)*)"')


def latest_version() -> str:
    out = subprocess.run(
        ["npm", "view", NPM_PACKAGE, "version"],
        capture_output=True, text=True, check=True,
    )
    return out.stdout.strip()


def download_bundle(version: str, dest: Path) -> Path:
    subprocess.run(
        ["npm", "pack", f"{NPM_PACKAGE}@{version}"],
        cwd=dest, check=True, capture_output=True, text=True,
    )
    tarballs = list(dest.glob("*.tgz"))
    if not tarballs:
        raise RuntimeError("npm pack produced no tarball")
    subprocess.run(["tar", "xzf", tarballs[0].name], cwd=dest, check=True)
    bundle = dest / BUNDLE_RELATIVE_PATH
    if not bundle.exists():
        raise RuntimeError(f"expected bundle not found at {bundle}")
    return bundle


def extract_system_prompt(bundle_path: Path) -> str:
    text = bundle_path.read_text(encoding="utf-8")
    match = PROMPT_VAR_PATTERN.search(text)
    if not match:
        raise RuntimeError("system prompt anchor not found in bundle")
    return json.loads('"' + match.group(1) + '"')


def run() -> None:
    version = latest_version()
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        bundle_path = download_bundle(version, tmp_path)
        system_prompt = extract_system_prompt(bundle_path)

    record = Record(
        harness=HARNESS,
        version=version,
        source_url=f"https://www.npmjs.com/package/{NPM_PACKAGE}/v/{version}",
        system_prompt=system_prompt,
        extraction_method="npm_bundle_grep",
        extraction_confidence="high",
    )
    written = save_record(record)
    if written:
        print(f"[{HARNESS}] saved new record for version {version}")
    else:
        print(f"[{HARNESS}] version {version} already recorded, skipped")


if __name__ == "__main__":
    run()
