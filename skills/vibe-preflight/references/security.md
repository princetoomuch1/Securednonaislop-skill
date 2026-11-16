# Security rules (S-)

Why this matters: Veracode found 45% of AI-generated code samples introduced OWASP Top 10 flaws across 100+ models, with no improvement in newer models (2025). Real AI-built apps fail mostly on **access control**, not classic injection: an arXiv study of 200 deployed vibe-coded apps found 91% vulnerable, broken access control the top class (Deng, Fan, Meng, 2026). Tenzai's Dec 2025 test of five agents found SSRF from every agent and CSRF/security headers in none of 15 apps. GitGuardian measured AI-assisted commits leaking secrets at about 2x the baseline (3.2% vs 1.5%).

Order of work: secrets (S-01, S-02, S-04) → database rules (S-03, S-05, S-06, S-07) → server auth (S-08..S-13) → injection (S-14, S-16, S-17) → hardening (S-15, S-18..S-23) → supply chain (S-24) → AI features (S-25).

## s-01
**Secrets in code or bundle.** Detect: provider key regexes in source and in `dist/ build/ out/ .next/static`; public env prefixes on secret names. Fix: move the call server-side, rotate the key (removing it is not enough; it is in history and caches), add secret scanning (gitleaks) in CI. Public by design: Supabase anon key (with RLS), Firebase web config, Stripe publishable key, Maps key restricted by referrer.

## s-02
**Env files committed.** Detect: `git ls-files` lists `.env`, `.env.local`, `.env.production`. Fix: `git rm --cached .env*`, add `.env*` and `!.env.example` to `.gitignore`, rotate everything in the file, purge history with `git filter-repo --path .env --invert-paths` if the repo was ever public.

## s-03
**Supabase RLS missing or open.** The CVE-2025-48757 pattern: 170 of 1,645 Lovable showcase apps (10.3%) had tables readable/writable with the public anon key. Detect statically: `create table` without `enable row level security`; `using (true)` on user tables; `disable row level security`. Detect live (read-only): `preflight.py probe-supabase` reads the REST OpenAPI and requests `select=*&limit=1` per table. Fix: `templates/rls-policies.sql`; test with two real accounts that user A cannot read user B's rows. Remember `insert` needs `with check`, `update` needs both `using` and `with check`. Views bypass RLS unless created with `security_invoker = on`.

## s-04
**service_role in the browser.** It bypasses RLS completely. Detect: decode every `eyJ…` JWT in code/bundle; `"role":"service_role"`; `SERVICE_ROLE` referenced from a `"use client"` file or a Vite `src/` file. Fix: rotate in Supabase settings; use it only in server routes / edge functions.

## s-05
**Firebase open rules.** Tea app (Jul 2025) leaked 72k images and 1.1M messages from an open legacy bucket. Detect: `allow read, write: if true`, test-mode `request.time < timestamp.date(...)`, RTDB `".read": true`. Fix:
```
rules_version = '2';
service cloud.firestore { match /databases/{db}/documents {
  match /users/{uid}/{doc=**} { allow read, write: if request.auth != null && request.auth.uid == uid; }
}}
```
Test with the Firebase emulator. Delete unused legacy buckets.

## s-06
**Public storage buckets.** Fine for marketing images, not for uploads, IDs, invoices. Make private; serve with signed URLs that expire.

## s-07
**Functions callable by anon.** `SECURITY DEFINER` runs as the owner and skips RLS. Check `auth.uid()` inside, `set search_path = ''`, `revoke execute … from anon, public`.

## s-08
**API route without server auth.** Detect: route files exporting POST/PUT/PATCH/DELETE or reading the DB with no session/JWT call and no covering middleware. Base44 (Jul 2025) exposed undocumented register/verify endpoints that bypassed SSO. Fix: an auth helper at the top of every handler; deny by default; list every route (including debug/internal) and confirm each.

## s-09
**Client-only guards.** `if (!user) router.push('/login')` hides the page but not the data. Enforce in middleware, server components, and DB policies.

## s-10
**IDOR / BOLA.** Detect: handlers using `body.userId`, `params.id` to fetch/update without an ownership condition. Fix: `where: { id, ownerId: session.user.id }` or RLS.

## s-11
**Mass assignment.** `update(req.body)` lets the client set `role`, `isAdmin`, `credits`, `plan`. Fix: Zod `pick` of allowed fields.

## s-12
**Client-trusted prices and quantities.** Tenzai: 4 of 5 agents allowed negative-quantity orders. Fix: look up prices server-side (Stripe Price IDs); validate `quantity >= 1`, max limits, currency.

## s-13
**Placeholder security.** Distinctive to vibe-coded apps: stubbed `return true` checks, `TODO: add auth`, hardcoded OTP/password compares. Fix: implement or delete; fail closed.

## s-14
**SSRF.** Server fetches a URL the user controls (image import, link preview, webhook tester). Fix: allowlist hosts; resolve DNS and block private, loopback, link-local and metadata IPs (169.254.169.254); no redirects; timeouts and size limits.

## s-15
**CSRF.** Cookie-authenticated state changes need SameSite=Lax/Strict plus an Origin check, or CSRF tokens. Next.js server actions check Origin; custom route handlers do not.

## s-16
**XSS sinks.** `dangerouslySetInnerHTML`, `v-html`, `{@html}`, `set:html`, `innerHTML`, `document.write`, markdown rendered as HTML. Veracode: XSS defence failed in 86% of relevant samples. Fix: DOMPurify, CSP. JSON-LD via `dangerouslySetInnerHTML` is fine when the data is yours; mark with `preflight-ignore S-16: static JSON-LD`.

## s-17
**SQL/NoSQL injection.** Template-string SQL, `$queryRawUnsafe`, Python f-string SQL, Mongo `$where`. Fix: parameters, ORM, schema validation.

## s-18
**No rate limits / spend caps.** Login brute force, signup spam, and "denial of wallet" on AI endpoints. Fix: `@upstash/ratelimit`, `express-rate-limit`, Cloudflare Turnstile on public forms, provider budget alerts, per-user quotas.

## s-19
**Security headers.** Tenzai: 0 of 15 apps set any. Fix: `templates/security-headers.md`.

## s-20
**Session handling.** Tokens in localStorage are readable by any XSS. Use httpOnly Secure SameSite cookies; verify JWT signature, algorithm and expiry; never accept `alg: none`.

## s-21
**CORS.** `*` with credentials, or reflecting any origin. Allowlist.

## s-22
**Debug surface.** Public source maps, `x-powered-by`, Swagger/GraphQL introspection in prod, verbose stack traces, `DEBUG=True`.

## s-23
**Webhooks.** Verify signatures (`stripe.webhooks.constructEvent(rawBody, sig, secret)`), use the raw body, return 2xx fast, store event ids for idempotency.

## s-24
**Supply chain.** About 1 in 5 AI-suggested packages do not exist; 43% of hallucinated names repeat on every run, so attackers can pre-register them ("slopsquatting"). Snyk's ToxicSkills audit found 76 confirmed malicious payloads among 3,984 agent skills. Detect: registry 404, age < 60 days, < 200 weekly downloads, no repo, one-typo-from-popular names, install scripts. Fix: remove, use the real package, commit lockfiles, `npm ci --ignore-scripts` in CI, vet agent skills and MCP servers before installing.

## s-25
**AI features.** Model keys in the browser, user text concatenated into system prompts, tools with broad permissions, no token caps, PII sent to providers without notice. Fix: server proxy with auth + rate limit + `max_tokens`; separate system and user content; least-privilege tools; disclose AI processing in the privacy policy.
