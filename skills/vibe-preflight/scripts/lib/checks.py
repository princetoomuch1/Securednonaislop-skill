"""Project-level checks: things that are missing, cross-file logic, stack-specific gaps."""
import base64
import json
import os
import re
import subprocess
from pathlib import Path

from .scan import walk, read, mask

CONSENT_LIBS = r"cookieconsent|vanilla-cookieconsent|klaro|cookiebot|onetrust|otSDKStub|usercentrics|iubenda|termly|consentmanager|cookieyes|osano|didomi|tarteaucitron|react-cookie-consent|cookie-consent|gtag\(\s*['\"]consent['\"]|consentMode|CookieBanner|ConsentBanner|hasConsent|analytics_storage"
TRACKERS = r"googletagmanager\.com|google-analytics\.com|gtag\(|\bga\(|fbq\(|connect\.facebook\.net|static\.hotjar\.com|hotjar|clarity\.ms|posthog\.init|posthog-js|mixpanel\.init|analytics\.tiktok\.com|snap\.licdn\.com|_linkedin_partner_id|plausible|@vercel/analytics|segment\.com/analytics|amplitude\.init|intercom|crisp\.chat|tawk\.to|hs-scripts\.com"
COOKIELESS = r"plausible|@vercel/analytics|umami|fathom|simpleanalytics|pirsch"


def F(id, sev, cat, title, fix, file="", line=0, evidence="", confidence="high", **kw):
    d = dict(id=id, severity=sev, category=cat, title=title, file=file, line=line,
             evidence=evidence, fix=fix, confidence=confidence, source="static")
    d.update(kw)
    return d


def load_pkg(root: Path):
    pkgs = []
    for p in [root / "package.json"] + list(root.glob("*/package.json")) + list(root.glob("apps/*/package.json")) + list(root.glob("packages/*/package.json")):
        if "node_modules" in p.parts:
            continue
        try:
            pkgs.append((p, json.loads(p.read_text(encoding="utf-8"))))
        except Exception:
            pass
    return pkgs


def all_deps(pkgs):
    deps = {}
    for _p, j in pkgs:
        for k in ("dependencies", "devDependencies", "peerDependencies", "optionalDependencies"):
            deps.update(j.get(k) or {})
    return deps


def detect_stack(root: Path):
    pkgs = load_pkg(root)
    deps = all_deps(pkgs)
    has = lambda *names: any(n in deps for n in names)
    exists = lambda *globs: any(list(root.glob(g)) for g in globs)
    stack = {
        "next": has("next"), "vite": has("vite"), "react": has("react"), "vue": has("vue", "nuxt"),
        "svelte": has("svelte", "@sveltejs/kit"), "astro": has("astro"), "remix": has("@remix-run/react", "@react-router/dev"),
        "express": has("express", "fastify", "koa", "hono"),
        "supabase": has("@supabase/supabase-js", "@supabase/ssr", "@supabase/auth-helpers-nextjs") or exists("supabase/config.toml", "supabase/migrations"),
        "firebase": has("firebase", "firebase-admin") or exists("firebase.json", "firestore.rules"),
        "stripe": has("stripe", "@stripe/stripe-js"),
        "prisma": has("prisma", "@prisma/client") or exists("prisma/schema.prisma"),
        "drizzle": has("drizzle-orm"),
        "tailwind": has("tailwindcss") or exists("tailwind.config.*"),
        "clerk": has("@clerk/nextjs", "@clerk/clerk-react"),
        "nextauth": has("next-auth", "@auth/core"),
        "openai": has("openai", "@anthropic-ai/sdk", "ai", "@ai-sdk/openai"),
        "python": exists("requirements.txt", "pyproject.toml"),
        "django": (root / "manage.py").exists(),
        "flask": "flask" in read(root / "requirements.txt").lower() if (root / "requirements.txt").exists() else False,
        "fastapi": "fastapi" in read(root / "requirements.txt").lower() if (root / "requirements.txt").exists() else False,
        "static_html": exists("index.html") and not pkgs,
    }
    deploy = []
    for f, name in [("vercel.json", "vercel"), ("netlify.toml", "netlify"), ("firebase.json", "firebase"),
                    ("render.yaml", "render"), ("fly.toml", "fly"), ("Dockerfile", "docker"), ("wrangler.toml", "cloudflare"),
                    (".replit", "replit"), ("railway.json", "railway")]:
        if (root / f).exists():
            deploy.append(name)
    platform = []
    txt = json.dumps([j for _p, j in pkgs])
    if "lovable-tagger" in txt or (root / ".lovable").exists():
        platform.append("lovable")
    if (root / ".bolt").exists():
        platform.append("bolt")
    if (root / ".replit").exists():
        platform.append("replit")
    if (root / ".cursor").exists() or (root / ".cursorrules").exists():
        platform.append("cursor")
    if (root / "CLAUDE.md").exists() or (root / ".claude").exists():
        platform.append("claude-code")
    return {"stack": [k for k, v in stack.items() if v], "deploy": deploy, "ai_platform": platform,
            "package_json": [str(p.relative_to(root)) for p, _ in pkgs], "deps": deps}


