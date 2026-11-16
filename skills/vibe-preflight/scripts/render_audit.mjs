#!/usr/bin/env node
// vibe-preflight rendered audit. Proves what static scans cannot:
// trackers before consent, WCAG via axe-core, keyboard focus, mobile overflow, headers, SEO meta, links, soft 404.
// Safe by design: it never clicks buttons or submits forms.
//
// Usage: node render_audit.mjs --url http://localhost:3000 [--out ./.preflight] [--pages /,/pricing] [--max-links 40]
// Needs: npm i -D playwright @axe-core/playwright && npx playwright install chromium

import fs from "node:fs";
import path from "node:path";

const args = Object.fromEntries(process.argv.slice(2).reduce((acc, a, i, arr) => {
  if (a.startsWith("--")) acc.push([a.slice(2), arr[i + 1] && !arr[i + 1].startsWith("--") ? arr[i + 1] : true]);
  return acc;
}, []));
if (!args.url) { console.error("Usage: node render_audit.mjs --url <url> [--out dir] [--pages /,/about]"); process.exit(64); }
const OUT = path.resolve(args.out || ".preflight");
const SCREENS = path.join(OUT, "screens");
fs.mkdirSync(SCREENS, { recursive: true });
const base = new URL(args.url);
const pages = (args.pages ? String(args.pages).split(",") : ["/"]).map(p => new URL(p, base).toString());
const MAX_LINKS = Number(args["max-links"] || 40);

let chromium, AxeBuilder;
try {
  ({ chromium } = await import("playwright"));
  ({ default: AxeBuilder } = await import("@axe-core/playwright"));
} catch (e) {
  console.error("Missing deps. Run: npm i -D playwright @axe-core/playwright && npx playwright install chromium");
  fs.writeFileSync(path.join(OUT, "render-findings.json"), JSON.stringify({ meta: { skipped_checks: ["Rendered checks: playwright/@axe-core not installed"] }, findings: [] }, null, 1));
  process.exit(3);
}

const TRACKER_HOSTS = /(google-analytics\.com|googletagmanager\.com|doubleclick\.net|googleadservices\.com|connect\.facebook\.net|facebook\.com\/tr|analytics\.tiktok\.com|static\.hotjar\.com|script\.hotjar\.com|clarity\.ms|snap\.licdn\.com|px\.ads\.linkedin\.com|bat\.bing\.com|cdn\.segment\.com|api\.segment\.io|api\.mixpanel\.com|cdn\.mxpnl\.com|cdn\.amplitude\.com|api2\.amplitude\.com|i\.posthog\.com|app\.posthog\.com|js\.intercomcdn\.com|widget\.intercom\.io|client\.crisp\.chat|embed\.tawk\.to|js\.hs-scripts\.com|js\.hs-analytics\.net|sc-static\.net|ct\.pinterest\.com|static\.ads-twitter\.com|fonts\.googleapis\.com|fonts\.gstatic\.com|youtube\.com\/embed|maps\.googleapis\.com)/i;
const TRACKER_COOKIES = /^(_ga|_ga_.*|_gid|_gat.*|_gcl_.*|_fbp|_fbc|_hj.*|_clck|_clsk|MUID|li_sugr|bcookie|_ttp|ajs_.*|mp_.*|ph_.*|_uetsid|_uetvid|__hs.*|hubspotutk|intercom-.*|_pin_unauth)$/;
const AXE_MAP = {
  "color-contrast": ["F-01", "P1"], "image-alt": ["F-02", "P1"], "button-name": ["F-09", "P1"], "link-name": ["F-02", "P1"],
  "input-image-alt": ["F-02", "P1"], "svg-img-alt": ["F-02", "P2"], "label": ["F-07", "P0"], "select-name": ["F-07", "P1"],
  "html-has-lang": ["F-13", "P1"], "document-title": ["F-13", "P1"], "heading-order": ["F-10", "P2"],
  "page-has-heading-one": ["F-10", "P2"], "region": ["F-10", "P2"], "landmark-one-main": ["F-10", "P2"],
  "bypass": ["F-10", "P2"], "aria-required-attr": ["F-03", "P1"], "aria-valid-attr-value": ["F-03", "P1"],
  "aria-allowed-attr": ["F-03", "P1"], "nested-interactive": ["F-03", "P1"], "target-size": ["F-09", "P1"],
  "meta-viewport": ["F-12", "P1"], "duplicate-id-aria": ["F-03", "P1"], "list": ["F-10", "P2"], "listitem": ["F-10", "P2"],
};
const findings = [];
let renderedTextLen = 0;
const add = (id, severity, category, title, fix, extra = {}) =>
  findings.push({ id, severity, category, title, fix, file: extra.file || "", line: 0, evidence: extra.evidence || "", confidence: extra.confidence || "high", source: "rendered", ...extra });

