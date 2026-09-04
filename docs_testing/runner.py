"""Execute the deterministic half of a run and combine everything into results.

Every failure mode here has one rule behind it: a run that did not work must not
produce a clean pass. A crashed command, a missing results file, or malformed
JSON is recorded as a `ToolError`, never quietly turned into zero findings.
"""

from __future__ import annotations

import json
import shlex
import subprocess
import sys
from pathlib import Path

from docs_testing.checks import source_evidence, undocumented_surface
from docs_testing.checks.globs import find_files
from docs_testing.config import Config, Test
from docs_testing.results import (
    UNSUPPORTED,
    Results,
    ToolError,
    normalize_coverage,
    normalize_finding,
)

DEFAULT_TIMEOUT = 1800

# Characters that only mean something to a shell. User commands are executed
# without one, so these would be passed through as literal arguments and silently
# do the wrong thing. Rejecting them early is clearer than debugging that later.
_SHELL_METACHARACTERS = ("|", "&", ";", ">", "<", "`", "$(", "&&", "||")


def _split(command: str) -> list[str]:
    try:
        parts = shlex.split(command)
    except ValueError as exc:
        raise ValueError(f"could not parse the command ({exc})") from exc
    if not parts:
        raise ValueError("the command is empty")
    return parts


def _reject_shell_syntax(command: str) -> None:
    used = [m for m in _SHELL_METACHARACTERS if m in command]
    if used:
        raise ValueError(
            f"the command uses shell syntax ({', '.join(used)}), but commands run "
            "without a shell so that configuration cannot inject one. "
            "Move the pipeline into a script and call that script instead"
        )


def _execute(command: str, *, cwd: Path, label: str, timeout: int) -> subprocess.CompletedProcess:
    _reject_shell_syntax(command)
    argv = _split(command)
    sys.stderr.write(f"[{label}] $ {command}\n")
    return subprocess.run(
        argv,
        cwd=cwd,
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
    )


def _tail(text: str | None, lines: int = 20) -> str | None:
    if not text:
        return None
    trimmed = text.strip().splitlines()
    return "\n".join(trimmed[-lines:]) if trimmed else None


def _run_builtin(test: Test, config: Config, root: Path) -> tuple[list[dict], list[dict]]:
    if test.uses == "undocumented-surface":
        manifest = test.options["manifest"]
        manifests = [manifest] if isinstance(manifest, str) else list(manifest)
        ignore = test.options.get("ignore") or []
        return undocumented_surface.run(
            manifests=manifests,
            docs=test.docs,
            exclude=test.exclude,
            root=root,
            ignore=[ignore] if isinstance(ignore, str) else list(ignore),
            severity=test.options.get("severity", "warning"),
            source_name=test.options.get("source_name"),
        )
    raise ValueError(f"`{test.uses}` is not a deterministic built-in")


def _ingest_results(path: Path, label: str, test: Test, results: Results) -> None:
    """Read one test's results file, recording anything wrong with it."""
    if not path.exists():
        results.errors.append(
            ToolError(
                stage="results",
                test=test.name,
                message=f"declared `results: {label}` but the file was not written",
                remedy=(
                    "make the command write that file, or remove `results:` to judge the "
                    "test by its exit status alone"
                ),
            )
        )
        return

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        results.errors.append(
            ToolError(
                stage="results",
                test=test.name,
                message=f"could not read `{label}`: {exc}",
                remedy="the file must be JSON matching docs/reference/results.md",
            )
        )
        return

    if not isinstance(data, dict):
        results.errors.append(
            ToolError(
                stage="results",
                test=test.name,
                message=f"`{label}` contains {type(data).__name__}, expected an object",
                remedy="see docs/reference/results.md for the expected shape",
            )
        )
        return

    for raw in data.get("findings") or []:
        finding, problem = normalize_finding(raw, test=test.name)
        if finding:
            results.findings.append(finding)
        else:
            results.errors.append(
                ToolError(
                    stage="results",
                    test=test.name,
                    message=f"discarded a malformed finding: {problem}",
                    remedy="see docs/reference/results.md",
                )
            )

    for raw in data.get("coverage") or []:
        entry, problem = normalize_coverage(raw, test=test.name)
        if entry:
            results.coverage.append(entry)
        else:
            results.errors.append(
                ToolError(
                    stage="results",
                    test=test.name,
                    message=f"discarded a malformed coverage entry: {problem}",
                    remedy="see docs/reference/results.md",
                )
            )

    for evidence in data.get("source_evidence") or []:
        if isinstance(evidence, dict):
            results.source_evidence.append(evidence)


