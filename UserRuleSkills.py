"""Preview, install or roll back the user-scoped CrazyPlay skills only."""
import argparse,base64,json,os,re,sys,tempfile
from pathlib import Path
from urllib.request import urlopen
import RulesSkills as rules

def home():
 return Path(os.environ.get("CODEX_HOME",str(Path.home()/".codex"))).resolve()

def safe(root,rel):
 if not re.fullmatch(r"cp-[a-z0-9-]+/(?:SKILL\.md|agents/openai\.yaml)",rel):raise ValueError("Not an owned user skill path")
 p=root/rel
 for q in [p]+list(p.parents):
  if q==root.parent:break
  if q.is_symlink() or (hasattr(q,"is_junction") and q.is_junction()):raise ValueError("Linked user skill path preserved")
 return p

def state_path(user):return user/"crazyplay-skills-installed.json"

def write_state(user,state):
 user.mkdir(parents=True,exist_ok=True)
 with tempfile.NamedTemporaryFile(dir=user,delete=False) as f:
  tmp=Path(f.name);f.write(json.dumps(state,ensure_ascii=False,indent=2).encode("utf-8"))
 os.replace(tmp,state_path(user))

def load_state(user):
 p=state_path(user)
 return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None

def check_files(root,previous,wanted):
 # Preflight the whole transaction before changing any owned file.
 for rel in set(previous)|set(wanted):
  p=safe(root,rel)
  if p.exists() and (rel not in previous or rules.sha(p.read_bytes())!=previous[rel]):raise ValueError("Unknown/modified user skill preserved: "+rel)
  if not p.exists() and rel in previous:raise ValueError("Owned user skill missing: "+rel)
 for name in {Path(rel).parts[0] for rel in wanted}:
  folder=root/name
  if folder.exists():
   existing={str(p.relative_to(root)).replace("\\","/") for p in folder.rglob("*") if p.is_file() or p.is_symlink()}
   if existing-set(previous):raise ValueError("Unknown contents in skill folder preserved: "+name)

def write_files(root,wanted):
 for rel,data in wanted.items():
  p=safe(root,rel)
  if data is None:
   if p.exists():p.unlink()
  else:
   p.parent.mkdir(parents=True,exist_ok=True)
   with tempfile.NamedTemporaryFile(dir=p.parent,delete=False) as f:tmp=Path(f.name);f.write(data)
   os.replace(tmp,p)

def sync(user,text,version,assets,apply=False):
 user=user.resolve();root=user/"skills";old=load_state(user)
 if old and old.get("rolledBack"):old=None
 m,files,_=rules.unpack(text,version,assets)
 wanted={rel[len(".agents/skills/"): ]:data for rel,data in files.items()}
 previous=old["files"] if old else {}
 check_files(root,previous,wanted)
 before={rel:safe(root,rel).read_bytes() if safe(root,rel).exists() else None for rel in set(previous)|set(wanted)}
 report={"category":"瘋玩（CrazyPlay）","version":version,"scope":"user","skillsRoot":str(root),"apply":apply,"skills":[x["displayName"] for x in m["skills"]],"gameChanges":False,"projectOptInChanges":False}
 if not apply:return report
 original=dict(old["originalFiles"]) if old else {}
 for rel,b in before.items():
  if rel not in original:original[rel]=None if b is None else base64.b64encode(b).decode()
 ledger_before=state_path(user).read_bytes() if state_path(user).exists() else None
 try:
  write_files(root,{**{k:None for k in set(previous)-set(wanted)},**wanted})
  ledger={"version":version,"files":{k:rules.sha(v) for k,v in wanted.items()},"originalFiles":original,"rolledBack":False}
  write_state(user,ledger)
 except Exception:
  write_files(root,before)
  if ledger_before is None:
   if state_path(user).exists():state_path(user).unlink()
  else:state_path(user).write_bytes(ledger_before)
  raise
 return report

def rollback(user,apply=False):
 root=user/"skills";state=load_state(user)
 if not state or state.get("rolledBack"):raise ValueError("No active user-skill installation")
 check_files(root,state["files"],{})
 wanted={rel:None if b is None else base64.b64decode(b) for rel,b in state["originalFiles"].items()}
 # Previous releases may have removed an owned file; do not overwrite a new occupant.
 for rel in set(wanted)-set(state["files"]):
  if safe(root,rel).exists():raise ValueError("Former owned path reused; preserve: "+rel)
 report={"apply":apply,"restoreOwnedFiles":list(wanted),"gameChanges":False,"projectOptInChanges":False}
 if apply:
  before={rel:safe(root,rel).read_bytes() if safe(root,rel).exists() else None for rel in wanted}
  try:
   write_files(root,wanted);state["rolledBack"]=True;write_state(user,state)
  except Exception:write_files(root,before);raise
 return report

def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument("--codex-home",type=Path,default=home());p.add_argument("--central-root",type=Path)
 sub=p.add_subparsers(dest="command",required=True)
 for command in ["sync","rollback"]:s=sub.add_parser(command);s.add_argument("--apply",action="store_true")
 a=p.parse_args()
 try:
  if a.command=="rollback":result=rollback(a.codex_home.resolve(),a.apply)
  else:
   import UpdateRules
   center=a.central_root or UpdateRules.central_location();text,version=rules.body(center)
   # Only immutable published payloads are installed; verify this executable and reader too.
   base=rules.REPOSITORY+"/releases/download/rules-"+version+"/"
   with urlopen(base+"SHA256SUMS.txt",timeout=30) as response:sums={name:value for value,name in (line.split() for line in response.read(rules.LIMIT).decode().splitlines())}
   for name in ["RulesSkills.py","UserRuleSkills.py"]:
    if rules.sha((Path(__file__).parent/name).read_bytes())!=sums.get(name):raise ValueError("Local installer/reader differs from published release: "+name)
   result=sync(a.codex_home,text,version,rules.fetch(version),a.apply)
  print(json.dumps(result,ensure_ascii=False,indent=2));return 0
 except Exception as error:print("CrazyPlay skills unchanged or restored: "+str(error),file=sys.stderr);return 1
if __name__=="__main__":sys.exit(main())
