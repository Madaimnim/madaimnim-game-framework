"""Synchronize published COMMON_RULES.md without discarding local changes."""
import argparse
import contextlib
import io
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
from urllib.parse import urlparse
from urllib.request import urlopen

UPDATER_VERSION = "2026-10-30.3"
LIMIT = 262144
MARKER = "<!-- MADAIMNIM_GAME_FRAMEWORK_RULES -->"


def normalized(payload):
    if not 100 <= len(payload) <= LIMIT:
        raise ValueError("Unexpected rules file size")
    text = payload.decode("utf-8-sig").replace("\r\n", "\n").rstrip() + "\n"
    match = re.search(r"^RulesVersion:[ \t]*([0-9]+(?:[.-][0-9]+)+)[ \t]*$", text, re.M)
    if not text.startswith(MARKER) or not match or re.search(r"<(?:!doctype\s+html|html)\b", text, re.I):
        raise ValueError("Missing marker/version or HTML response")
    return text, match[1], tuple(map(int, re.split(r"[.-]", match[1])))


def digest(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def git(root, *args):
    try:
        result = subprocess.run(["git", "-C", str(root), *args], capture_output=True, timeout=10)
        return result.stdout.decode("utf-8", errors="replace").strip() if result.returncode == 0 else None
    except (OSError, subprocess.TimeoutExpired):
        return None


def baseline(root):
    """Keep private synchronization state in the repository's local Git directory."""
    top = git(root, "rev-parse", "--show-toplevel")
    directory = git(root, "rev-parse", "--absolute-git-dir")
    if not top or Path(top).resolve() != root or not directory:
        if not (root / ".shared-rules-root").is_file():
            return None, None
        state = root / ".shared-rules-baseline.json"
        if not state.exists():
            return state, None
        value = json.loads(state.read_text(encoding="utf-8")).get("normalizedSha256")
        if not isinstance(value, str) or not re.fullmatch(r"[a-f0-9]{64}", value):
            raise ValueError("Invalid shared cache baseline")
        return state, value
    state = Path(directory) / "madaimnim-common-rules.json"
    if state.exists():
        report = json.loads(state.read_text(encoding="utf-8"))
        value = report.get("normalizedSha256")
        if not isinstance(value, str) or not re.fullmatch(r"[a-f0-9]{64}", value):
            raise ValueError("Invalid synchronization baseline; inspect local state")
        return state, value
    original = git(root, "show", "HEAD:COMMON_RULES.md")
    if original:
        text, _, _ = normalized(original.encode("utf-8"))
        return state, digest(text)
    return state, None


def update(root, source_uri=None, source_path=None, accept_local_replacement=False):
    root = Path(root).resolve(strict=True)
    entry, target = root / "AGENTS.md", root / "COMMON_RULES.md"
    if not entry.is_file():
        raise ValueError("AGENTS.md missing in project root")
    if source_uri and source_path:
        raise ValueError("Choose --source-uri or --source-path")
    if not source_uri and not source_path:
        match = re.search(r"^RulesSource:[ \t]*(\S+)[ \t]*$", entry.read_text(encoding="utf-8-sig"), re.M)
        if not match or match[1] == "not-configured":
            print("Source not configured; retaining local rules. No remote update performed.")
            return False
        source_uri = match[1]
    if source_path:
        with Path(source_path).open("rb") as handle:
            payload = handle.read(LIMIT + 1)
    else:
        address = urlparse(source_uri)
        if address.scheme != "https" or address.hostname not in {"github.com", "raw.githubusercontent.com"} or address.username or address.password:
            raise ValueError("Only HTTPS GitHub release/raw sources are allowed")
        with urlopen(source_uri, timeout=30) as response:
            if urlparse(response.geturl()).scheme != "https":
                raise ValueError("Non-HTTPS redirect")
            payload = response.read(LIMIT + 1)
    return apply_payload(root, payload, accept_local_replacement)


def apply_payload(root, payload, accept_local_replacement=False):
    root = Path(root).resolve(strict=True)
    if not (root / "AGENTS.md").is_file():
        raise ValueError("AGENTS.md missing in project root")
    target = root / "COMMON_RULES.md"
    text, version, order = normalized(payload)
    state, known = baseline(root)
    if target.exists():
        local, local_version, local_order = normalized(target.read_bytes())
        if local != text:
            if order < local_order:
                raise ValueError("Remote version is older than local " + local_version + "; no downgrade performed")
            if order == local_order:
                raise ValueError("Same version has different content; merge and publish a new version")
            if not accept_local_replacement and (known is None or digest(local) != known):
                raise ValueError("Local changes or unknown baseline; compare and merge before --accept-local-replacement")
        else:
            print("Already current: " + version + "; SHA256=" + digest(text))
            if state:
                state.write_text(json.dumps({"version": version, "normalizedSha256": digest(text)}, indent=2), encoding="utf-8")
            return False
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", newline="\n", prefix=".COMMON_RULES.", suffix=".tmp", dir=root, delete=False) as handle:
            temporary = Path(handle.name)
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, target)
        temporary = None
    finally:
        if temporary is not None and temporary.exists():
            temporary.unlink()
    if state:
        state.write_text(json.dumps({"version": version, "normalizedSha256": digest(text)}, indent=2), encoding="utf-8")
    print("Updated COMMON_RULES.md to " + version + "; SHA256=" + digest(text) + "; read before continuing.")
    return True