const browser = await chromium.launch();
try {
  // ---------- 1. Pre-consent capture: fresh profile, no interaction ----------
  {
    const ctx = await browser.newContext({ viewport: { width: 1440, height: 900 } });
    const page = await ctx.newPage();
    const reqs = new Set();
    page.on("request", r => { try { const u = new URL(r.url()); if (TRACKER_HOSTS.test(u.host + u.pathname)) reqs.add(u.host + u.pathname.slice(0, 40)); } catch {} });
    const consoleErrors = [];
    page.on("console", m => { if (m.type() === "error") consoleErrors.push(m.text().slice(0, 200)); });
    page.on("pageerror", e => consoleErrors.push(String(e).slice(0, 200)));
    const resp = await page.goto(pages[0], { waitUntil: "networkidle", timeout: 45000 }).catch(e => null);
    await page.waitForTimeout(4000);
    const cookies = (await ctx.cookies()).map(c => c.name);
    const trackingCookies = cookies.filter(n => TRACKER_COOKIES.test(n));
    const ls = await page.evaluate(() => Object.keys(localStorage)).catch(() => []);
    const fontsOnly = [...reqs].every(r => /fonts\.(googleapis|gstatic)/.test(r));
    if (trackingCookies.length || (reqs.size && !fontsOnly)) {
      add("L-07", "P0", "legal", "Trackers load before any consent (EU/UK breach)",
        "Block analytics/ads/embeds until the visitor opts in; equal Accept/Reject buttons; no pre-ticked boxes.",
        { evidence: `requests: ${[...reqs].filter(r => !/fonts\./.test(r)).slice(0, 8).join(", ")} | cookies: ${trackingCookies.join(", ")}` });
    }
    if ([...reqs].some(r => /fonts\.(googleapis|gstatic)/.test(r)))
      add("L-10", "P1", "legal", "Google Fonts requested from Google on page load", "Self-host fonts (EU: IP transfer without consent).", { evidence: "fonts.googleapis.com / fonts.gstatic.com" });
    // Consent banner presence + reject button
    const banner = await page.evaluate(() => {
      const txt = (document.body?.innerText || "").toLowerCase();
      const hasBanner = /cookie|consent|privacy preferences/.test(txt);
      const btns = [...document.querySelectorAll("button, a, [role=button]")].map(b => (b.innerText || b.getAttribute("aria-label") || "").trim().toLowerCase());
      const accept = btns.some(t => /^(accept|accept all|allow all|agree|i agree|ok|got it)/.test(t));
      const reject = btns.some(t => /(reject|decline|deny|refuse|necessary only|only necessary|essential only)/.test(t));
      return { hasBanner, accept, reject };
    }).catch(() => ({}));
    if (banner.accept && !banner.reject)
      add("L-08", "P0", "legal", "Cookie banner has Accept but no equal Reject", "Add a Reject button with the same size and prominence on the first layer.", { evidence: JSON.stringify(banner) });
    if (resp) {
      const h = resp.headers();
      const missing = ["content-security-policy", "strict-transport-security", "x-content-type-options", "referrer-policy"].filter(k => !h[k]);
      if (!h["content-security-policy"] && !/frame-ancestors/.test(h["content-security-policy"] || "") && !h["x-frame-options"]) missing.push("frame-ancestors/x-frame-options");
      if (missing.length && base.protocol === "https:")
        add("S-19", "P1", "security", "Missing security headers", "Set CSP, HSTS, X-Content-Type-Options, Referrer-Policy, frame-ancestors (templates/security-headers.md).", { evidence: missing.join(", ") });
      if (h["access-control-allow-origin"] === "*" && h["access-control-allow-credentials"] === "true")
        add("S-21", "P0", "security", "CORS * with credentials", "Allowlist origins.", { evidence: "ACAO: * + credentials" });
      if (h["x-powered-by"]) add("S-22", "P2", "security", "X-Powered-By header leaks stack", "Remove the header.", { evidence: h["x-powered-by"] });
    }
    if (consoleErrors.length) add("T-14", "P1", "technical", "Console errors on load", "Fix runtime errors; they often mean broken features.", { evidence: consoleErrors.slice(0, 5).join(" | ") });
    await ctx.close();
  }

  // ---------- 2. Per page: axe, meta, keyboard, overflow, screenshots ----------
  for (const url of pages) {
    const slug = (new URL(url).pathname.replace(/\W+/g, "_") || "home").replace(/^_|_$/g, "") || "home";
    for (const vp of [{ name: "desktop", width: 1440, height: 900 }, { name: "mobile", width: 375, height: 812 }]) {
      const ctx = await browser.newContext({ viewport: { width: vp.width, height: vp.height }, reducedMotion: "reduce" });
      const page = await ctx.newPage();
      await page.goto(url, { waitUntil: "networkidle", timeout: 45000 }).catch(() => null);
      await page.waitForTimeout(800);
      await page.screenshot({ path: path.join(SCREENS, `${slug}-${vp.name}.png`), fullPage: true }).catch(() => {});
      if (vp.name === "desktop") {
        // axe-core WCAG 2.2 AA
        try {
          const res = await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa", "wcag22aa"]).analyze();
          for (const v of res.violations) {
            const [id, sev] = AXE_MAP[v.id] || ["F-00", v.impact === "critical" ? "P1" : "P2"];
            add(id, sev, "a11y", `axe: ${v.help}`, v.helpUrl, { evidence: `${v.nodes.length} node(s), e.g. ${v.nodes[0]?.target?.join(" ")}`.slice(0, 220), file: new URL(url).pathname, axe: v.id });
          }
        } catch (e) { add("F-00", "P2", "a11y", "axe-core failed to run", String(e).slice(0, 160), { skipped: true }); }
        // SEO / meta
        const meta = await page.evaluate(() => ({
          title: document.title, lang: document.documentElement.lang,
          desc: document.querySelector('meta[name="description"]')?.content || "",
          canonical: document.querySelector('link[rel="canonical"]')?.href || "",
          robots: document.querySelector('meta[name="robots"]')?.content || "",
          og: !!document.querySelector('meta[property="og:image"]'),
          viewport: !!document.querySelector('meta[name="viewport"]'),
          h1: document.querySelectorAll("h1").length,
          icon: !!document.querySelector('link[rel~="icon"]'),
          jsonld: [...document.querySelectorAll('script[type="application/ld+json"]')].map(s => s.textContent.slice(0, 2000)),
          bodyText: (document.body?.innerText || "").slice(0, 20000),
        })).catch(() => ({}));
        const p = new URL(url).pathname;
        if (!meta.title || /^(vite \+|react app|create next app|lovable|my app|document)/i.test(meta.title)) add("T-02", "P1", "technical", "Missing or template <title>", "Write a specific title.", { evidence: meta.title || "(empty)", file: p });
        if (!meta.desc) add("T-02", "P1", "technical", "No meta description", "Add a 120-160 character description.", { file: p });
        if (!meta.canonical) add("T-03", "P1", "technical", "No canonical link", "Add an absolute canonical URL.", { file: p });
        if (/noindex/i.test(meta.robots)) add("T-06", "P0", "technical", "Page is noindex", "Remove noindex for production.", { file: p, evidence: meta.robots });
        if (meta.canonical && /localhost|127\.0\.0\.1|vercel\.app|netlify\.app|lovable\.app/.test(meta.canonical) && !/localhost|127\.0\.0\.1/.test(base.host)) add("T-03", "P1", "technical", "Canonical points to a preview/dev host", "Point canonical at the production domain.", { file: p, evidence: meta.canonical });
        if (!meta.og) add("T-08", "P2", "technical", "No og:image", "Add Open Graph tags.", { file: p });
        if (!meta.icon) add("T-01", "P2", "technical", "No favicon link", "Add icons.", { file: p });
        if (meta.h1 !== 1) add("F-10", "P2", "a11y", `Page has ${meta.h1} <h1> elements`, "Use exactly one h1.", { file: p });
        for (const j of meta.jsonld || []) {
          if (/AggregateRating|"Review"/.test(j)) add("L-06", /"(Organization|LocalBusiness)"/.test(j) ? "P0" : "P1", "legal", "Review/rating structured data on page", "Keep only genuine, visible, non-self-serving reviews.", { file: p, evidence: j.slice(0, 160) });
        }
        const bt = meta.bodyText || "";
        const claim = bt.match(/\b\d{1,3}(?:[,.]\d{3})*\s*[kKmM]?\+?\s*(?:happy |active )?(?:users|customers|teams|companies|developers|downloads)\b/);
        if (claim) add("L-05", "P1", "legal", "Rendered page makes a usage-number claim", "Keep only numbers you can prove.", { file: p, evidence: claim[0], confidence: "medium" });
        if (/lorem ipsum|your company|john doe|acme inc/i.test(bt)) add("U-18", "P1", "ux", "Placeholder text visible on page", "Replace with real content.", { file: p });
        // Keyboard walk
        const kb = [];
        await page.evaluate(() => { document.activeElement?.blur?.(); window.scrollTo(0, 0); }).catch(() => {});
        renderedTextLen = Math.max(renderedTextLen, (meta.bodyText || "").length);
        for (let i = 0; i < 40; i++) {
          await page.keyboard.press("Tab");
          const st = await page.evaluate(() => {
            const el = document.activeElement;
            if (!el || el === document.body) return null;
            const cs = getComputedStyle(el);
            const r = el.getBoundingClientRect();
            const visible = (cs.outlineStyle !== "none" && parseFloat(cs.outlineWidth) > 0) || (cs.boxShadow && cs.boxShadow !== "none");
            let covered = false;
            const cx = r.left + r.width / 2, cy = r.top + r.height / 2;
            if (cx >= 0 && cy >= 0 && cx < innerWidth && cy < innerHeight) {
              const top = document.elementFromPoint(cx, cy);
              if (top && !el.contains(top) && !top.contains(el)) {
                for (let n = top; n && n !== document.body; n = n.parentElement) {
                  if (["fixed", "sticky"].includes(getComputedStyle(n).position)) { covered = true; break; }
                }
              }
            }
            const inline = cs.display === "inline" && el.tagName === "A";
            const key = el.tagName + "|" + (el.id || "") + "|" + Math.round(r.left + scrollX) + "," + Math.round(r.top + scrollY);
            return { key, tag: el.tagName.toLowerCase(), text: (el.innerText || el.getAttribute("aria-label") || "").trim().slice(0, 40), visible, covered, inline, w: r.width, h: r.height };
          }).catch(() => null);
          if (st && !kb.some(k => k.key === st.key)) kb.push(st);
          else if (st && kb.length > 2) break; // focus wrapped around
        }
        if (!kb.length) add("F-04", "P0", "a11y", "Nothing on the page is reachable by keyboard", "Use native links/buttons; remove tabindex=-1 from interactive elements.", { file: p });
        const noRing = kb.filter(k => !k.visible);
        if (noRing.length) add("F-05", "P1", "a11y", `${noRing.length} focused element(s) show no visible focus indicator`, "Add a :focus-visible ring (2px, 3:1 contrast).", { file: p, evidence: noRing.slice(0, 5).map(k => `${k.tag}:${k.text}`).join(", ") });
        const covered = kb.filter(k => k.covered);
        if (covered.length) add("F-06", "P1", "a11y", "Focused element hidden behind a sticky/fixed element", "Add scroll-padding-top equal to the sticky header height.", { file: p, evidence: covered.slice(0, 3).map(k => `${k.tag}:${k.text}`).join(", ") });
        const tiny = kb.filter(k => !k.inline && k.w > 0 && (k.w < 24 || k.h < 24));
        if (tiny.length) add("F-09", "P1", "a11y", `${tiny.length} interactive target(s) under 24x24 px`, "Make targets at least 24x24 CSS px (aim 44).", { file: p, evidence: tiny.slice(0, 5).map(k => `${k.tag}:${k.text} ${Math.round(k.w)}x${Math.round(k.h)}`).join(", ") });
        // Zoom 200% approximation: halve viewport width
        await page.setViewportSize({ width: 720, height: 900 });
        await page.evaluate(() => { document.documentElement.style.fontSize = "200%"; });
        const zoomOverflow = await page.evaluate(() => document.documentElement.scrollWidth > innerWidth + 2).catch(() => false);
        if (zoomOverflow) add("F-12", "P1", "a11y", "Horizontal scroll at 200% text size", "Use fluid layouts and rem units; avoid fixed widths.", { file: p, confidence: "medium" });
      } else {
        const of = await page.evaluate(() => {
          const over = document.documentElement.scrollWidth - innerWidth;
          const culprits = [...document.querySelectorAll("body *")].filter(e => e.getBoundingClientRect().right > innerWidth + 2).slice(0, 5).map(e => e.tagName.toLowerCase() + (e.className && typeof e.className === "string" ? "." + e.className.split(" ")[0] : ""));
          return { over, culprits };
        }).catch(() => ({ over: 0 }));
        if (of.over > 2) add("U-12", "P1", "ux", `Horizontal overflow on mobile (${of.over}px at 375px)`, "Find the wide element; use max-w-full, min-w-0, flex-wrap.", { file: new URL(url).pathname, evidence: (of.culprits || []).join(", ") });
        await page.setViewportSize({ width: 320, height: 640 });
        const of320 = await page.evaluate(() => document.documentElement.scrollWidth - innerWidth).catch(() => 0);
        if (of320 > 2 && of.over <= 2) add("U-12", "P2", "ux", `Horizontal overflow at 320px (${of320}px)`, "Check small phones and 400% zoom (WCAG 1.4.10).", { file: new URL(url).pathname });
      }
      await ctx.close();
    }
  }

  // ---------- 3. Links, soft 404, no-JS render ----------
  {
    const ctx = await browser.newContext();
    const page = await ctx.newPage();
    await page.goto(pages[0], { waitUntil: "domcontentloaded", timeout: 45000 }).catch(() => null);
    const links = await page.evaluate(() => [...new Set([...document.querySelectorAll("a[href]")].map(a => a.href))]).catch(() => []);
    const internal = links.filter(l => { try { const u = new URL(l); return u.origin === location.origin || u.host === location.host; } catch { return false; } });
    const sameOrigin = links.filter(l => { try { return new URL(l).origin === base.origin; } catch { return false; } }).slice(0, MAX_LINKS);
    const broken = [];
    for (const l of sameOrigin) {
      const r = await ctx.request.get(l, { maxRedirects: 5, timeout: 15000 }).catch(() => null);
      if (!r || r.status() >= 400) broken.push(`${new URL(l).pathname} (${r ? r.status() : "error"})`);
    }
    if (broken.length) add("T-10", "P1", "technical", `${broken.length} broken internal link(s)`, "Fix or remove the links; add a real 404 page.", { evidence: broken.slice(0, 8).join(", ") });
    const deadHash = links.filter(l => /#$/.test(l)).length;
    if (deadHash) add("U-01", "P1", "ux", `${deadHash} link(s) to "#"`, "Wire the action or remove the link.");
    const nf = await ctx.request.get(new URL("/__preflight_should_404__", base).toString(), { timeout: 15000 }).catch(() => null);
    if (nf && nf.status() === 200) add("T-11", "P1", "technical", "Unknown URLs return 200 (soft 404)", "Return HTTP 404 for unknown routes (host rewrite + not-found page).");
    const raw = await ctx.request.get(pages[0], { timeout: 15000 }).catch(() => null);
    if (raw) {
      const html = await raw.text();
      const text = html.replace(/<script[\s\S]*?<\/script>/gi, "").replace(/<style[\s\S]*?<\/style>/gi, "").replace(/<[^>]+>/g, " ").replace(/\s+/g, " ").trim();
      if (text.length < 200 && renderedTextLen > Math.max(400, text.length * 3)) add("T-07", "P1", "technical", "Page HTML is empty without JavaScript", "Server-render or prerender public pages so crawlers and link previews see content.", { evidence: `${text.length} chars in raw HTML vs ${renderedTextLen} after JS` });
    }
    await ctx.close();
  }
} finally {
  await browser.close();
}

fs.writeFileSync(path.join(OUT, "render-findings.json"), JSON.stringify({ meta: { rendered_url: args.url, pages }, findings }, null, 1));
const p0 = findings.filter(f => f.severity === "P0").length;
console.log(`Rendered audit: ${findings.length} findings (${p0} P0). Screens in ${SCREENS}. Run: python3 preflight.py report ${OUT}`);
process.exit(p0 ? 1 : 0);
