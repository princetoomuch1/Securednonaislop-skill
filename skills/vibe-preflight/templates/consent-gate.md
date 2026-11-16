# Consent gate patterns

Goal: no analytics, ad pixel, chat widget, video or map embed loads before the visitor opts in (EU/UK ePrivacy Art. 5(3)). Reject must be as easy as Accept.

## Option A: a consent manager

Use one that blocks scripts until consent and logs choices: vanilla-cookieconsent (open source), Klaro (open source), Cookiebot, Usercentrics, CookieYes, iubenda. Configure:

- Categories: necessary (always on), analytics, marketing, functional.
- First layer: "Accept all" and "Reject all" with equal size and colour, plus "Settings".
- No pre-ticked categories. No cookie wall.
- Footer link "Cookie settings" that reopens the dialog.

## Option B: hand-rolled gate (small sites)

```tsx
// ConsentGate.tsx: render children only after the visitor accepted `category`
"use client";
import { useEffect, useState } from "react";
export function useConsent(category: "analytics" | "marketing") {
  const [ok, setOk] = useState(false);
  useEffect(() => {
    try { setOk(JSON.parse(localStorage.getItem("consent") || "{}")[category] === true); } catch {}
    const on = () => { try { setOk(JSON.parse(localStorage.getItem("consent") || "{}")[category] === true); } catch {} };
    window.addEventListener("consent-changed", on);
    return () => window.removeEventListener("consent-changed", on);
  }, [category]);
  return ok;
}
export function saveConsent(c: { analytics: boolean; marketing: boolean }) {
  localStorage.setItem("consent", JSON.stringify({ ...c, ts: Date.now(), v: 1 }));
  window.dispatchEvent(new Event("consent-changed"));
}
// Usage: const analytics = useConsent("analytics"); {analytics && <Script src="https://www.googletagmanager.com/gtag/js?id=G-XXXX" />}
```

## Google Consent Mode v2

If you use Google tags, set defaults to denied before the tag loads and update on choice:

```js
gtag('consent', 'default', { ad_storage: 'denied', ad_user_data: 'denied', ad_personalization: 'denied', analytics_storage: 'denied' });
```

Consent Mode alone still sends cookieless pings; many EU regulators expect no request at all before consent. Prefer not loading the tag.

## Cookieless alternatives

Plausible, Fathom, Umami, Vercel Web Analytics and Simple Analytics do not set cookies; confirm their DPA and whether your regulator still expects notice.