REPOSITORY = "https://github.com/Madaimnim/madaimnim-game-framework"
OFFICIAL_SOURCE = REPOSITORY + "/releases/latest/download/COMMON_RULES.md"
SKIP_DIRECTORIES = {".git", ".svn", "Library", "Temp", "Logs", "obj", "node_modules",
                    "Assets", "Packages", "Builds", "AIWorkspace", "SourceMaterial", "__pycache__"}


def is_link(path):
    return path.is_symlink() or bool(getattr(path.stat(follow_symlinks=False), "st_file_attributes", 0) & 0x400)


def discover_projects(workspace):
    """Only configured entry roots, not game-name guesses or nested Unity wrappers."""
    workspace = Path(workspace).resolve(strict=True)
    found = []
    own = Path(__file__).resolve().parent
    for current, dirs, files in os.walk(workspace, followlinks=False):
        directory = Path(current)
        dirs[:] = sorted(n for n in dirs if n not in SKIP_DIRECTORIES and
                         not is_link(directory / n) and (directory / n).resolve() != own)
        if directory == own:
            dirs[:] = []
            continue
        entry = directory / "AGENTS.md"
        if "AGENTS.md" not in files or is_link(entry):
            if (directory / "ProjectSettings/ProjectVersion.txt").is_file():
                found.append(directory)
                dirs[:] = []
            continue
        text = entry.read_text(encoding="utf-8-sig")
        match = re.search(r"^RulesSource:[ \t]*(\S+)[ \t]*$", text, re.M)
        if match and match[1] == OFFICIAL_SOURCE:
            found.append(directory)
            dirs[:] = []  # This entry owns its nested Unity directory, e.g. a split Git/Unity root.
        elif (directory / "ProjectSettings/ProjectVersion.txt").is_file():
            found.append(directory)  # Report unconfigured Unity roots instead of silently overwriting.
            dirs[:] = []
    return found


def load_release_bundle():
    """Resolve latest once; all downloads then use the same immutable release tag."""
    with urlopen("https://api.github.com/repos/Madaimnim/madaimnim-game-framework/releases/latest", timeout=30) as response:
        release = json.load(response)
    tag = release["tag_name"]
    if not re.fullmatch(r"rules-\d{4}-\d{2}-\d{2}\.\d+", tag):
        raise ValueError("Unexpected release tag")
    base = REPOSITORY + "/releases/download/" + tag + "/"
    def read(name):
        with urlopen(base + name, timeout=30) as response:
            if urlparse(response.geturl()).scheme != "https":
                raise ValueError("Non-HTTPS release redirect")
            data = response.read(LIMIT + 1)
            if len(data) > LIMIT:
                raise ValueError("Oversized release asset")
            return data
    checks = {}
    for line in read("SHA256SUMS.txt").decode("utf-8").splitlines():
        value, name = line.split()
        if not re.fullmatch(r"[a-f0-9]{64}", value):
            raise ValueError("Invalid release checksum")
        checks[name] = value
    bundle = {}
    for name in ("COMMON_RULES.md", "UpdateRules.py"):
        data = read(name)
        if hashlib.sha256(data).hexdigest() != checks.get(name):
            raise ValueError("Release checksum mismatch: " + name)
        bundle[name] = data
    if "ArtStyles_manifest.json" in checks:
        data = read("ArtStyles_manifest.json")
        if hashlib.sha256(data).hexdigest() != checks["ArtStyles_manifest.json"]:
            raise ValueError("Release style manifest checksum mismatch")
        bundle["ArtStyles_manifest.json"] = data
        manifest = json.loads(data.decode("utf-8"))
        for entry in manifest.get("styles", []):
            name = entry.get("file", "")
            if not re.fullmatch(r"STYLE-[0-9]{3}\.md", name):
                raise ValueError("Unsafe release style filename")
            data = read(name)
            if hashlib.sha256(data).hexdigest() != checks.get(name):
                raise ValueError("Release style checksum mismatch: " + name)
            bundle[name] = data
        style_files(bundle)
    _, version, _ = normalized(bundle["COMMON_RULES.md"])
    if tag != "rules-" + version:
        raise ValueError("Release tag and rules version differ")
    return bundle