def run_deterministic(
    config: Config,
    *,
    root: Path,
    sources_root: Path,
    timeout: int = DEFAULT_TIMEOUT,
) -> Results:
    results = Results()
    results.tests_declared = len(config.deterministic_tests)
    results.reviews_declared = len(config.agentic_tests)
    results.plan = config.plan()

    # Source evidence is infrastructure, not a test: it runs on every run so that
    # nothing downstream can claim to have reviewed a source that was never there.
    evidence, coverage = source_evidence.collect(config, sources_root)
    results.source_evidence.extend(evidence)
    results.coverage.extend(coverage)

    # A test whose glob matches no file examines nothing. Left alone it would
    # sail through as a pass, which is the most misleading result of all.
    for test in config.tests:
        if test.docs and not find_files(test.docs, root, test.exclude):
            results.coverage.append(
                {
                    "area": f"documentation in scope for `{test.name}`",
                    "state": UNSUPPORTED,
                    "sources": [],
                    "detail": (
                        f"No file matches {', '.join(test.docs)}, so `{test.name}` "
                        "examined nothing. Check the glob."
                    ),
                    "test": test.name,
                }
            )

    for test in config.deterministic_tests:
        for index, command in enumerate(test.setup):
            try:
                completed = _execute(command, cwd=root, label=f"{test.name}:setup", timeout=timeout)
            except (ValueError, OSError, subprocess.SubprocessError) as exc:
                results.errors.append(
                    ToolError(
                        stage="setup",
                        test=test.name,
                        message=f"setup command {index + 1} could not run: {exc}",
                        detail=command,
                    )
                )
                break
            if completed.returncode != 0:
                results.errors.append(
                    ToolError(
                        stage="setup",
                        test=test.name,
                        message=f"setup command {index + 1} failed with exit status {completed.returncode}",
                        remedy="fix the setup command; this test did not run",
                        detail=_tail(completed.stderr or completed.stdout),
                    )
                )
                break
        else:
            _run_one(test, config, results, root=root, timeout=timeout)

    return results


def _run_one(test: Test, config: Config, results: Results, *, root: Path, timeout: int) -> None:
    if test.uses:
        try:
            findings, coverage = _run_builtin(test, config, root)
        except Exception as exc:  # a built-in raising is a bug in this tool
            results.errors.append(
                ToolError(
                    stage="check",
                    test=test.name,
                    message=f"the built-in `{test.uses}` check failed: {exc}",
                    remedy="this is a bug in user-docs-testing; please report it",
                )
            )
            return
        results.tests_run += 1
        for finding in findings:
            finding["test"] = test.name
            results.findings.append(finding)
        for entry in coverage:
            entry["test"] = test.name
            results.coverage.append(entry)
        return

    try:
        completed = _execute(test.run, cwd=root, label=test.name, timeout=timeout)
    except ValueError as exc:
        results.errors.append(
            ToolError(
                stage="command",
                test=test.name,
                message=str(exc),
                detail=test.run,
            )
        )
        return
    except FileNotFoundError as exc:
        results.errors.append(
            ToolError(
                stage="command",
                test=test.name,
                message=f"command not found: {exc.filename}",
                remedy="check the path, or install it in a `setup:` command",
                detail=test.run,
            )
        )
        return
    except subprocess.TimeoutExpired:
        results.errors.append(
            ToolError(
                stage="command",
                test=test.name,
                message=f"command timed out after {timeout}s",
                detail=test.run,
            )
        )
        return
    except (OSError, subprocess.SubprocessError) as exc:
        results.errors.append(
            ToolError(stage="command", test=test.name, message=str(exc), detail=test.run)
        )
        return

    results.tests_run += 1

    if test.results:
        # With a results file, the exit status is advisory: the file is the report.
        # A crash still matters, because the file may be absent or half-written.
        if completed.returncode != 0:
            results.errors.append(
                ToolError(
                    stage="command",
                    test=test.name,
                    message=f"command exited with status {completed.returncode}",
                    remedy="its results may be incomplete; fix the command before trusting this run",
                    detail=_tail(completed.stderr or completed.stdout),
                )
            )
        _ingest_results(root / test.results, test.results, test, results)
        return

    # No results file: this is the exit-status adapter. A non-zero exit is a
    # documentation finding, not a tool error — the command ran and said "no".
    if completed.returncode != 0:
        results.findings.append(
            {
                "check": test.name,
                "severity": "error",
                "doc_file": None,
                "doc_line": None,
                "source": None,
                "source_ref": None,
                "message": f"`{test.name}` reported a problem (exit status {completed.returncode}).",
                "detail": _tail(completed.stdout or completed.stderr),
                "test": test.name,
            }
        )