def git_tracked(root: Path):
    try:
        out = subprocess.run(["git", "-C", str(root), "ls-files"], capture_output=True, text=True, timeout=20)
        if out.returncode == 0:
            return out.stdout.splitlines()
    except Exception:
        pass
    return None


def decode_jwt_role(tok: str):
    try:
        parts = tok.split(".")
        if len(parts) != 3:
            return None
        pad = parts[1] + "=" * (-len(parts[1]) % 4)
        payload = json.loads(base64.urlsafe_b64decode(pad))
        return payload.get("role")
    except Exception:
        return None


def any_file(root: Path, patterns):
    for pat in patterns:
        if list(root.glob(pat)):
            return True
    return False


def grep_files(files, rx):
    r = re.compile(rx, re.I)
    hits = []
    for p, text in files:
        m = r.search(text)
        if m:
            hits.append((p, text.count("\n", 0, m.start()) + 1, m.group(0)))
    return hits


def run_checks(root: Path, jurisdictions=("eu", "uk", "us")):
    root = root.resolve()
    info = detect_stack(root)
    stack = set(info["stack"])
    findings = []
    files = []
    for p in walk(root):
        rel = str(p.relative_to(root)).replace(os.sep, "/")
        files.append((rel, read(p)))
    src = [(r, t) for r, t in files if not re.search(r"(^|/)(tests?|__tests__|e2e|cypress)(/|$)", r)]
    alltext = "\n".join(t for _r, t in src)
    eu = any(j in jurisdictions for j in ("eu", "uk"))

    # ---------- secrets & env ----------
    tracked = git_tracked(root)
    if tracked is not None:
        for f in tracked:
            base = f.split("/")[-1]
            if re.fullmatch(r"\.env(\.(local|production|prod|development|dev|staging))?", base):
                findings.append(F("S-02", "P0", "security", "Env file committed to git", "git rm --cached the file, add .env* to .gitignore, rotate every key in it, purge history (git filter-repo).", file=f))
    gi = read(root / ".gitignore")
    if (root / ".env").exists() or (root / ".env.local").exists():
        if not re.search(r"^\.env", gi, re.M):
            findings.append(F("S-02", "P1", "security", ".env not in .gitignore", "Add .env* (and !.env.example) to .gitignore.", file=".gitignore"))
    if not any_file(root, [".env.example", ".env.sample", ".env.template", ".env.local.example"]) and any_file(root, [".env", ".env.local"]):
        findings.append(F("T-18", "P2", "technical", "No .env.example", "Add .env.example listing every variable with empty values.", file=""))

    # Supabase JWT with service_role anywhere in source or build
    for rel, text in files:
        if rel.startswith(".env") or "/.env" in rel:
            continue
        for m in re.finditer(r"eyJ[A-Za-z0-9_-]{10,}\.eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}", text):
            role = decode_jwt_role(m.group(0))
            if role == "service_role":
                ln = text.count("\n", 0, m.start()) + 1
                findings.append(F("S-04", "P0", "security", "Supabase service_role key in code", "service_role bypasses RLS. Remove it from code, rotate it in Supabase, use it only in server/edge functions.", file=rel, line=ln, evidence=mask(m.group(0))))
    # service role env referenced from client code
    for rel, text in src:
        if re.search(r"SERVICE_ROLE", text) and (re.search(r"^['\"]use client['\"]", text, re.M) or ("vite" in stack and rel.startswith("src/") and "supabase/functions" not in rel)):
            findings.append(F("S-04", "P0", "security", "Service role key referenced from browser code", "Use the anon key in the browser; move service_role usage to a server route or edge function.", file=rel, evidence="SERVICE_ROLE in client bundle path"))

    # ---------- Supabase migrations: RLS coverage ----------
    sql = [(r, t) for r, t in files if r.endswith(".sql")]
    if sql:
        created, rls = {}, set()
        for rel, t in sql:
            for m in re.finditer(r"(?i)create\s+table\s+(?:if\s+not\s+exists\s+)?(?:\"?public\"?\.)?\"?([a-z_][a-z0-9_]*)\"?", t):
                created.setdefault(m.group(1).lower(), (rel, t.count("\n", 0, m.start()) + 1))
            for m in re.finditer(r"(?i)alter\s+table\s+(?:only\s+)?(?:\"?public\"?\.)?\"?([a-z_][a-z0-9_]*)\"?\s+enable\s+row\s+level\s+security", t):
                rls.add(m.group(1).lower())
        for tname, (rel, ln) in created.items():
            if tname not in rls and ("supabase" in stack or "supabase" in rel):
                findings.append(F("S-03", "P0", "security", f"Table '{tname}' created without enabling RLS", f"ALTER TABLE public.{tname} ENABLE ROW LEVEL SECURITY; then add owner policies (see references/security.md#s-03).", file=rel, line=ln, evidence=f"create table {tname}"))
    elif "supabase" in stack:
        findings.append(F("S-03", "P1", "security", "Supabase used but no migrations in repo (RLS cannot be verified from code)", "Run `supabase db pull` to commit the schema, or run the live probe: preflight.py probe-supabase.", confidence="medium"))

    # ---------- Firebase rules ----------
    if "firebase" in stack and not any_file(root, ["firestore.rules", "storage.rules", "database.rules.json", "**/firestore.rules"]):
        findings.append(F("S-05", "P1", "security", "Firebase used but no security rules file in repo", "Commit firestore.rules / storage.rules and deploy them; check the console is not in test mode.", confidence="medium"))
    for rel, t in files:
        if rel.endswith("database.rules.json") and re.search(r"\"\.(read|write)\"\s*:\s*(true|\"true\")", t):
            findings.append(F("S-05", "P0", "security", "Realtime Database rules allow everyone", "Use auth != null and per-user paths.", file=rel))

    # ---------- API routes: auth heuristics ----------
    auth_rx = r"getServerSession|getSession\(|auth\(\)|currentUser\(|getUser\(|getAuth\(|verifyIdToken|requireAuth|withAuth|isAuthenticated|getToken\(|clerkClient|auth\.protect|supabase\.auth\.getUser|validateRequest|jwt\.verify|verifyJWT|authenticate|passport\.|@login_required|Depends\(get_current_user|request\.user|ensureAuth|session\.user|authorization|x-api-key|bearer|get\(['\"]secret|REVALIDATION_SECRET|CRON_SECRET|timingSafeEqual"
    mw = any_file(root, ["middleware.ts", "middleware.js", "src/middleware.ts", "src/middleware.js"])
    mw_text = read(root / "middleware.ts") + read(root / "src/middleware.ts") + read(root / "middleware.js") + read(root / "src/middleware.js")
    mw_covers_api = mw and re.search(r"/api", mw_text) and re.search(auth_rx, mw_text, re.I)
    route_rx = re.compile(r"(^|/)(app|src/app)/.*api/.*route\.(ts|js)$|(^|/)pages/api/.*\.(ts|js)$|(^|/)(routes|api|server|controllers)/.*\.(ts|js|py)$|supabase/functions/.*/index\.ts$")
    for rel, t in src:
        if not route_rx.search(rel):
            continue
        if re.search(r"webhook", rel, re.I):
            if re.search(r"stripe", t, re.I) and not re.search(r"constructEvent|constructEventAsync|webhooks\.verify|verifyHeader", t):
                findings.append(F("S-23", "P0", "security", "Stripe webhook without signature verification", "Use stripe.webhooks.constructEvent(rawBody, sig, endpointSecret) and reject on failure; make handling idempotent.", file=rel))
            elif not re.search(r"signature|verify|hmac|svix|constructEvent", t, re.I):
                findings.append(F("S-23", "P1", "security", "Webhook handler without signature check", "Verify the provider's signature header before trusting the payload.", file=rel, confidence="medium"))
            continue
        mutating = re.search(r"export\s+(?:async\s+)?function\s+(POST|PUT|PATCH|DELETE)|\.(post|put|patch|delete)\(\s*['\"]|methods=\[[^\]]*(POST|PUT|DELETE)|req\.method\s*===?\s*['\"](POST|PUT|PATCH|DELETE)|Deno\.serve|serve\(", t)
        reads_db = re.search(r"\.from\(|prisma\.|db\.|\.query\(|collection\(|findMany|select\(", t)
        if (mutating or reads_db) and not re.search(auth_rx, t, re.I) and not mw_covers_api:
            if re.search(r"(?i)(health|status|og|sitemap|robots|public|contact|newsletter|subscribe|login|signin|signup|register|callback|cron)", rel):
                continue
            findings.append(F("S-08", "P1", "security", "API route with no visible auth check", "Authenticate on the server (session/JWT) and check the caller owns the data. If it is meant to be public, add `// preflight-ignore S-08: public endpoint`.", file=rel, confidence="medium"))

    # ---------- rate limiting / CSRF / headers ----------
    has_api = any(route_rx.search(r) for r, _ in src)
    if has_api and not re.search(r"ratelimit|rate-limit|rateLimit|rate_limit|express-rate-limit|rate-limiter-flexible|@upstash/ratelimit|slowapi|throttle|limiter|arcjet|turnstile|hcaptcha|recaptcha", alltext, re.I):
        findings.append(F("S-18", "P1", "security", "No rate limiting or bot protection found", "Add per-IP/per-user limits on login, signup, password reset, contact forms and AI endpoints (@upstash/ratelimit, express-rate-limit), plus spend caps on paid APIs.", confidence="medium"))
    if "express" in stack and re.search(r"express-session|cookie-session|cookie-parser", alltext) and not re.search(r"csurf|csrf|lusca|csrf-csrf|sameSite\s*:\s*['\"](strict|lax)", alltext, re.I):
        findings.append(F("S-15", "P1", "security", "Cookie sessions without CSRF protection", "Add CSRF tokens (csrf-csrf) or SameSite=Lax/Strict cookies plus an Origin check on state-changing routes.", confidence="medium"))
    header_cfg = alltext + read(root / "vercel.json") + read(root / "netlify.toml") + read(root / "public/_headers") + read(root / "_headers") + read(root / "firebase.json")
    if not re.search(r"Content-Security-Policy|Strict-Transport-Security|helmet\(|X-Content-Type-Options", header_cfg, re.I) and not info["stack"] == ["python"]:
        findings.append(F("S-19", "P1", "security", "No security headers configured", "Add CSP, HSTS, X-Content-Type-Options, Referrer-Policy, frame-ancestors (templates/security-headers.md).", confidence="medium"))

    # ---------- LLM in client ----------
    for rel, t in src:
        if re.search(r"new\s+(OpenAI|Anthropic|GoogleGenerativeAI)\(", t) and (re.search(r"^['\"]use client['\"]", t, re.M) or ("vite" in stack and rel.startswith("src/"))):
            findings.append(F("S-25", "P0", "security", "LLM client created in browser code", "Move the SDK call to a server route; the key ships to every visitor otherwise.", file=rel))

    # ---------- package scripts ----------
    for p, j in load_pkg(root):
        for k in ("preinstall", "install", "postinstall"):
            v = (j.get("scripts") or {}).get(k)
            if v and re.search(r"curl|wget|http|node -e|bash|sh -c|powershell", v):
                findings.append(F("S-24", "P1", "security", f"{k} script runs network/shell code", "Review it; install scripts run on every machine that installs the package.", file=str(p.relative_to(root)), evidence=v[:120]))

    # ---------- dangerouslySetInnerHTML with JSON-LD is fine (handled), skip ----------

    # ---------- legal ----------
    strong = re.search(r"type=[\"'](?:email|password|tel)[\"']|name=[\"'](?:email|phone|full_?name)[\"']|signUp|signIn|auth\.sign|createUser|newsletter|subscribe\(|supabase\.auth|useUser\(|clerk|next-auth", alltext)
    collects = strong or re.search(r"\bcheckout\b|stripe|<form|mailto:", alltext)
    tracks = re.search(TRACKERS, alltext)
    route_names = " ".join(r.lower() for r, _ in files)
    has_privacy = re.search(r"privacy", route_names) or re.search(r"href=[\"'][^\"']*privacy", alltext, re.I)
    has_terms = re.search(r"terms|tos\b|conditions", route_names) or re.search(r"href=[\"'][^\"']*(terms|conditions)", alltext, re.I)
    if (collects or tracks) and not has_privacy:
        findings.append(F("L-01", "P0" if (strong or tracks) else "P1", "legal", "Collects data but has no Privacy Policy", "Add a privacy page (what you collect, why, legal basis, processors, retention, rights, contact) linked in the footer and at every form. Have a lawyer review.", evidence="forms/auth/analytics detected; no privacy route or link"))
    if re.search(r"signUp|signup|register|checkout|stripe|subscription|createUser", alltext, re.I) and not has_terms:
        findings.append(F("L-03", "P1", "legal", "Accounts or payments without Terms", "Add Terms of Service and link them at signup and checkout."))
    if tracks and not re.search(CONSENT_LIBS, alltext, re.I):
        if re.search(COOKIELESS, alltext, re.I) and not re.search(r"gtag\(|fbq\(|hotjar|clarity\.ms|posthog|mixpanel|tiktok|licdn|segment|amplitude|intercom", alltext, re.I):
            pass  # cookieless analytics only
        else:
            sev = "P0" if eu else "P1"
            ev = re.search(TRACKERS, alltext).group(0)
            findings.append(F("L-07", sev, "legal", "Trackers present with no consent manager", "Load analytics/ads/chat widgets only after opt-in. Use a consent manager that blocks scripts, with equal Accept/Reject buttons and a footer link to change choices. Confirm with the rendered pre-consent test.", evidence=f"tracker: {ev}", confidence="medium"))
    if re.search(r"\b(stripe|checkout|add to cart|shopping cart|cartItems|useCart)\b", alltext, re.I) and not re.search(r"refund|returns", route_names, re.I) and not re.search(r"href=[\"'][^\"']*(refund|returns)", alltext, re.I):
        findings.append(F("L-15", "P1", "legal", "Selling online without refund/returns page", "Add refund, returns and shipping terms; show total price including fees early.", confidence="medium"))
    # testimonials without source: block that mentions testimonial and has no link/source
    for rel, t in src:
        if re.search(r"testimonial|reviews?\s*=\s*\[|const\s+reviews", t, re.I) and re.search(r"(name|author)\s*:\s*['\"][A-Z][a-z]+ [A-Z]", t):
            if not re.search(r"source|url|href|linkedin|twitter|verified|g2|trustpilot|capterra", t, re.I):
                findings.append(F("L-04", "P1", "legal", "Testimonials hardcoded with no source", "Confirm each quote is from a real customer who agreed to be quoted; keep proof. Fabricated testimonials are illegal (FTC 16 CFR 465, UK DMCC Act).", file=rel, confidence="low", evidence="hardcoded name/quote array"))
    for rel, t in src:
        if re.search(r"[\"']@type[\"']\s*:\s*[\"'](?:Organization|LocalBusiness)[\"']", t) and re.search(r"aggregateRating|[\"']Review[\"']", t):
            findings.append(F("L-06", "P0", "legal", "Self-serving review markup on Organization/LocalBusiness", "Remove the review/rating from your own Organization/LocalBusiness markup; Google treats it as self-serving and fake ratings breach FTC/CMA rules.", file=rel))

    # ---------- technical / SEO ----------
    is_site = bool(info["deps"]) or any(r.endswith(".html") for r, _ in files)
    if is_site:
        if not any_file(root, ["public/favicon.*", "favicon.*", "app/favicon.*", "src/app/favicon.*", "app/icon.*", "src/app/icon.*", "static/favicon.*", "public/icon*"]):
            findings.append(F("T-01", "P2", "technical", "No favicon", "Add favicon.ico/icon.svg, apple-touch-icon and a web manifest."))
        if not any_file(root, ["public/robots.txt", "robots.txt", "app/robots.*", "src/app/robots.*", "static/robots.txt"]):
            findings.append(F("T-05", "P1", "technical", "No robots.txt", "Add robots.txt with a Sitemap: line; decide rules for AI crawlers (GPTBot, ClaudeBot, Google-Extended)."))
        if not any_file(root, ["public/sitemap*.xml", "sitemap*.xml", "app/sitemap.*", "src/app/sitemap.*", "static/sitemap*.xml"]) and not re.search(r"next-sitemap|@astrojs/sitemap|vite-plugin-sitemap|sitemap", json.dumps(info["deps"])):
            findings.append(F("T-05", "P1", "technical", "No sitemap.xml", "Generate a sitemap of indexable pages."))
        if not any_file(root, ["app/not-found.*", "src/app/not-found.*", "pages/404.*", "src/pages/404.*", "public/404.html", "404.html", "src/routes/+error.svelte", "src/pages/NotFound.*", "src/pages/not-found.*"]) and not re.search(r"NotFound|path=[\"']\*[\"']|path:\s*[\"']\*", alltext):
            findings.append(F("T-11", "P2", "technical", "No custom 404 page", "Add a 404 page that returns HTTP 404 and links home."))
        if not re.search(r"rel=[\"']canonical|alternates\s*:\s*\{\s*canonical|canonical", alltext, re.I):
            findings.append(F("T-03", "P1", "technical", "No canonical URLs", "Add <link rel=\"canonical\"> (Next.js: metadata.alternates.canonical) on every indexable page."))
        if not re.search(r"og:image|openGraph|og:title", alltext):
            findings.append(F("T-08", "P2", "technical", "No Open Graph tags", "Add og:title, og:description, og:image, twitter:card for link previews."))
        if ("react" in stack or "vue" in stack) and "next" not in stack and "astro" not in stack and "remix" not in stack and not re.search(r"vite-plugin-ssr|vike|react-snap|prerender|@nuxt", json.dumps(info["deps"])):
            findings.append(F("T-07", "P1", "technical", "Client-only SPA (search engines and link previews see an empty page)", "Prerender public pages (vite-plugin-prerender/react-snap) or move marketing pages to SSR/SSG (Next.js, Astro).", confidence="medium"))
        if ("react" in stack or "next" in stack) and not re.search(r"ErrorBoundary|componentDidCatch|error\.(tsx|jsx|js)|errorElement", alltext + " ".join(r for r, _ in files)):
            findings.append(F("T-15", "P1", "technical", "No error boundary", "Add error.tsx (Next.js) or a React ErrorBoundary so one crash does not blank the page."))
        if not re.search(r"@sentry|sentry_sdk|logrocket|bugsnag|rollbar|datadog|highlight\.run|@axiomhq|newrelic|honeybadger|posthog", json.dumps(info["deps"]) + alltext, re.I):
            findings.append(F("T-16", "P1", "technical", "No error tracking", "Add an error tracker (Sentry free tier) so you hear about crashes before users tell you."))
    if info["package_json"] and not any_file(root, ["package-lock.json", "pnpm-lock.yaml", "yarn.lock", "bun.lockb", "bun.lock"]):
        findings.append(F("T-19", "P1", "technical", "No lockfile", "Commit your lockfile so every install gets the same, verified versions."))
    if not any_file(root, [".github/workflows/*.yml", ".github/workflows/*.yaml", ".gitlab-ci.yml", "vercel.json"]) and info["package_json"]:
        findings.append(F("T-20", "P2", "technical", "No CI workflow", "Add a workflow that runs lint, typecheck, tests and vibe-preflight on every PR (preflight.py gate --ci)."))
    test_files = [r for r, _ in files if re.search(r"\.(test|spec)\.(t|j)sx?$|(^|/)tests?/.*\.py$|_test\.py$", r)]
    if is_site and not test_files:
        findings.append(F("T-20", "P1", "technical", "No tests", "Add at least one end-to-end test of the main flow (sign up, core action, pay)."))
    if ("prisma" in stack and not any_file(root, ["prisma/migrations/*"])) or ("drizzle" in stack and not any_file(root, ["drizzle/*", "migrations/*"])):
        findings.append(F("T-21", "P1", "technical", "ORM without committed migrations", "Use migrations (prisma migrate / drizzle-kit generate) instead of db push in production."))
    envs = {}
    for name in [".env", ".env.local", ".env.production", ".env.development"]:
        t = read(root / name)
        m = re.search(r"^(?:DATABASE_URL|SUPABASE_URL|NEXT_PUBLIC_SUPABASE_URL|VITE_SUPABASE_URL)\s*=\s*(\S+)", t, re.M)
        if m:
            envs[name] = m.group(1)
    if len(envs) >= 2 and len(set(envs.values())) == 1:
        findings.append(F("T-21", "P0", "technical", "Development and production use the same database", "Create a separate dev/staging project; an agent or a test run can wipe production otherwise (Replit/SaaStr incident).", evidence=", ".join(envs)))

    # ---------- a11y project level ----------
    if re.search(r"framer-motion|motion/react|gsap|aos|@keyframes|animate-|lottie", alltext) and not re.search(r"prefers-reduced-motion|useReducedMotion|motion-reduce:|reducedMotion", alltext):
        findings.append(F("F-11", "P1", "a11y", "Animations ignore prefers-reduced-motion", "Wrap motion in @media (prefers-reduced-motion: no-preference) or use useReducedMotion / Tailwind motion-safe:."))

    # ---------- design project level ----------
    fonts = set(m.group(1) for m in re.finditer(r"(?:family=|font-family\s*:\s*['\"]?|from ['\"]next/font/google['\"][^\n]*?\{?\s*|fontFamily\s*:\s*\{?[^\n]*?['\"])([A-Z][A-Za-z ]+?)(?:[:'\",&]|\s*\(|\s*\})", alltext))
    fonts = {f.strip() for f in fonts if len(f) < 30}
    if fonts and fonts <= {"Inter", "Roboto", "Arial", "Helvetica", "system-ui", "Open Sans", "Geist", "Geist Mono", "Poppins"}:
        findings.append(F("D-04", "P2", "design", "Only default fonts in use", "Pick a display face with character for headings; keep Inter for body if you like.", evidence=", ".join(sorted(fonts)), confidence="low"))
    em = alltext.count("—")
    words = max(1, len(re.findall(r"\b\w+\b", alltext)))
    copy_files = [t for r, t in src if r.endswith((".tsx", ".jsx", ".html", ".vue", ".svelte", ".astro", ".mdx"))]
    copy_em = sum(t.count("—") for t in copy_files)
    if copy_em >= 8:
        findings.append(F("D-24", "P2", "design", "Em-dash heavy copy (reads as AI text)", "Rewrite with plain sentences; use commas or full stops.", evidence=f"{copy_em} em dashes in UI files", confidence="low"))

    return info, findings
