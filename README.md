# vibe-preflight

**Ship AI-built apps without the AI-built mistakes.**

An agent skill + CLI + GitHub Action that finds what Lovable, Bolt, v0, Cursor, Replit and Claude Code usually miss before launch: open databases, leaked keys, routes with no auth, fake testimonials, trackers firing before consent, hallucinated npm packages, accessibility failures, SEO gaps and the generic "AI slop" look. It ranks every finding (P0 blocks launch), fixes the safe ones, writes guardrails so the next build is right, and can block a production deploy while P0s are open.

Works with Claude Code, Codex, Cursor, Gemini CLI, Copilot, Windsurf and any agent that reads `SKILL.md`. The scanner is Python standard library only: no install, no API key, nothing leaves your machine.

```text
$ python3 preflight.py scan .
Verdict: BLOCK  P0=23 P1=37 P2=17
  P0 S-01 Stripe live secret key in code                  src/lib/pay.ts:1
  P0 S-03 Table 'profiles' created without enabling RLS   supabase/migrations/001_init.sql:1
  P0 S-04 Supabase service_role key in code               src/lib/supabase.ts:3
  P0 S-12 Price or amount taken from the client           src/app/api/orders/route.ts:7
  P0 S-23 Stripe webhook without signature verification   src/app/api/stripe/webhook/route.ts
  P0 L-04 Testimonial uses stock or generated avatar      src/components/Testimonials.tsx:2
  P0 L-07 Trackers present with no consent manager
  ...
Report: .preflight/report.md
```

## Why this exists

AI coding tools build the happy path a demo needs. Launches fail on what nobody asked for.

