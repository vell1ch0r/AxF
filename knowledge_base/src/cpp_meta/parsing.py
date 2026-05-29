from __future__ import annotations

import re
from pathlib import Path
from typing import Iterable

from .models import C_KEYWORDS, CodeItem


def read_lines(path_text: str) -> list[str]:
    path = Path(path_text)
    return path.read_text(encoding="utf-8", errors="replace").splitlines()


def source_slice(item: CodeItem, max_lines: int | None = None) -> str:
    lines = read_lines(item.file)
    start = max(1, item.start_line)
    end = max(start, item.end_line)
    if max_lines is not None and end - start + 1 > max_lines:
        end = start + max_lines - 1
    return "\n".join(lines[start - 1 : end])


def numbered_slice(item: CodeItem, max_lines: int | None = None) -> list[str]:
    lines = read_lines(item.file)
    start = max(1, item.start_line)
    end = max(start, item.end_line)
    truncated = False
    if max_lines is not None and end - start + 1 > max_lines:
        end = start + max_lines - 1
        truncated = True
    out = [f"{lineno}: {lines[lineno - 1]}" for lineno in range(start, end + 1)]
    if truncated:
        out.append("... <truncated>")
    return out


def strip_comments_and_strings(source: str) -> str:
    out: list[str] = []
    i = 0
    n = len(source)
    in_block = False
    while i < n:
        ch = source[i]
        nxt = source[i + 1] if i + 1 < n else ""
        if in_block:
            if ch == "*" and nxt == "/":
                out.extend("  ")
                i += 2
                in_block = False
            else:
                out.append("\n" if ch == "\n" else " ")
                i += 1
            continue
        if ch == "/" and nxt == "*":
            out.extend("  ")
            i += 2
            in_block = True
            continue
        if ch == "/" and nxt == "/":
            while i < n and source[i] != "\n":
                out.append(" ")
                i += 1
            continue
        if ch in ("'", '"'):
            quote = ch
            out.append(" ")
            i += 1
            while i < n:
                c = source[i]
                out.append("\n" if c == "\n" else " ")
                if c == "\\":
                    i += 2
                    if i <= n:
                        out.append(" ")
                    continue
                i += 1
                if c == quote:
                    break
            continue
        out.append(ch)
        i += 1
    return "".join(out)


def tokens_from_source(source: str) -> set[str]:
    return {
        tok
        for tok in re.findall(r"\b[A-Za-z_]\w*\b", strip_comments_and_strings(source))
        if tok not in C_KEYWORDS
    }


def discover_local_names(source: str) -> set[str]:
    names: set[str] = set()
    names.update(re.findall(r"\bCLASS\s*\(\s*[A-Za-z_]\w*\s*,\s*([A-Za-z_]\w*)", source))
    clean_lines = strip_comments_and_strings(source).splitlines()
    declaration = re.compile(
        r"^\s*(?:static\s+|const\s+|unsigned\s+|signed\s+|volatile\s+|struct\s+\w+\s+|union\s+\w+\s+|enum\s+\w+\s+|[A-Za-z_]\w+\s+)+"
        r"\*?\s*(?P<name>[A-Za-z_]\w*)\s*(?:\[|=|;|,)"
    )
    for idx, line in enumerate(clean_lines):
        if idx == 0:
            continue
        stripped = line.strip()
        if not stripped or stripped.startswith(("if", "for", "while", "switch", "return", "else")):
            continue
        match = declaration.match(line)
        if match:
            names.add(match.group("name"))
    return names


def chunked(values: list[str], size: int = 500) -> Iterable[list[str]]:
    for i in range(0, len(values), size):
        yield values[i : i + size]

