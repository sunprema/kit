#!/usr/bin/env bash
# PostToolUse hook: after a Write/Edit lands inside a BookBank book folder,
# run the structural validator (library/validate_book.py) and surface any
# findings back into context so they get fixed immediately during
# generation. Non-blocking — never denies/fails the tool call; the hard
# gate is CI.
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"   # bookbank/ plugin root
VALIDATOR="${CLAUDE_PLUGIN_ROOT:-$HERE}/library/validate_book.py"
[ -f "$VALIDATOR" ] || exit 0

payload="$(cat)"

book_dir="$(BOOKBANK_ROOT="${BOOKBANK_ROOT:-}" python3 -c '
import json, os, subprocess, sys

payload = json.load(sys.stdin)
ti = payload.get("tool_input") or {}
file_path = ti.get("file_path") or (payload.get("tool_response") or {}).get("filePath") or ""
if not file_path:
    sys.exit(0)

# Same cascade as write-book/build-library.py/validate_book.py: $BOOKBANK_ROOT,
# else cwd if it looks like a content-repo clone, else ~/bookbank.
root = os.environ.get("BOOKBANK_ROOT")
if not root:
    cwd = os.getcwd()
    repo_hint = os.environ.get("BOOKBANK_BOOKS_REPO", "sunprema/books")
    looks_like_clone = os.path.isdir(os.path.join(cwd, "books")) or os.path.isfile(os.path.join(cwd, "catalog.json"))
    if not looks_like_clone:
        try:
            r = subprocess.run(["git", "remote", "-v"], cwd=cwd, capture_output=True, text=True, timeout=3)
            looks_like_clone = repo_hint in r.stdout
        except Exception:
            pass
    root = cwd if looks_like_clone else os.path.expanduser("~/bookbank")
books_root = os.path.normpath(os.path.join(root, "books"))
p = os.path.normpath(file_path)

prefix = books_root + os.sep
if not p.startswith(prefix):
    sys.exit(0)

book_id = p[len(prefix):].split(os.sep)[0]
if book_id:
    print(os.path.join(books_root, book_id))
' <<<"$payload")"

[ -z "$book_dir" ] && exit 0
[ -d "$book_dir" ] || exit 0

out="$(python3 "$VALIDATOR" "$book_dir" 2>&1 || true)"
[ -z "$out" ] && exit 0

python3 -c '
import json, sys
print(json.dumps({
    "hookSpecificOutput": {
        "hookEventName": "PostToolUse",
        "additionalContext": sys.argv[1],
    }
}))
' "$out"
exit 0
