"""Glob matching shared by the built-in checks.

`Path.glob` cannot express the `**`-anywhere patterns people write in config, so
patterns are translated to regexes over repo-relative POSIX paths.
"""

from __future__ import annotations

import re
from pathlib import Path

_IGNORED_DIRS = {".git", "node_modules", "__pycache__", ".venv", "venv"}


def glob_to_regex(pattern: str) -> re.Pattern:
    i, n = 0, len(pattern)
    out = ["^"]
    while i < n:
        char = pattern[i]
        if char == "*":
            if pattern[i : i + 3] == "**/":
                out.append("(?:.*/)?")
                i += 3
                continue
            if pattern[i : i + 2] == "**":
                out.append(".*")
                i += 2
                continue
            out.append("[^/]*")
            i += 1
        elif char == "?":
            out.append("[^/]")
            i += 1
        else:
            out.append(re.escape(char))
            i += 1
    out.append("$")
    return re.compile("".join(out))


def matches(rel_path: str, patterns: list[str]) -> bool:
    return any(glob_to_regex(p).match(rel_path) for p in patterns)


def find_files(patterns: list[str], root: Path, exclude: list[str] | None = None) -> list[Path]:
    """Repo-relative glob match, with excludes applied."""
    if not patterns:
        return []
    include = [glob_to_regex(p) for p in patterns]
    deny = [glob_to_regex(p) for p in (exclude or [])]
    found: list[Path] = []
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        if _IGNORED_DIRS.intersection(path.parts):
            continue
        rel = path.relative_to(root).as_posix()
        if any(rx.match(rel) for rx in include) and not any(rx.match(rel) for rx in deny):
            found.append(path)
    return found
