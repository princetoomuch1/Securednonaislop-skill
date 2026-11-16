#!/usr/bin/env python3
"""Claude Code PreToolUse hook: block production deploys while the last preflight scan has P0 findings.

Reads the hook JSON from stdin. If the Bash command is a deploy/publish command:
  - no scan yet            -> block, ask to run the scan
  - scan older than HEAD   -> block, ask to re-run
  - scan has active P0     -> block, list them
Exit 2 blocks the tool call and shows stderr to Claude. Exit 0 allows it.
Override for one command: prefix it with PREFLIGHT_SKIP=1
"""
import json
import os
import re
import subprocess
import sys
from pathlib import Path

DEPLOY = re.compile(
    r"\b(vercel\s+(deploy\s+)?--prod|vercel\s+deploy\s+--prod|netlify\s+deploy\b[^\n]*--prod|firebase\s+deploy|"
    r"supabase\s+db\s+push|supabase\s+functions\s+deploy|fly\s+deploy|railway\s+up|wrangler\s+(deploy|pages\s+deploy)|"
    r"npm\s+publish|pnpm\s+publish|git\s+push\b[^\n]*\b(main|master|production|prod)\b|gh\s+release\s+create|"
    r"amplify\s+publish|eb\s+deploy|gcloud\s+(app|run)\s+deploy|heroku\s+[^\n]*releases|docker\s+push)"
)


def main():
    try:
        data = json.load(sys.stdin)
    except Exception:
        return 0
    if data.get("tool_name") not in (None, "Bash"):
        return 0
    cmd = (data.get("tool_input") or {}).get("command", "")
    if not DEPLOY.search(cmd) or "PREFLIGHT_SKIP=1" in cmd:
        return 0
    root = Path(data.get("cwd") or os.getcwd())
    rep = root / ".preflight" / "report.json"
    skill = Path(__file__).resolve().parent
    if not rep.exists():
        print(f"vibe-preflight: no scan found. Run `python3 {skill}/preflight.py scan .` before deploying.", file=sys.stderr)
        return 2
    try:
        head_ts = int(subprocess.run(["git", "-C", str(root), "log", "-1", "--format=%ct"], capture_output=True, text=True, timeout=10).stdout.strip() or 0)
    except Exception:
        head_ts = 0
    if head_ts and rep.stat().st_mtime < head_ts:
        print("vibe-preflight: last scan is older than the latest commit. Re-run the scan before deploying.", file=sys.stderr)
        return 2
    try:
        j = json.loads(rep.read_text(encoding="utf-8"))
    except Exception:
        return 0
    p0 = [f for f in j.get("findings", []) if f.get("severity") == "P0" and not f.get("ignored") and not f.get("skipped")]
    if p0:
        lines = [f"- {f['id']} {f['title']} {f.get('file','')}" for f in p0[:10]]
        print("vibe-preflight blocked this deploy: P0 findings open\n" + "\n".join(lines) +
              "\nFix them (see .preflight/report.md), mark accepted risks with `preflight-ignore <ID>: <reason>`, or ask the user to approve PREFLIGHT_SKIP=1.", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
