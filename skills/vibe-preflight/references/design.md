# Design rules (D-): the generic AI look

Cause: models fill every unmade design decision with the median of their training data. Tailwind UI shipped `bg-indigo-500` as its default accent, so the median is indigo (its creator apologised for this in Aug 2025). Banning purple alone moves models to a "second wave": cream plus terracotta, near-black plus one acid accent, italic serif heroes. So judge **unchosen defaults**, not colours.

Design findings are P2 unless they also break accessibility (then the F-rule wins). Never block a launch on taste.

## Tells

| Rule | Tell | How to spot | Better |
| --- | --- | --- | --- |
| d-01 | Indigo/violet/purple gradient or accent | `from-indigo-500`, `#6366F1`, `#8B5CF6`, `#A855F7`, gradient hue 240-290 | 4-6 named brand tokens, one accent |
| d-02 | Gradient text | `bg-clip-text text-transparent` | Solid colour |
| d-03 | Side-stripe card border | `border-l-4 rounded-xl` | Full border, tint, or nothing |
| d-04 | Default fonts only | Inter/Roboto/system everywhere | Chosen display face |
| d-05 | Centre everything | most text centred | Left-align body |
| d-06 | Hero formula | Centred h1 + subhead + two buttons + fake screenshot | Lead with the real product or a concrete claim |
| d-07 | Three identical feature cards | `grid-cols-3`, icon + title + text x3 | Vary, use real content, or a list |
| d-08 | Hero metrics row | Big numbers + tiny labels, often invented | Only real, sourced metrics (L-05) |
| d-09 | Same big radius on everything | `rounded-2xl` everywhere | Radius scale |
| d-10 | Hairline border + big shadow | `border shadow-2xl` | Pick one |
| d-11 | Glassmorphism by default | `backdrop-blur`, `bg-white/10` | Only for real layering |
| d-12 | Blurred blobs/orbs | absolute `blur-3xl` circles | Remove |
| d-13 | Emoji as icons | 🚀 ⚡ ✨ in headings and cards | One icon set |
| d-14 | Bounce/elastic easing | `animate-bounce`, back/elastic easings | Ease-out, reduced motion |
| d-15 | Fade-up on every section | same scroll animation everywhere | Animate meaning only |
| d-16 | Pure #000/#fff | untinted extremes | Tinted neutrals |
| d-17 | Light grey copy | `text-gray-400` body | Contrast (F-01) |
| d-18 | Cards inside cards | nested bordered boxes | Flatten |
| d-19 | Fake dashboard mock | lorem charts, decorative sparklines | Real screenshot |
| d-20 | Logo wall with no source | grey logos under hero | Real, permitted logos (L-05) |
| d-21 | Pricing triple, middle "Popular" | when you have one plan | Real tiers only |
| d-22 | Buzzword copy | empower, unlock, seamless, revolutionize, elevate, supercharge | Specific claim + number |
| d-23 | Generic CTAs | Get Started, Learn More | Name the outcome |
| d-24 | Em-dash confetti, tricolons | many — and "X, Y, and Z" | Plain sentences |
| d-25 | Italic serif hero (second wave) | `font-serif italic` h1 | Commit to a face |
| d-26 | Cream + terracotta / acid on black | second-wave palettes | Palette from brand brief |
| d-27 | App screens built as landing pages | heroes inside the product | Task UI |

## Scoring (from screenshots in `.preflight/screens/`)

Count tells you can see. 0-3 intentional. 4-7 generic: fix the top three (palette, hero, cards). 8+ template: redesign hero and palette before launch.

## False positives

Real brand violet used consistently via tokens; Inter for body with a distinct display face; blur in genuine overlays. Mark with `preflight-ignore D-01: brand colour`.

## Pairs well with

Impeccable (`npx impeccable detect`), Taste Skill, Anthropic's frontend-design skill. Run them for deeper design critique; this skill only flags and scores.
