"""Dependency verification: hallucinated (slopsquatted), brand-new, unpopular or typosquat packages."""
import json
import re
import urllib.error
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

POPULAR_NPM = [
    "react", "react-dom", "next", "vue", "svelte", "express", "axios", "lodash", "moment", "dayjs", "zod",
    "tailwindcss", "typescript", "vite", "eslint", "prettier", "jest", "vitest", "webpack", "esbuild",
    "@supabase/supabase-js", "firebase", "stripe", "openai", "@anthropic-ai/sdk", "prisma", "@prisma/client",
    "mongoose", "pg", "mysql2", "redis", "jsonwebtoken", "bcrypt", "bcryptjs", "dotenv", "cors", "helmet",
    "uuid", "nanoid", "date-fns", "framer-motion", "lucide-react", "clsx", "class-variance-authority",
    "react-router-dom", "react-hook-form", "@tanstack/react-query", "swr", "zustand", "redux", "chalk",
    "commander", "yargs", "socket.io", "graphql", "apollo-server", "nodemailer", "sharp", "multer",
    "cookie-parser", "body-parser", "passport", "next-auth", "drizzle-orm", "hono", "fastify", "colors",
]
POPULAR_PY = [
    "requests", "numpy", "pandas", "flask", "django", "fastapi", "uvicorn", "pydantic", "sqlalchemy",
    "openai", "anthropic", "boto3", "pytest", "beautifulsoup4", "scrapy", "pillow", "matplotlib", "scipy",
    "langchain", "transformers", "torch", "tensorflow", "psycopg2", "redis", "celery", "httpx", "aiohttp",
]
UA = {"User-Agent": "vibe-preflight/1.0 (+https://github.com)"}


def lev1(a: str, b: str) -> bool:
    """True if edit distance between a and b is exactly 1 (or a swap)."""
    if a == b:
        return False
    la, lb = len(a), len(b)
    if abs(la - lb) > 1:
        return False
    if la == lb:
        diff = [i for i in range(la) if a[i] != b[i]]
        if len(diff) == 1:
            return True
        if len(diff) == 2 and a[diff[0]] == b[diff[1]] and a[diff[1]] == b[diff[0]] and diff[1] == diff[0] + 1:
            return True
        return False
    if la > lb:
        a, b = b, a
    i = j = edits = 0
    while i < len(a) and j < len(b):
        if a[i] != b[j]:
            edits += 1
            if edits > 1:
                return False
            j += 1
        else:
            i += 1
            j += 1
    return True


def near_popular(name, popular):
    n = name.lower()
    for p in popular:
        if lev1(n, p) or (n.replace("-", "") == p.replace("-", "") and n != p) or (n.replace("_", "-") == p and n != p and "_" in n):
            return p
    return None


def get_json(url, timeout=8):
    req = urllib.request.Request(url, headers=UA)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, json.loads(r.read().decode("utf-8", "ignore"))
    except urllib.error.HTTPError as e:
        return e.code, None
    except Exception:
        return None, None


def check_npm(name, spec):
    if spec and re.match(r"^(file:|link:|workspace:|git\+|github:|https?:|\.\.?/)", str(spec)):
        return {"name": name, "eco": "npm", "status": "local"}
    status, data = get_json("https://registry.npmjs.org/" + urllib.parse.quote(name, safe="@"))
    out = {"name": name, "eco": "npm", "spec": spec, "http": status}
    if status == 404:
        out["status"] = "missing"
        return out
    if status != 200 or not data:
        out["status"] = "unknown"
        return out
    t = (data.get("time") or {}).get("created")
    if t:
        try:
            created = datetime.fromisoformat(t.replace("Z", "+00:00"))
            out["age_days"] = (datetime.now(timezone.utc) - created).days
        except Exception:
            pass
    out["has_repo"] = bool(data.get("repository"))
    latest = (data.get("dist-tags") or {}).get("latest")
    if latest:
        v = (data.get("versions") or {}).get(latest) or {}
        out["deprecated"] = v.get("deprecated")
        scripts = v.get("scripts") or {}
        out["install_scripts"] = {k: scripts[k] for k in ("preinstall", "install", "postinstall") if k in scripts}
    st, dl = get_json("https://api.npmjs.org/downloads/point/last-week/" + urllib.parse.quote(name, safe="@"))
    if st == 200 and dl:
        out["weekly_downloads"] = dl.get("downloads")
    out["status"] = "ok"
    return out


def check_pypi(name, spec):
    status, data = get_json(f"https://pypi.org/pypi/{urllib.parse.quote(name)}/json")
    out = {"name": name, "eco": "pypi", "spec": spec, "http": status}
    if status == 404:
        out["status"] = "missing"
        return out
    if status != 200 or not data:
        out["status"] = "unknown"
        return out
    rel = data.get("releases") or {}
    times = []
    for files in rel.values():
        for f in files or []:
            if f.get("upload_time_iso_8601"):
                times.append(f["upload_time_iso_8601"])
    if times:
        first = min(times)
        try:
            out["age_days"] = (datetime.now(timezone.utc) - datetime.fromisoformat(first.replace("Z", "+00:00"))).days
        except Exception:
            pass
    info = data.get("info") or {}
    out["has_repo"] = bool(info.get("project_urls") or info.get("home_page"))
    out["status"] = "ok"
    return out