def style_files(bundle):
    """Validate the complete text-only style bundle before any destination write."""
    if "ArtStyles_manifest.json" not in bundle:
        return {}
    payload = bundle["ArtStyles_manifest.json"]
    manifest = json.loads(payload.decode("utf-8"))
    if manifest.get("schemaVersion") != 1 or not isinstance(manifest.get("styles"), list):
        raise ValueError("Invalid art style manifest")
    files = {"manifest.json": payload}
    identities = set()
    for entry in manifest["styles"]:
        identity, name = entry.get("id", ""), entry.get("file", "")
        if not re.fullmatch(r"STYLE-[0-9]{3}", identity) or name != identity + ".md" or identity in identities:
            raise ValueError("Unsafe or duplicate style identity/path")
        identities.add(identity)
        data = bundle.get(name)
        if data is None or len(data) > LIMIT or hashlib.sha256(data).hexdigest() != entry.get("sha256"):
            raise ValueError("Missing or mismatched style content: " + name)
        data.decode("utf-8")
        files[name] = data
    return files


def sync_styles(root, bundle, apply=False):
    """Preserve local edits and extra files; never follow destination links."""
    files = style_files(bundle)
    if not files:
        return False
    root = Path(root).resolve(strict=True)
    directory = root / "ArtStyles"
    if directory.exists() and (not directory.is_dir() or is_link(directory)):
        raise ValueError("Linked or invalid ArtStyles directory; preserved")
    state_path, _ = baseline(root)
    state_path = state_path.parent / "madaimnim-art-styles.json" if state_path else directory / ".sync-state.json"
    if state_path.exists() and is_link(state_path):
        raise ValueError("Linked art style baseline; preserved")
    known = json.loads(state_path.read_text(encoding="utf-8")) if state_path.exists() else {}
    changed = []
    for name, data in files.items():
        target = directory / name
        if target.exists() or target.is_symlink():
            if is_link(target) or not target.is_file():
                raise ValueError("Linked or invalid style file; preserved: " + name)
            current = target.read_bytes()
            if current == data:
                continue
            if known.get(name) != hashlib.sha256(current).hexdigest():
                raise ValueError("Local style changes or unknown baseline; preserved: " + name)
        changed.append(name)
    if apply:
        directory.mkdir(exist_ok=True)
        for name in changed:
            target = directory / name
            temporary = None
            try:
                with tempfile.NamedTemporaryFile(dir=directory, prefix=".style-", suffix=".tmp", delete=False) as stream:
                    temporary = Path(stream.name)
                    stream.write(files[name])
                    stream.flush()
                    os.fsync(stream.fileno())
                os.replace(temporary, target)
                temporary = None
            finally:
                if temporary is not None and temporary.exists():
                    temporary.unlink()
        for name, data in files.items():
            if (directory / name).read_bytes() != data:
                raise ValueError("Style readback mismatch: " + name)
        state_path.write_text(json.dumps({name: hashlib.sha256(data).hexdigest() for name, data in files.items()}, indent=2), encoding="utf-8")
    return bool(changed)


