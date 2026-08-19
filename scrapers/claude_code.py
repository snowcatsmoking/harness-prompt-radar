"""Scraper for Claude Code (@anthropic-ai/claude-code).

The npm package is a thin installer; the actual CLI ships as a per-platform
native binary (@anthropic-ai/claude-code-<platform>) built with `bun build
--compile`. Bun embeds the full, unminified-in-structure JS source (not
bytecode) in a dedicated Mach-O section (__BUN,__bun on macOS) as a
length-prefixed, offset-addressed blob -- see StandaloneModuleGraph in
https://github.com/oven-sh/bun (src/standalone_graph/StandaloneModuleGraph.rs)
for the exact layout this module parses.

The prompt itself is not a static string: it is assembled at runtime by a
function (`l8` in the 2.1.235 build -- minified names drift across
versions) that concatenates ~20 named sections, some pure string constants,
some session-state-dependent (open git status, loaded memory files,
output-style config, model name, etc). Full runtime reconstruction is out
of scope here -- this scraper extracts the sections that are genuine
string/template-literal/array constants under the *default* interactive
session (no output-style override, no SDK/non-interactive mode) by parsing
the actual array/string literals out of the source (see js_literals.py),
not by hand-copying text, so it won't silently go stale if Anthropic edits
the wording. Every section that requires live session state (memory,
environment info, communication/action-caution flag branches) is left as
an explicit placeholder rather than guessed.

This still depends on a handful of minified local variable/function names
(zml, mZs, hdT, gdT, SdT, PdT, adT, mdT, hkm) that Anthropic could rename on
any release -- when that happens `run()` raises instead of silently
producing a wrong or empty prompt, which surfaces as a normal per-harness
scrape failure (see run_all.py). Confidence stays "low" for that reason,
but this is a materially more faithful "low" than the old strings(1)
fragment-stitching approach: every included section is a real literal
copied verbatim from the current release's source.
"""
from __future__ import annotations

import json
import re
import struct
import subprocess
import tempfile
from pathlib import Path

from common import Record, save_record
from js_literals import extract_array_after, parse_js_string_literal

HARNESS = "claude-code"
NPM_PACKAGE = "@anthropic-ai/claude-code"
NATIVE_PACKAGE = "@anthropic-ai/claude-code-darwin-arm64"

BUN_TRAILER = b"\n---- Bun! ----\n"
OFFSETS_STRUCT_SIZE = 8 + 4 + 4 + 4 + 4 + 4 + 4  # byte_count, modules_ptr{off,len}, entry_point_id, argv_ptr{off,len}, flags
MODULE_RECORD_SIZE = 52  # 6 x StringPointer(8 bytes) + 4 x u8, see CompiledModuleGraphFile

DYNAMIC_PLACEHOLDER = (
    "[[ 本节依赖运行时会话状态(如已加载的 memory 文件、环境信息、"
    "工具注册表、通信/操作谨慎程度的动态开关等),无法静态抓取,此处省略。 ]]"
)


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


def _find_bun_section_macho(data: bytes) -> tuple[int, int]:
    """Returns (file_offset, size) of the __BUN,__bun section in a Mach-O binary."""
    magic, = struct.unpack_from("<I", data, 0)
    if magic != 0xFEEDFACF:
        raise RuntimeError(f"not a 64-bit Mach-O binary (magic={magic:#x})")

    ncmds, = struct.unpack_from("<I", data, 16)
    offset = 32
    for _ in range(ncmds):
        cmd, cmdsize = struct.unpack_from("<II", data, offset)
        if cmd == 0x19:  # LC_SEGMENT_64
            nsects, = struct.unpack_from("<I", data, offset + 64)
            sec_off = offset + 72
            for _ in range(nsects):
                sectname = data[sec_off:sec_off + 16].rstrip(b"\x00").decode()
                segname = data[sec_off + 16:sec_off + 32].rstrip(b"\x00").decode()
                s_size, = struct.unpack_from("<Q", data, sec_off + 40)
                s_offset, = struct.unpack_from("<I", data, sec_off + 48)
                if segname == "__BUN" and sectname == "__bun":
                    return s_offset, s_size
                sec_off += 80
        offset += cmdsize
    raise RuntimeError("__BUN,__bun section not found (binary may not be a bun-compiled executable)")


def extract_module_source(binary_path: Path) -> str:
    """Extracts the main JS entry point's source text from Bun's embedded module graph."""
    data = binary_path.read_bytes()
    sect_off, sect_size = _find_bun_section_macho(data)
    section = data[sect_off:sect_off + sect_size]

    blob_len, = struct.unpack_from("<Q", section, 0)
    body = section[8:8 + blob_len]
    if body[-len(BUN_TRAILER):] != BUN_TRAILER:
        raise RuntimeError("Bun module graph trailer mismatch -- format may have changed")

    offsets_start = len(body) - len(BUN_TRAILER) - OFFSETS_STRUCT_SIZE
    (_byte_count, modules_off, modules_len, entry_point_id,
     _argv_off, _argv_len, _flags) = struct.unpack_from("<Q I I I I I I", body, offsets_start)

    if modules_len % MODULE_RECORD_SIZE != 0:
        raise RuntimeError("module list size is not a multiple of the record size -- format may have changed")

    base = modules_off + entry_point_id * MODULE_RECORD_SIZE
    _name_off, _name_len, cont_off, cont_len = struct.unpack_from("<4I", body, base)
    return body[cont_off:cont_off + cont_len].decode("latin-1")


