"""File walker + regex rule runner."""
import os
import re
from pathlib import Path

from .rules import compile_rules, EMOJI_RE, EMOJI_RULE, MARKUP, CODE

SKIP_DIRS = {
    "node_modules", ".git", ".next", ".nuxt", ".svelte-kit", ".turbo", ".vercel", ".netlify",
    ".cache", ".parcel-cache", "coverage", "__pycache__", ".venv", "venv", "env", ".mypy_cache",
    ".pytest_cache", ".preflight", "vendor", "bower_components", ".expo", ".idea", ".vscode",
}
BUILD_DIRS = ["dist", "build", "out", ".next/static", ".output/public", "public/build", ".svelte-kit/output"]
TEXT_EXT = {
    ".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs", ".vue", ".svelte", ".astro", ".html", ".htm",
    ".css", ".scss", ".sass", ".less", ".md", ".mdx", ".json", ".py", ".sql", ".rules", ".toml",
    ".yaml", ".yml", ".txt", ".env", ".sh", ".xml",
}
MAX_BYTES = 1_500_000
IGNORE_RX = re.compile(r"preflight-ignore\s+([A-Z]-\d{2})(?::\s*(.*))?")


def is_text_file(p: Path) -> bool:
    name = p.name
    if name.startswith(".env"):
        return True
    if name in {"firestore.rules", "storage.rules", "database.rules.json", "_headers", "_redirects"}:
        return True
    return p.suffix.lower() in TEXT_EXT


def ext_of(p: Path) -> str:
    if p.name.startswith(".env"):
        return ".env"
    if p.name.endswith(".rules"):
        return ".rules"
    return p.suffix.lower()


def walk(root: Path, include_build=False):
    root = root.resolve()
    build_abs = {(root / b).resolve() for b in BUILD_DIRS}
    for dirpath, dirnames, filenames in os.walk(root):
        d = Path(dirpath)
        keep = []
        for dn in dirnames:
            full = (d / dn).resolve()
            if dn in SKIP_DIRS and not (include_build and full in build_abs):
                continue
            if not include_build and full in build_abs:
                continue
            keep.append(dn)
        dirnames[:] = keep
        for fn in filenames:
            p = d / fn
            if not is_text_file(p):
                continue
            try:
                if p.stat().st_size > MAX_BYTES:
                    continue
            except OSError:
                continue
            yield p


def walk_build(root: Path):
    for b in BUILD_DIRS:
        bd = (root / b)
        if bd.is_dir():
            for dirpath, _dn, filenames in os.walk(bd):
                for fn in filenames:
                    p = Path(dirpath) / fn
                    if p.suffix.lower() in {".js", ".mjs", ".html", ".json", ".map", ".css", ".txt"}:
                        try:
                            if p.stat().st_size <= MAX_BYTES * 4:
                                yield p
                        except OSError:
                            pass


def read(p: Path) -> str:
    try:
        return p.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return ""


def ignores_for(lines):
    """Map line number (1-based) -> set of ignored rule ids (same line or line above)."""
    ign = {}
    for i, line in enumerate(lines, 1):
        for m in IGNORE_RX.finditer(line):
            for ln in (i, i + 1):
                ign.setdefault(ln, {})[m.group(1)] = (m.group(2) or "").strip()
    return ign


def mask(s: str) -> str:
    s = s.strip()
    if len(s) <= 8:
        return s[:2] + "…"
    return f"{s[:4]}…({len(s)})"


def make_finding(rule, rel, line, snippet, **extra):
    f = {
        "id": rule["id"], "severity": rule["sev"], "category": rule["cat"], "title": rule["title"],
        "file": rel, "line": line, "evidence": snippet, "fix": rule["fix"],
        "confidence": rule.get("confidence", "high"), "source": "static",
    }
    f.update(extra)
    return f


def run_rules(root: Path, include_build=True):
    root = root.resolve()
    rules = compile_rules()
    findings = []
    agg = {}  # (id,title) -> finding with count

    def handle(p: Path, scope: str):
        rel = str(p.relative_to(root)).replace(os.sep, "/")
        e = ext_of(p)
        text = read(p)
        if not text:
            return
        # Real env files are where secrets belong; S-02 checks they are not committed.
        if re.fullmatch(r"\.env(\.[a-z]+)?", p.name) and not re.search(r"example|sample|template", p.name):
            return
        lines = text.splitlines()
        ign = ignores_for(lines)
        for r in rules:
            if scope == "build" and r["scope"] == "source":
                continue
            if scope == "source" and r["scope"] == "build":
                continue
            if r["exts"] is not None and e not in r["exts"]:
                continue
            if r["only_rx"] and not r["only_rx"].search(rel):
                continue
            if r["not_rx"] and r["not_rx"].search(rel):
                continue
            if r["skip_rx"] and r["skip_rx"].search(text):
                continue
            hits = []
            if r.get("multiline"):
                for m in r["rx"].finditer(text):
                    ln = text.count("\n", 0, m.start()) + 1
                    hits.append((ln, m.group(0)))
            else:
                for i, line in enumerate(lines, 1):
                    if len(line) > 3000:  # minified: search but trim evidence
                        for m in r["rx"].finditer(line):
                            hits.append((i, m.group(0)))
                            break
                        continue
                    m = r["rx"].search(line)
                    if m:
                        hits.append((i, m.group(0) if r["cat"] == "security" and r["id"] == "S-01" else line.strip()))
            for ln, snip in hits:
                ignored = ign.get(ln, {}).get(r["id"])
                if r["id"] == "S-01":
                    snip = mask(snip)
                snip = snip[:200]
                extra = {"scope": scope}
                if ignored is not None:
                    extra["ignored"] = ignored or "no reason given"
                if r.get("aggregate") and ignored is None:
                    key = (r["id"], r["title"])
                    if key not in agg:
                        agg[key] = make_finding(r, rel, ln, snip, count=0, locations=[], **extra)
                    agg[key]["count"] += 1
                    if len(agg[key]["locations"]) < 15:
                        agg[key]["locations"].append(f"{rel}:{ln}")
                    continue
                findings.append(make_finding(r, rel, ln, snip, **extra))

    for p in walk(root):
        handle(p, "source")
    if include_build:
        for p in walk_build(root):
            handle(p, "build")

    # emoji-as-icon: count emoji inside markup/code text, outside comments
    emoji_hits = []
    for p in walk(root):
        e = ext_of(p)
        if e not in (MARKUP | CODE) or e in {".md", ".mdx"}:
            continue
        rel = str(p.relative_to(root)).replace(os.sep, "/")
        for i, line in enumerate(read(p).splitlines(), 1):
            s = line.strip()
            if s.startswith(("//", "*", "#", "/*")):
                continue
            if EMOJI_RE.search(line):
                emoji_hits.append(f"{rel}:{i}")
    if len(emoji_hits) >= 3:
        r = EMOJI_RULE
        findings.append({
            "id": r["id"], "severity": r["sev"], "category": r["cat"], "title": r["title"],
            "file": emoji_hits[0].split(":")[0], "line": int(emoji_hits[0].split(":")[1]),
            "evidence": f"{len(emoji_hits)} lines with emoji in UI code", "fix": r["fix"],
            "confidence": "medium", "source": "static", "count": len(emoji_hits), "locations": emoji_hits[:15],
        })

    for f in agg.values():
        f["evidence"] = f"{f['count']} occurrence(s); first: {f['evidence']}"
        findings.append(f)
    return findings
