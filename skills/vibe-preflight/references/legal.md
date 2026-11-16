# Legal, privacy and trust rules (L-)

Engineering guidance, not legal advice. Say once in every report: "confirm legal items with a lawyer for your jurisdiction."

Why this matters: AI fills testimonial, stats and logo slots with invented content by default, and drops analytics scripts in `<head>` with no consent. Penalties: FTC Consumer Review Rule (16 CFR 465, effective 21 Oct 2024) up to $51,744 per violation, explicitly covering AI-generated fake reviews; UK DMCC Act fake-review and drip-pricing bans from 6 Apr 2025 with CMA fines up to 10% of global turnover; Google's review-snippet guidelines (24 Jul 2026) ban fake or undisclosed incentivised reviews on the page and in markup; India CCPA dark-pattern guidelines list 13 banned patterns with a June 2025 self-audit advisory.

## Jurisdiction quick map

| Topic | EU/EEA | UK | US | India |
| --- | --- | --- | --- | --- |
| Cookies | Prior opt-in (ePrivacy 5(3) + GDPR consent) | PECR, same | Opt-out; honour GPC / Do Not Sell (CA and other states) | DPDP notice + consent |
| Fake reviews | UCPD / Omnibus | DMCC Act | FTC 16 CFR 465 | Consumer Protection Act, E-Commerce Rules, ASCI |
| Accessibility | EAA since 28 Jun 2025 (micro-enterprise services exempt) | Equality Act | ADA suits (5,000+ in 2025) | RPwD Act, GIGW |
| Company identity | Impressum DE/AT; e-commerce info | Company details | State rules | Grievance officer (e-commerce) |

## l-01
**No Privacy Policy while collecting data.** Any form, account, analytics, newsletter or payment collects personal data. Policy must name the controller, data collected, purposes, legal basis, processors (Supabase, Vercel, Stripe, OpenAI, email, analytics), international transfers, retention, rights, how to exercise them, contact. Link it in the footer and next to every form.

## l-02
**Template placeholders in legal pages.** `[Company Name]`, `Your Company`, wrong jurisdiction, AI-written policy describing data you do not collect. A wrong policy is a misrepresentation.

## l-03
**Terms missing** where there are accounts, payments, subscriptions or user content.

## l-04
**Fabricated testimonials.** Signals: avatar URLs from randomuser.me, pravatar, ui-avatars, dicebear, Unsplash face crops; "Name, Title at Company" with no link; identical length and tone; all five stars; quotes using buzzwords. Fix: remove or replace with real, permissioned quotes; keep written consent; disclose any material connection (employee, friend, paid, free product).

## l-05
**Invented numbers and logos.** "10,000+ users", "Trusted by 500 companies", logo walls, "As seen in", animated counters to constants, star ratings without a source. Keep only what you can prove today, with the source in your records.

## l-06
**Review markup.** `Review`/`AggregateRating` JSON-LD must reflect real reviews visible on the page. Never on your own `Organization`/`LocalBusiness` (self-serving, ineligible since 2019). Fake markup risks a manual action.

## l-07
**Trackers before consent.** The static check flags tracker code with no consent manager; the rendered check proves it: fresh profile, no clicks, 4 s idle, record tracker requests and cookies (`_ga`, `_fbp`, `_hjSession*`, `_clck`, `MUID`, `_ttp`, `ajs_*`, `ph_*`). Fix: `templates/consent-gate.md`.

## l-08
**Banner without equal Reject; pre-ticked boxes; cookie walls.** Invalid consent under EDPB guidance and CNIL practice. First layer needs Accept and Reject with equal prominence.

## l-09
**No way to withdraw consent.** Footer "Cookie settings" link.

## l-10
**Google Fonts from Google's CDN.** Munich Regional Court (20 Jan 2022, 3 O 17493/20): IP sent to Google without consent breached GDPR; EUR 100 damages and an injunction. Self-host (`next/font/google` does it automatically).

## l-11
**Third-party embeds on load.** YouTube, Maps, Calendly, Intercom, Crisp load trackers. Use click-to-load facades.

## l-12
**No data deletion/export path.** Add account deletion and a privacy contact.

## l-13
**Unsubstantiated claims.** "GDPR/HIPAA compliant", "SOC 2", "bank-level security", "military-grade", "#1", "AI-powered" when it is not.

## l-14
**Missing business identity.** Legal name, address, contact email (and Impressum in DE/AT, grievance officer for Indian e-commerce).

## l-15
**E-commerce disclosures.** Refund, returns, shipping, total price including mandatory fees early (UK DMCC drip pricing ban; India CCPA "drip pricing").

## l-16
**Undisclosed affiliate or sponsored links.** Disclose near the link.

## l-17
**Licences.** Copied GPL/AGPL code in a closed product, unlicensed fonts/icons, AI images of real brands or people.

## l-18
**Accessibility statement** where EAA applies (EU consumer e-commerce, banking, e-books, transport, telecoms).
