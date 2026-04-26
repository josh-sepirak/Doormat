# .impeccable.md

Design context for the Doormat project. Loaded by the `impeccable` skill to guide all UI/UX work.

---

## Design Context

### Users

A solo developer or apartment-hunter who self-hosts Doormat to automate their own rental search. They set it up once — configure a city and preferences, add API keys — then come back periodically to see what the agent found. They are technically comfortable but not necessarily a designer. The core job: eliminate the exhausting, repetitive act of checking property manager sites and scoring listings by hand.

Context of use: usually at a laptop, probably at home, likely stressed about housing. The tool should feel like a relief, not another chore.

### Brand Personality

**Warm, capable, quiet.**

Like a trusted doorman — helpful without being showy, knowledgeable without being intimidating. The name *Doormat* is self-deprecating and approachable on purpose; the tool should match that tone. Think Notion or Loom: human, clear, a little personality in the small moments. Not startup-bold, not enterprise-cold.

Voice: first-person friendly, short sentences, no jargon. Empty states explain what to do next. Errors are matter-of-fact, not alarming.

### Aesthetic Direction

**Clean, warm-minimal, type-led.** Inter for body, Lexend for display headings — keep that pairing, it reads as friendly + precise. Blue-600 (`#2563EB`) as the one accent color; everything else is slate. Rounded-2xl cards with subtle slate-200 borders — no harsh shadows, no gradients.

Supports **both light and dark mode** via `prefers-color-scheme`. Dark mode is an equal citizen, not an afterthought.

Anti-reference: avoid the "AI startup" aesthetic — no glowing neon, no animated meshes, no purple/gradient hero sections. Also avoid the enterprise dashboard look — heavy sidebars, data-dense tables, and icon-heavy navigation all feel wrong for a single-user personal tool.

### Design Principles

1. **Trust through clarity** — The user always knows what's running, what succeeded, and what failed. Status is surfaced prominently and legibly, never buried. Discovery log messages are human-readable sentences, not JSON blobs.

2. **Confidence without anxiety** — During agent runs, the UI communicates "it's working, you can step away" rather than demanding attention. Spinners are minimal; progress is shown but not dramatized. The agent is competent; the UI reflects that.

3. **Warmth in the margins** — Personality lives in empty states, log messages, error copy, and micro-interactions — not in flashy visuals. A listing with a high score gets a small celebration; an empty state explains exactly what to do next.

4. **Dark mode as equal citizen** — Both themes are designed intentionally. Dark mode uses deep slate (not pure black), warm white text, and the same blue-600 accent. Color choices are verified in both modes.

5. **Personal, not enterprise** — One person, one housing search. The UI should feel like a personal tool, not a SaaS dashboard. No unnecessary chrome, no sidebar navigation, no "upgrade" prompts.
