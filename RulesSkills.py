"""Versioned on-demand shared rules; no game mutations."""
import argparse,base64,hashlib,io,json,os,re,subprocess,sys,tempfile,zipfile
from pathlib import Path,PurePosixPath
from urllib.request import urlopen
REPOSITORY="https://github.com/Madaimnim/madaimnim-game-framework"
LIMIT=2097152
def sha(b):return hashlib.sha256(b).hexdigest()
def norm(b):return b.decode("utf-8-sig").replace("\r\n","\n").rstrip()+"\n"
def sections(text):
 ms=list(re.finditer(r"(?m)^## (\d+)\. .+$",text)); out={}
 for i,m in enumerate(ms):
  if int(m[1]) in out:raise ValueError("Duplicate section")
  out[int(m[1])]=text[m.start():ms[i+1].start() if i+1<len(ms) else len(text)]
 if set(out)!=set(range(10)):raise ValueError("Missing canonical section")
 return out
def subheading(text,name):
 ms=list(re.finditer(r"(?m)^### (.+)$",text))
 for i,m in enumerate(ms):
  if m[1]==name:return text[m.start():ms[i+1].start() if i+1<len(ms) else len(text)]
 raise ValueError("Missing subsection: "+name)
def body(root):
 text=norm((Path(root)/"COMMON_RULES.md").read_bytes());m=re.search(r"(?m)^RulesVersion: (\d{4}-\d{2}-\d{2}\.\d+)$",text)
 if not text.startswith("<!-- MADAIMNIM_GAME_FRAMEWORK_RULES -->") or not m:raise ValueError("Not canonical rules")
 return text,m[1]
def read_module(text,m,module,heading=None):
 entry=next((x for x in m["skills"] if x["module"]==module),None)
 if entry is None or module=="catalog":raise ValueError("Use list for catalog; unknown module")
 ss=sections(text);parts=[]
 for selector in entry["selectors"]:
  block=ss[selector["section"]]
  parts.extend([subheading(block,h) for h in selector["headings"]] if selector.get("headings") else [block])
 out="\n".join(parts)
 return subheading(out,heading) if heading else out
def validate(text,version,m):
 if m.get("rulesVersion")!=version or m.get("commonSha256")!=sha(text.encode()):raise ValueError("Version/hash mismatch; sync or fall back to full rules")
 if len({x["name"] for x in m["skills"]})!=len(m["skills"]):raise ValueError("Duplicate skill")
 covered=set()
 for x in m["skills"]:
  if not re.fullmatch(r"cp-[a-z0-9-]{1,55}",x["name"]):raise ValueError("Unsafe skill name")
  for s in x["selectors"]:
   if not s.get("headings"):covered.add(s["section"])
  if x["module"]!="catalog":read_module(text,m,x["module"])
 if not set(range(2,10)).issubset(covered):raise ValueError("Unrouted section")
def safe(root,rel):
 if not (rel in {"Tools/RulesSkills.py","Tools/rules-skills-manifest.json","Tools/rules-skills-installed.json","Tools/rules-skill-pilot.json"} or re.fullmatch(r"\.agents/skills/cp-[a-z0-9-]+/SKILL\.md",rel)):raise ValueError("Not a managed skill path")
 p=PurePosixPath(rel)
 if p.is_absolute() or ".." in p.parts or "\\" in rel or ":" in rel:raise ValueError("Unsafe relative path")
 path=Path(root).joinpath(*p.parts)
 for q in [path]+list(path.parents):
  if q==Path(root).parent:break
  if q.is_symlink() or (hasattr(q,"is_junction") and q.is_junction()):raise ValueError("Linked managed path")
 return path
def project_parts(project):
 config=json.loads((project/"Tools/rules-skill-pilot.json").read_text(encoding="utf-8"))
 if not config.get("enabled"):raise ValueError("Project not opted in")
 text=norm((project/"PROJECT_RULES.md").read_bytes());ms=list(re.finditer(r"(?m)^## (.+)$",text));chunks={}
 for i,m in enumerate(ms):
  if m[1] in chunks:raise ValueError("Ambiguous project section")
  chunks[m[1]]=text[m.start():ms[i+1].start() if i+1<len(ms) else len(text)]
 required=config["projectCoreHeadings"]
 if any(h not in chunks for h in required):raise ValueError("Required project constraint missing")
 prefix=text[:ms[0].start()] if ms else text
 index="\n## Project section index\n"+"\n".join("- "+h+" ("+str(len(t))+" chars)" for h,t in chunks.items())+"\n"
 return prefix+"\n".join(chunks[h] for h in required)+index,chunks
