#!/usr/bin/env python3
"""Generate offline.json and stamp sw.js for a CourseBank course.

Usage: gen_offline_manifest.py <course-dir>

- Walks the course directory and writes offline.json: the './'-relative list
  of every file the service worker should precache, plus the total byte count
  (the future academy shelf shows it on its "⤓ Offline" button, like
  BookBank's).
- Stamps sw.js's CACHE_NAME with 'cb-<course-id>-<content-hash>'. The hash
  covers every precached file's bytes, so regenerating the course invalidates
  the old cache and installed PWAs pick up the new content on next visit.

Idempotent: run it as the last build step, and re-run it any time any file in
the course changes. Running it twice with no changes is a no-op.
"""

import hashlib
import json
import re
import sys
from pathlib import Path

# Never precached: the worker itself (the browser manages it), the manifest we
# are generating, VCS/OS noise, and staging dirs that must not ship.
EXCLUDE_NAMES = {"sw.js", "offline.json", ".DS_Store"}
EXCLUDE_DIRS = {".git", "inbox", "node_modules"}


def file_list(course_dir: Path):
    files = []
    for p in sorted(course_dir.rglob("*")):
        if not p.is_file():
            continue
        rel = p.relative_to(course_dir)
        if any(part in EXCLUDE_DIRS or part.startswith(".") for part in rel.parts[:-1]):
            continue
        if rel.name in EXCLUDE_NAMES or rel.name.startswith("."):
            continue
        files.append(rel)
    return files


def main() -> int:
    if len(sys.argv) != 2:
        print(__doc__.strip(), file=sys.stderr)
        return 2
    course_dir = Path(sys.argv[1]).resolve()
    if not (course_dir / "course.json").is_file():
        print(f"error: {course_dir} has no course.json — not a course directory", file=sys.stderr)
        return 1
    course_id = json.loads((course_dir / "course.json").read_text())["id"]

    files = file_list(course_dir)
    digest = hashlib.sha1()
    total = 0
    for rel in files:
        data = (course_dir / rel).read_bytes()
        total += len(data)
        digest.update(rel.as_posix().encode())
        digest.update(hashlib.sha1(data).digest())
    version = digest.hexdigest()[:12]

    manifest = {
        "course": course_id,
        "version": version,
        "bytes": total,
        "files": ["./" + rel.as_posix() for rel in files],
    }
    (course_dir / "offline.json").write_text(json.dumps(manifest, indent=2) + "\n")

    sw = course_dir / "sw.js"
    if not sw.is_file():
        print("error: sw.js missing — copy the skill's assets/sw.js into the course first", file=sys.stderr)
        return 1
    stamped, n = re.subn(
        r"var CACHE_NAME = '[^']*';",
        f"var CACHE_NAME = 'cb-{course_id}-{version}';",
        sw.read_text(),
        count=1,
    )
    if n != 1:
        print("error: sw.js has no CACHE_NAME line to stamp — was it hand-edited?", file=sys.stderr)
        return 1
    sw.write_text(stamped)

    print(f"offline.json: {len(files)} files, {total / 1024:.0f} KB · sw cache cb-{course_id}-{version}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
