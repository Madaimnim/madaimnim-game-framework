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


class WorkspaceUpdateTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.workspace = Path(self.temp.name)
        self.bundle = {"COMMON_RULES.md": rules("2026-10-22.4").encode(), "UpdateRules.py": b"# published updater\n"}

    def project(self, name, version="2026-10-22.3"):
        root = self.workspace / name
        root.mkdir()
        (root / "AGENTS.md").write_text("RulesSource: " + u.OFFICIAL_SOURCE + "\n", encoding="utf-8")
        (root / "COMMON_RULES.md").write_text(rules(version), encoding="utf-8")
        subprocess.run(["git", "init", "-q", str(root)], check=True)
        subprocess.run(["git", "-C", str(root), "add", "AGENTS.md", "COMMON_RULES.md"], check=True)
        subprocess.run(["git", "-C", str(root), "-c", "user.name=Test", "-c", "user.email=test@example.invalid",
                        "commit", "-qm", "baseline"], check=True)
        return root

    def test_preview_does_not_write_and_apply_updates_all(self):
        first = self.project("first")
        second = self.project("second")
        before = (first / "COMMON_RULES.md").read_bytes()
        report = u.batch_update(self.workspace, self.bundle)
        self.assertEqual([p["status"] for p in report["projects"]], ["would_update", "would_update"])
        self.assertEqual((first / "COMMON_RULES.md").read_bytes(), before)
        self.assertFalse((first / ".git/madaimnim-common-rules.json").exists())
        report = u.batch_update(self.workspace, self.bundle, apply=True)
        self.assertTrue(all(p["status"] == "updated" for p in report["projects"]))
        for root in (first, second):
            self.assertEqual(u.normalized((root / "COMMON_RULES.md").read_bytes())[0], u.normalized(self.bundle["COMMON_RULES.md"])[0])

    def test_conflict_does_not_stop_other_projects(self):
        changed = self.project("changed")
        good = self.project("good")
        (changed / "COMMON_RULES.md").write_text(rules("2026-10-22.3", "private edit"), encoding="utf-8")
        report = u.batch_update(self.workspace, self.bundle, apply=True)
        self.assertEqual(report["projects"][0]["status"], "blocked")
        self.assertEqual(report["projects"][1]["status"], "updated")
        self.assertIn("private edit", (changed / "COMMON_RULES.md").read_text())

    def test_split_git_unity_root_is_only_discovered_once(self):
        root = self.project("split")
        unity = root / "UnityProject"
        (unity / "ProjectSettings").mkdir(parents=True)
        (unity / "AGENTS.md").write_text("Read ../AGENTS.md", encoding="utf-8")
        (unity / "ProjectSettings/ProjectVersion.txt").write_text("2022.3", encoding="utf-8")
        self.assertEqual(u.discover_projects(self.workspace), [root])

    def test_unconfigured_unity_root_and_newer_version_are_preserved(self):
        root = self.project("newer", "2026-10-23.1")
        unknown = self.workspace / "unknown"
        (unknown / "ProjectSettings").mkdir(parents=True)
        (unknown / "AGENTS.md").write_text("RulesSource: not-configured", encoding="utf-8")
        (unknown / "ProjectSettings/ProjectVersion.txt").write_text("2022.3", encoding="utf-8")
        report = u.batch_update(self.workspace, self.bundle, apply=True)
        self.assertTrue(all(p["status"] == "blocked" for p in report["projects"]))
        self.assertFalse((unknown / "COMMON_RULES.md").exists())
        self.assertIn("2026-10-23.1", (root / "COMMON_RULES.md").read_text())

    def test_modified_updater_blocks_and_tracked_updater_can_upgrade(self):
        root = self.project("tool")
        (root / "Tools").mkdir()
        tool = root / "Tools/UpdateRules.py"
        tool.write_text("# old tool\n", encoding="utf-8")
        subprocess.run(["git", "-C", str(root), "add", "Tools/UpdateRules.py"], check=True)
        subprocess.run(["git", "-C", str(root), "-c", "user.name=Test", "-c", "user.email=test@example.invalid", "commit", "-qm", "tool"], check=True)
        tool.write_text("# local edit\n", encoding="utf-8")
        self.assertEqual(u.batch_update(self.workspace, self.bundle, apply=True, sync_updater=True)["projects"][0]["status"], "blocked")
        tool.write_text("# old tool\n", encoding="utf-8")
        self.assertEqual(u.batch_update(self.workspace, self.bundle, apply=True, sync_updater=True)["projects"][0]["status"], "updated")
        self.assertEqual(tool.read_bytes(), self.bundle["UpdateRules.py"])


    def test_reviewed_digest_only_accepts_the_exact_reviewed_content(self):
        root = self.project("reviewed")
        target = root / "COMMON_RULES.md"
        target.write_text(rules("2026-10-22.3", "reviewed legacy content"), encoding="utf-8")
        reviews = {str(root): {"rulesSha256": u.digest(u.normalized(target.read_bytes())[0])}}
        self.assertEqual(u.batch_update(self.workspace, self.bundle, reviewed_baselines=reviews)["projects"][0]["status"], "would_update")
        target.write_text(rules("2026-10-22.3", "changed after review"), encoding="utf-8")
        self.assertEqual(u.batch_update(self.workspace, self.bundle, apply=True, reviewed_baselines=reviews)["projects"][0]["status"], "blocked")


    def test_upgraded_tool_has_baseline_for_the_next_release(self):
        root = self.project("tool-upgrade")
        first = u.batch_update(self.workspace, self.bundle, apply=True, sync_updater=True)
        self.assertEqual(first["projects"][0]["status"], "updated")
        second_bundle = {"COMMON_RULES.md": rules("2026-10-22.5").encode(), "UpdateRules.py": b"# next published updater\n"}
        second = u.batch_update(self.workspace, second_bundle, apply=True, sync_updater=True)
        self.assertEqual(second["projects"][0]["status"], "updated")
        (root / "Tools/UpdateRules.py").write_text("# edited", encoding="utf-8")
        third_bundle = {"COMMON_RULES.md": rules("2026-10-22.6").encode(), "UpdateRules.py": b"# third updater\n"}
        self.assertEqual(u.batch_update(self.workspace, third_bundle, apply=True, sync_updater=True)["projects"][0]["status"], "blocked")
