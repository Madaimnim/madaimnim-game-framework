import contextlib,io,importlib.util,json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
import UserRuleSkills as u
import BuildRuleSkills
class UserSkillsTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):BuildRuleSkills.generate(check=True)
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.user=Path(self.temp.name).resolve();self.text,self.version=u.rules.body(ROOT);self.assets={n:(ROOT/n).read_bytes() for n in ["RulesSkills.py","RulesSkills.zip"]}
 def install(self,apply=True):return u.sync(self.user,self.text,self.version,self.assets,apply)
 def test_preview_writes_nothing(self):
  report=self.install(False);self.assertEqual(len(report["skills"]),10);self.assertEqual(list(self.user.iterdir()),[])
 def test_install_metadata_and_repeat(self):
  self.install();first=u.state_path(self.user).read_bytes();self.install();self.assertEqual(first,u.state_path(self.user).read_bytes());self.assertEqual(len(list((self.user/"skills").glob("*/agents/openai.yaml"))),10)
  for p in (self.user/"skills").glob("*/SKILL.md"):
   t=p.read_text(encoding="utf-8");self.assertIn("瘋玩",t);self.assertNotIn("D:/",t);self.assertIn("當前",t)
 def test_unknown_collision_preserved_atomic(self):
  p=self.user/"skills/cp-art/SKILL.md";p.parent.mkdir(parents=True);p.write_text("mine")
  with self.assertRaises(ValueError):self.install()
  self.assertEqual(p.read_text(),"mine");self.assertFalse(u.state_path(self.user).exists());self.assertFalse((self.user/"skills/cp-files").exists())
 def test_modified_metadata_blocks_whole_update(self):
  self.install();p=self.user/"skills/cp-art/agents/openai.yaml";p.write_text("mine");before=u.state_path(self.user).read_bytes()
  with self.assertRaises(ValueError):self.install()
  self.assertEqual(p.read_text(),"mine");self.assertEqual(before,u.state_path(self.user).read_bytes())
 def test_rollback_and_reinstall(self):
  self.install();u.rollback(self.user,True);self.assertEqual(list((self.user/"skills").rglob("SKILL.md")),[]);self.install();self.assertEqual(len(list((self.user/"skills").rglob("SKILL.md"))),10)
 def test_unknown_extra_file_blocks_install(self):
  self.install();p=self.user/"skills/cp-art/notes.md";p.write_text("keep")
  with self.assertRaises(ValueError):self.install()
  self.assertEqual(p.read_text(),"keep")
 def test_rollback_keeps_unrelated_skill(self):
  self.install();p=self.user/"skills/other/SKILL.md";p.parent.mkdir();p.write_text("keep");u.rollback(self.user,True);self.assertEqual(p.read_text(),"keep")
 def test_failed_write_restores_previous(self):
  self.install();before={p:p.read_bytes() for p in self.user.rglob("*") if p.is_file()};original=u.write_files
  def fail_once(root,wanted):
   u.write_files=original;original(root,dict(list(wanted.items())[:2]));raise OSError("injected")
  with patch.object(u,"write_files",side_effect=fail_once),self.assertRaises(OSError):self.install()
  self.assertEqual(before,{p:p.read_bytes() for p in self.user.rglob("*") if p.is_file()})
 def test_project_scope_user_removes_owned_copies_and_keeps_reader(self):
  project=self.user/"project";(project/"Tools").mkdir(parents=True);config=project/"Tools/rules-skill-pilot.json";config.write_text('{"enabled":true}')
  snap=self.user/"snap.json"
  with patch.object(u.rules,"snapshot_path",return_value=snap):
   u.rules.install(project,self.text,self.version,self.assets)
   state={"project":str(project),"patches":[],"originalFiles":{},"afterFiles":{k:v for k,v in json.loads((project/"Tools/rules-skills-installed.json").read_text())["files"].items()},"aliases":[]};snap.write_text(json.dumps(state));config.write_text('{"enabled":true,"skillScope":"user"}')
   u.rules.install(project,self.text,self.version,self.assets)
  self.assertFalse(list((project/".agents/skills").rglob("SKILL.md")));self.assertTrue((project/"Tools/RulesSkills.py").exists());self.assertFalse(any(k.startswith(".agents/") for k in json.loads(snap.read_text())["afterFiles"]))