def snapshot_path(project):
 p=subprocess.run(["git","-C",str(project),"rev-parse","--absolute-git-dir"],capture_output=True,check=True)
 return Path(p.stdout.decode().strip())/"rules-skill-pilot/active.json"
def rollback(project,apply=False):
 state_path=snapshot_path(project);state=json.loads(state_path.read_text(encoding="utf-8"));plans=[]
 if state["project"]!=str(project):raise ValueError("Wrong rollback project")
 allowed={project/"AGENTS.md",project/"PROJECT_RULES.md",project.parent/"AGENTS.md"}
 for item in state["patches"]:
  p=Path(item["path"])
  if p.resolve() not in allowed:raise ValueError("Unsafe rollback instruction path")
  text=p.read_bytes().decode("utf-8")
  for change in reversed(item["changes"]):
   if text.count(change["after"])!=1:raise ValueError("Managed instructions changed; merge required: "+str(p))
   text=text.replace(change["after"],change["before"],1)
  plans.append((p,text.encode("utf-8")))
 for rel,value in state["afterFiles"].items():
  p=safe(project,rel)
  if not p.is_file() or sha(p.read_bytes())!=value:raise ValueError("Modified skill preserved: "+rel)
 for alias in state.get("aliases",[]):
  if Path(alias["path"])!=project.parent/".agents/skills" or Path(alias["target"])!=project/".agents/skills" or Path(alias["path"]).resolve()!=Path(alias["target"]).resolve():raise ValueError("Discovery alias changed")
 print(json.dumps({"apply":apply,"restoreInstructions":[str(p) for p,_ in plans],"removeManagedFiles":list(state["afterFiles"]),"gameChanges":False},ensure_ascii=False,indent=2))
 if not apply:return
 for p,data in plans:p.write_bytes(data)
 for rel in reversed(list(state["afterFiles"])):
  p=safe(project,rel);old=state["originalFiles"].get(rel)
  if old is None:p.unlink()
  else:p.write_bytes(base64.b64decode(old))
 for alias in state.get("aliases",[]):
  if any(Path(alias["target"]).rglob("SKILL.md")):print("Keeping alias for unrelated skills")
  else:os.rmdir(alias["path"])
 state["rolledBack"]=True;state_path.write_text(json.dumps(state,ensure_ascii=False,indent=2),encoding="utf-8")
 print("Pilot rolled back. Start a new conversation. No game/build/cloud changes.")
def fetch(version):
 if not re.fullmatch(r"\d{4}-\d{2}-\d{2}\.\d+",version):raise ValueError("Unsafe release version")
 base=REPOSITORY+"/releases/download/rules-"+version+"/"
 def get(name):
  with urlopen(base+name,timeout=30) as r:
   if not r.geturl().startswith("https://"):raise ValueError("Insecure redirect")
   b=r.read(LIMIT+1)
   if len(b)>LIMIT:raise ValueError("Oversized release asset")
   return b
 sums={}
 for line in get("SHA256SUMS.txt").decode().splitlines():
  value,name=line.split()
  if not re.fullmatch("[a-f0-9]{64}",value):raise ValueError("Invalid checksum")
  sums[name]=value
 assets={name:get(name) for name in ["RulesSkills.py","RulesSkills.zip"]}
 for name,b in assets.items():
  if sha(b)!=sums.get(name):raise ValueError("Release checksum mismatch")
 return assets