| Evidence | Source |
| --- | --- |
| 45% of AI-generated code samples introduced OWASP Top 10 flaws across 100+ models; no improvement in newer models | [Veracode 2025](https://www.veracode.com/genai-code-security-report) |
| 170 of 1,645 Lovable showcase apps (10.3%) had databases readable/writable with the public key (CVE-2025-48757) | [SentinelOne CVE entry](https://www.sentinelone.com/vulnerability-database/cve-2025-48757/) |
| 5 agents x 3 identical apps: SSRF from every agent; 0 of 15 apps had CSRF protection or security headers; 4 of 5 allowed negative-quantity checkout | [Tenzai via InfoWorld](https://www.infoworld.com/article/4116937/output-from-vibe-coding-tools-prone-to-critical-security-flaws-study-finds-2.html) |
| AI-assisted commits leaked secrets at 3.2% vs a 1.5% baseline | [GitGuardian 2026](https://blog.gitguardian.com/the-state-of-secrets-sprawl-2026/) |
| ~1 in 5 AI-suggested packages do not exist; attackers register the names ("slopsquatting") | [Cloud Security Alliance](https://labs.cloudsecurityalliance.org/research/csa-research-note-slopsquatting-ai-supply-chain-20260419-csa/) |
| 380,000 public assets on vibe platforms, ~5,000 leaking sensitive data | [Axios, May 2026](https://axios.com/2026/05/07/loveable-replit-vibe-coding-privacy) |
| 95.9% of top home pages fail WCAG; low contrast on 83.9% | WebAIM Million 2026 |
| Fake reviews: FTC up to $51,744 per violation; UK CMA up to 10% of global turnover | FTC 16 CFR 465, UK DMCC Act |

## What it does that AI builders do not

| Gap | Lovable / Bolt / v0 / Cursor | vibe-preflight |
| --- | --- | --- |
| Supabase RLS and Firebase rules | Sometimes warns in-app | Checks migrations, decodes JWTs, probes tables read-only with the anon key |
| Secrets in the shipped bundle | Rarely | Scans source **and** `dist/`, `.next/static`, git-tracked `.env` |
| Routes with no server auth, IDOR, client-set prices | No | Heuristics + a judgment rubric for business logic |
| Hallucinated / typosquatted packages | No | Live npm + PyPI lookups: 404, age, downloads, install scripts |
| Fake testimonials, invented user counts, review JSON-LD | Generates them | Flags them as legal risk (FTC, CMA, Google) |
| Trackers before cookie consent | No | Headless browser records requests and cookies before any click |
| WCAG 2.2 | No | axe-core + keyboard walk + 320px + 200% zoom |
| AI-slop design tells | Produces them | 27 tells, scored from code and screenshots |
| Guardrails for the next build | No | Writes rules into CLAUDE.md, AGENTS.md, Cursor, Copilot, Windsurf |
| Block a bad deploy | No | Claude Code hook + GitHub Action with SARIF |

## Install

**Any agent (skills CLI)**
```bash
npx skills add princetoomuch1/Securednonaislop-skill
```

**Claude Code plugin**
```text
/plugin marketplace add princetoomuch1/Securednonaislop-skill
/plugin install vibe-preflight@vibe-preflight
```

**Manual**
```bash
git clone https://github.com/princetoomuch1/Securednonaislop-skill
cp -r Securednonaislop-skill/skills/vibe-preflight ~/.claude/skills/        # Claude Code
cp -r Securednonaislop-skill/skills/vibe-preflight .agents/skills/          # Codex, Gemini CLI, others
```

**Lovable / Bolt / v0** do not read repo skills. Paste [`templates/guardrails.md`](skills/vibe-preflight/templates/guardrails.md) into the project's Knowledge or custom instructions, then run the audit on the exported repo.

## Use

Ask your agent in plain words:

- "Is this ready to ship?" → full audit and verdict
- "Fix the safe ones" → alt text, labels, headers, meta, favicon, fonts, `.env.example`; then re-scan
- "Set up guardrails" → rules into every agent file before you build
- "Block bad deploys" → deploy hook + CI

Or run it yourself:

```bash
S=~/.claude/skills/vibe-preflight/scripts

python3 $S/preflight.py recon .                     # what stack is this?
python3 $S/preflight.py scan .                      # static audit -> .preflight/report.md, .sarif
python3 $S/preflight.py probe-supabase --url https://xyz.supabase.co --anon-key <anon>   # read-only
cd $S && npm run setup && node render_audit.mjs --url http://localhost:3000 --out <project>/.preflight
python3 $S/preflight.py report <project>/.preflight # merge everything
python3 $S/preflight.py guard .                     # write guardrails
python3 $S/preflight.py gate . --hook --ci          # deploy hook + GitHub Action
```

Exit codes: `0` ship, `1` P0 found, `2` P1 only. Accept a known risk with a comment: `// preflight-ignore S-16: sanitized above`.

## GitHub Action

```yaml
- uses: actions/checkout@v4
- uses: princetoomuch1/Securednonaislop-skill@v1
  with:
    jurisdiction: eu,uk,us
    fail-on: P0
- uses: github/codeql-action/upload-sarif@v3
  if: always()
  with: { sarif_file: .preflight/results.sarif }
```

Findings appear in the Security tab and the job summary. `preflight.py gate --ci` writes a full workflow that also comments on PRs.

## Rule families

| Prefix | Area | Examples |
| --- | --- | --- |
| S- | Security | Secrets, service_role, RLS, Firebase rules, public buckets, auth gaps, IDOR, mass assignment, client prices, stub auth, SSRF, XSS, SQLi, rate limits, headers, webhooks, slopsquatting, LLM keys in browser |
| L- | Legal & privacy | Privacy/Terms, template legal text, fake testimonials, invented counts, review markup, trackers before consent, Reject button, Google Fonts, compliance claims |
| U- | UX & logic | Dead controls, loading/error/empty states, auth flow gaps, deep links, mobile overflow, scroll-jacking, placeholders, fake urgency, dark patterns |
| F- | Accessibility | Contrast, alt, div buttons, keyboard, focus, sticky header covering focus, labels, target size, landmarks, reduced motion, zoom |
| T- | Technical & SEO | Titles, canonical, robots, sitemap, noindex, client-only SPA, 404, error boundary, error tracking, lockfile, tests, shared dev/prod DB |
| D- | AI-slop design | Indigo gradients, gradient text, side-stripe cards, default fonts, emoji icons, glass, blobs, bounce, buzzwords, generic CTAs |

Full rule text with fixes: [`skills/vibe-preflight/references/`](skills/vibe-preflight/references).

## Safety

- Read-only by default. The Supabase probe uses only the public anon key and `GET`. The browser audit never clicks buttons or submits forms.
- Secrets are masked in every output (`sk_l…(107)`).
- Audited content is treated as data; prompt injection found in a repo or page is reported, not followed.
- Legal findings are engineering guidance, not legal advice.

## Tests

```bash
python3 tests/test_bad_app.py
```

Scans `examples/bad-app` (a deliberately broken Next.js + Supabase app) and requires 42 planted rule hits, masked secrets, valid SARIF, an idempotent guard/gate and a blocking deploy hook. Secrets are injected at test time so the repo contains none.

## Standing on shoulders

Ideas borrowed with thanks: [Impeccable](https://github.com/pbakaus/impeccable) (deterministic slop detection, exit codes), [Taste Skill](https://github.com/Leonxlnx/taste-skill) (anti-slop bans, multi-agent install), [web-quality-skills](https://github.com/addyosmani/web-quality-skills) (Lighthouse budgets), [Trail of Bits skills](https://github.com/trailofbits/skills) (SARIF, audit rigor), [gstack](https://github.com/garrytan/gstack) (report-only vs fix modes, browser QA), ship-gate (deploy interception). Use Impeccable or Taste Skill alongside this for deeper design work.

## License

MIT © 2026 Prince K. Parmar · Draft X
