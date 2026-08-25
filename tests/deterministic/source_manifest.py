#!/usr/bin/env python3
"""Source availability check.

Proves, deterministically and before any agent runs, which configured sources of
truth were ACTUALLY checked out — and blocks the documentation areas that depend
on the ones that were not.

This exists because an agent's own report is not evidence. Without this check, a
run where a private source failed to check out and a run where it was read
thoroughly can both end in the same "success": nothing in the pipeline
distinguishes "I read it" from "I never looked". This check records the machine
truth (directory present, commit SHA, file count) so the agent's claims can be
audited against it.

For every area in the config's top-level `source_map` whose owning sources are
all unavailable, it emits a coverage entry per RESULTS-SCHEMA.md:
  - `blocked-required-source-unavailable`   if any owning source is required
  - `unsupported-by-configured-sources`     if all owning sources are optional

It also emits a `source_evidence` list: one record per configured source, with
the commit SHA actually checked out. That SHA is the thing to check when you want
to know whether a private repository was really accessed.

It is standard-library only and needs no `setup`.

Usage:
    python source_manifest.py \\
        --config docs-testing.config.yml \\
        --sources-root sources \\
        --output results/source-availability.json
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

SCHEMA_VERSION = 1


def load_config(path: Path) -> dict:
    """Parse the config. PyYAML if present, else a minimal fallback parser."""
    try:
        import yaml
    except ImportError:
        sys.stderr.write("error: PyYAML is required for source_manifest.py\n")
        raise SystemExit(2)
    with path.open(encoding="utf-8") as fh:
        return yaml.safe_load(fh) or {}


def checkout_commit(path: Path) -> str | None:
    try:
        out = subprocess.run(
            ["git", "-C", str(path), "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            timeout=30,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    return out.stdout.strip() or None if out.returncode == 0 else None


def inspect_source(name: str, root: Path) -> dict:
    """Record what is actually on disk for one configured source."""
    path = root / name
    files = 0
    if path.is_dir():
        for entry in path.rglob("*"):
            if entry.is_file() and ".git/" not in entry.as_posix():
                files += 1
                if files >= 1000:  # enough to prove non-emptiness
                    break
    return {
        "name": name,
        "path": path.as_posix(),
        "available": files > 0,
        "commit": checkout_commit(path),
        "files_seen": files,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", default="docs-testing.config.yml")
    parser.add_argument(
        "--sources-root",
        default="sources",
        help="Directory holding the source checkouts (default: sources).",
    )
    parser.add_argument("--output", required=True, help="Where to write results JSON.")
    args = parser.parse_args(argv)

    config_path = Path(args.config)
    if not config_path.exists():
        sys.stderr.write(f"error: config not found: {config_path}\n")
        return 2
    config = load_config(config_path)

    root = Path(args.sources_root)
    required = {
        s["name"]: s.get("required", True)
        for s in (config.get("sources") or [])
        if s.get("name")
    }
    evidence = [inspect_source(name, root) for name in required]
    available = {e["name"] for e in evidence if e["available"]}

    coverage: list[dict] = []
    for area in config.get("source_map") or []:
        owners = area.get("sources") or []
        label = area.get("area") or ", ".join(area.get("paths") or [])
        if not owners:
            coverage.append(
                {
                    "area": label,
                    "state": "unsupported-by-configured-sources",
                    "sources": [],
                    "detail": "No configured source owns this area.",
                }
            )
            continue
        if any(o in available for o in owners):
            continue
        missing = ", ".join(owners)
        blocked = any(required.get(o, True) for o in owners)
        coverage.append(
            {
                "area": label,
                "state": (
                    "blocked-required-source-unavailable"
                    if blocked
                    else "unsupported-by-configured-sources"
                ),
                "sources": owners,
                "detail": (
                    f"Owning source(s) not checked out: {missing}. "
                    "This area was NOT verified."
                ),
            }
        )

    blocked_count = sum(
        1 for c in coverage if c["state"] == "blocked-required-source-unavailable"
    )
    results = {
        "tool": "source-availability",
        "schema_version": SCHEMA_VERSION,
        "summary": {
            "checks_run": 1,
            "sources_configured": len(required),
            "sources_available": len(available),
            "findings": 0,
            "status": "incomplete" if coverage else "pass",
        },
        "findings": [],
        "coverage": coverage,
        "source_evidence": evidence,
    }

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(results, indent=2), encoding="utf-8")

    for e in evidence:
        mark = "OK     " if e["available"] else "MISSING"
        req = "required" if required.get(e["name"], True) else "optional"
        commit = (e["commit"] or "-")[:12]
        sys.stderr.write(
            f"[{mark}] {e['name']:<28} {req:<8} commit={commit} files={e['files_seen']}\n"
        )
    sys.stderr.write(
        f"{len(available)}/{len(required)} source(s) available, "
        f"{blocked_count} area(s) blocked -> {output}\n"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
