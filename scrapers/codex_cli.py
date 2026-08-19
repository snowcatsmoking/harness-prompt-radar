"""Scraper for Codex CLI (openai/codex).

Codex CLI is open source and its base system prompt ships as a plain
markdown file in the repo (codex-rs/core/gpt_5_codex_prompt.md). We fetch it
pinned to each release tag via raw.githubusercontent.com, so extraction is
a plain text fetch rather than any binary reverse engineering -> high
confidence.
"""
from __future__ import annotations

import json
import urllib.request

from common import Record, save_record

HARNESS = "codex-cli"
REPO = "openai/codex"
PROMPT_PATH = "codex-rs/core/gpt_5_codex_prompt.md"


def _get(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": "harness-prompt-radar"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return resp.read()


def latest_release_tag() -> str:
    data = json.loads(_get(f"https://api.github.com/repos/{REPO}/releases").decode())
    for release in data:
        if not release.get("prerelease") and release["tag_name"].startswith("rust-v"):
            return release["tag_name"]
    raise RuntimeError("no stable rust-v* release found")


def fetch_prompt(tag: str) -> str:
    url = f"https://raw.githubusercontent.com/{REPO}/{tag}/{PROMPT_PATH}"
    return _get(url).decode("utf-8")


def run() -> None:
    tag = latest_release_tag()
    version = tag.removeprefix("rust-v")
    system_prompt = fetch_prompt(tag)

    record = Record(
        harness=HARNESS,
        version=version,
        source_url=f"https://github.com/{REPO}/blob/{tag}/{PROMPT_PATH}",
        system_prompt=system_prompt,
        extraction_method="repo_source_file",
        extraction_confidence="high",
    )
    written = save_record(record)
    if written:
        print(f"[{HARNESS}] saved new record for version {version}")
    else:
        print(f"[{HARNESS}] version {version} already recorded, skipped")


if __name__ == "__main__":
    run()
