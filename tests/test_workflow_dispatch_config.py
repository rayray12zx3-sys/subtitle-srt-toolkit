"""Regression: GitHub workflow_dispatch off must remain a YAML string.

Unquoted YAML 'off' can become boolean false in GitHub UI, resulting
in cloud_handshake argparse rejecting --alignment false before inference.
"""
from pathlib import Path
import re
import unittest


class WorkflowChoiceRegressionTests(unittest.TestCase):
    def test_optional_alignment_off_is_explicit_string(self):
        root = Path(__file__).resolve().parents[1]
        workflow = (root / ".github/workflows/cloud-handshake.yml").read_text("utf-8")
        section = workflow.split("      alignment:\n", 1)[1].split("      chunk_seconds:", 1)[0]
        self.assertRegex(section, r"(?m)^\s*default:\s*['\"]off['\"]\s*$")
        self.assertRegex(section, r"(?m)^\s*-\s*['\"]off['\"]\s*$")
        self.assertNotRegex(section, r"(?m)^\s*(?:default:\s*|-\s*)false\s*$")


if __name__ == "__main__":
    unittest.main()