def batch_update(workspace, bundle, apply=False, sync_updater=False, reviewed_baselines=None):
    """No force option: one project's conflict cannot authorize overwriting another."""
    workspace = Path(workspace).resolve(strict=True)
    text, version, order = normalized(bundle["COMMON_RULES.md"])
    results = []
    reviewed_baselines = reviewed_baselines or {}
    for root in discover_projects(workspace):
        result = {"project": str(root), "version": version}
        try:
            entry = (root / "AGENTS.md").read_text(encoding="utf-8-sig")
            if not re.search(r"^RulesSource:[ \t]*" + re.escape(OFFICIAL_SOURCE) + r"[ \t]*$", entry, re.M):
                raise ValueError("Official RulesSource missing; entry preserved")
            target = root / "COMMON_RULES.md"
            if target.is_symlink() or (target.exists() and is_link(target)):
                raise ValueError("Linked rules file; preserved")
            state, known = baseline(root)
            changed = True
            reviewed = reviewed_baselines.get(str(root), {})
            reviewed_rules = False
            if target.exists():
                local, local_version, local_order = normalized(target.read_bytes())
                changed = local != text
                if changed:
                    if order < local_order:
                        raise ValueError("Local version newer; no downgrade")
                    if order == local_order:
                        raise ValueError("Same-version content conflict")
                    if known is None or digest(local) != known:
                        reviewed_rules = reviewed.get("rulesSha256") == digest(local)
                        if not reviewed_rules:
                            raise ValueError("Local changes or unknown baseline; manual comparison required")
            tool = root / "Tools/UpdateRules.py"
            tool_changed = False
            tool_state = state.parent / "madaimnim-updater.json" if state else None
            known_tool = None
            if tool_state and tool_state.exists():
                known_tool = json.loads(tool_state.read_text(encoding="utf-8")).get("normalizedSha256")
                if not isinstance(known_tool, str) or not re.fullmatch(r"[a-f0-9]{64}", known_tool):
                    raise ValueError("Invalid updater baseline")
            if sync_updater:
                payload = bundle["UpdateRules.py"]
                if tool.parent.is_symlink() or (tool.parent.exists() and is_link(tool.parent)):
                    raise ValueError("Linked Tools directory; preserved")
                if tool.exists():
                    if is_link(tool):
                        raise ValueError("Linked updater; preserved")
                    local_tool = tool.read_bytes().decode("utf-8-sig").replace("\r\n", "\n")
                    remote_tool = payload.decode("utf-8-sig").replace("\r\n", "\n")
                    tool_changed = local_tool != remote_tool
                    if tool_changed:
                        original = git(root, "show", "HEAD:Tools/UpdateRules.py")
                        reviewed_tool = reviewed.get("updaterSha256") == digest(local_tool.rstrip() + "\n") or known_tool == digest(local_tool.rstrip() + "\n")
                        if (original is None or original.rstrip() != local_tool.rstrip()) and not reviewed_tool:
                            raise ValueError("Modified or untracked updater; manual comparison required")
                else:
                    tool_changed = True
            styles_changed = sync_styles(root, bundle, apply=False)
            if apply:
                with contextlib.redirect_stdout(io.StringIO()):
                    apply_payload(root, bundle["COMMON_RULES.md"], accept_local_replacement=reviewed_rules)
                if sync_updater and tool_changed:
                    tool.parent.mkdir(exist_ok=True)
                    temporary = tool.with_name(".UpdateRules.py.tmp")
                    if temporary.exists():
                        raise ValueError("Updater temporary path occupied")
                    try:
                        with temporary.open("xb") as stream:
                            stream.write(bundle["UpdateRules.py"])
                        os.replace(temporary, tool)
                    finally:
                        if temporary.exists():
                            temporary.unlink()
                if sync_updater and tool_state:
                    tool_state.write_text(json.dumps({"normalizedSha256": digest(bundle["UpdateRules.py"].decode("utf-8-sig").replace("\r\n", "\n").rstrip() + "\n")}, indent=2), encoding="utf-8")
                sync_styles(root, bundle, apply=True)
                result["status"] = "updated" if changed or tool_changed or styles_changed else "current"
                if normalized(target.read_bytes())[0] != text:
                    raise ValueError("Readback mismatch")
            else:
                result["status"] = "would_update" if changed or tool_changed or styles_changed else "current"
            result["stylesChanged"] = styles_changed
            result["rulesChanged"] = changed
            result["updaterChanged"] = tool_changed
        except Exception as error:
            result["status"] = "blocked"
            result["reason"] = str(error)
        results.append(result)
    return {"workspace": str(workspace), "version": version, "apply": apply,
            "normalizedSha256": digest(text), "projects": results}


