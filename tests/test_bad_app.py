#!/usr/bin/env python3
"""Regression test: scan the seeded bad app and require every planted issue to be found.

Secrets are injected into a temp copy at test time so the repo never contains
anything that looks like a real credential (keeps GitHub push protection happy).
Run: python3 tests/test_bad_app.py
"""
import base64
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CLI = ROOT / "skills" / "vibe-preflight" / "scripts" / "preflight.py"
FIXTURE = ROOT / "examples" / "bad-app"

EXPECTED = {
    "S-01", "S-03", "S-04", "S-05", "S-08", "S-11", "S-12", "S-13", "S-14", "S-17", "S-23", "S-24", "S-25",
    "L-01", "L-04", "L-05", "L-06", "L-07", "L-10", "L-13",
    "U-01", "U-30",
    "F-02", "F-03", "F-05", "F-07", "F-09", "F-11", "F-13",
    "T-02", "T-05", "T-14", "T-15", "T-16", "T-19", "T-21",
    "D-01", "D-02", "D-03", "D-13", "D-14", "D-22",
}
MUST_BE_P0 = {"S-01", "S-03", "S-04", "S-05", "S-12", "S-13", "S-14", "S-17", "S-23", "S-25", "L-01", "L-04", "L-06", "L-07", "T-21"}


def b64(d):
    return base64.urlsafe_b64encode(json.dumps(d).encode()).decode().rstrip("=")


def inject_secrets(app: Path):
    # Built at runtime from parts so no literal credential exists in the repo.
    stripe = "sk_" + "live_" + "4eC39HqLyjWDarjtT1zdp7dc" + "X" * 8
    openai = "sk-" + "proj-" + "A1b2C3d4E5f6G7h8I9j0K1l2M3n4O5p6"
    service = ".".join([b64({"alg": "HS256", "typ": "JWT"}), b64({"iss": "supabase", "role": "service_" + "role", "ref": "abcd"}), "c2lnbmF0dXJlLXNpZ25hdHVyZS1zaWc"])
    (app / "src" / "lib" / "supabase.ts").write_text(
        '"use client";\nimport { createClient } from "@supabase/supabase-js";\n'
        f'export const admin = createClient("https://abcd.supabase.co", "{service}");\n'
        'export const key = process.env.NEXT_PUBLIC_SUPABASE_SERVICE_ROLE_KEY;\n', encoding="utf-8")
    (app / "src" / "lib" / "pay.ts").write_text(f'export const STRIPE = "{stripe}";\nexport const OAI = "{openai}";\n', encoding="utf-8")
    db = "postgres" + "ql://postgres:" + "hunter2pass" + "@db.abcd.supabase.co:5432/postgres"
    (app / ".env").write_text(f"DATABASE_URL={db}\n", encoding="utf-8")
    (app / ".env.production").write_text(f"DATABASE_URL={db}\n", encoding="utf-8")


def main():
    tmp = Path(tempfile.mkdtemp(prefix="preflight-test-"))
    app = tmp / "bad-app"
    shutil.copytree(FIXTURE, app)
    inject_secrets(app)
    r = subprocess.run([sys.executable, str(CLI), "scan", str(app), "--offline", "--fail-on", "P0"], capture_output=True, text=True)
    print(r.stdout[-1500:])
    if r.stderr.strip():
        print(r.stderr[-1500:], file=sys.stderr)
    rep = json.loads((app / ".preflight" / "report.json").read_text())
    found = {f["id"] for f in rep["findings"]}
    p0 = {f["id"] for f in rep["findings"] if f["severity"] == "P0"}
    missing = sorted(EXPECTED - found)
    not_p0 = sorted(MUST_BE_P0 - p0)
    ok = True
    if missing:
        print("MISSING rule ids:", missing); ok = False
    if not_p0:
        print("Expected P0 but not:", not_p0); ok = False
    if rep["verdict"] != "BLOCK":
        print("Verdict should be BLOCK, got", rep["verdict"]); ok = False
    if r.returncode != 1:
        print("Exit code should be 1, got", r.returncode); ok = False
    # secrets must be masked in every output
    for name in ("report.md", "report.json", "results.sarif", "findings.json"):
        t = (app / ".preflight" / name).read_text()
        if "4eC39HqLyjWDarjtT1zdp7dc" in t or "hunter2pass" in t or "A1b2C3d4E5f6G7h8" in t:
            print("SECRET LEAKED in", name); ok = False
    sarif = json.loads((app / ".preflight" / "results.sarif").read_text())
    assert sarif["version"] == "2.1.0" and sarif["runs"][0]["results"], "SARIF empty"
    # guard + gate are idempotent
    for _ in range(2):
        subprocess.run([sys.executable, str(CLI), "guard", str(app)], check=True, capture_output=True)
        subprocess.run([sys.executable, str(CLI), "gate", str(app), "--hook", "--ci"], check=True, capture_output=True)
    claude_md = (app / "CLAUDE.md").read_text()
    assert claude_md.count("vibe-preflight:start") == 1, "guard block duplicated"
    hooks = json.loads((app / ".claude" / "settings.json").read_text())["hooks"]["PreToolUse"]
    assert len(hooks) == 1, "hook duplicated"
    # deploy guard blocks a prod deploy while P0s are open
    g = subprocess.run([sys.executable, str(ROOT / "skills/vibe-preflight/scripts/deploy_guard.py")],
                       input=json.dumps({"tool_name": "Bash", "tool_input": {"command": "vercel --prod"}, "cwd": str(app)}),
                       capture_output=True, text=True)
    if g.returncode != 2:
        print("deploy_guard should block (2), got", g.returncode, g.stderr); ok = False
    g2 = subprocess.run([sys.executable, str(ROOT / "skills/vibe-preflight/scripts/deploy_guard.py")],
                        input=json.dumps({"tool_name": "Bash", "tool_input": {"command": "ls -la"}, "cwd": str(app)}),
                        capture_output=True, text=True)
    if g2.returncode != 0:
        print("deploy_guard should allow non-deploy commands"); ok = False
    print(f"\nFound {len(found)} distinct rule ids, {len(rep['findings'])} findings. Verdict {rep['verdict']}.")
    print("PASS" if ok else "FAIL")
    shutil.rmtree(tmp, ignore_errors=True)
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
