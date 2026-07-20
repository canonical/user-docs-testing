#!/usr/bin/env python3
"""Deterministic test orchestrator for the documentation testing tool.

Reads a project config, runs each *deterministic* test's optional setup and its
command, then aggregates every test's results into a single combined file using
the schema in RESULTS-SCHEMA.md.

This orchestrator is project-agnostic. It does not know anything about a specific
product, documentation type, or language. It only:
  1. finds the deterministic tests declared in the config,
  2. runs their commands (which you provide, in any language), and
  3. collects the JSON results each command writes.

Agentic tests are handled by the AI engine in the workflow, not here.

The orchestrator runs on the CI runner. It does NOT set up your product's
environment — each deterministic test is responsible for its own dependencies
via its `setup` commands (or by needing none, which many doc checks do).

Usage:
    python run_tests.py --config docs-testing.config.yml
    python run_tests.py --config docs-testing.config.yml --output results/all.json
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

try:
    import yaml
except ImportError:  # pragma: no cover
    sys.stderr.write("error: PyYAML is required. Install with `pip install pyyaml`.\n")
    raise SystemExit(2)


SCHEMA_VERSION = 1


def load_config(path: Path) -> dict:
    with path.open(encoding="utf-8") as fh:
        return yaml.safe_load(fh) or {}


def deterministic_tests(config: dict) -> list[dict]:
    return [
        t
        for t in (config.get("tests", []) or [])
        if (t.get("type") == "deterministic") and t.get("enabled", True)
    ]


def run_commands(commands: list[str], *, label: str) -> None:
    for cmd in commands:
        sys.stderr.write(f"[{label}] $ {cmd}\n")
        subprocess.run(cmd, shell=True, check=True)


def read_results(path: Path, test_name: str) -> list[dict]:
    """Read one test's results file and return its findings, tagged with the test."""
    if not path.exists():
        sys.stderr.write(
            f"warning: test '{test_name}' produced no results file at {path}\n"
        )
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        sys.stderr.write(f"warning: could not read results for '{test_name}': {exc}\n")
        return []
    findings = data.get("findings", []) or []
    for finding in findings:
        finding.setdefault("test", test_name)
    return findings


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", default="docs-testing.config.yml")
    parser.add_argument(
        "--output",
        default="results/all.json",
        help="Where to write the combined results (default: results/all.json).",
    )
    parser.add_argument(
        "--continue-on-error",
        action="store_true",
        help="Keep running remaining tests if one command fails.",
    )
    args = parser.parse_args(argv)

    config_path = Path(args.config)
    if not config_path.exists():
        sys.stderr.write(f"error: config not found: {config_path}\n")
        return 2

    config = load_config(config_path)
    tests = deterministic_tests(config)

    all_findings: list[dict] = []
    tests_run = 0

    for test in tests:
        name = test.get("name", "unnamed")
        command = test.get("command")
        if not command:
            sys.stderr.write(f"warning: deterministic test '{name}' has no command; skipping.\n")
            continue

        try:
            run_commands(test.get("setup", []) or [], label=f"{name}:setup")
            run_commands([command], label=name)
        except subprocess.CalledProcessError as exc:
            sys.stderr.write(f"error: test '{name}' command failed: {exc}\n")
            if not args.continue_on_error:
                return 1

        tests_run += 1
        results_file = test.get("results_file")
        if results_file:
            all_findings.extend(read_results(Path(results_file), name))

    has_error = any(f.get("severity") == "error" for f in all_findings)
    combined = {
        "tool": "user-docs-testing",
        "schema_version": SCHEMA_VERSION,
        "summary": {
            "tests_run": tests_run,
            "findings": len(all_findings),
            "status": "fail" if has_error else "pass",
        },
        "findings": all_findings,
    }

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(combined, indent=2), encoding="utf-8")

    sys.stderr.write(
        f"ran {tests_run} deterministic test(s), "
        f"{len(all_findings)} finding(s) -> {output}\n"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
