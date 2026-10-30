import contextlib,io,importlib.util,json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
spec=importlib.util.spec_from_file_location('central_updater',Path(__file__).resolve().parents[1]/'UpdateRules.py');u=importlib.util.module_from_spec(spec);spec.loader.exec_module(u)
def rules(v='2026-10-30.3'):
 return (u.MARKER+'\n# Rules\nRulesVersion: '+v+'\n'+'Preserve all unrelated user data. '*5+'\n').encode()
class CentralRulesTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.base=Path(self.tmp.name);self.center=self.base/'shared';self.bundle={'COMMON_RULES.md':rules(),'UpdateRules.py':b'# verified updater\n','AGENTS.md':b'# Shared maintenance\n'}
 def init(self):
  with contextlib.redirect_stdout(io.StringIO()):u.sync_central(self.center,self.bundle)
 def project(self,name='project'):
  p=self.base/name;p.mkdir();(p/'AGENTS.md').write_text('RulesSource: '+u.OFFICIAL_SOURCE+'\n');(p/'COMMON_RULES.md').write_bytes(self.bundle['COMMON_RULES.md']);return p
 def test_initial_install_and_two_projects_use_one_body(self):
  self.init()
  for name in ['a','b']:
   p=self.project(name);r=u.migrate_project_pointer(p,self.bundle,self.center,True);self.assertEqual(r['rulesPath'],str(self.center/'COMMON_RULES.md'));self.assertTrue((p/'COMMON_RULES.md').read_text(encoding="utf-8").startswith(u.POINTER_MARKER));self.assertNotIn(u.MARKER,(p/'COMMON_RULES.md').read_text(encoding="utf-8"))
 def test_preview_does_not_change_project(self):
  self.init();p=self.project();before=(p/'COMMON_RULES.md').read_bytes();u.migrate_project_pointer(p,self.bundle,self.center,False);self.assertEqual(before,(p/'COMMON_RULES.md').read_bytes());self.assertFalse((p/'Tools').exists())
 def test_modified_same_version_rules_are_preserved(self):
  self.init();p=self.project();(p/'COMMON_RULES.md').write_bytes(rules()+b'private amendment\n');before=(p/'COMMON_RULES.md').read_bytes()
  with self.assertRaises(ValueError):u.migrate_project_pointer(p,self.bundle,self.center,True)
  self.assertEqual(before,(p/'COMMON_RULES.md').read_bytes());self.assertFalse((p/'Tools').exists())
 def test_modified_updater_blocks_before_pointer_write(self):
  self.init();p=self.project();(p/'Tools').mkdir();(p/'Tools/UpdateRules.py').write_text('# custom work\n');before=(p/'COMMON_RULES.md').read_bytes()
  with self.assertRaises(ValueError):u.migrate_project_pointer(p,self.bundle,self.center,True)
  self.assertEqual(before,(p/'COMMON_RULES.md').read_bytes())
 def test_idempotence_and_modified_pointer_preserved(self):
  self.init();p=self.project();u.migrate_project_pointer(p,self.bundle,self.center,True);before=(p/'COMMON_RULES.md').stat().st_mtime_ns;self.assertEqual(u.migrate_project_pointer(p,self.bundle,self.center,True)['status'],'current');self.assertEqual(before,(p/'COMMON_RULES.md').stat().st_mtime_ns);(p/'COMMON_RULES.md').write_text(u.POINTER_TEXT+'custom\n')
  with self.assertRaises(ValueError):u.migrate_project_pointer(p,self.bundle,self.center,True)
 def test_central_cache_updates_and_protects_local_edits(self):
  self.init();self.bundle['COMMON_RULES.md']=rules('2026-10-30.4')
  with contextlib.redirect_stdout(io.StringIO()):u.sync_central(self.center,self.bundle)
  self.bundle['COMMON_RULES.md']=rules('2026-10-30.5');p=self.center/'COMMON_RULES.md';p.write_bytes(p.read_bytes()+b'work in progress\n');before=p.read_bytes()
  with self.assertRaises(ValueError):u.sync_central(self.center,self.bundle)
  self.assertEqual(before,p.read_bytes())
 def test_machine_config_and_new_machine_default(self):
  home=self.base/'home';home.mkdir()
  with patch.dict(u.os.environ,{'CODEX_HOME':str(home)}):
   self.assertEqual(u.central_location(),home/'shared-rules');self.center.mkdir();(home/'shared-rules.json').write_text(json.dumps({'root':str(self.center)}));self.assertEqual(u.central_location(),self.center)
 def test_cli_checks_remote_and_keeps_project_pointer(self):
  self.init();p=self.project();u.migrate_project_pointer(p,self.bundle,self.center,True);before=(p/'COMMON_RULES.md').read_bytes()
  with patch.object(u.sys,'argv',['UpdateRules.py','--central-root',str(self.center),'--project-root',str(p)]),patch.object(u,'load_release_bundle',return_value=self.bundle) as remote,contextlib.redirect_stdout(io.StringIO()):self.assertEqual(u.main(),0);remote.assert_called_once()
  self.assertEqual(before,(p/'COMMON_RULES.md').read_bytes())
