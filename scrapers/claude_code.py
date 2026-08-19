"""Scraper for Claude Code (@anthropic-ai/claude-code).

The npm package is a thin installer; the actual CLI ships as a per-platform
native binary (@anthropic-ai/claude-code-<platform>) containing a V8 heap
snapshot. The system prompt text survives inside that snapshot as a run of
plain-text string fragments in roughly original order, anchored by a known
opening line. We extract that run heuristically and join it back into prose.

Because the reconstruction is fragment-based (not a single verbatim string
pulled out of source), this scraper always reports "low" confidence.
"""
from __future__ import annotations

import re
import subprocess
import tempfile
from pathlib import Path

from common import Record, save_record

HARNESS = "claude-code"
NPM_PACKAGE = "@anthropic-ai/claude-code"
NATIVE_PACKAGE = "@anthropic-ai/claude-code-darwin-arm64"

ANCHOR = b"You are an interactive agent that helps users"
SCAN_WINDOW = 20_000  # bytes to scan forward from the anchor for prompt fragments
MIN_FRAGMENT_LEN = 15


def latest_version() -> str:
    out = subprocess.run(
        ["npm", "view", NPM_PACKAGE, "version"],
        capture_output=True, text=True, check=True,
    )
    return out.stdout.strip()


def download_native_binary(version: str, dest: Path) -> Path:
    subprocess.run(
        ["npm", "pack", f"{NATIVE_PACKAGE}@{version}"],
        cwd=dest, check=True, capture_output=True, text=True,
    )
    tarballs = list(dest.glob("*.tgz"))
    if not tarballs:
        raise RuntimeError("npm pack produced no tarball")
    subprocess.run(["tar", "xzf", tarballs[0].name], cwd=dest, check=True)
    binary = dest / "package" / "claude"
    if not binary.exists():
        raise RuntimeError(f"expected binary not found at {binary}")
    return binary


def extract_system_prompt(binary_path: Path) -> str:
    data = binary_path.read_bytes()
    idx = data.find(ANCHOR)
    if idx == -1:
        raise RuntimeError("system prompt anchor not found in binary")

    region = data[idx : idx + SCAN_WINDOW]
    fragments = re.findall(rb"[\x20-\x7e]{%d,}" % MIN_FRAGMENT_LEN, region)
    text_fragments = [f.decode("ascii") for f in fragments]

    # Drop obvious non-prose noise (bare identifiers, URLs-only lines, version
    # strings, git shas) that shares the same string table region.
    prose = [
        f for f in text_fragments
        if re.search(r"[a-zA-Z]{4,}\s[a-zA-Z]{2,}", f)
    ]

    return "\n".join(prose).strip()


def run() -> None:
    version = latest_version()
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        binary_path = download_native_binary(version, tmp_path)
        system_prompt = extract_system_prompt(binary_path)

    record = Record(
        harness=HARNESS,
        version=version,
        source_url=f"https://www.npmjs.com/package/{NPM_PACKAGE}/v/{version}",
        system_prompt=system_prompt,
        extraction_method="binary_strings",
        extraction_confidence="low",
    )
    written = save_record(record)
    if written:
        print(f"[{HARNESS}] saved new record for version {version}")
    else:
        print(f"[{HARNESS}] version {version} already recorded, skipped")


if __name__ == "__main__":
    run()
