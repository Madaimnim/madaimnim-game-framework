"""Synchronize published COMMON_RULES.md without discarding local changes."""
import argparse
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

UPDATER_VERSION = "2026-10-21.2"
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


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--version", action="version", version=UPDATER_VERSION)
    parser.add_argument("--project-root", type=Path, default=Path(__file__).resolve().parent.parent)
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--source-uri")
    group.add_argument("--source-path", type=Path)
    parser.add_argument("--accept-local-replacement", action="store_true", help="Only after reviewing and preserving local changes")
    args = parser.parse_args()
    try:
        update(args.project_root, args.source_uri, args.source_path, args.accept_local_replacement)
    except Exception as error:
        print("Rules update failed; existing local rules retained: " + str(error), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
