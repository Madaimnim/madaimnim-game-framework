"""Create deterministic discovery assets; clauses remain in COMMON_RULES.md."""
from pathlib import Path
import argparse,hashlib,json,re,zipfile
ROOT=Path(__file__).parent
ENTRIES=[{"module":"files","name":"cp-files","description":"專案檔案歸屬、搬移、清理及舊美術留存；詢問功能不自動清理。","selectors":[{"section":2}]},{"module":"unity-ui","name":"cp-unity-ui","description":"Unity 架構、場景、Prefab、固定 UI、版面與章節故事線工具修改。","selectors":[{"section":3}]},{"module":"art","name":"cp-art","description":"遊戲圖片、美術、九宮格、比例與匯入設定；實際生圖搭配製作技能。","selectors":[{"section":4}]},{"module":"localization","name":"cp-localization","description":"玩家文字、翻譯、TMP、缺字、字型及 Localization Table。","selectors":[{"section":5}]},{"module":"verification","name":"cp-verification","description":"工程、畫面及互動驗證、遊戲問題定位與證據；不自行操作 UI。","selectors":[{"section":6}]},{"module":"build-release","name":"cp-build-release","description":"遊戲打包、APK、EXE、H5、進版、簽章、成品交付與留存；不新增發布授權。","selectors":[{"section":7}]},{"module":"delivery-docs","name":"cp-delivery-docs","description":"使用者要求成果摘要、改善紀錄或工作交付文件；不自動產報告。","selectors":[{"section":8}]},{"module":"resources","name":"cp-resources","description":"共用資料庫、個人風格、音樂音效、特效及角色參考查找；不整包下載。","selectors":[{"section":9}]},{"module":"fmv-playback","name":"cp-fmv-playback","description":"遊戲影片、H5/iOS 片頭、黑屏、卡頓及播放器生命週期的工程診斷。","selectors":[{"section":3,"headings":["Unity正式來源與工具"]},{"section":6,"headings":["證據留存與問題定位"]}]},{"module":"catalog","name":"cp-skills-catalog","description":"詢問有哪些 Skill、可用哪些技能、某類任務可選項或本次讀過哪些 Skill。","selectors":[]}]
LABELS={'files': '檔案管理', 'unity-ui': 'Unity 與 UI', 'art': '遊戲美術', 'localization': '文字與多語系', 'verification': '問題驗證', 'build-release': '打包交付', 'delivery-docs': '成果文件', 'resources': '共用資源', 'fmv-playback': '影片播放', 'catalog': '技能目錄'}
def generate(root=ROOT,check=False):
 text=(root/"COMMON_RULES.md").read_text(encoding="utf-8-sig").replace("\r\n","\n").rstrip()+"\n";version=re.search(r"(?m)^RulesVersion: (.+)$",text)[1]
 m={"format":1,"rulesVersion":version,"commonSha256":hashlib.sha256(text.encode()).hexdigest(),"readerSha256":hashlib.sha256((root/"RulesSkills.py").read_bytes()).hexdigest(),"skills":[]};files={}
 for entry in ENTRIES:
  b=(root/"RuleSkills"/entry["name"]/"SKILL.md").read_bytes();ui=(root/"RuleSkills"/entry["name"]/"agents/openai.yaml").read_bytes();m["skills"].append(dict(entry,description="瘋玩（CrazyPlay）共用技能："+entry["description"],displayName="瘋玩｜"+LABELS[entry["module"]],sha256=hashlib.sha256(b).hexdigest(),uiSha256=hashlib.sha256(ui).hexdigest()));files[entry["name"]+"/SKILL.md"]=b;files[entry["name"]+"/agents/openai.yaml"]=ui
 data=(json.dumps(m,ensure_ascii=False,indent=2)+"\n").encode();path=root/"RuleSkills/manifest.json"
 if check:
  if path.read_bytes()!=data:raise ValueError("Regenerate RuleSkills/manifest.json")
 else:path.write_bytes(data)
 files["manifest.json"]=data
 with zipfile.ZipFile(root/"RulesSkills.zip","w",compression=zipfile.ZIP_DEFLATED) as z:
  for name,b in sorted(files.items()):
   info=zipfile.ZipInfo(name,(1980,1,1,0,0,0));info.compress_type=zipfile.ZIP_DEFLATED;info.external_attr=0o100644<<16;z.writestr(info,b)
 return m
if __name__=="__main__":
 p=argparse.ArgumentParser();p.add_argument("--check",action="store_true");a=p.parse_args();m=generate(check=a.check);print("Rule skills: "+m["rulesVersion"]+"; "+str(len(m["skills"])))