def _bulleted(items: list[str]) -> str:
    return "\n".join(f" - {item}" for item in items)


def _extract_template_literal_after(source: str, marker: str) -> str:
    idx = source.index(marker) + len(marker)
    while source[idx] != "`":
        idx += 1
    value, _ = parse_js_string_literal(source, idx)
    return value


def build_default_prompt(source: str) -> str:
    """Reconstructs the default (standard interactive, no output-style override)
    system prompt from real source literals, in the assembly order used by
    the current build's orchestrator function."""

    # zml: security-use-policy line, referenced inside the identity template.
    m = re.search(r'var zml="((?:[^"\\]|\\.)*)"', source)
    if not m:
        raise RuntimeError("security policy anchor (zml) not found")
    security_policy = json.loads('"' + m.group(1) + '"')

    identity = (
        'You are an interactive agent that helps users with software engineering tasks. '
        'Use the instructions below and the tools available to you to assist the user.\n\n'
        f'{security_policy}\n'
        "IMPORTANT: You must NEVER generate or guess URLs for the user unless you are "
        "confident that the URLs are for helping the user with programming. You may use "
        "URLs provided by the user in their messages or local files."
    )

    # mdT: "# System" section.
    mdt_idx = source.index("function mdT(e){")
    system_items = extract_array_after(source, "let t=", start=mdt_idx)
    hooks_note = re.search(r'function adT\(\)\{return"((?:[^"\\]|\\.)*)"', source)
    if not hooks_note:
        raise RuntimeError("hooks note anchor (adT) not found")
    hooks_note = json.loads('"' + hooks_note.group(1) + '"')
    standard_reminder = re.search(r'return t==="standard"\?"((?:[^"\\]|\\.)*)"', source)
    if not standard_reminder:
        raise RuntimeError("system-reminder note anchor (hkm) not found")
    standard_reminder = json.loads('"' + standard_reminder.group(1) + '"')
    # system_items has 4 entries with two opaque function-call slots
    # (hkm(e,"standard"), adT()) dropped by the array parser; splice them
    # back in at their known positions (3rd and 5th line respectively).
    system_items = [system_items[0], system_items[1], standard_reminder,
                     system_items[2], hooks_note, system_items[3]]
    system_section = "# System\n" + _bulleted(system_items)

    # hdT: "# Doing tasks" section.
    hdt_idx = source.index("function hdT(){")
    style_items = extract_array_after(source, "let t=", start=hdt_idx)
    doing_items = extract_array_after(source, ",n=[", {"t": style_items}, start=hdt_idx)
    feedback_items = extract_array_after(source, ",r=[", start=hdt_idx)
    issues_url_match = re.search(r'ISSUES_EXPLAINER:"((?:[^"\\]|\\.)*)"', source)
    if not issues_url_match:
        raise RuntimeError("issues URL anchor not found")
    issues_line = feedback_items[1].split("${")[0] + json.loads('"' + issues_url_match.group(1) + '"')
    doing_tasks = "# Doing tasks\n" + _bulleted(doing_items)
    doing_tasks += "\n   - " + feedback_items[0]
    doing_tasks += "\n   - " + issues_line

    # gdT: "# Executing actions with care" -- fully static template literal.
    actions_with_care = _extract_template_literal_after(source, "function gdT(){return")

    # SdT: "# Tone and style" -- fully static array literal.
    sdt_idx = source.index("function SdT(){")
    tone_items = extract_array_after(source, "let e=", start=sdt_idx)
    tone_and_style = "# Tone and style\n" + _bulleted(tone_items)

    # PdT: "# Context management" -- fully static template literal (var, not function).
    context_management = _extract_template_literal_after(source, "PdT=")

    sections = [
        identity,
        system_section,
        doing_tasks,
        actions_with_care,
        tone_and_style,
        context_management,
        "# Communicating with the user\n" + DYNAMIC_PLACEHOLDER,
        "# Action caution\n" + DYNAMIC_PLACEHOLDER,
        "# Memory\n" + DYNAMIC_PLACEHOLDER,
        "# Environment info\n" + DYNAMIC_PLACEHOLDER,
        "# Todo tool guidance\n" + DYNAMIC_PLACEHOLDER,
    ]
    return "\n\n".join(sections)


def run() -> None:
    version = latest_version()
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        binary_path = download_native_binary(version, tmp_path)
        source = extract_module_source(binary_path)
        system_prompt = build_default_prompt(source)

    record = Record(
        harness=HARNESS,
        version=version,
        source_url=f"https://www.npmjs.com/package/{NPM_PACKAGE}/v/{version}",
        system_prompt=system_prompt,
        extraction_method="bun_module_graph_static_sections",
        extraction_confidence="low",
    )
    written = save_record(record)
    if written:
        print(f"[{HARNESS}] saved new record for version {version}")
    else:
        print(f"[{HARNESS}] version {version} already recorded, skipped")


if __name__ == "__main__":
    run()
