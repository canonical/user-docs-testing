"""The `docs-testing` command line.

Deliberately small. It exists so that nobody has to know where results files live
or how the built-in checks are implemented:

    init      write a starter configuration
    list      show the checks this tool ships
    validate  check the configuration before CI does
    run       run the locally runnable (deterministic) tests
    report    re-render the results of a previous run
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

import yaml

from docs_testing import __version__, report
from docs_testing.config import (
    BUILTINS,
    DEFAULT_CONFIG_NAME,
    AGENTIC,
    Config,
    ConfigError,
    load,
    warnings as config_warnings,
)
from docs_testing.results import EXIT_FOR_STATUS, EXIT_OK, EXIT_TOOL_ERROR, Results
from docs_testing.runner import run_deterministic

STARTER_CONFIG = """\
# Documentation testing — https://github.com/canonical/user-docs-testing
version: 1

# The documentation to test.
targets: "docs/reference/**/*.md"

# The product this documentation describes. Findings must be backed by evidence
# from a source, so a review with no source cannot prove anything.
sources:
  - name: product
    repo: {repo}

# What to check. `docs-testing list` shows every available check.
tests:
  - reference-review
"""

WORKFLOW_PATH = Path(".github/workflows/docs-testing.md")


def _fail(message: str) -> int:
    sys.stderr.write(f"error: {message}\n")
    return EXIT_TOOL_ERROR


def _load_or_report(path: Path) -> Config | int:
    try:
        return load(path)
    except ConfigError as exc:
        sys.stderr.write(exc.render(path) + "\n")
        return EXIT_TOOL_ERROR


# --- Commands ---------------------------------------------------------------


def cmd_init(args) -> int:
    path = Path(args.config)
    if path.exists() and not args.force:
        return _fail(f"{path} already exists (use --force to overwrite)")
    path.write_text(STARTER_CONFIG.format(repo=args.repo or "my-org/my-product"), encoding="utf-8")
    sys.stdout.write(
        f"Wrote {path}\n\n"
        "Next:\n"
        "  1. Point `targets:` at your documentation and `sources.repo` at your product.\n"
        "  2. Run `docs-testing validate`.\n"
        "  3. Install the workflow:  gh aw add canonical/user-docs-testing/docs-testing\n"
    )
    return EXIT_OK


def cmd_list(args) -> int:
    sys.stdout.write("\nReviews this tool ships (performed by an AI engine in CI):\n")
    for builtin in BUILTINS.values():
        sys.stdout.write(f"  {builtin.id:<24} {builtin.summary}\n")

    sys.stdout.write(
        "\nUse one in docs-testing.config.yml:\n"
        "  tests:\n"
        "    - reference-review\n"
        "\nDeterministic checks are your own command \u2014 any language, as long as it\n"
        "writes the schema in docs/reference/results.md, or just exits non-zero:\n"
        "  tests:\n"
        "    - name: my-check\n"
        "      run: \"python3 scripts/my_check.py --output results/my.json\"\n"
        "      results: \"results/my.json\"\n"
        "\nThe scripts under tests/deterministic/ in the user-docs-testing repository\n"
        "are worked examples of writing one. They are demonstrations, not checks you\n"
        "are expected to run.\n\n"
    )
    return EXIT_OK


def _workflow_checkouts(path: Path) -> tuple[list[str], str | None]:
    """Source directories the installed workflow checks out, if it can be read."""
    if not path.exists():
        return [], f"{path} not found"
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---"):
        return [], f"{path} has no frontmatter"
    parts = text.split("---", 2)
    if len(parts) < 3:
        return [], f"{path} has no frontmatter"
    try:
        frontmatter = yaml.safe_load(parts[1]) or {}
    except yaml.YAMLError as exc:
        return [], f"could not parse {path} frontmatter: {exc}"

    names: list[str] = []
    for entry in frontmatter.get("checkout") or []:
        if isinstance(entry, dict) and isinstance(entry.get("path"), str):
            checkout_path = entry["path"].strip("/")
            if checkout_path.startswith("sources/"):
                names.append(checkout_path[len("sources/"):])
    return names, None


def cmd_validate(args) -> int:
    config = _load_or_report(Path(args.config))
    if isinstance(config, int):
        return config

    problems: list[str] = []
    notes = config_warnings(config)

    # The config declares which sources a review needs; the workflow declares
    # which ones actually get checked out. When they disagree, the review is
    # silently narrower than the config claims, so it is worth saying out loud.
    checked_out, why_not = _workflow_checkouts(Path(args.workflow))
    if why_not:
        notes.append(f"could not cross-check the workflow ({why_not})")
    else:
        declared = {s.name for s in config.sources}
        for source in config.sources:
            if source.name not in checked_out:
                message = (
                    f"source `{source.name}` is configured but {args.workflow} does not "
                    f"check it out into sources/{source.name}"
                )
                (problems if source.required else notes).append(message)
        for name in checked_out:
            if name not in declared:
                notes.append(
                    f"{args.workflow} checks out sources/{name}, which is not declared in "
                    f"{args.config}"
                )

    # Built as one block and printed in order: interleaving stdout and stderr
    # produced a report that said "Problems:" and "is valid" in the same breath.
    lines: list[str] = ["", f"Configuration: {args.config}", ""]
    lines.append(f"  documentation: {', '.join(config.targets) or '(per-test)'}")
    if config.exclude:
        lines.append(f"  excluded:      {', '.join(config.exclude)}")
    lines.append(
        f"  sources:       {len(config.sources)} "
        f"({sum(1 for s in config.sources if s.required)} required, "
        f"{sum(1 for s in config.sources if s.is_private)} private)"
    )
    for test in config.tests:
        kind = "review" if test.kind == AGENTIC else "check "
        lines.append(f"  {kind}         {test.name}")

    secrets = sorted({s.secret_name for s in config.sources if s.secret_name})
    if secrets:
        lines.append("")
        lines.append(f"  Required repository secrets: {', '.join(secrets)}")
        lines.append(
            "  (read tokens for private sources; separate from the AI engine's token)"
        )

    if notes:
        lines.append("")
        lines.append("Warnings:")
        lines.extend(f"  - {note}" for note in notes)

    if problems:
        lines.append("")
        lines.append("Problems:")
        lines.extend(f"  - {problem}" for problem in problems)
        lines.append("")
        lines.append(
            "A required source that is never checked out makes every review that "
            "depends on it incomplete."
        )
        lines.append("")
        plural = "problem" if len(problems) == 1 else "problems"
        lines.append(
            f"FAILED: fix the {len(problems)} {plural} above before relying on this "
            "configuration."
        )
        lines.append("")
        sys.stdout.write("\n".join(lines))
        sys.stdout.flush()
        return EXIT_TOOL_ERROR

    lines.append("")
    lines.append("OK: this configuration is valid.")
    lines.append("")
    sys.stdout.write("\n".join(lines))
    sys.stdout.flush()
    return EXIT_OK


def cmd_run(args) -> int:
    config = _load_or_report(Path(args.config))
    if isinstance(config, int):
        # A malformed config cannot produce meaningful results, so record the
        # failure where CI will find it rather than leaving an empty directory.
        payload = _write_config_error(Path(args.output), Path(args.config))
        _emit(payload, args)
        return EXIT_TOOL_ERROR

    root = Path(args.root).resolve()
    results = run_deterministic(
        config,
        root=root,
        sources_root=root / args.sources_root,
        timeout=args.timeout,
    )
    payload = results.write(
        Path(args.output), fail_on_findings=config.reporting.fail_on_findings
    )
    _emit(payload, args)
    return EXIT_FOR_STATUS[payload["summary"]["status"]]


def _write_config_error(output: Path, config_path: Path) -> dict:
    from docs_testing.results import ToolError

    results = Results()
    results.errors.append(
        ToolError(
            stage="config",
            test=None,
            message=f"`{config_path}` could not be loaded, so no test could run",
            remedy="run `docs-testing validate` to see exactly what is wrong",
        )
    )
    return results.write(output)


def cmd_report(args) -> int:
    path = Path(args.results)
    if not path.exists():
        return _fail(f"no results at {path} — run `docs-testing run` first")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return _fail(f"could not read {path}: {exc}")
    if not isinstance(payload, dict) or "summary" not in payload:
        return _fail(f"{path} is not a docs-testing results file")
    _emit(payload, args)
    return EXIT_FOR_STATUS[payload["summary"]["status"]]


def _emit(payload: dict, args) -> None:
    if getattr(args, "json", False):
        sys.stdout.write(json.dumps(payload, indent=2) + "\n")
    else:
        sys.stdout.write(report.render_text(payload))

    step_summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if step_summary:
        try:
            with open(step_summary, "a", encoding="utf-8") as handle:
                handle.write(report.render_markdown(payload) + "\n")
        except OSError:
            pass


# --- Entry point ------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="docs-testing",
        description="Reusable documentation testing.",
    )
    parser.add_argument("--version", action="version", version=f"docs-testing {__version__}")
    subparsers = parser.add_subparsers(dest="command", required=True)

    def add_config_arg(sub):
        sub.add_argument("--config", default=DEFAULT_CONFIG_NAME, help="Configuration file.")

    init = subparsers.add_parser("init", help="Write a starter configuration.")
    add_config_arg(init)
    init.add_argument("--repo", help="Your product repository, as owner/name.")
    init.add_argument("--force", action="store_true", help="Overwrite an existing config.")
    init.set_defaults(func=cmd_init)

    listing = subparsers.add_parser("list", help="Show the checks this tool ships.")
    listing.set_defaults(func=cmd_list)

    validate = subparsers.add_parser("validate", help="Check the configuration.")
    add_config_arg(validate)
    validate.add_argument(
        "--workflow",
        default=str(WORKFLOW_PATH),
        help="Installed workflow to cross-check source checkouts against.",
    )
    validate.set_defaults(func=cmd_validate)

    run = subparsers.add_parser("run", help="Run the deterministic tests.")
    add_config_arg(run)
    run.add_argument("--root", default=".", help="Repository root.")
    run.add_argument("--sources-root", default="sources", help="Where sources are checked out.")
    run.add_argument("--output", default="results/all.json", help="Where to write results.")
    run.add_argument("--timeout", type=int, default=1800, help="Per-command timeout, in seconds.")
    run.add_argument("--json", action="store_true", help="Print results as JSON.")
    run.set_defaults(func=cmd_run)

    show = subparsers.add_parser("report", help="Re-render a previous run's results.")
    show.add_argument("--results", default="results/all.json", help="Results file to render.")
    show.add_argument("--json", action="store_true", help="Print results as JSON.")
    show.set_defaults(func=cmd_report)

    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)