def parse_requirements(text):
    deps = {}
    for line in text.splitlines():
        line = line.split("#")[0].strip()
        if not line or line.startswith(("-", "git+", "http")):
            continue
        m = re.match(r"([A-Za-z0-9_.\-]+)(\[.*\])?\s*(.*)", line)
        if m:
            deps[m.group(1)] = m.group(3)
    return deps


def parse_pyproject(text):
    deps = {}
    m = re.search(r"dependencies\s*=\s*\[(.*?)\]", text, re.S)
    if m:
        for s in re.findall(r"[\"']([^\"']+)[\"']", m.group(1)):
            mm = re.match(r"([A-Za-z0-9_.\-]+)", s)
            if mm:
                deps[mm.group(1)] = s[len(mm.group(1)):]
    return deps


def F(id, sev, title, fix, file, evidence, confidence="high"):
    return dict(id=id, severity=sev, category="security", title=title, file=file, line=0,
                evidence=evidence, fix=fix, confidence=confidence, source="static")


def run_deps(root: Path, offline=False):
    root = root.resolve()
    targets = []
    for pj in [root / "package.json"] + list(root.glob("*/package.json")) + list(root.glob("apps/*/package.json")) + list(root.glob("packages/*/package.json")):
        if "node_modules" in pj.parts or not pj.exists():
            continue
        try:
            j = json.loads(pj.read_text(encoding="utf-8"))
        except Exception:
            continue
        local_names = {j.get("name")}
        for k in ("dependencies", "devDependencies", "optionalDependencies"):
            for n, v in (j.get(k) or {}).items():
                if n not in local_names:
                    targets.append(("npm", n, v, str(pj.relative_to(root))))
    for rq in [root / "requirements.txt"] + list(root.glob("*/requirements.txt")):
        if rq.exists():
            for n, v in parse_requirements(rq.read_text(encoding="utf-8", errors="ignore")).items():
                targets.append(("pypi", n, v, str(rq.relative_to(root))))
    pp = root / "pyproject.toml"
    if pp.exists():
        for n, v in parse_pyproject(pp.read_text(encoding="utf-8", errors="ignore")).items():
            targets.append(("pypi", n, v, "pyproject.toml"))

    findings, results = [], []
    # offline: typosquat heuristic only
    for eco, n, v, f in targets:
        near = near_popular(n, POPULAR_NPM if eco == "npm" else POPULAR_PY)
        if near:
            findings.append(F("S-24", "P1", f"Package name one typo away from '{near}'", "Check you meant the popular package; typosquats steal tokens on install.", f, f"{n} vs {near}", "medium"))
    if offline or not targets:
        return findings, results

    def work(t):
        eco, n, v, f = t
        r = check_npm(n, v) if eco == "npm" else check_pypi(n, v)
        r["file"] = f
        return r

    with ThreadPoolExecutor(max_workers=12) as ex:
        results = list(ex.map(work, targets[:400]))
    unknown = 0
    for r in results:
        n, f = r["name"], r["file"]
        if r["status"] == "missing":
            findings.append(F("S-24", "P0", f"Dependency '{n}' does not exist on {r['eco']} (hallucinated package)", "Remove it and find the real package. If someone registers this name later, installs will run their code (slopsquatting).", f, f"{r['eco']} returned 404"))
        elif r["status"] == "unknown":
            unknown += 1
        elif r["status"] == "ok":
            age = r.get("age_days")
            dl = r.get("weekly_downloads")
            if age is not None and age < 60:
                findings.append(F("S-24", "P1", f"Dependency '{n}' is only {age} days old", "Confirm it is the package you intended and inspect its code before shipping.", f, f"created {age} days ago, downloads/week={dl}", "medium"))
            if dl is not None and dl < 200 and (age is None or age < 365):
                findings.append(F("S-24", "P1", f"Dependency '{n}' has very few downloads ({dl}/week)", "Low-use, young packages are where slopsquatting payloads hide. Verify the author and repo.", f, f"downloads/week={dl}, has_repo={r.get('has_repo')}", "medium"))
            if r.get("deprecated"):
                findings.append(F("S-24", "P2", f"Dependency '{n}' is deprecated", "Move to the maintained replacement named in the deprecation notice.", f, str(r["deprecated"])[:160]))
            if r.get("install_scripts") and (dl or 0) < 10000:
                findings.append(F("S-24", "P1", f"Dependency '{n}' runs install scripts", "Review the script; consider --ignore-scripts.", f, json.dumps(r["install_scripts"])[:160], "medium"))
    if unknown and unknown == len(results):
        findings.append(dict(id="S-24", severity="P2", category="security", title="Dependency registry unreachable; existence not verified",
                             file="", line=0, evidence=f"{unknown} packages unchecked", fix="Re-run with network access, or run `npm view <pkg>` / `pip index versions <pkg>` for each.",
                             confidence="high", source="static", skipped=True))
    return findings, results
