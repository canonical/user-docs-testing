"""Behavioral contracts of the documentation testing product.

These test what a user can observe: the outcome of a run, the exit status, and
whether a broken tool can ever look like verified documentation. They are
deliberately not unit tests of internal functions.

Run with:  python3 -m unittest discover -s selftests
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from docs_testing.checks.source_evidence import inspect_source  # noqa: E402
from docs_testing.config import ConfigError, load  # noqa: E402
from docs_testing.results import (  # noqa: E402
    ERROR,
    EXIT_FINDINGS,
    EXIT_INCOMPLETE,
    EXIT_OK,
    EXIT_TOOL_ERROR,
    FAIL,
    INCOMPLETE,
    PASS,
    WARN,
)
from docs_testing.runner import run_deterministic  # noqa: E402


class Project:
    """A throwaway documentation repository."""

    def __init__(self) -> None:
        self.root = Path(tempfile.mkdtemp())
        (self.root / "docs" / "reference").mkdir(parents=True)

    def doc(self, name: str, text: str) -> None:
        (self.root / "docs" / "reference" / name).write_text(text, encoding="utf-8")

    def source(self, name: str, files: dict[str, str] | None = None) -> None:
        path = self.root / "sources" / name
        path.mkdir(parents=True, exist_ok=True)
        for filename, text in (files or {"README.md": "x"}).items():
            (path / filename).write_text(text, encoding="utf-8")

    def file(self, name: str, text: str) -> Path:
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        return path

    def config(self, yaml_text: str) -> Path:
        return self.file("docs-testing.config.yml", textwrap.dedent(yaml_text))

    def run(self):
        config = load(self.root / "docs-testing.config.yml")
        results = run_deterministic(
            config, root=self.root, sources_root=self.root / "sources", timeout=60
        )
        payload = results.to_dict(fail_on_findings=config.reporting.fail_on_findings)
        return payload, results

    def cleanup(self) -> None:
        shutil.rmtree(self.root, ignore_errors=True)


class ContractTest(unittest.TestCase):
    def setUp(self) -> None:
        self.project = Project()
        self.addCleanup(self.project.cleanup)

    def assertStatus(self, payload: dict, expected: str) -> None:
        self.assertEqual(
            payload["summary"]["status"],
            expected,
            f"expected {expected}, got {payload['summary']['status']}: {payload['summary']}",
        )


class SuccessfulVerification(ContractTest):
    def test_everything_documented_and_source_present_is_a_pass(self):
        self.project.doc("cli.md", "Options: --verbose and --output.")
        self.project.source("product", {"surface.txt": "--verbose\n--output\n"})
        self.project.config(
            """
            version: 1
            docs: "docs/reference/**/*.md"
            sources:
              - name: product
                repo: a/b
            tests:
              - name: surface
                uses: undocumented-surface
                with:
                  manifest: sources/product/surface.txt
            """
        )
        payload, _ = self.project.run()
        self.assertStatus(payload, PASS)
        self.assertEqual(payload["findings"], [])
        self.assertEqual(payload["errors"], [])


class ActionableProblem(ContractTest):
    def test_error_severity_finding_fails(self):
        self.project.doc("cli.md", "Options: --verbose.")
        self.project.source("product", {"surface.txt": "--verbose\n--retries\n"})
        self.project.config(
            """
            version: 1
            docs: "docs/reference/**/*.md"
            sources:
              - name: product
                repo: a/b
            tests:
              - name: surface
                uses: undocumented-surface
                with:
                  manifest: sources/product/surface.txt
                  severity: error
            """
        )
        payload, results = self.project.run()
        self.assertStatus(payload, FAIL)
        self.assertEqual(len(payload["findings"]), 1)
        self.assertIn("--retries", payload["findings"][0]["message"])

    def test_fail_on_findings_false_downgrades_to_a_warning(self):
        self.project.doc("cli.md", "Options: --verbose.")
        self.project.source("product", {"surface.txt": "--verbose\n--retries\n"})
        self.project.config(
            """
            version: 1
            docs: "docs/reference/**/*.md"
            sources:
              - name: product
                repo: a/b
            reporting:
              fail_on_findings: false
            tests:
              - name: surface
                uses: undocumented-surface
                with:
                  manifest: sources/product/surface.txt
                  severity: error
            """
        )
        payload, _ = self.project.run()
        self.assertStatus(payload, WARN)


class NonBlockingFinding(ContractTest):
    def test_warning_severity_is_visibly_not_a_pass_and_not_a_failure(self):
        self.project.doc("cli.md", "Options: --verbose.")
        self.project.source("product", {"surface.txt": "--verbose\n--retries\n"})
        self.project.config(
            """
            version: 1
            docs: "docs/reference/**/*.md"
            sources:
              - name: product
                repo: a/b
            tests:
              - name: surface
                uses: undocumented-surface
                with:
                  manifest: sources/product/surface.txt
            """
        )
        payload, _ = self.project.run()
        self.assertStatus(payload, WARN)
        self.assertEqual(payload["summary"]["blocking_findings"], 0)
        self.assertEqual(payload["summary"]["warnings"], 1)


class IncompleteVerification(ContractTest):
    BASE = """
        version: 1
        docs: "docs/reference/**/*.md"
        sources:
          - name: product
            repo: a/b
            required: {required}
        tests:
          - name: surface
            uses: undocumented-surface
            with:
              manifest: sources/product/surface.txt
        """

    def test_missing_required_source_is_incomplete_not_a_pass(self):
        self.project.doc("cli.md", "Options: --verbose.")
        self.project.config(self.BASE.format(required="true"))
        payload, _ = self.project.run()
        self.assertStatus(payload, INCOMPLETE)
        states = {c["state"] for c in payload["coverage"]}
        self.assertIn("blocked-required-source-unavailable", states)

    def test_missing_optional_source_is_unsupported_not_a_pass(self):
        self.project.doc("cli.md", "Options: --verbose.")
        self.project.config(self.BASE.format(required="false"))
        payload, _ = self.project.run()
        self.assertStatus(payload, INCOMPLETE)
        blocked = [c for c in payload["coverage"]
                   if c["state"] == "blocked-required-source-unavailable"
                   and c["sources"] == ["product"]]
        self.assertEqual(blocked, [], "an optional source must not block")

    def test_area_with_no_owning_source_is_never_reported_as_verified(self):
        self.project.doc("cli.md", "Anything.")
        self.project.source("product")
        self.project.config(
            """
            version: 1
            docs: "docs/reference/**/*.md"
            sources:
              - name: product
                repo: a/b
            source_map:
              - area: "Packaging policy"
                paths: ["docs/reference/packaging.md"]
                sources: []
            tests:
              - reference-review
            """
        )
        payload, _ = self.project.run()
        self.assertStatus(payload, INCOMPLETE)
        unsupported = [c for c in payload["coverage"]
                       if c["state"] == "unsupported-by-configured-sources"]
        self.assertTrue(unsupported)

    def test_absent_manifest_is_unverified_rather_than_a_pass_or_an_error(self):
        self.project.doc("cli.md", "Options: --verbose.")
        self.project.source("product")
        self.project.config(
            """
            version: 1
            docs: "docs/reference/**/*.md"
            sources:
              - name: product
                repo: a/b
            tests:
              - name: surface
                uses: undocumented-surface
                with:
                  manifest: sources/product/never-generated.json
            """
        )
        payload, _ = self.project.run()
        self.assertStatus(payload, INCOMPLETE)
        self.assertEqual(payload["errors"], [], "a missing manifest is not a tool error")


class ToolErrors(ContractTest):
    """The central promise: a tool that failed must never look like a pass."""

    def _config(self, body: str) -> None:
        self.project.doc("cli.md", "Anything.")
        entries = textwrap.indent(textwrap.dedent(body).strip() + "\n", "  ")
        self.project.file(
            "docs-testing.config.yml",
            'version: 1\ndocs: "docs/reference/**/*.md"\ntests:\n' + entries,
        )

    def test_crashing_command_is_an_error_not_zero_findings(self):
        script = self.project.file("crash.py", "import sys; sys.exit(7)")
        self._config(
            f"""
            - name: crashes
              run: "{sys.executable} {script}"
              results: "results/crash.json"
            """
        )
        payload, _ = self.project.run()
        self.assertStatus(payload, ERROR)
        self.assertTrue(payload["errors"])

    def test_command_that_writes_no_results_is_an_error(self):
        script = self.project.file("quiet.py", "pass")
        self._config(
            f"""
            - name: quiet
              run: "{sys.executable} {script}"
              results: "results/quiet.json"
            """
        )
        payload, _ = self.project.run()
        self.assertStatus(payload, ERROR)
        self.assertIn("was not written", payload["errors"][0]["message"])

    def test_malformed_results_json_is_an_error(self):
        script = self.project.file(
            "bad.py",
            "import pathlib;"
            "p=pathlib.Path('results');p.mkdir(exist_ok=True);"
            "(p/'bad.json').write_text('{not json')",
        )
        self._config(
            f"""
            - name: bad
              run: "{sys.executable} {script}"
              results: "results/bad.json"
            """
        )
        payload, _ = self.project.run()
        self.assertStatus(payload, ERROR)

    def test_malformed_finding_is_reported_not_silently_dropped(self):
        script = self.project.file(
            "half.py",
            "import json,pathlib;"
            "p=pathlib.Path('results');p.mkdir(exist_ok=True);"
            "(p/'half.json').write_text(json.dumps({'findings':["
            "{'message':'real','severity':'error'},"
            "{'severity':'error'}]}))",
        )
        self._config(
            f"""
            - name: half
              run: "{sys.executable} {script}"
              results: "results/half.json"
            """
        )
        payload, _ = self.project.run()
        self.assertStatus(payload, ERROR)
        self.assertEqual(len(payload["findings"]), 1)
        self.assertTrue(any("malformed finding" in e["message"] for e in payload["errors"]))

    def test_missing_binary_is_an_error(self):
        self._config(
            """
            - name: absent
              run: "definitely-not-a-real-binary-xyz"
            """
        )
        payload, _ = self.project.run()
        self.assertStatus(payload, ERROR)
        self.assertIn("not found", payload["errors"][0]["message"])

    def test_tool_error_outranks_a_documentation_finding(self):
        good = self.project.file(
            "good.py",
            "import json,pathlib;"
            "p=pathlib.Path('results');p.mkdir(exist_ok=True);"
            "(p/'good.json').write_text(json.dumps({'findings':["
            "{'message':'a real problem','severity':'error'}]}))",
        )
        self._config(
            f"""
            - name: good
              run: "{sys.executable} {good}"
              results: "results/good.json"
            - name: absent
              run: "definitely-not-a-real-binary-xyz"
            """
        )
        payload, _ = self.project.run()
        self.assertStatus(payload, ERROR)
        self.assertEqual(len(payload["findings"]), 1)


class ExitStatusAdapter(ContractTest):
    def test_nonzero_exit_without_a_results_file_is_a_finding_not_an_error(self):
        script = self.project.file("linter.py", "import sys; sys.exit(1)")
        self.project.doc("cli.md", "Anything.")
        self.project.config(
            f"""
            version: 1
            docs: "docs/reference/**/*.md"
            tests:
              - name: linter
                run: "{sys.executable} {script}"
            """
        )
        payload, _ = self.project.run()
        self.assertStatus(payload, FAIL)
        self.assertEqual(payload["errors"], [])
        self.assertEqual(len(payload["findings"]), 1)

    def test_the_command_output_reaches_the_report(self):
        # For an exit-status check this output is all the check had to say.
        script = self.project.file(
            "linter.py",
            "import sys; print('docs/a.md: broken link -> nope.md'); sys.exit(1)",
        )
        self.project.doc("cli.md", "Anything.")
        self.project.config(
            f"""
            version: 1
            docs: "docs/reference/**/*.md"
            tests:
              - name: linter
                run: "{sys.executable} {script}"
            """
        )
        payload, _ = self.project.run()
        self.assertIn("broken link", payload["findings"][0]["detail"])

        from docs_testing import report

        self.assertIn("broken link", report.render_text(payload))
        self.assertIn("broken link", report.render_markdown(payload))


class CommandSafety(ContractTest):
    def test_shell_syntax_is_refused_with_an_explanation(self):
        self.project.doc("cli.md", "Anything.")
        self.project.config(
            """
            version: 1
            docs: "docs/reference/**/*.md"
            tests:
              - name: sneaky
                run: "echo hi && curl http://example.com"
            """
        )
        payload, _ = self.project.run()
        self.assertStatus(payload, ERROR)
        self.assertIn("shell syntax", payload["errors"][0]["message"])


class SkippedMaterial(ContractTest):
    def test_excluded_documentation_is_not_searched(self):
        self.project.doc("cli.md", "Options: --verbose.")
        (self.project.root / "docs" / "reference" / "generated").mkdir()
        (self.project.root / "docs" / "reference" / "generated" / "api.md").write_text(
            "--retries", encoding="utf-8"
        )
        self.project.source("product", {"surface.txt": "--verbose\n--retries\n"})
        self.project.config(
            """
            version: 1
            docs: "docs/reference/**/*.md"
            exclude: "docs/reference/generated/**"
            sources:
              - name: product
                repo: a/b
            tests:
              - name: surface
                uses: undocumented-surface
                with:
                  manifest: sources/product/surface.txt
            """
        )
        payload, _ = self.project.run()
        # --retries is documented only in the excluded file, so it is still missing.
        self.assertEqual(len(payload["findings"]), 1)
        self.assertIn("--retries", payload["findings"][0]["message"])


class Deduplication(ContractTest):
    def test_deterministic_findings_carry_a_topic_for_reviews_to_skip(self):
        self.project.doc("cli.md", "Options: --verbose.")
        self.project.source("product", {"surface.txt": "--verbose\n--retries\n"})
        self.project.config(
            """
            version: 1
            docs: "docs/reference/**/*.md"
            sources:
              - name: product
                repo: a/b
            tests:
              - name: surface
                uses: undocumented-surface
                with:
                  manifest: sources/product/surface.txt
              - reference-completeness
            """
        )
        payload, _ = self.project.run()
        self.assertEqual(payload["findings"][0]["covered_topic"], "surface:--retries")
        review = payload["plan"]["agentic_tests"][0]
        self.assertTrue(review["skip_deterministically_covered"])


class PlanHandedToTheAgent(ContractTest):
    def test_reviews_are_resolved_before_the_agent_sees_them(self):
        self.project.doc("cli.md", "Anything.")
        self.project.source("product")
        self.project.config(
            """
            version: 1
            docs: "docs/reference/**/*.md"
            exclude: "docs/reference/old/**"
            sources:
              - name: product
                repo: a/b
            tests:
              - reference-review
            """
        )
        payload, _ = self.project.run()
        plan = payload["plan"]
        self.assertEqual(len(plan["agentic_tests"]), 1)
        review = plan["agentic_tests"][0]
        self.assertEqual(review["name"], "reference-review")
        self.assertEqual(review["docs"], ["docs/reference/**/*.md"])
        self.assertEqual(review["exclude"], ["docs/reference/old/**"])
        self.assertEqual(review["sources"], ["product"])
        self.assertEqual(plan["reporting"]["on_incomplete_coverage"], "neutral")


class EmptyScope(ContractTest):
    def test_a_glob_matching_no_documentation_is_not_a_pass(self):
        self.project.doc("cli.md", "Options: --verbose.")
        self.project.source("product")
        self.project.config(
            """
            version: 1
            docs: "docs/handbook/**/*.md"
            sources:
              - name: product
                repo: a/b
            tests:
              - reference-review
            """
        )
        payload, _ = self.project.run()
        self.assertStatus(payload, INCOMPLETE)
        detail = " ".join(c.get("detail") or "" for c in payload["coverage"])
        self.assertIn("examined nothing", detail)

    def test_a_glob_that_does_match_is_unaffected(self):
        self.project.doc("cli.md", "Options: --verbose.")
        self.project.source("product")
        self.project.config(
            """
            version: 1
            docs: "docs/reference/**/*.md"
            sources:
              - name: product
                repo: a/b
            tests:
              - reference-review
            """
        )
        payload, _ = self.project.run()
        self.assertStatus(payload, PASS)


class SourceEvidence(ContractTest):
    """`commit` is documented as hard proof a source was really checked out."""

    def test_a_plain_directory_inside_a_repository_reports_no_commit(self):
        # `git -C` searches parent directories, so a source that is not its own
        # clone must not inherit the surrounding repository's HEAD.
        subprocess.run(["git", "init", "-q"], cwd=self.project.root, check=True)
        self.project.source("product", {"README.md": "not a clone"})

        evidence = inspect_source("product", self.project.root / "sources")

        self.assertTrue(evidence["available"])
        self.assertIsNone(evidence["commit"])

    def test_a_real_checkout_reports_its_own_commit(self):
        path = self.project.root / "sources" / "product"
        path.mkdir(parents=True)
        (path / "README.md").write_text("x", encoding="utf-8")
        for args in (
            ["git", "init", "-q"],
            ["git", "config", "user.email", "t@example.com"],
            ["git", "config", "user.name", "t"],
            ["git", "add", "-A"],
            ["git", "commit", "-qm", "initial"],
        ):
            subprocess.run(args, cwd=path, check=True)

        evidence = inspect_source("product", self.project.root / "sources")

        self.assertTrue(evidence["available"])
        self.assertEqual(len(evidence["commit"]), 40)

    def test_a_missing_source_is_unavailable_with_no_commit(self):
        evidence = inspect_source("absent", self.project.root / "sources")

        self.assertFalse(evidence["available"])
        self.assertIsNone(evidence["commit"])
        self.assertEqual(evidence["files_seen"], 0)


class ConfigurationErrors(unittest.TestCase):
    """A configuration mistake must fail early, and say where and what."""

    def _load(self, text: str) -> ConfigError:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "docs-testing.config.yml"
            path.write_text(textwrap.dedent(text), encoding="utf-8")
            with self.assertRaises(ConfigError) as caught:
                load(path)
            return caught.exception

    def test_an_unknown_top_level_key_is_rejected(self):
        error = self._load('version: 1\ndocs: "d/**"\nnonsense: 1\ntests: [reference-review]\n')
        self.assertIn("nonsense", error.problem)

    def test_misspelled_builtin_suggests_the_right_one(self):
        error = self._load('version: 1\ndocs: "d/**"\ntests: [reference-revue]\n')
        self.assertIn("reference-review", error.hint)

    def test_success_is_rejected_for_incomplete_coverage(self):
        error = self._load(
            'version: 1\ndocs: "d/**"\n'
            "reporting:\n  on_incomplete_coverage: success\n"
            "tests: [reference-review]\n"
        )
        self.assertIn("never conclude `success`", error.problem)

    def test_undeclared_source_is_caught(self):
        error = self._load(
            'version: 1\ndocs: "d/**"\n'
            "sources:\n  - name: product\n    repo: a/b\n"
            "tests:\n  - name: r\n    uses: reference-review\n    sources: [prodcut]\n"
        )
        self.assertIn("product", error.hint)

    def test_a_test_that_does_nothing_is_rejected(self):
        error = self._load('version: 1\ndocs: "d/**"\ntests:\n  - name: empty\n')
        self.assertIn("does nothing", error.problem)

    def test_missing_required_built_in_option_is_caught(self):
        error = self._load(
            'version: 1\ndocs: "d/**"\n'
            "tests:\n  - name: s\n    uses: undocumented-surface\n"
        )
        self.assertIn("manifest", error.problem)

    def test_no_tests_is_rejected_rather_than_verifying_nothing(self):
        error = self._load('version: 1\ndocs: "d/**"\n')
        self.assertIn("tests", error.problem)

    def test_invalid_yaml_reports_a_line(self):
        error = self._load('version: 1\ndocs: "unterminated\n')
        self.assertIn("line", error.where)


class CommandLine(unittest.TestCase):
    """The CLI's exit codes are part of the contract."""

    def _run(self, args: list[str], cwd: Path) -> subprocess.CompletedProcess:
        return subprocess.run(
            [sys.executable, "-m", "docs_testing", *args],
            cwd=cwd,
            capture_output=True,
            text=True,
            env={"PATH": "/usr/bin:/bin", "PYTHONPATH": str(REPO_ROOT)},
            check=False,
        )

    def test_minimal_example_matches_its_documented_behavior(self):
        example = REPO_ROOT / "examples" / "minimal"
        result = self._run(["run", "--output", "/tmp/docs-testing-selftest.json"], example)
        self.assertEqual(result.returncode, EXIT_OK, result.stderr)
        self.assertIn("--retries", result.stdout)
        payload = json.loads(Path("/tmp/docs-testing-selftest.json").read_text())
        self.assertEqual(payload["summary"]["status"], WARN)

    def test_validate_rejects_a_bad_config_with_exit_2(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "docs-testing.config.yml").write_text(
                'version: 1\ndocs: "d/**"\nnonsense: 1\ntests: [reference-review]\n',
                encoding="utf-8",
            )
            result = self._run(["validate"], root)
            self.assertEqual(result.returncode, EXIT_TOOL_ERROR)
            self.assertIn("unknown key", result.stderr)

    def test_run_with_a_bad_config_still_writes_results_recording_the_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "docs-testing.config.yml").write_text("version: 99\n", encoding="utf-8")
            result = self._run(["run", "--output", "results/all.json"], root)
            self.assertEqual(result.returncode, EXIT_TOOL_ERROR)
            payload = json.loads((root / "results" / "all.json").read_text())
            self.assertEqual(payload["summary"]["status"], ERROR)
            self.assertTrue(payload["errors"])

    def test_list_shows_the_built_in_checks(self):
        result = self._run(["list"], REPO_ROOT)
        self.assertEqual(result.returncode, EXIT_OK)
        for expected in ("reference-review", "reference-completeness", "undocumented-surface"):
            self.assertIn(expected, result.stdout)


class ExitCodeMapping(unittest.TestCase):
    def test_each_outcome_maps_to_a_distinct_and_sensible_exit_status(self):
        from docs_testing.results import EXIT_FOR_STATUS

        self.assertEqual(EXIT_FOR_STATUS[PASS], EXIT_OK)
        self.assertEqual(EXIT_FOR_STATUS[WARN], EXIT_OK)
        self.assertEqual(EXIT_FOR_STATUS[FAIL], EXIT_FINDINGS)
        self.assertEqual(EXIT_FOR_STATUS[INCOMPLETE], EXIT_INCOMPLETE)
        self.assertEqual(EXIT_FOR_STATUS[ERROR], EXIT_TOOL_ERROR)

    def test_no_outcome_other_than_pass_or_warn_is_silently_successful(self):
        from docs_testing.results import CONCLUSION_FOR_STATUS

        for status in (INCOMPLETE, FAIL, ERROR):
            self.assertNotEqual(CONCLUSION_FOR_STATUS[status], "success")


if __name__ == "__main__":
    unittest.main()
