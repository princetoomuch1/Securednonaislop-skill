#!/usr/bin/env python3
"""vibe-preflight: pre-launch audit and guardrails for AI-built apps.

Usage:
  preflight.py recon   [ROOT]
  preflight.py scan    [ROOT] [--out DIR] [--offline] [--jurisdiction eu,uk,us,in] [--no-build] [--fail-on P0|P1|none]
  preflight.py report  [OUT_DIR]
  preflight.py diff    PREV.json CUR.json
  preflight.py probe-supabase --url URL --anon-key KEY [--out DIR] [--tables auto|a,b]
  preflight.py guard   [ROOT] [--targets claude,agents,cursor,copilot,windsurf]
  preflight.py gate    [ROOT] [--hook] [--ci]

Standard library only. Python 3.8+.
"""
import argparse
import json
import os
import re
import shutil
import sys
import urllib.error
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
SKILL = HERE.parent
sys.path.insert(0, str(HERE))

from lib.checks import detect_stack, run_checks  # noqa: E402
from lib.deps import run_deps  # noqa: E402
from lib.report import build_report, diff  # noqa: E402
from lib.scan import run_rules  # noqa: E402

ICON = {"BLOCK": "BLOCK", "FIX FIRST": "FIX FIRST", "SHIP": "SHIP"}


def cmd_recon(a):
    root = Path(a.root).resolve()
    info = detect_stack(root)
    routes = []
    for pat in ["app/**/page.*", "src/app/**/page.*", "pages/**/*.*", "src/pages/**/*.*", "src/routes/**/+page.svelte", "*.html"]:
        for p in root.glob(pat):
            if "node_modules" in p.parts or "/api/" in str(p):
                continue
            routes.append(str(p.relative_to(root)))
    apis = [str(p.relative_to(root)) for pat in ["app/**/route.*", "src/app/**/route.*", "pages/api/**/*.*", "src/pages/api/**/*.*", "supabase/functions/*/index.ts"] for p in root.glob(pat) if "node_modules" not in p.parts]
    envs = [p.name for p in root.glob(".env*")]
    builds = [b for b in ["dist", "build", "out", ".next"] if (root / b).exists()]
    out = {"root": str(root), "stack": info["stack"], "deploy": info["deploy"], "ai_platform": info["ai_platform"],
           "pages": sorted(routes)[:60], "api_routes": sorted(apis)[:60], "env_files": envs, "build_dirs": builds,
           "dependency_count": len(info["deps"])}
    print(json.dumps(out, indent=2))
    hints = []
    if "supabase" in info["stack"]:
        hints.append("Supabase detected: ask for project URL + anon key to run probe-supabase (read-only).")
    if not builds:
        hints.append("No build output found: run the build first so secrets in the bundle are scanned.")
    if apis or routes:
        hints.append("Start the app and run render_audit.mjs for consent, a11y, headers and layout checks.")
    for h in hints:
        print("hint:", h, file=sys.stderr)


def cmd_scan(a):
    root = Path(a.root).resolve()
    out = Path(a.out if os.path.isabs(a.out) else root / a.out)
    out.mkdir(parents=True, exist_ok=True)
    prev = out / "findings.json"
    if prev.exists():
        shutil.copy(prev, out / "findings.prev.json")
    jur = tuple(x.strip().lower() for x in a.jurisdiction.split(",") if x.strip())
    rule_f = run_rules(root, include_build=not a.no_build)
    info, check_f = run_checks(root, jur)
    dep_f, dep_r = run_deps(root, offline=a.offline)
    skipped = []
    if a.offline:
        skipped.append("Dependency registry lookups (offline): only typosquat heuristics ran")
    if not any((root / b).exists() for b in ["dist", "build", "out", ".next"]):
        skipped.append("Build output scan: no dist/build/out/.next found (run the build to scan the shipped bundle)")
    if not (out / "render-findings.json").exists():
        skipped.append("Rendered checks (consent capture, axe, keyboard, headers, overflow): run render_audit.mjs")
    findings = rule_f + check_f + dep_f
    meta = {"stack": info["stack"], "deploy": info["deploy"], "ai_platform": info["ai_platform"],
            "jurisdiction": list(jur), "skipped_checks": skipped}
    (out / "findings.json").write_text(json.dumps({"meta": meta, "findings": findings}, indent=1), encoding="utf-8")
    if dep_r:
        (out / "deps.json").write_text(json.dumps(dep_r, indent=1), encoding="utf-8")
    gi = out / ".gitignore"
    if not gi.exists():
        gi.write_text("*\n!.gitignore\n", encoding="utf-8")
    v, code, allf = build_report(out)
    active = [f for f in allf if not f.get("ignored") and not f.get("skipped")]
    c = {s: sum(1 for f in active if f["severity"] == s) for s in ("P0", "P1", "P2")}
    print(f"Verdict: {v}  P0={c['P0']} P1={c['P1']} P2={c['P2']}")
    for f in [f for f in active if f["severity"] == "P0"][:15]:
        loc = f"{f['file']}:{f['line']}" if f.get("file") and f.get("line") else f.get("file", "")
        print(f"  P0 {f['id']} {f['title']} {loc}")
    print(f"Report: {out / 'report.md'}")
    if a.fail_on == "none":
        return 0
    if a.fail_on == "P1":
        return 1 if c["P0"] or c["P1"] else 0
    return 1 if c["P0"] else (2 if c["P1"] else 0)


