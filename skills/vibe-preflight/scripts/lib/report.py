"""Merge findings, compute verdict, write JSON / Markdown / SARIF."""
import json
from datetime import datetime, timezone
from pathlib import Path

SEV_ORDER = {"P0": 0, "P1": 1, "P2": 2}
CAT_NAMES = {"security": "Security", "legal": "Legal & privacy", "ux": "UX & product logic",
             "a11y": "Accessibility", "technical": "Technical, SEO & ops", "design": "Design (AI slop)"}
RULE_DOCS = {"S": "security", "L": "legal", "U": "ux", "F": "a11y", "T": "technical", "D": "design", "J": "judgment"}


def dedupe(findings):
    seen, out = set(), []
    for f in findings:
        key = (f.get("id"), f.get("title"), f.get("file"), f.get("line"))
        if key in seen:
            continue
        seen.add(key)
        out.append(f)
    return out


def sort_key(f):
    return (SEV_ORDER.get(f.get("severity"), 3), f.get("category", ""), f.get("id", ""), f.get("file", ""), f.get("line", 0))


def verdict(findings):
    active = [f for f in findings if not f.get("ignored") and not f.get("skipped")]
    if any(f["severity"] == "P0" for f in active):
        return "BLOCK", 1
    if any(f["severity"] == "P1" for f in active):
        return "FIX FIRST", 2
    return "SHIP", 0


def load_all(out_dir: Path):
    findings, meta = [], {}
    for p in sorted(out_dir.glob("*findings*.json")):
        if p.name.endswith(".prev.json"):
            continue
        try:
            j = json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            continue
        if isinstance(j, dict):
            findings += j.get("findings", [])
            for k, v in (j.get("meta") or {}).items():
                meta.setdefault(k, v)
        elif isinstance(j, list):
            findings += j
    return dedupe(findings), meta


def write_markdown(out_dir: Path, findings, meta):
    v, _ = verdict(findings)
    active = [f for f in findings if not f.get("ignored") and not f.get("skipped")]
    ignored = [f for f in findings if f.get("ignored")]
    skipped = [f for f in findings if f.get("skipped")] + [dict(title=s) for s in meta.get("skipped_checks", [])]
    counts = {s: sum(1 for f in active if f["severity"] == s) for s in ("P0", "P1", "P2")}
    lines = [
        "# Vibe Preflight report", "",
        f"**Verdict: {v}**  ·  P0 {counts['P0']}  ·  P1 {counts['P1']}  ·  P2 {counts['P2']}  ·  {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}", "",
    ]
    if meta.get("stack"):
        lines += [f"Stack: {', '.join(meta['stack'])}" + (f" · Deploy: {', '.join(meta.get('deploy', []))}" if meta.get('deploy') else "") + (f" · Built with: {', '.join(meta.get('ai_platform', []))}" if meta.get('ai_platform') else ""), ""]
    lines += ["P0 = blocks launch · P1 = fix before launch · P2 = polish. Legal items are engineering guidance, not legal advice.", ""]
    by_cat = {}
    for f in sorted(active, key=sort_key):
        by_cat.setdefault(f.get("category", "other"), []).append(f)
    lines += ["## Summary", "", "| Area | P0 | P1 | P2 |", "| --- | --- | --- | --- |"]
    for c, fs in by_cat.items():
        lines.append(f"| {CAT_NAMES.get(c, c)} | {sum(1 for f in fs if f['severity']=='P0')} | {sum(1 for f in fs if f['severity']=='P1')} | {sum(1 for f in fs if f['severity']=='P2')} |")
    lines.append("")
    for c, fs in by_cat.items():
        lines += [f"## {CAT_NAMES.get(c, c)}", ""]
        for f in fs:
            loc = f"`{f['file']}:{f['line']}`" if f.get("file") and f.get("line") else (f"`{f['file']}`" if f.get("file") else "")
            ref = RULE_DOCS.get(f["id"][0], "")
            lines.append(f"- **{f['severity']} {f['id']}** {f['title']} {loc}")
            if f.get("evidence"):
                lines.append(f"  - Evidence: `{str(f['evidence'])[:220]}`")
            if f.get("locations") and len(f["locations"]) > 1:
                lines.append(f"  - Also: {', '.join(f['locations'][1:8])}{' …' if len(f['locations']) > 8 else ''}")
            lines.append(f"  - Fix: {f['fix']}")
            if f.get("confidence") in ("low", "medium"):
                lines.append(f"  - Confidence: {f['confidence']} (verify)")
            if ref:
                lines.append(f"  - Ref: references/{ref}.md#{f['id'].lower()}")
        lines.append("")
    if ignored:
        lines += ["## Accepted risks (preflight-ignore)", ""]
        for f in ignored:
            lines.append(f"- {f['id']} {f['title']} `{f.get('file')}:{f.get('line')}`: {f['ignored']}")
        lines.append("")
    if skipped:
        lines += ["## Checks not run", ""]
        for f in skipped:
            lines.append(f"- {f.get('title')}")
        lines.append("")
    (out_dir / "report.md").write_text("\n".join(lines), encoding="utf-8")


def write_sarif(out_dir: Path, findings):
    level = {"P0": "error", "P1": "warning", "P2": "note"}
    rules, results, seen = [], [], set()
    for f in findings:
        if f.get("ignored") or f.get("skipped"):
            continue
        rid = f["id"]
        if rid not in seen:
            seen.add(rid)
            rules.append({"id": rid, "name": rid.replace("-", ""), "shortDescription": {"text": f["title"][:120]},
                          "help": {"text": f["fix"]}, "properties": {"category": f.get("category")}})
        r = {"ruleId": rid, "level": level.get(f["severity"], "note"),
             "message": {"text": f"{f['title']}. Fix: {f['fix']}"}}
        if f.get("file"):
            r["locations"] = [{"physicalLocation": {"artifactLocation": {"uri": f["file"]},
                                                    "region": {"startLine": max(1, int(f.get("line") or 1))}}}]
        results.append(r)
    sarif = {"$schema": "https://json.schemastore.org/sarif-2.1.0.json", "version": "2.1.0",
             "runs": [{"tool": {"driver": {"name": "vibe-preflight", "informationUri": "https://github.com/princetoomuch1/Securednonaislop-skill", "rules": rules}},
                       "results": results}]}
    (out_dir / "results.sarif").write_text(json.dumps(sarif, indent=1), encoding="utf-8")


def build_report(out_dir: Path):
    findings, meta = load_all(out_dir)
    findings.sort(key=sort_key)
    v, code = verdict(findings)
    (out_dir / "report.json").write_text(json.dumps({"verdict": v, "meta": meta, "findings": findings}, indent=1), encoding="utf-8")
    write_markdown(out_dir, findings, meta)
    write_sarif(out_dir, findings)
    return v, code, findings


def diff(prev_path: Path, cur_path: Path):
    def keyset(p):
        j = json.loads(Path(p).read_text(encoding="utf-8"))
        fs = j.get("findings", j) if isinstance(j, dict) else j
        return {(f["id"], f["title"], f.get("file"), f.get("line")): f for f in fs if not f.get("ignored")}
    a, b = keyset(prev_path), keyset(cur_path)
    fixed = [a[k] for k in a if k not in b]
    new = [b[k] for k in b if k not in a]
    return fixed, new
