import contextlib
import importlib.util
import io
from pathlib import Path
import subprocess
import tempfile
import unittest

spec = importlib.util.spec_from_file_location("updater", Path(__file__).resolve().parents[1] / "UpdateRules.py")
u = importlib.util.module_from_spec(spec)
spec.loader.exec_module(u)


def rules(version, extra=""):
    return u.MARKER + "\n# Shared rules\nRulesVersion: " + version + "\n" + "Preserve unrelated project state. " * 4 + extra + "\n"


class UpdateRulesTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / "project"
        self.root.mkdir()
        (self.root / "AGENTS.md").write_text("RulesSource: not-configured\n", encoding="utf-8")
        self.target = self.root / "COMMON_RULES.md"
        self.source = Path(self.temp.name) / "remote.md"
        self.source.write_text(rules("2026-10-21.2"), encoding="utf-8")

    def call(self, **kwargs):
        with contextlib.redirect_stdout(io.StringIO()):
            return u.update(self.root, source_path=self.source, **kwargs)

    def test_initial_download_and_no_rewrite(self):
        self.assertTrue(self.call())
        before = self.target.stat().st_mtime_ns
        self.assertFalse(self.call())
        self.assertEqual(before, self.target.stat().st_mtime_ns)

    def test_reject_html_missing_marker_and_large_response(self):
        for content in ["<html>" * 30, "invalid" * 30, "x" * (u.LIMIT + 1)]:
            self.source.write_text(content, encoding="utf-8")
            with self.assertRaises(ValueError): self.call()
            self.assertFalse(self.target.exists())

    def test_never_downgrade_even_with_override(self):
        self.target.write_text(rules("2026-10-22.1"), encoding="utf-8")
        before = self.target.read_bytes()
        with self.assertRaises(ValueError): self.call(accept_local_replacement=True)
        self.assertEqual(before, self.target.read_bytes())

    def test_same_version_divergence_is_conflict(self):
        self.target.write_text(rules("2026-10-21.2", "local"), encoding="utf-8")
        with self.assertRaises(ValueError): self.call(accept_local_replacement=True)

    def test_unknown_baseline_requires_review(self):
        self.target.write_text(rules("2026-10-20.1"), encoding="utf-8")
        with self.assertRaises(ValueError): self.call()
        self.assertTrue(self.call(accept_local_replacement=True))

    def test_git_baseline_update_and_local_changes(self):
        def git(*args):
            subprocess.run(["git", "-C", str(self.root), *args], check=True, capture_output=True)
        git("init", "--quiet")
        self.target.write_text(rules("2026-10-20.1"), encoding="utf-8")
        git("add", "COMMON_RULES.md")
        git("-c", "user.name=Fixture", "-c", "user.email=fixture@example.invalid", "commit", "--quiet", "-m", "fixture")
        self.assertTrue(self.call())
        state = self.root / ".git/madaimnim-common-rules.json"
        self.assertTrue(state.exists())
        self.source.write_text(rules("2026-10-22.1"), encoding="utf-8")
        self.assertTrue(self.call())
        self.target.write_text(self.target.read_text(encoding="utf-8") + "local edit\n", encoding="utf-8")
        self.source.write_text(rules("2026-10-23.1"), encoding="utf-8")
        before = self.target.read_bytes()
        with self.assertRaises(ValueError): self.call()
        self.assertEqual(before, self.target.read_bytes())

    def test_reject_non_github_source(self):
        with self.assertRaises(ValueError):
            u.update(self.root, source_uri="https://example.invalid/rules")


if __name__ == "__main__": unittest.main()