POINTER_MARKER = "<!-- MADAIMNIM_SHARED_RULES_POINTER -->"
POINTER_TEXT = POINTER_MARKER + """
# 共用規範入口（不保存正文）

RulesSource: https://github.com/Madaimnim/madaimnim-game-framework/releases/latest/download/COMMON_RULES.md

本機只有一份共用正文。新工作對話執行 `python Tools/UpdateRules.py`，檢查正式GitHub Release並按需要更新共用正文；依輸出路徑完整閱讀。只查位置可執行 `python Tools/UpdateRules.py --show-location`。本檔不是規範副本，不在此新增通用條文。
專案僅在PROJECT_RULES.md保存本案識別、實際來源／入口、必要例外及待辦。共用規範修改須回正式維護來源完成測試、提交、推送、Release與回讀；正常檢查更新不自行發布遊戲或無關變更。
"""


def central_location(explicit=None):
    if explicit:
        return Path(explicit).expanduser().resolve()
    home = Path(os.environ.get("CODEX_HOME", str(Path.home() / ".codex")))
    config = home / "shared-rules.json"
    if config.exists():
        value = json.loads(config.read_text(encoding="utf-8-sig")).get("root")
        if not isinstance(value, str) or not Path(value).is_absolute():
            raise ValueError("Invalid shared-rules.json root; absolute local path required")
        return Path(value).resolve(strict=True)
    return (home / "shared-rules").resolve()


def sync_central(root, bundle):
    root = Path(root).resolve()
    if root.exists() and is_link(root):
        raise ValueError("Linked shared-rules directory; preserved")
    # Validate the complete style bundle before any write.
    style_files(bundle)
    root.mkdir(parents=True, exist_ok=True)
    sync_styles(root, bundle, apply=False)
    if not git(root, "rev-parse", "--absolute-git-dir"):
        (root / ".shared-rules-root").touch(exist_ok=True)
    if not (root / "AGENTS.md").exists():
        (root / "AGENTS.md").write_bytes(bundle["AGENTS.md"])
    changed = apply_payload(root, bundle["COMMON_RULES.md"])
    sync_styles(root, bundle, apply=True)
    return changed


def migrate_project_pointer(project, bundle, central, apply=False, sync_updater=True, reviewed=None):
    reviewed = reviewed or {}
    project = Path(project).resolve(strict=True)
    central = Path(central).resolve(strict=True)
    if project == central:
        return {"project": str(project), "status": "central", "rulesPath": str(central / "COMMON_RULES.md")}
    entry = project / "AGENTS.md"
    if not entry.exists() or not re.search(r"^RulesSource:[ \t]*" + re.escape(OFFICIAL_SOURCE) + r"[ \t]*$", entry.read_text(encoding="utf-8-sig"), re.M):
        raise ValueError("Official RulesSource missing; project preserved")
    target = project / "COMMON_RULES.md"
    pointer = target.exists() and target.read_text(encoding="utf-8-sig").startswith(POINTER_MARKER)
    if target.exists() and is_link(target):
        raise ValueError("Linked project rules; preserved")
    if pointer and target.read_text(encoding="utf-8-sig").replace("\r\n", "\n") != POINTER_TEXT:
        raise ValueError("Modified pointer; preserved for review")
    if target.exists() and not pointer:
        text, version, order = normalized(target.read_bytes())
        remote, remote_version, remote_order = normalized(bundle["COMMON_RULES.md"])
        _, known = baseline(project)
        if order > remote_order or (order == remote_order and text != remote):
            raise ValueError("Newer or same-version conflicting local rules; preserve and merge")
        if text != remote and digest(text) != known and reviewed.get("rulesSha256") != digest(text):
            raise ValueError("Local rules differ from known baseline; preserve and merge")
    tool = project / "Tools/UpdateRules.py"
    if tool.parent.exists() and is_link(tool.parent):
        raise ValueError("Linked Tools directory; preserved")
    new_tool = bundle["UpdateRules.py"].decode("utf-8-sig").replace("\r\n", "\n")
    tool_changed = not tool.exists() or tool.read_text(encoding="utf-8-sig").replace("\r\n", "\n") != new_tool
    if tool.exists() and is_link(tool):
        raise ValueError("Linked updater; preserved")
    if tool.exists() and tool_changed:
        local_tool = tool.read_text(encoding="utf-8-sig").replace("\r\n", "\n")
        original = git(project, "show", "HEAD:Tools/UpdateRules.py")
        state, _ = baseline(project)
        known_file = state.parent / "madaimnim-updater.json" if state else None
        known_tool = json.loads(known_file.read_text(encoding="utf-8")).get("normalizedSha256") if known_file and known_file.exists() else None
        if (original is None or original.rstrip() != local_tool.rstrip()) and known_tool != digest(local_tool.rstrip() + "\n"):
            raise ValueError("Modified or untracked updater; preserve for review")
    if tool_changed and not sync_updater:
        raise ValueError("Central pointer requires updated tool; use --sync-updater")
    # Preflight above is complete before either file changes. Replace tool first:
    # interruption leaves a working old copy with a central-aware updater, never the reverse.
    if apply:
        if tool_changed:
            tool.parent.mkdir(exist_ok=True)
            temporary = tool.with_name(".UpdateRules.central.tmp")
            with temporary.open("xb") as stream:
                stream.write(bundle["UpdateRules.py"])
            os.replace(temporary, tool)
        if not pointer:
            temporary = target.with_name(".COMMON_RULES.central.tmp")
            with temporary.open("x", encoding="utf-8", newline="\n") as stream:
                stream.write(POINTER_TEXT)
            os.replace(temporary, target)
        state, _ = baseline(project)
        if state:
            (state.parent / "madaimnim-updater.json").write_text(json.dumps({"normalizedSha256": digest(new_tool.rstrip() + "\n")}), encoding="utf-8")
        if target.read_text(encoding="utf-8-sig") != POINTER_TEXT:
            raise ValueError("Pointer readback failed")
    changed = not pointer or tool_changed
    return {"project": str(project), "status": ("updated" if apply else "would_update") if changed else "current",
            "rulesPath": str(central / "COMMON_RULES.md"), "projectBodyRemoved": not pointer,
            "updaterChanged": tool_changed, "readbackVerified": bool(apply)}


