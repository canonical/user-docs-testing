"""The result model: what a documentation test run is allowed to say happened.

The whole product rests on five outcomes staying distinct. Collapsing any of them
into "pass" would let a broken tool look like verified documentation, so the
precedence below is deliberate and load-bearing:

    error > fail > incomplete > warn > pass

`error` outranks everything because a run that could not execute correctly tells
you nothing about the documentation, including the parts that appeared to pass.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

SCHEMA_VERSION = 2

# --- Statuses ---------------------------------------------------------------

PASS = "pass"
WARN = "warn"
INCOMPLETE = "incomplete"
FAIL = "fail"
ERROR = "error"

#: Worst-first. `worst_status` relies on this ordering.
STATUS_PRECEDENCE = [ERROR, FAIL, INCOMPLETE, WARN, PASS]

STATUS_MEANING = {
    PASS: "Documentation was verified and nothing actionable was found.",
    WARN: "Documentation was verified; only non-blocking findings were reported.",
    INCOMPLETE: "Part of the intended scope could not be verified.",
    FAIL: "An actionable documentation problem was found.",
    ERROR: "The tool itself failed, so these results are not trustworthy.",
}

# --- Exit codes -------------------------------------------------------------

EXIT_OK = 0
EXIT_FINDINGS = 1
EXIT_TOOL_ERROR = 2
EXIT_INCOMPLETE = 3

EXIT_FOR_STATUS = {
    PASS: EXIT_OK,
    WARN: EXIT_OK,
    FAIL: EXIT_FINDINGS,
    INCOMPLETE: EXIT_INCOMPLETE,
    ERROR: EXIT_TOOL_ERROR,
}

# --- Check Run conclusions --------------------------------------------------

CONCLUSION_FOR_STATUS = {
    PASS: "success",
    WARN: "neutral",
    FAIL: "failure",
    INCOMPLETE: "neutral",  # overridable via reporting.on_incomplete_coverage
    ERROR: "action_required",
}

# --- Coverage vocabulary ----------------------------------------------------

REVIEWED = "reviewed-and-supported"
CONFLICTING = "reviewed-with-conflicting-evidence"
SKIPPED = "skipped-by-policy"
UNSUPPORTED = "unsupported-by-configured-sources"
BLOCKED = "blocked-required-source-unavailable"

COVERAGE_STATES = {REVIEWED, CONFLICTING, SKIPPED, UNSUPPORTED, BLOCKED}

#: Coverage states that mean "this area was not actually verified".
INCOMPLETE_STATES = {BLOCKED, UNSUPPORTED}

SEVERITIES = ("error", "warning")


def worst_status(statuses: list[str]) -> str:
    for candidate in STATUS_PRECEDENCE:
        if candidate in statuses:
            return candidate
    return PASS


@dataclass
class ToolError:
    """An infrastructure failure: the tool could not do its job.

    Kept separate from `findings` on purpose. A finding is a statement about the
    documentation; a tool error is a statement about the run. Merging them would
    let "the checker crashed" read as "the docs have a problem", or worse, let a
    crash that produced no findings read as a clean pass.
    """

    stage: str
    test: str | None
    message: str
    remedy: str | None = None
    detail: str | None = None

    def to_dict(self) -> dict:
        return {
            "stage": self.stage,
            "test": self.test,
            "message": self.message,
            "remedy": self.remedy,
            "detail": self.detail,
        }


@dataclass
class Results:
    """One run's combined outcome."""

    findings: list[dict] = field(default_factory=list)
    coverage: list[dict] = field(default_factory=list)
    source_evidence: list[dict] = field(default_factory=list)
    errors: list[ToolError] = field(default_factory=list)
    tests_run: int = 0
    tests_declared: int = 0
    #: Reviews are performed by the AI engine in CI, not by this process. They
    #: are counted so a local run does not look like it skipped half the work.
    reviews_declared: int = 0
    plan: dict = field(default_factory=dict)

    @property
    def blocking_findings(self) -> list[dict]:
        return [f for f in self.findings if f.get("severity") == "error"]

    @property
    def warnings(self) -> list[dict]:
        return [f for f in self.findings if f.get("severity") != "error"]

    @property
    def unverified(self) -> list[dict]:
        return [c for c in self.coverage if c.get("state") in INCOMPLETE_STATES]

    def status(self, *, fail_on_findings: bool = True) -> str:
        if self.errors:
            return ERROR
        if self.blocking_findings and fail_on_findings:
            return FAIL
        if self.unverified:
            return INCOMPLETE
        if self.findings:
            return WARN
        return PASS

    def to_dict(self, *, fail_on_findings: bool = True) -> dict:
        status = self.status(fail_on_findings=fail_on_findings)
        return {
            "tool": "user-docs-testing",
            "schema_version": SCHEMA_VERSION,
            "summary": {
                "status": status,
                "meaning": STATUS_MEANING[status],
                "tests_declared": self.tests_declared,
                "tests_run": self.tests_run,
                "reviews_declared": self.reviews_declared,
                "findings": len(self.findings),
                "blocking_findings": len(self.blocking_findings),
                "warnings": len(self.warnings),
                "unverified_areas": len(self.unverified),
                "tool_errors": len(self.errors),
            },
            "errors": [e.to_dict() for e in self.errors],
            "findings": self.findings,
            "coverage": self.coverage,
            "source_evidence": self.source_evidence,
            "plan": self.plan,
        }

    def write(self, path: Path, *, fail_on_findings: bool = True) -> dict:
        payload = self.to_dict(fail_on_findings=fail_on_findings)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
        return payload


def normalize_finding(raw: dict, *, test: str) -> tuple[dict | None, str | None]:
    """Coerce one finding from a test's results file.

    Returns `(finding, problem)`. A malformed finding is reported rather than
    dropped: silently discarding it would shrink the finding count and could turn
    a real failure into a pass.
    """
    if not isinstance(raw, dict):
        return None, f"finding is {type(raw).__name__}, expected an object"

    message = raw.get("message")
    if not isinstance(message, str) or not message.strip():
        return None, "finding has no 'message'"

    severity = raw.get("severity", "warning")
    if severity not in SEVERITIES:
        return None, f"finding has invalid severity {severity!r} (expected error or warning)"

    finding = dict(raw)
    finding["severity"] = severity
    finding.setdefault("check", test)
    finding.setdefault("doc_file", None)
    finding["test"] = test
    return finding, None


def normalize_coverage(raw: dict, *, test: str) -> tuple[dict | None, str | None]:
    if not isinstance(raw, dict):
        return None, f"coverage entry is {type(raw).__name__}, expected an object"
    area = raw.get("area")
    if not isinstance(area, str) or not area.strip():
        return None, "coverage entry has no 'area'"
    state = raw.get("state")
    if state not in COVERAGE_STATES:
        return None, f"coverage entry for {area!r} has invalid state {state!r}"
    entry = dict(raw)
    entry["test"] = test
    return entry, None
