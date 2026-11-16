## Production guardrails (vibe-preflight)

These rules apply to every change in this project. They exist because AI-built apps routinely ship with open databases, leaked keys and invented content. Follow them even when the user's request does not mention them. If a rule blocks the request, say so and propose the safe version.

### Security
- Every API route, server action and edge function authenticates the caller on the server and checks they own the data. Derive the user id from the session, never from the request body or URL.
- Client-side route guards are UX only, never security.
- Supabase: enable Row Level Security on every table in `public` in the same migration that creates it, with owner-scoped policies (`auth.uid() = user_id`). Never use `USING (true)` on tables with user data. Never send the `service_role` key to the browser.
- Firebase: never ship test-mode rules (`if true`, `request.time < timestamp.date(...)`). Require `request.auth.uid` matching the document owner.
- Secrets live only in server env vars. Never put a secret behind `NEXT_PUBLIC_`, `VITE_`, `REACT_APP_`, `PUBLIC_` or `EXPO_PUBLIC_`. Keep `.env*` in `.gitignore` and maintain `.env.example`.
- Validate every input with a schema (Zod, Pydantic) at the boundary. Allowlist writable fields; never pass `req.body` straight to an update.
- Prices, totals, quantities, roles and plan limits are computed on the server. Reject quantity < 1 and negative amounts.
- Parameterised SQL only. No string-built queries. No `dangerouslySetInnerHTML`/`v-html`/`innerHTML` without DOMPurify.
- Server code that fetches a URL supplied by a user must allowlist hosts and block private IP ranges.
- Verify webhook signatures (Stripe `constructEvent`) and make handlers idempotent.
- Rate-limit login, signup, password reset, contact forms and every AI endpoint. Set spend caps on paid APIs.
- Call LLM APIs only from the server. Never `dangerouslyAllowBrowser`.
- Add security headers: CSP, HSTS, X-Content-Type-Options, Referrer-Policy, frame-ancestors.
- No stub security: never write `return true` in an auth/permission check or leave `TODO` on auth. If unsure, fail closed.
- Before adding a dependency, confirm it exists on the registry, is established and is the package you mean. Never invent package names.
- Never run destructive commands (drop, delete, reset, force push) against production. Keep separate dev and prod databases.

### Content and legal
- Never invent testimonials, customer names, user counts, ratings, logos, press mentions, awards or case studies. Use a clearly marked placeholder `[NEEDS REAL CONTENT: testimonial]` and tell the user.
- Never add `Review` or `AggregateRating` structured data unless the reviews are real and shown on the page, and never on your own Organization/LocalBusiness.
- No fake urgency: no random "people viewing" counters, no countdown timers that reset, no invented stock levels.
- Opt-in checkboxes are unchecked by default. No confirm-shaming copy. Show the full price including fees up front.
- Load analytics, ad pixels, chat widgets, video and map embeds only after cookie consent. Self-host fonts.
- Every site that collects any personal data links a Privacy Policy in the footer and at each form; accounts and payments also need Terms. Never fill legal pages with template placeholders.
- Do not claim "GDPR compliant", "HIPAA compliant", "bank-level security" or "#1" without proof.

### Accessibility (WCAG 2.2 AA)
- Use native `<button>`, `<a>`, `<label>`, `<dialog>`. No `onClick` on `div`/`span`.
- Every image has `alt` (empty for decoration). Every input has a visible label and the right `autocomplete`.
- Never remove focus outlines without a visible `:focus-visible` replacement.
- Text contrast at least 4.5:1, UI components 3:1. No grey-400 body text on white.
- Touch targets at least 24x24 px. One `<h1>` per page, logical headings, `<main>`/`<nav>` landmarks, `lang` on `<html>`.
- Respect `prefers-reduced-motion`. No autoplay without a pause control.

### Product states
- Every data view has loading, empty and error states. Every form has inline errors, keeps entered data on error and blocks double submit.
- Destructive actions ask for confirmation or offer undo.
- Every `href` goes somewhere real; every button does something.
- Add an error boundary and an error tracker. Never swallow errors with empty `catch`.

### SEO and production basics
- Real `<title>` and meta description per page, canonical URL, Open Graph image, favicon, `robots.txt`, `sitemap.xml`, custom 404 that returns HTTP 404.
- Server-render or prerender public marketing pages.
- No `localhost` URLs, template titles ("Vite + React", "Create Next App"), lorem ipsum or `console.log` in shipped code.

### Design (avoid the generic AI look)
- Use the project's design tokens. If none exist, ask for brand colours and fonts before building UI.
- Do not default to indigo/violet/purple gradients, gradient text, glassmorphism, blurred blobs, emoji as icons, side-stripe card borders, three identical feature cards under a centered hero, or bounce easing.
- Write specific copy with real numbers. Avoid "empower", "unlock", "seamless", "revolutionize", "elevate", "supercharge".

### Before you say "done"
Run `python3 <vibe-preflight>/scripts/preflight.py scan .` and fix every P0. Report remaining P1s to the user.
