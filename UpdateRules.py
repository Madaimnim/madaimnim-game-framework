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

UPDATER_VERSION = "2026-10-22.4"
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
        return None, None
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
    _, version, _ = normalized(bundle["COMMON_RULES.md"])
    if tag != "rules-" + version:
        raise ValueError("Release tag and rules version differ")
    return bundle


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
                result["status"] = "updated" if changed or tool_changed else "current"
                if normalized(target.read_bytes())[0] != text:
                    raise ValueError("Readback mismatch")
            else:
                result["status"] = "would_update" if changed or tool_changed else "current"
            result["rulesChanged"] = changed
            result["updaterChanged"] = tool_changed
        except Exception as error:
            result["status"] = "blocked"
            result["reason"] = str(error)
        results.append(result)
    return {"workspace": str(workspace), "version": version, "apply": apply,
            "normalizedSha256": digest(text), "projects": results}

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--version", action="version", version=UPDATER_VERSION)
    parser.add_argument("--workspace-root", type=Path, help="Discover all configured projects; preview unless --apply")
    parser.add_argument("--apply", action="store_true", help="Apply the workspace preview without forcing conflicts")
    parser.add_argument("--reviewed-baselines", type=Path, help="Explicit per-project SHA256 review manifest for first-time legacy migration; never a blanket force")
    parser.add_argument("--sync-updater", action="store_true", help="Also update unchanged tracked project updaters from the same release")
    parser.add_argument("--project-root", type=Path, default=Path(__file__).resolve().parent.parent)
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--source-uri")
    group.add_argument("--source-path", type=Path)
    parser.add_argument("--accept-local-replacement", action="store_true", help="Only after reviewing and preserving local changes")
    args = parser.parse_args()
    try:
        if args.workspace_root:
            if args.source_uri or args.source_path or args.accept_local_replacement:
                raise ValueError("Workspace mode only accepts the verified official release, without forced replacement")
            reviews = json.loads(args.reviewed_baselines.read_text(encoding="utf-8")) if args.reviewed_baselines else None
            report = batch_update(args.workspace_root, load_release_bundle(), args.apply, args.sync_updater, reviews)
            print(json.dumps(report, ensure_ascii=False, indent=2))
            return 1 if not report["projects"] or any(p["status"] == "blocked" for p in report["projects"]) else 0
        if args.apply or args.sync_updater or args.reviewed_baselines:
            raise ValueError("--apply and --sync-updater require --workspace-root")
        update(args.project_root, args.source_uri, args.source_path, args.accept_local_replacement)
    except Exception as error:
        print("Rules update failed; existing local rules retained: " + str(error), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
