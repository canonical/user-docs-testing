"""Additional contract: scope that resolves to nothing must not read as a pass."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from docs_testing.results import INCOMPLETE, PASS  # noqa: E402

from test_contracts import ContractTest  # noqa: E402


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
        self.assertEqual(payload["summary"]["status"], INCOMPLETE)
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
        self.assertEqual(payload["summary"]["status"], PASS)


if __name__ == "__main__":
    unittest.main()