def central_workspace(workspace, bundle, central, apply=False, sync_updater=True, reviews=None):
    reviews = reviews or {}
    results = []
    for project in discover_projects(workspace):
        try:
            results.append(migrate_project_pointer(project, bundle, central, apply, sync_updater, reviews.get(str(Path(project).resolve()))))
        except Exception as error:
            results.append({"project": str(project), "status": "blocked", "reason": str(error)})
    return {"workspace": str(Path(workspace).resolve()), "version": normalized(bundle["COMMON_RULES.md"])[1],
            "apply": apply, "central": str(central), "projects": results}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--version", action="version", version=UPDATER_VERSION)
    parser.add_argument("--central-root", type=Path, help="Single machine-local shared rules location")
    parser.add_argument("--show-location", action="store_true", help="Print body path without claiming remote freshness")
    parser.add_argument("--workspace-root", type=Path, help="Preview pointer migration of configured projects")
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--sync-updater", action="store_true")
    parser.add_argument("--project-root", type=Path, default=Path(__file__).resolve().parent.parent)
    # Retained for explicit source diagnostics; target is always the central body.
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--source-uri")
    group.add_argument("--source-path", type=Path)
    parser.add_argument("--accept-local-replacement", action="store_true")
    parser.add_argument("--reviewed-baselines", type=Path)
    args = parser.parse_args()
    try:
        central = central_location(args.central_root)
        if args.show_location:
            print(central / "COMMON_RULES.md")
            return 0
        if args.source_uri or args.source_path:
            if args.workspace_root or args.apply:
                raise ValueError("Explicit source is for central diagnostics, not workspace migration")
            update(central, args.source_uri, args.source_path, args.accept_local_replacement)
        else:
            if args.accept_local_replacement:
                raise ValueError("No forced pointer migration; compare conflicting sources first")
            bundle = load_release_bundle()
            sync_central(central, bundle)
            if args.workspace_root:
                reviews = json.loads(args.reviewed_baselines.read_text(encoding="utf-8")) if args.reviewed_baselines else None
                report = central_workspace(args.workspace_root, bundle, central, args.apply, args.sync_updater, reviews)
                print(json.dumps(report, ensure_ascii=False, indent=2))
                return 1 if not report["projects"] or any(p["status"] == "blocked" for p in report["projects"]) else 0
            if args.apply or args.sync_updater:
                raise ValueError("Migration flags require --workspace-root")
            print("Shared rules verified against GitHub release. Read: " + str(central / "COMMON_RULES.md"))
        return 0
    except Exception as error:
        print("Shared rules not updated; local content preserved: " + str(error), file=sys.stderr)
        try:
            if (central / "COMMON_RULES.md").exists():
                print("Available local body (freshness not verified): " + str(central / "COMMON_RULES.md"), file=sys.stderr)
        except Exception:
            pass
        return 1


if __name__ == "__main__":
    sys.exit(main())
