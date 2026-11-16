# Technical, SEO, performance and ops rules (T-)

Core Web Vitals "good" thresholds (Google, unchanged in 2026): LCP ≤ 2.5 s, INP ≤ 200 ms, CLS ≤ 0.1 at the 75th percentile of real users. Lighthouse targets: Performance ≥ 90, Accessibility ≥ 95, SEO ≥ 95. Budgets: initial JS ≤ 200 KB gzipped on marketing pages.

| Rule | Issue | Fix |
| --- | --- | --- |
| t-01 | No favicon / touch icon / manifest | Add icon set |
| t-02 | Template title ("Vite + React", "Create Next App", "Lovable App"), missing description | Specific title + 120-160 char description per page |
| t-03 | No canonical, or canonical to preview host | Absolute canonical on production domain |
| t-04 | No `lang`, viewport, charset | Add |
| t-05 | No robots.txt / sitemap.xml | Generate; declare AI crawler policy |
| t-06 | `noindex` on production | Remove (P0 if on live pages) |
| t-07 | Client-only SPA: empty HTML without JS | SSR/SSG/prerender public pages |
| t-08 | No Open Graph image | og:title, og:description, og:image, twitter:card |
| t-09 | Invalid or fabricated JSON-LD | Validate (Rich Results Test); see L-06 |
| t-10 | Broken internal links | Fix; crawl in CI (lychee) |
| t-11 | Soft 404 / no 404 page | Return HTTP 404 with a helpful page |
| t-12 | localhost/staging URLs in code | Env-based base URL |
| t-13 | Mixed content | https everywhere |
| t-14 | Swallowed errors, console errors | Log to tracker; user-facing message |
| t-15 | No error boundary | `error.tsx` / ErrorBoundary |
| t-16 | No error tracking | Sentry or similar |
| t-17 | No uptime check | `/health` + monitor |
| t-18 | No `.env.example` / README setup | Add |
| t-19 | No lockfile | Commit it |
| t-20 | No tests / CI | One e2e of the main flow; lint, typecheck, preflight in CI |
| t-21 | Shared dev/prod DB; no migrations | Separate projects; migrations. Replit's agent deleted a production DB during a code freeze (Jul 2025) |
| t-22 | No backups | Enable PITR/backups; test a restore |
| t-23 | Leftovers: console.log, TODO, unused deps | Clean (`knip`, `depcheck`) |
| t-24 | `any` sprawl | Types |
| t-25 | LCP image lazy-loaded, huge, not WebP/AVIF | `priority`/`fetchpriority="high"`, modern formats |
| t-26 | Images without dimensions (CLS) | width/height or aspect-ratio |
| t-27 | Heavy JS / animation libs on static pages | Code split, drop libraries |
| t-28 | Too many third-party scripts | Defer, facade, remove |
| t-29 | Unbounded lists, N+1 queries | Pagination, batching |
| t-30 | No caching/compression | Immutable cache headers, Brotli |
| t-31 | Email without SPF/DKIM/DMARC | DNS records |
| t-32 | Preview/staging URLs public and indexable | Protect; `noindex`. RedAccess found ~380k public assets on vibe platforms, ~5k leaking sensitive data (May 2026) |
| t-33 | Scaled thin AI pages | Merge or add real value (Google scaled-content-abuse policy) |
| t-34 | No About / author / contact | Real identity (E-E-A-T) |
| t-35 | `target=_blank` without `rel=noopener` | Add rel |
