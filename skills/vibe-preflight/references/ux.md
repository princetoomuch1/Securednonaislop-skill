# UX, states and product logic rules (U-)

AI builds the happy path. CodeRabbit's study of 470 PRs found error-handling gaps nearly 2x and logic/correctness issues 75% more common in AI-authored code. Most U-rules need the rendered pass or your judgment; the static scan only finds code-level hints.

## u-01 Dead controls
`href="#"`, `javascript:void(0)`, empty `onClick`. Wire or remove.

## u-02 Loading states
Throttle to Slow 3G (DevTools or Playwright `route` delay). Blank areas or layout jumps without skeletons fail.

## u-03 Error states
Mock 500 and timeouts. White screens, raw stack traces or silent failure fail. Add error boundaries and retry messages.

## u-04 Empty states
New account with zero data shows guidance and a next action.

## u-05 Form data loss
Validation error or refresh must not wipe what the user typed.

## u-06 Validation
Inline, next to the field, in text (not colour only), announced to screen readers (`aria-describedby`, `aria-invalid`).

## u-07 Double submit
Disable on submit; idempotency keys on payments and creates.

## u-08 Destructive actions
Confirm or undo.

## u-09 Auth flow completeness (P0)
Logout, password reset, email verification handling, session expiry, "check your email" state, account deletion.

## u-10 Deep links
Every client route loads directly (host rewrite to `index.html` for SPAs) and returns 404 for unknown paths.

## u-11 Back button and refresh
State that matters lives in the URL.

## u-12 Mobile overflow
No horizontal scroll at 320 and 375 px.

## u-13 Hover-only content
Anything shown on hover must show on focus and tap.

## u-14 Scroll-jacking
No wheel/touch `preventDefault`, no hijacked scroll speed, no long pinned sections.

## u-15 Navigation
Visible labelled nav on desktop; no mystery icons.

## u-16 Current page
`aria-current="page"` plus a visible style.

## u-17 Competing CTAs
One primary action per view.

## u-18 Placeholder content
Lorem ipsum, "Your Company", "John Doe", "Coming soon", sample data.

## u-19 Toasts and modals
Toasts with actions stay at least 5 s or until dismissed; avoid modals for simple information.

## u-20 Infinite scroll
Footer must stay reachable; prefer "Load more".

## u-21 Autoplay
Carousels and video need a pause control (WCAG 2.2.2).

## u-22 Mobile viewport
Use `dvh`/`svh` instead of `100vh`; inputs stay visible above the keyboard; respect safe-area insets.

## u-23 Locale
Dates, numbers, currency via `Intl`.

## u-24 Business logic (P0)
Negative or zero quantities, zero prices, past dates, huge strings, unicode edge cases, coupon stacking, plan-limit bypass. Read the handlers.

## Dark patterns (U-30..U-36)
False urgency (random "people viewing", resetting countdowns), basket sneaking, confirm-shaming, pre-ticked add-ons, drip pricing, subscription traps without a visible cancel path, forced signup, nagging. Banned or actionable under India CCPA guidelines (13 patterns), EU UCPD/DSA, UK DMCC (drip pricing), FTC Act s.5 and the FTC's negative-option rules. Fix by removing them; disclose real stock and real deadlines only.
