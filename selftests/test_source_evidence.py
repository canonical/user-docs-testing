"""Contract: source evidence must not attest a commit it cannot prove.

`commit` is documented as the hard proof that a source was really checked out.
`git -C` searches parent directories, so a source directory that is not its own
clone must not inherit the surrounding repository's HEAD.
"""

from __future__ import annotations

import subprocess
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from docs_testing.checks.source_evidence import inspect_source  # noqa: E402

from test_contracts import ContractTest  # noqa: E402


class SourceEvidence(ContractTest):
    def test_a_plain_directory_inside_a_repository_reports_no_commit(self):
        subprocess.run(["git", "init", "-q"], cwd=self.project.root, check=True)
        self.project.source("product", {"README.md": "not a clone"})

        evidence = inspect_source("product", self.project.root / "sources")

        self.assertTrue(evidence["available"])
        self.assertIsNone(
            evidence["commit"],
            "a directory that is not its own checkout must not inherit a commit",
        )

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
        self.assertIsNotNone(evidence["commit"])
        self.assertEqual(len(evidence["commit"]), 40)

    def test_a_missing_source_is_unavailable_with_no_commit(self):
        evidence = inspect_source("absent", self.project.root / "sources")

        self.assertFalse(evidence["available"])
        self.assertIsNone(evidence["commit"])
        self.assertEqual(evidence["files_seen"], 0)


if __name__ == "__main__":
    unittest.main()
