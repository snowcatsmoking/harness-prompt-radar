"""Shared helpers for harness scrapers: the on-disk record format and storage."""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

DATA_DIR = Path(__file__).resolve().parent.parent / "data"


def now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def count_tokens(text: str) -> int:
    """Rough token count. Uses tiktoken if available, else a chars/4 estimate."""
    try:
        import tiktoken

        enc = tiktoken.get_encoding("cl100k_base")
        return len(enc.encode(text))
    except Exception:
        return max(1, len(text) // 4)


@dataclass
class Record:
    harness: str
    version: str
    source_url: str
    system_prompt: str
    extraction_method: str
    extraction_confidence: str  # "high" | "low"
    tool_schemas: list[dict[str, Any]] = field(default_factory=list)
    extracted_at: str = field(default_factory=now_iso)

    def to_dict(self) -> dict[str, Any]:
        return {
            "harness": self.harness,
            "version": self.version,
            "extracted_at": self.extracted_at,
            "source_url": self.source_url,
            "system_prompt": self.system_prompt,
            "system_prompt_token_count": count_tokens(self.system_prompt),
            "tool_schemas": self.tool_schemas,
            "extraction_method": self.extraction_method,
            "extraction_confidence": self.extraction_confidence,
        }


def harness_file(harness: str) -> Path:
    return DATA_DIR / f"{harness}.json"


def load_records(harness: str) -> list[dict[str, Any]]:
    path = harness_file(harness)
    if not path.exists():
        return []
    return json.loads(path.read_text())


def save_record(record: Record) -> bool:
    """Append the record unless harness+version already exists. Returns True if written."""
    DATA_DIR.mkdir(exist_ok=True)
    records = load_records(record.harness)
    if any(r["version"] == record.version for r in records):
        return False
    records.append(record.to_dict())
    records.sort(key=lambda r: r["extracted_at"])
    harness_file(record.harness).write_text(
        json.dumps(records, ensure_ascii=False, indent=2) + "\n"
    )
    return True
