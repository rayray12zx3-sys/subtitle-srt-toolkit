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
        dispatch = workflow.split("  workflow_dispatch:\n", 1)[1]
        section = dispatch.split("      alignment:\n", 1)[1].split("      chunk_seconds:", 1)[0]
        self.assertRegex(section, r"(?m)^\s*default:\s*['\"]off['\"]\s*$")
        self.assertRegex(section, r"(?m)^\s*-\s*['\"]off['\"]\s*$")
        self.assertNotRegex(section, r"(?m)^\s*(?:default:\s*|-\s*)false\s*$")

    def test_production_normalization_skips_system_ffmpeg(self):
        root = Path(__file__).resolve().parents[1]
        workflow = (root / ".github/workflows/cloud-handshake.yml").read_text("utf-8")
        section = workflow.split("      - name: Verify FFmpeg (legacy candidate benchmarks only)\n", 1)[1]
        self.assertTrue(section.startswith("        if: ${{ inputs.model == 'qwen3-asr-1.7b' || inputs.model == 'fun-asr-nano-2512' }}\n"))
        self.assertIn("--only-binary=av -r requirements.txt", workflow)
        self.assertIn("PYAV_AUDIO_PREFLIGHT_PASS", workflow)
        runner = (root / "tools/cloud_handshake.py").read_text("utf-8")
        self.assertIn("normalize_opus_bytes(opus_bytes, audio)", runner)
        self.assertNotIn("['ffmpeg'", runner)
        self.assertIn("av==18.1.1", (root / "requirements.txt").read_text("utf-8"))


if __name__ == "__main__":
    unittest.main()
