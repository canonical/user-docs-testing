#!/usr/bin/env python3
"""Undocumented-surface (reference completeness) check.

A deterministic documentation check. Given a machine-readable description of a
product's interface (its "surface"), it flags identifiers that exist in the
interface but are not mentioned anywhere in the reference docs. It is the precise,
repeatable counterpart to the agentic `reference-completeness` test: use this
wherever the surface is machine-enumerable, and reserve the agentic test for
surface that is not (prose concepts, roles, states).

This script is PRODUCT-AGNOSTIC. The product-specific part is the *manifest* you
feed it, which you generate from the owning source (for example, dumping a CLI's
`--help`, exporting an OpenAPI/Swagger spec, or emitting a JSON Schema). The
matching logic here does not know or care what product it describes.

Supported manifest formats (auto-detected):
  - OpenAPI / Swagger JSON: extracts path templates and operationIds.
  - JSON Schema JSON (has top-level "properties"): extracts property names,
    recursing into nested object/array schemas (dotted, e.g. "server.port").
  - JSON array of strings: used verbatim as the identifier list.
  - Plain text: one identifier per line; blank lines and `#` comments ignored.

Matching is literal and token-bounded (alphanumeric/underscore boundaries), so an
identifier counts as documented if it appears as a whole token in any target file.
Path templates are matched literally, so keep placeholder names (e.g. `{id}`)
consistent between the manifest and the docs, or list paths in a plain-text
manifest.

It is standard-library only, so it runs anywhere with Python and needs no `setup`.
Findings follow RESULTS-SCHEMA.md; each carries a stable `covered_topic`
(`surface:<identifier>`) so the agentic `reference-completeness` test can skip
anything this check already reported.

Usage:
    python undocumented_surface.py \\
        --manifest openapi.json \\
        --targets 'reference/**/*.md' \\
        --output results/surface-coverage.json
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

SCHEMA_VERSION = 1
CHECK_ID = "undocumented-surface-element"


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


def _schema_properties(schema: dict, prefix: str = "") -> list[str]:
    """Collect property names from a JSON Schema, dotted for nested objects."""
    names: list[str] = []
    props = schema.get("properties")
    if isinstance(props, dict):
        for key, sub in props.items():
            dotted = f"{prefix}{key}"
            names.append(dotted)
            if isinstance(sub, dict):
                names.extend(_schema_properties(sub, prefix=f"{dotted}."))
                items = sub.get("items")
                if isinstance(items, dict):
                    names.extend(_schema_properties(items, prefix=f"{dotted}."))
    return names


def _openapi_identifiers(doc: dict) -> list[str]:
    """Collect path templates and operationIds from an OpenAPI/Swagger doc."""
    names: list[str] = []
    paths = doc.get("paths")
    if isinstance(paths, dict):
        for path, item in paths.items():
            names.append(path)
            if isinstance(item, dict):
                for op in item.values():
                    if isinstance(op, dict) and isinstance(op.get("operationId"), str):
                        names.append(op["operationId"])
    return names


def load_manifest(path: Path) -> list[str]:
    """Parse a surface manifest into a de-duplicated list of identifiers."""
    text = path.read_text(encoding="utf-8")
    identifiers: list[str] = []

    stripped = text.lstrip()
    is_json = path.suffix.lower() == ".json" or stripped[:1] in "{["
    if is_json:
        try:
            data = json.loads(text)
        except json.JSONDecodeError as exc:  # fall back to plain text
            sys.stderr.write(f"warning: {path} is not valid JSON ({exc}); reading as text\n")
            data = None
        if isinstance(data, list):
            identifiers = [str(x) for x in data if isinstance(x, (str, int, float))]
        elif isinstance(data, dict):
            if "paths" in data or "openapi" in data or "swagger" in data:
                identifiers = _openapi_identifiers(data)
            elif "properties" in data:
                identifiers = _schema_properties(data)
            else:  # unknown object shape: try schema-style, then top-level keys
                identifiers = _schema_properties(data) or list(data.keys())

    if not identifiers:
        for line in text.splitlines():
            item = line.strip()
            if item and not item.startswith("#"):
                identifiers.append(item)

    seen: set[str] = set()
    unique: list[str] = []
    for item in identifiers:
        item = item.strip()
        if item and item not in seen:
            seen.add(item)
            unique.append(item)
    return unique


def _ignored(identifier: str, ignore: list[str]) -> bool:
    for pat in ignore:
        if pat.endswith("*"):
            if identifier.startswith(pat[:-1]):
                return True
        elif identifier == pat:
            return True
    return False


def is_documented(identifier: str, corpus: str) -> bool:
    esc = re.escape(identifier)
    pattern = rf"(?<![A-Za-z0-9_]){esc}(?![A-Za-z0-9_])"
    return re.search(pattern, corpus) is not None


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--manifest",
        action="append",
        required=True,
        help="Interface manifest file(s) (repeatable): OpenAPI/Swagger JSON, a JSON "
        "Schema, a JSON array of strings, or a plain newline list.",
    )
    parser.add_argument(
        "--targets",
        action="append",
        required=True,
        help="Glob(s) of docs to search (repeatable). Supports **.",
    )
    parser.add_argument("--root", default=".", help="Repo root (default: cwd).")
    parser.add_argument("--output", required=True, help="Where to write results JSON.")
    parser.add_argument(
        "--ignore",
        action="append",
        default=[],
        help="Identifier(s) to skip (repeatable). Trailing '*' matches a prefix.",
    )
    parser.add_argument(
        "--severity",
        choices=("error", "warning"),
        default="warning",
        help="Severity for findings (default: warning; a coverage gap, not a broken claim).",
    )
    parser.add_argument(
        "--source-name",
        default=None,
        help="Name recorded in each finding's `source` field (default: manifest filename).",
    )
    args = parser.parse_args(argv)

    root = Path(args.root).resolve()
    docs = find_targets(args.targets, root)
    corpus = "\n".join(
        doc.read_text(encoding="utf-8", errors="replace") for doc in docs
    )

    findings: list[dict] = []
    identifiers_checked = 0
    for manifest_arg in args.manifest:
        manifest_path = Path(manifest_arg)
        if not manifest_path.exists():
            sys.stderr.write(f"error: manifest not found: {manifest_path}\n")
            return 2
        rel_manifest = (
            manifest_path.resolve().relative_to(root).as_posix()
            if manifest_path.resolve().is_relative_to(root)
            else manifest_path.as_posix()
        )
        source_name = args.source_name or manifest_path.name
        for identifier in load_manifest(manifest_path):
            if _ignored(identifier, args.ignore):
                continue
            identifiers_checked += 1
            if not is_documented(identifier, corpus):
                findings.append(
                    {
                        "check": CHECK_ID,
                        "severity": args.severity,
                        "doc_file": rel_manifest,
                        "doc_line": None,
                        "source": source_name,
                        "source_ref": rel_manifest,
                        "message": (
                            f"Interface element not documented in reference targets: "
                            f"{identifier}"
                        ),
                        "covered_topic": f"surface:{identifier}",
                    }
                )

    results = {
        "tool": "undocumented-surface",
        "schema_version": SCHEMA_VERSION,
        "summary": {
            "checks_run": 1,
            "files_checked": len(docs),
            "identifiers_checked": identifiers_checked,
            "findings": len(findings),
            "status": "fail" if any(f["severity"] == "error" for f in findings) else "pass",
        },
        "findings": findings,
    }

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(results, indent=2), encoding="utf-8")

    sys.stderr.write(
        f"checked {identifiers_checked} identifier(s) across {len(docs)} doc file(s), "
        f"{len(findings)} undocumented -> {output}\n"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