def cmd_report(a):
    out = Path(a.out)
    v, code, findings = build_report(out)
    print(f"Verdict: {v}. Report: {out / 'report.md'}")
    return code


def cmd_diff(a):
    fixed, new = diff(Path(a.prev), Path(a.cur))
    print(f"Fixed: {len(fixed)}  New: {len(new)}")
    for f in fixed:
        print(f"  - fixed {f['severity']} {f['id']} {f['title']} {f.get('file','')}")
    for f in new:
        print(f"  + new   {f['severity']} {f['id']} {f['title']} {f.get('file','')}")
    return 0


def http_get(url, headers, timeout=10):
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, r.read().decode("utf-8", "ignore"), dict(r.headers)
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", "ignore") if e.fp else "", dict(e.headers or {})
    except Exception as e:
        return None, str(e), {}


def cmd_probe_supabase(a):
    """Read-only probe with the PUBLIC anon key. GET requests only."""
    base = a.url.rstrip("/")
    h = {"apikey": a.anon_key, "Authorization": f"Bearer {a.anon_key}", "Accept": "application/json"}
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    findings = []
    st, body, _ = http_get(f"{base}/rest/v1/", h)
    tables = []
    if a.tables and a.tables != "auto":
        tables = [t.strip() for t in a.tables.split(",") if t.strip()]
    elif st == 200:
        try:
            spec = json.loads(body)
            tables = [p.strip("/") for p in (spec.get("paths") or {}) if p.strip("/") and not p.startswith("/rpc/")]
            rpcs = [p for p in (spec.get("paths") or {}) if p.startswith("/rpc/")]
            if rpcs:
                findings.append(dict(id="S-07", severity="P1", category="security", title=f"{len(rpcs)} RPC functions exposed to anon via REST",
                                     file="", line=0, evidence=", ".join(rpcs[:10]), fix="Revoke EXECUTE from anon on functions that should not be public; check auth.uid() inside.",
                                     confidence="medium", source="probe"))
        except Exception:
            pass
    sensitive = re.compile(r"user|profile|account|customer|order|payment|invoice|message|chat|patient|employee|address|email|contact|lead|subscription|session|token|key|secret|document|file|note", re.I)
    for t in tables[:200]:
        s2, b2, hd = http_get(f"{base}/rest/v1/{t}?select=*&limit=1", {**h, "Prefer": "count=exact"})
        if s2 in (200, 206):
            try:
                rows = json.loads(b2)
            except Exception:
                rows = []
            total = (hd.get("Content-Range") or hd.get("content-range") or "").split("/")[-1]
            if rows:
                cols = list(rows[0].keys())[:12] if isinstance(rows, list) and rows and isinstance(rows[0], dict) else []
                sev = "P0" if sensitive.search(t) or any(sensitive.search(c) for c in cols) else "P1"
                findings.append(dict(id="S-03", severity=sev, category="security", title=f"Table '{t}' readable with the public anon key",
                                     file="", line=0, evidence=f"{total or '?'} rows readable; columns: {', '.join(cols)}",
                                     fix=f"ALTER TABLE public.{t} ENABLE ROW LEVEL SECURITY; add owner-scoped policies. If it is public by design, add it to an allowlist.",
                                     confidence="high", source="probe"))
    s3, b3, _ = http_get(f"{base}/storage/v1/bucket", h)
    if s3 == 200:
        try:
            for bkt in json.loads(b3):
                if bkt.get("public"):
                    findings.append(dict(id="S-06", severity="P1", category="security", title=f"Storage bucket '{bkt.get('name')}' is public",
                                         file="", line=0, evidence="public: true", fix="Make it private and use signed URLs unless it only holds public assets.",
                                         confidence="medium", source="probe"))
        except Exception:
            pass
    (out / "probe-findings.json").write_text(json.dumps({"findings": findings}, indent=1), encoding="utf-8")
    print(f"Probed {len(tables)} tables. Findings: {len(findings)}. Written to {out / 'probe-findings.json'}")
    build_report(out)
    return 1 if any(f["severity"] == "P0" for f in findings) else 0


