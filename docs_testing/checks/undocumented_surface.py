"""Undocumented-surface check: interface that exists but is never documented.

Given a machine-readable description of a product's interface, flag identifiers
that appear in it but nowhere in the documentation. This is the precise,
repeatable counterpart to the agentic `reference-completeness` review — prefer it
wherever the surface is machine-enumerable, and let the agent handle surface that
is not (prose concepts, roles, states).

The check is product-agnostic. The product-specific part is the manifest, which
you generate from the owning source (dump a CLI's `--help`, export an OpenAPI
spec, emit a JSON Schema).
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from docs_testing.checks.globs import find_files
from docs_testing.results import BLOCKED, CONFLICTING, REVIEWED

CHECK_ID = "undocumented-surface-element"


def _schema_properties(schema: dict, prefix: str = "") -> list[str]:
    names: list[str] = []
    properties = schema.get("properties")
    if isinstance(properties, dict):
        for key, sub in properties.items():
            dotted = f"{prefix}{key}"
            names.append(dotted)
            if isinstance(sub, dict):
                names.extend(_schema_properties(sub, prefix=f"{dotted}."))
                items = sub.get("items")
                if isinstance(items, dict):
                    names.extend(_schema_properties(items, prefix=f"{dotted}."))
    return names


def _openapi_identifiers(doc: dict) -> list[str]:
    names: list[str] = []
    paths = doc.get("paths")
    if isinstance(paths, dict):
        for path, item in paths.items():
            names.append(path)
            if isinstance(item, dict):
                for operation in item.values():
                    if isinstance(operation, dict) and isinstance(operation.get("operationId"), str):
                        names.append(operation["operationId"])
    return names


def load_manifest(path: Path) -> list[str]:
    """Parse a surface manifest into a de-duplicated identifier list.

    Formats are auto-detected: OpenAPI/Swagger JSON, JSON Schema, a JSON array of
    strings, or plain text with one identifier per line.
    """
    text = path.read_text(encoding="utf-8")
    identifiers: list[str] = []

    if path.suffix.lower() == ".json" or text.lstrip()[:1] in "{[":
        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            data = None  # fall through to the plain-text reader
        if isinstance(data, list):
            identifiers = [str(x) for x in data if isinstance(x, (str, int, float))]
        elif isinstance(data, dict):
            if "paths" in data or "openapi" in data or "swagger" in data:
                identifiers = _openapi_identifiers(data)
            elif "properties" in data:
                identifiers = _schema_properties(data)
            else:
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


def _ignored(identifier: str, patterns: list[str]) -> bool:
    for pattern in patterns:
        if pattern.endswith("*"):
            if identifier.startswith(pattern[:-1]):
                return True
        elif identifier == pattern:
            return True
    return False


def is_documented(identifier: str, corpus: str) -> bool:
    """Literal, token-bounded match, so `--retry` does not satisfy `--retries`."""
    pattern = rf"(?<![A-Za-z0-9_]){re.escape(identifier)}(?![A-Za-z0-9_])"
    return re.search(pattern, corpus) is not None


def run(
    *,
    manifests: list[str],
    docs: list[str],
    exclude: list[str],
    root: Path,
    ignore: list[str] | None = None,
    severity: str = "warning",
    source_name: str | None = None,
) -> tuple[list[dict], list[dict]]:
    """Return `(findings, coverage)`."""
    ignore = ignore or []
    doc_files = find_files(docs, root, exclude)
    corpus = "\n".join(f.read_text(encoding="utf-8", errors="replace") for f in doc_files)

    findings: list[dict] = []
    coverage: list[dict] = []

    for manifest_arg in manifests:
        manifest_path = Path(manifest_arg)
        if not manifest_path.is_absolute():
            manifest_path = root / manifest_path
        label = manifest_arg
        name = source_name or Path(manifest_arg).name

        # A manifest is generated from the owning source, so its absence means
        # that source could not be read. That is unverified surface, not a pass,
        # and not a tool error either.
        if not manifest_path.exists():
            coverage.append(
                {
                    "area": f"surface manifest: {label}",
                    "state": BLOCKED,
                    "sources": [name],
                    "detail": (
                        f"Manifest `{label}` is absent, so the interface could not be "
                        "enumerated. This surface was NOT verified."
                    ),
                }
            )
            continue

        undocumented = 0
        for identifier in load_manifest(manifest_path):
            if _ignored(identifier, ignore):
                continue
            if not is_documented(identifier, corpus):
                undocumented += 1
                findings.append(
                    {
                        "check": CHECK_ID,
                        "severity": severity,
                        "doc_file": None,
                        "doc_line": None,
                        "source": name,
                        "source_ref": label,
                        "message": f"Interface element is not documented: {identifier}",
                        "covered_topic": f"surface:{identifier}",
                    }
                )

        coverage.append(
            {
                "area": f"surface manifest: {label}",
                "state": CONFLICTING if undocumented else REVIEWED,
                "sources": [name],
                "detail": (
                    f"{undocumented} undocumented interface element(s) across "
                    f"{len(doc_files)} documentation file(s)."
                ),
            }
        )

    return findings, coverage
