"""Minimal parser for JS string/template/array literals, used to pull real
content out of a minified JS bundle without hand-copying it (which would go
stale silently on the next version bump). Not a general JS parser -- just
enough to walk `["a", "b", ...cond?[...]:[], nested]`-shaped array literals
built from string/template literals, spreads of other such arrays, and
conditional (ternary) spreads, which is what Claude Code's prompt-section
builder functions are made of.
"""
from __future__ import annotations

import json


def parse_js_string_literal(s: str, i: int) -> tuple[str, int]:
    """Parses a JS string literal (single/double/template-quoted) starting at
    s[i]. Template `${...}` interpolations are kept as literal `${...}` text
    (not evaluated). Returns (value, index_after_closing_quote)."""
    quote = s[i]
    assert quote in ('"', "'", "`"), f"not a string literal start: {s[i - 5:i + 5]!r}"
    j = i + 1
    buf = []
    while True:
        c = s[j]
        if c == "\\":
            buf.append(s[j:j + 2])
            j += 2
            continue
        if quote == "`" and c == "$" and j + 1 < len(s) and s[j + 1] == "{":
            depth = 1
            k = j + 2
            while depth > 0:
                if s[k] == "{":
                    depth += 1
                elif s[k] == "}":
                    depth -= 1
                k += 1
            buf.append(s[j:k])
            j = k
            continue
        if c == quote:
            j += 1
            break
        buf.append(c)
        j += 1
    raw = "".join(buf)
    if quote in ('"', "'"):
        if quote == "'":
            raw = raw.replace("\\'", "'").replace('"', '\\"')
        try:
            value = json.loads('"' + raw + '"')
        except Exception:
            value = raw
    else:
        # Template literal: unescape backslash sequences (—, \`, \n, \\, ...)
        # but leave ${...} interpolations untouched (they were preserved as
        # literal `${...}` text above, with no backslashes inside to collide).
        # json.loads can't be reused here directly since raw `\`` and bare
        # newlines inside a template literal aren't valid JSON string content;
        # escape those first, then let JSON handle the rest of the \-escapes.
        json_safe = raw.replace("\\`", "`").replace("\n", "\\n").replace('"', '\\"')
        try:
            value = json.loads('"' + json_safe + '"')
        except Exception:
            value = raw
    return value, j


def _skip_balanced_expr(s: str, i: int) -> int:
    """Advances past a balanced expression (no top-level comma) starting at
    s[i], stopping right before the terminating `,` or the enclosing `]`/`)`."""
    depth = 0
    j = i
    while True:
        c = s[j]
        if c in "([{":
            depth += 1
        elif c in ")]}":
            if depth == 0:
                return j
            depth -= 1
        elif c == "," and depth == 0:
            return j
        elif c in "\"'`":
            _, j = parse_js_string_literal(s, j)
            continue
        j += 1


def parse_array_literal(s: str, i: int, known_vars: dict[str, list] | None = None) -> tuple[list, int]:
    """s[i] == '['. Returns (flat_list_of_string_values, index_after_closing_bracket).
    Spreads of nested array literals (`...[...]`), of other array literals
    reached via a conditional (`...cond?[...]:[]`), and of bare identifiers
    naming a previously-parsed array (`...t`, resolved via `known_vars`) are
    flattened; anything else opaque is dropped (best-effort: these mostly
    gate optional/feature-flagged lines that don't apply in the default
    session anyway)."""
    known_vars = known_vars or {}
    assert s[i] == "["
    j = i + 1
    out: list[str] = []
    while True:
        while s[j] in " \t\n\r":
            j += 1
        if s[j] == "]":
            return out, j + 1

        if s[j:j + 3] == "...":
            j += 3
            while s[j] in " \t\n\r":
                j += 1
            if s[j] == "[":
                sub, j = parse_array_literal(s, j, known_vars)
                out.extend(sub)
            elif s[j].isalpha() or s[j] == "_":
                end = _skip_balanced_expr(s, j)
                ident = s[j:end].strip()
                if ident in known_vars:
                    out.extend(known_vars[ident])
                elif "?" in ident:
                    arr_idx = ident.find("[")
                    if arr_idx != -1:
                        sub, _ = parse_array_literal(ident, arr_idx, known_vars)
                        out.extend(sub)
                j = end
            else:
                # conditional spread or opaque expression spread: try to find
                # a literal array in it (ternary true-branch), else skip.
                end = _skip_balanced_expr(s, j)
                expr = s[j:end]
                arr_idx = expr.find("[")
                if "?" in expr.split("[")[0] and arr_idx != -1:
                    sub, _ = parse_array_literal(expr, arr_idx, known_vars)
                    out.extend(sub)
                j = end
        elif s[j] in "\"'`":
            val, j = parse_js_string_literal(s, j)
            out.append(val)
        elif s[j] == "[":
            sub, j = parse_array_literal(s, j)
            out.extend(sub)
        else:
            j = _skip_balanced_expr(s, j)

        while s[j] in " \t\n\r":
            j += 1
        if s[j] == ",":
            j += 1
            continue
        elif s[j] == "]":
            return out, j + 1
        else:
            raise ValueError(f"unexpected char {s[j]!r} at offset {j}")


def extract_array_after(
    source: str, marker: str, known_vars: dict[str, list] | None = None, start: int = 0,
) -> list[str]:
    """Finds `marker` in source at or after `start`, then parses the first
    `[...]` literal that appears after it into a flat list of strings."""
    idx = source.index(marker, start)
    bracket = source.index("[", idx)
    items, _ = parse_array_literal(source, bracket, known_vars)
    return items