START, END = "<!-- vibe-preflight:start -->", "<!-- vibe-preflight:end -->"


def upsert_block(path: Path, block: str, header=""):
    path.parent.mkdir(parents=True, exist_ok=True)
    text = path.read_text(encoding="utf-8") if path.exists() else header
    wrapped = f"{START}\n{block.strip()}\n{END}"
    if START in text and END in text:
        text = re.sub(re.escape(START) + r".*?" + re.escape(END), lambda _m: wrapped, text, flags=re.S)
    else:
        text = (text.rstrip() + "\n\n" if text.strip() else "") + wrapped + "\n"
    path.write_text(text, encoding="utf-8")


def cmd_guard(a):
    root = Path(a.root).resolve()
    block = (SKILL / "templates" / "guardrails.md").read_text(encoding="utf-8")
    targets = [t.strip() for t in a.targets.split(",")]
    written = []
    mapping = {
        "claude": (root / "CLAUDE.md", ""),
        "agents": (root / "AGENTS.md", ""),
        "copilot": (root / ".github" / "copilot-instructions.md", ""),
        "windsurf": (root / ".windsurfrules", ""),
        "gemini": (root / "GEMINI.md", ""),
        "cursor": (root / ".cursor" / "rules" / "vibe-preflight.mdc",
                   "---\ndescription: Production guardrails for AI-built apps (vibe-preflight)\nalwaysApply: true\n---\n"),
    }
    for t in targets:
        if t in mapping:
            p, header = mapping[t]
            upsert_block(p, block, header)
            written.append(str(p.relative_to(root)))
    print("Guardrails written to: " + ", ".join(written))
    print("Lovable / Bolt / v0 do not read repo files: paste templates/guardrails.md into the project's Knowledge / system prompt.")
    return 0


def cmd_gate(a):
    root = Path(a.root).resolve()
    if a.hook:
        settings = root / ".claude" / "settings.json"
        settings.parent.mkdir(parents=True, exist_ok=True)
        try:
            j = json.loads(settings.read_text(encoding="utf-8")) if settings.exists() else {}
        except Exception:
            j = {}
        guard = SKILL / "scripts" / "deploy_guard.py"
        cmd = f"python3 \"{guard}\""
        hooks = j.setdefault("hooks", {}).setdefault("PreToolUse", [])
        if not any("deploy_guard" in json.dumps(h) for h in hooks):
            hooks.append({"matcher": "Bash", "hooks": [{"type": "command", "command": cmd, "timeout": 30}]})
        settings.write_text(json.dumps(j, indent=2), encoding="utf-8")
        print(f"Deploy guard hook added to {settings.relative_to(root)}")
    if a.ci:
        dst = root / ".github" / "workflows" / "vibe-preflight.yml"
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(SKILL / "templates" / "github-action.yml", dst)
        print(f"GitHub Action written to {dst.relative_to(root)}")
    if not a.hook and not a.ci:
        print("Nothing to do: pass --hook and/or --ci")
    return 0


def main():
    ap = argparse.ArgumentParser(prog="preflight", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("recon"); s.add_argument("root", nargs="?", default=".")
    s = sub.add_parser("scan"); s.add_argument("root", nargs="?", default=".")
    s.add_argument("--out", default=".preflight"); s.add_argument("--offline", action="store_true")
    s.add_argument("--jurisdiction", default="eu,uk,us"); s.add_argument("--no-build", action="store_true")
    s.add_argument("--fail-on", default="P0", choices=["P0", "P1", "none"])
    s = sub.add_parser("report"); s.add_argument("out", nargs="?", default=".preflight")
    s = sub.add_parser("diff"); s.add_argument("prev"); s.add_argument("cur")
    s = sub.add_parser("probe-supabase"); s.add_argument("--url", required=True); s.add_argument("--anon-key", required=True)
    s.add_argument("--tables", default="auto"); s.add_argument("--out", default=".preflight")
    s = sub.add_parser("guard"); s.add_argument("root", nargs="?", default=".")
    s.add_argument("--targets", default="claude,agents,cursor,copilot,windsurf")
    s = sub.add_parser("gate"); s.add_argument("root", nargs="?", default=".")
    s.add_argument("--hook", action="store_true"); s.add_argument("--ci", action="store_true")
    a = ap.parse_args()
    fn = {"recon": cmd_recon, "scan": cmd_scan, "report": cmd_report, "diff": cmd_diff,
          "probe-supabase": cmd_probe_supabase, "guard": cmd_guard, "gate": cmd_gate}[a.cmd]
    sys.exit(fn(a) or 0)


if __name__ == "__main__":
    main()
