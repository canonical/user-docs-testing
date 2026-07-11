#!/usr/bin/env python3
"""Broken relative link check.

A deterministic documentation check. It flags relative Markdown links whose target
file does not exist. External links (http, https, mailto, ...) and pure in-page
anchors are ignored.

It is standard-library only, so it runs anywhere with Python and needs no `setup`.
Enable it from your config, or use it as a starting point for your own check in any
language — the tool only requires the output schema in RESULTS-SCHEMA.md.

Usage:
    python broken_links.py --targets 'reference/**/*.md' --output results/reference-links.json
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

SCHEMA_VERSION = 1
CHECK_ID = "broken-relative-link"

_MD_LINK_RE = re.compile(r"\[[^\]]*\]\(([^)]+)\)")
_SCHEME_RE = re.compile(r"^[a-zA-Z][a-zA-Z0-9+.-]*:")


def glob_to_regex(pattern: str) -> re.Pattern:
    """Translate a glob (supporting `**`) to a full-path regex."""
    i, n = 0, len(pattern)
    out = ["^"]
    while i < n:
        c = pattern[i]
        if c == "*":
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
        elif c == "?":
            out.append("[^/]")
            i += 1
        else:
            out.append(re.escape(c))
            i += 1
    out.append("$")
    return re.compile("".join(out))


def find_targets(patterns: list[str], root: Path) -> list[Path]:
    regexes = [glob_to_regex(p) for p in patterns]
    matched: list[Path] = []
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        rel = path.relative_to(root).as_posix()
        if any(rx.match(rel) for rx in regexes):
            matched.append(path)
    return matched


def check_file(doc: Path, root: Path) -> list[dict]:
    findings: list[dict] = []
    try:
        lines = doc.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeDecodeError):
        return findings
    rel_doc = doc.relative_to(root).as_posix()
    for lineno, line in enumerate(lines, start=1):
        for match in _MD_LINK_RE.finditer(line):
            target = match.group(1).strip().split(" ", 1)[0]
            if not target or target.startswith("#"):
                continue
            if _SCHEME_RE.match(target):
                continue  # external link
            file_part = target.split("#", 1)[0]
            if not file_part:
                continue
            if not (doc.parent / file_part).resolve().exists():
                findings.append(
                    {
                        "check": CHECK_ID,
                        "severity": "error",
                        "doc_file": rel_doc,
                        "doc_line": lineno,
                        "source": None,
                        "source_ref": None,
                        "message": f"Relative link target does not exist: {file_part}",
                        "covered_topic": f"{rel_doc}:link:{file_part}",
                    }
                )
    return findings


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--targets",
        action="append",
        required=True,
        help="Glob(s) of docs to check (repeatable). Supports **.",
    )
    parser.add_argument("--root", default=".", help="Repo root (default: cwd).")
    parser.add_argument("--output", required=True, help="Where to write results JSON.")
    args = parser.parse_args(argv)

    root = Path(args.root).resolve()
    docs = find_targets(args.targets, root)

    findings: list[dict] = []
    for doc in docs:
        findings.extend(check_file(doc, root))

    results = {
        "tool": "broken-links",
        "schema_version": SCHEMA_VERSION,
        "summary": {
            "checks_run": 1,
            "files_checked": len(docs),
            "findings": len(findings),
            "status": "fail" if findings else "pass",
        },
        "findings": findings,
    }

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(results, indent=2), encoding="utf-8")

    sys.stderr.write(
        f"checked {len(docs)} file(s), {len(findings)} finding(s) -> {output}\n"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
