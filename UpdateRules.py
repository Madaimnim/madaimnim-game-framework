"""Sync COMMON_RULES.md only. Requires Python 3.8+; no third-party modules."""
import argparse
import os
from pathlib import Path
import re
import sys
import tempfile
from urllib.parse import urlparse
from urllib.request import urlopen

LIMIT = 262144

def update(root, source_uri=None, source_path=None):
    root = Path(root).resolve(strict=True)
    entry = root / "AGENTS.md"
    target = root / "COMMON_RULES.md"
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
    if not 100 <= len(payload) <= LIMIT:
        raise ValueError("Unexpected rules file size")
    text = payload.decode("utf-8-sig").replace("\r\n", "\n")
    version = re.search(r"^RulesVersion:[ \t]*([0-9]+(?:[.-][0-9]+)+)[ \t]*$", text, re.M)
    if not text.startswith("<!-- MADAIMNIM_GAME_FRAMEWORK_RULES -->") or not version or re.search(r"<(?:!doctype\s+html|html)\b", text, re.I):
        raise ValueError("Missing marker/version or HTML response")
    normalized = text.rstrip() + "\n"
    if target.exists() and target.read_text(encoding="utf-8-sig").replace("\r\n", "\n").rstrip() + "\n" == normalized:
        print("Already current: " + version[1])
        return False
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", newline="\n", prefix=".COMMON_RULES.", suffix=".tmp", dir=root, delete=False) as handle:
            temporary = Path(handle.name)
            handle.write(normalized)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, target)
    finally:
        if temporary is not None and temporary.exists():
            temporary.unlink()
    print("Updated COMMON_RULES.md to " + version[1] + "; read it before continuing.")
    return True

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", type=Path, default=Path(__file__).resolve().parent.parent)
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--source-uri")
    group.add_argument("--source-path", type=Path)
    args = parser.parse_args()
    try:
        update(args.project_root, args.source_uri, args.source_path)
    except Exception as error:
        print("Rules update failed; existing local rules retained: " + str(error), file=sys.stderr)
        return 1
    return 0

if __name__ == "__main__":
    sys.exit(main())