def install(project,text,version,assets):
 config=json.loads((project/"Tools/rules-skill-pilot.json").read_text(encoding="utf-8"))
 if not config.get("enabled"):raise ValueError("Explicit opt-in required")
 contents={}
 with zipfile.ZipFile(io.BytesIO(assets["RulesSkills.zip"])) as z:
  if sum(x.file_size for x in z.infolist())>LIMIT:raise ValueError("Oversized expanded bundle")
  for x in z.infolist():
   p=PurePosixPath(x.filename)
   if x.is_dir() or p.is_absolute() or ".." in p.parts or "\\" in x.filename or ":" in x.filename or x.filename in contents:raise ValueError("Unsafe archive")
   contents[x.filename]=z.read(x)
 blob=contents.pop("manifest.json");m=json.loads(blob);validate(text,version,m)
 if m["readerSha256"]!=sha(assets["RulesSkills.py"]):raise ValueError("Reader checksum mismatch")
 wanted={}
 for x in m["skills"]:
  rel=x["name"]+"/SKILL.md";data=contents.pop(rel)
  if sha(data)!=x["sha256"]:raise ValueError("Skill checksum mismatch")
  wanted[".agents/skills/"+rel]=data
 if contents:raise ValueError("Unexpected bundle entry")
 wanted["Tools/RulesSkills.py"]=assets["RulesSkills.py"];wanted["Tools/rules-skills-manifest.json"]=blob
 ledger_path=project/"Tools/rules-skills-installed.json"
 previous=json.loads(ledger_path.read_text(encoding="utf-8"))["files"] if ledger_path.exists() else {}
 for rel in set(previous)|set(wanted):
  p=safe(project,rel)
  if p.exists() and (rel not in previous or sha(p.read_bytes())!=previous[rel]):raise ValueError("Unknown/modified installed file: "+rel)
  if not p.exists() and rel in previous:raise ValueError("Installed file removed: "+rel)
 before={rel:safe(project,rel).read_bytes() if safe(project,rel).exists() else None for rel in set(previous)|set(wanted)}
 old_ledger=ledger_path.read_bytes() if ledger_path.exists() else None
 try:
  for rel,data in wanted.items():
   p=safe(project,rel);p.parent.mkdir(parents=True,exist_ok=True)
   with tempfile.NamedTemporaryFile(dir=p.parent,delete=False) as f:temp=Path(f.name);f.write(data)
   os.replace(temp,p)
  for rel in set(previous)-set(wanted):safe(project,rel).unlink()
  ledger_path.write_text(json.dumps({"version":version,"files":{k:sha(v) for k,v in wanted.items()}},ensure_ascii=False,indent=2),encoding="utf-8")
 except Exception:
  for rel,data in before.items():
   p=safe(project,rel)
   if data is None:
    if p.exists():p.unlink()
   else:p.write_bytes(data)
  if old_ledger is None:
   if ledger_path.exists():ledger_path.unlink()
  else:ledger_path.write_bytes(old_ledger)
  raise
 snap=snapshot_path(project)
 if snap.exists():
  state=json.loads(snap.read_text(encoding="utf-8"))
  for rel,data in wanted.items():
   if rel not in state["originalFiles"]:state["originalFiles"][rel]=base64.b64encode(before[rel]).decode() if before.get(rel) is not None else None
   state["afterFiles"][rel]=sha(data)
  state["afterFiles"]["Tools/rules-skills-installed.json"]=sha(ledger_path.read_bytes())
  snap.write_text(json.dumps(state,ensure_ascii=False,indent=2),encoding="utf-8")
 return m
def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument("--project-root",type=Path,default=Path(__file__).resolve().parent.parent);p.add_argument("--central-root",type=Path)
 sub=p.add_subparsers(dest="command",required=True)
 for name in ["core","list","project-core","sync"]:sub.add_parser(name)
 r=sub.add_parser("read");r.add_argument("module");r.add_argument("--heading")
 r=sub.add_parser("project-read");r.add_argument("heading")
 r=sub.add_parser("rollback");r.add_argument("--apply",action="store_true")
 a=p.parse_args();a.project_root=a.project_root.resolve()
 try:
  if a.command=="rollback":rollback(a.project_root,a.apply);return 0
  if a.central_root:center=a.central_root
  else:
   import UpdateRules
   center=UpdateRules.central_location()
  text,version=body(center);location=a.project_root/"Tools/rules-skills-manifest.json"
  if not location.exists():location=Path(__file__).parent/"RuleSkills/manifest.json"
  m=json.loads(location.read_text(encoding="utf-8")) if location.exists() else None
  if a.command=="sync":
   if m is not None:
    try:
     validate(text,version,m);ledger=json.loads((a.project_root/"Tools/rules-skills-installed.json").read_text(encoding="utf-8"))
     for rel,value in ledger["files"].items():
      if sha(safe(a.project_root,rel).read_bytes())!=value:raise ValueError("Modified installed file")
     print("Rule skills current: "+version);return 0
    except (ValueError,FileNotFoundError):pass
   m=install(a.project_root,text,version,fetch(version));print("Verified rule skills installed: "+m["rulesVersion"]);return 0
  if m is None:raise ValueError("Rule skills not installed")
  validate(text,version,m)
  if a.command=="list":print(json.dumps({"version":version,"scope":"installed shared-rule skills; check runtime available skills separately","skills":[{k:x[k] for k in ["name","module","description"]} for x in m["skills"]]},ensure_ascii=False,indent=2))
  elif a.command=="core":ss=sections(text);print("RulesVersion: "+version+"\n"+ss[0]+ss[1])
  elif a.command=="read":print("RulesVersion: "+version+"\n"+read_module(text,m,a.module,a.heading))
  else:
   core,chunks=project_parts(a.project_root)
   if a.command=="project-core":print(core)
   elif a.heading in chunks:print(chunks[a.heading])
   else:raise ValueError("Unknown project heading; use project-core")
  return 0
 except Exception as error:print("Skill trial unavailable; preserve files and read full canonical/project rules: "+str(error),file=sys.stderr);return 1
if __name__=="__main__":sys.exit(main())
