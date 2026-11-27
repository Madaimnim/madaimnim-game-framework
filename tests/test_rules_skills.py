import contextlib,copy,importlib.util,io,json,tempfile,unittest,zipfile
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location("rules_skills",ROOT/"RulesSkills.py");r=importlib.util.module_from_spec(spec);spec.loader.exec_module(r)
class RuleSkillsTests(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name).resolve();self.p=self.root/"project";(self.p/"Tools").mkdir(parents=True)
  (self.p/"Tools/rules-skill-pilot.json").write_text(json.dumps({"enabled":True,"projectCoreHeadings":["Required"]}))
  self.text,self.version=r.body(ROOT);self.m=json.loads((ROOT/"RuleSkills/manifest.json").read_text(encoding="utf-8"))
  self.assets={"RulesSkills.py":(ROOT/"RulesSkills.py").read_bytes(),"RulesSkills.zip":(ROOT/"RulesSkills.zip").read_bytes()}
 def install(self):
  with patch.object(r,"snapshot_path",return_value=self.root/"snapshot.json"):return r.install(self.p,self.text,self.version,self.assets)
 def test_canonical_coverage(self):
  r.validate(self.text,self.version,self.m);ss=r.sections(self.text)
  for n in range(2,10):
   entries=[e for e in self.m["skills"] if {"section":n} in e["selectors"]]
   self.assertTrue(entries);self.assertEqual(r.read_module(self.text,self.m,entries[0]["module"]),ss[n])
 def test_localization_does_not_load_build(self):
  out=r.read_module(self.text,self.m,"localization");self.assertIn("## 5.",out);self.assertNotIn("## 7.",out);self.assertNotIn("AndroidBundle",out)
 def test_art_keeps_texture_contract(self):
  out=r.read_module(self.text,self.m,"art");self.assertIn("Compression None",out);self.assertIn("九宮格",out)
 def test_changed_rules_rejected(self):
  with self.assertRaises(ValueError):r.validate(self.text+"changed",self.version,self.m)
 def test_missing_section_rejected(self):
  with self.assertRaises(ValueError):r.sections(self.text.replace("## 9.","## Other",1))
 def test_avpro_subsection_isolated(self):
  out=r.read_module(self.text,self.m,"build-release","AVPro Android 渲染與打包檢查");self.assertIn("Multithreaded Rendering",out);self.assertNotIn("### Android 共用正式簽章",out)
 def test_project_core_keeps_constraints_and_hides_history(self):
  (self.p/"PROJECT_RULES.md").write_text("# Project\n\n## Required\nNever delete player data.\n\n## OldHistory\n"+"obsolete "*1000)
  out,chunks=r.project_parts(self.p);self.assertIn("Never delete player data",out);self.assertIn("OldHistory",out);self.assertNotIn("obsolete obsolete",out)
 def test_missing_project_constraint_stops(self):
  (self.p/"PROJECT_RULES.md").write_text("# Project\n\n## Other\ntext")
  with self.assertRaises(ValueError):r.project_parts(self.p)
 def test_install_and_update_are_idempotent(self):
  self.install();first=(self.p/"Tools/rules-skills-installed.json").read_bytes();self.install();self.assertEqual(first,(self.p/"Tools/rules-skills-installed.json").read_bytes());self.assertFalse((self.p/"Assets").exists())
 def test_unknown_skill_preserved(self):
  p=self.p/".agents/skills/cp-art/SKILL.md";p.parent.mkdir(parents=True);p.write_text("user skill")
  with self.assertRaises(ValueError):self.install()
  self.assertEqual(p.read_text(),"user skill");self.assertFalse((self.p/"Tools/RulesSkills.py").exists())
 def test_modified_installed_skill_preserved(self):
  self.install();p=self.p/".agents/skills/cp-art/SKILL.md";p.write_text("local changes")
  before=(self.p/"Tools/rules-skills-installed.json").read_bytes()
  with self.assertRaises(ValueError):self.install()
  self.assertEqual(p.read_text(),"local changes");self.assertEqual(before,(self.p/"Tools/rules-skills-installed.json").read_bytes())
 def test_archive_traversal_stops_before_writes(self):
  buf=io.BytesIO()
  with zipfile.ZipFile(buf,"w") as z:z.writestr("../escape","bad")
  self.assets["RulesSkills.zip"]=buf.getvalue()
  with self.assertRaises(ValueError):self.install()
  self.assertFalse((self.root/"escape").exists());self.assertFalse((self.p/".agents").exists())
 def test_tampered_skill_stops(self):
  buf=io.BytesIO()
  with zipfile.ZipFile(io.BytesIO(self.assets["RulesSkills.zip"])) as old,zipfile.ZipFile(buf,"w") as new:
   for key in old.namelist():new.writestr(key,b"tamper" if key=="cp-art/SKILL.md" else old.read(key))
  self.assets["RulesSkills.zip"]=buf.getvalue()
  with self.assertRaises(ValueError):self.install()
  self.assertFalse((self.p/".agents").exists())
 def test_not_opted_in_preserved(self):
  (self.p/"Tools/rules-skill-pilot.json").write_text('{"enabled":false}')
  with self.assertRaises(ValueError):self.install()
  self.assertFalse((self.p/".agents").exists())
 def rollback_fixture(self):
  p=self.p/"AGENTS.md";p.write_text("start\nPILOT\nunrelated later note\n")
  f=self.p/"Tools/RulesSkills.py";f.write_text("owned")
  state={"project":str(self.p),"patches":[{"path":str(p),"changes":[{"before":"FULL","after":"PILOT"}]}],"originalFiles":{"Tools/RulesSkills.py":None},"afterFiles":{"Tools/RulesSkills.py":r.sha(f.read_bytes())},"aliases":[]}
  snapshot=self.root/"snapshot.json";snapshot.write_text(json.dumps(state));return p,f,snapshot
 def test_rollback_preserves_later_notes(self):
  p,f,snapshot=self.rollback_fixture()
  with patch.object(r,"snapshot_path",return_value=snapshot),contextlib.redirect_stdout(io.StringIO()):r.rollback(self.p,True)
  self.assertEqual(p.read_text(),"start\nFULL\nunrelated later note\n");self.assertFalse(f.exists())
 def test_rollback_conflict_is_atomic(self):
  p,f,snapshot=self.rollback_fixture();f.write_text("user changes")
  with patch.object(r,"snapshot_path",return_value=snapshot),self.assertRaises(ValueError):r.rollback(self.p,True)
  self.assertIn("PILOT",p.read_text());self.assertEqual(f.read_text(),"user changes")
 def test_game_path_cannot_be_managed(self):
  with self.assertRaises(ValueError):r.safe(self.p,"Assets/game.cs")
 def test_no_network_on_current_sync(self):
  self.install()
  center=self.root/"shared";center.mkdir();(center/"COMMON_RULES.md").write_text(self.text,encoding="utf-8")
  with patch.object(r.sys,"argv",["RulesSkills.py","--project-root",str(self.p),"--central-root",str(center),"sync"]),patch.object(r,"fetch",side_effect=AssertionError("unexpected network")),contextlib.redirect_stdout(io.StringIO()):self.assertEqual(r.main(),0)
 def test_catalog_reads_no_domain_body(self):
  self.install();center=self.root/"shared";center.mkdir();(center/"COMMON_RULES.md").write_text(self.text,encoding="utf-8")
  out=io.StringIO()
  with patch.object(r.sys,"argv",["RulesSkills.py","--project-root",str(self.p),"--central-root",str(center),"list"]),contextlib.redirect_stdout(out):self.assertEqual(r.main(),0)
  data=json.loads(out.getvalue());self.assertEqual(len(data["skills"]),10);self.assertNotIn("Multithreaded Rendering",out.getvalue())
