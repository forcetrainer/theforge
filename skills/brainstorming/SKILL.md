---
name: brainstorming
description: Use before creative work — new features, new components, behavior changes. Turns an idea into a validated design spec through collaborative dialogue, before any planning or implementation.
---

# Brainstorming

**Trigger:** creative work without an approved spec — new features, components, behavior changes. **Don't trigger:** bug fixes with a clear repro, questions, trivial mechanical edits.

Turn an idea into a validated design through dialogue, then a written spec the user approves before planning begins.

Don't write code, scaffold a project, or take any implementation action until the user has approved a design. "Simple" projects still get one — the design can be a few sentences, but it gets presented and approved. Simple is where unexamined assumptions waste the most work.

## Flow

1. **Explore context** — current files, docs, recent commits. Read `docs/theforge/DECISIONS.md` and `ROADMAP.md` if present; logged decisions are constraints — flag conflicts to the user, don't design around them silently.
2. **Scope check** — if the request spans multiple independent subsystems, decompose before refining details: identify the pieces, how they relate, what order to build them. Record the phases in `docs/theforge/ROADMAP.md` (formats: project-memory skill). Then brainstorm the first sub-project; each gets its own spec → plan → implementation cycle.
3. **Clarify** — one question at a time, multiple choice preferred. Focus on purpose, constraints, and success criteria.
4. **Propose 2–3 approaches** with trade-offs. Lead with your recommendation and why.
5. **Present the design** in sections scaled to their complexity (a few sentences when straightforward, ~200–300 words when nuanced); check in after each section. Cover architecture, components, data flow, error handling, testing.
6. **Write the spec** to `docs/theforge/specs/YYYY-MM-DD-<topic>-design.md` and commit it. (User/project preferences for spec location override this default.) Code appears in a spec only as **contract, never solution**: interface signatures (no bodies), data/wire-format examples, algorithms that are themselves the requirement, desired call-site ergonomics. If deleting a code block would lose only typing time — not a decision — cut it.
7. **Self-review the spec** with fresh eyes: placeholders ("TBD", vague requirements), internal contradictions, scope (focused enough for one plan?), ambiguity (any requirement readable two ways? pick one, make it explicit). Fix inline, no re-review.
8. **User review gate** — ask the user to review the spec file before proceeding; make requested changes. Only proceed on approval.
9. **Log the decision** — append the chosen approach and why it won over the alternatives to `docs/theforge/DECISIONS.md`.
10. **Hand off to the planning skill.** That is the only next step — no implementation skills.

## Design principles

- **YAGNI ruthlessly** — strip unnecessary features from every design.
- Break the system into units with one clear purpose, well-defined interfaces, and independent testability. For each unit you should be able to say what it does, how it's used, and what it depends on — without reading its internals.
- In existing codebases: explore the structure first and follow established patterns. Include targeted improvements where existing problems affect the work (an overgrown file, tangled boundaries); skip unrelated refactoring.

## Visual companion

When a question is genuinely visual — mockups, wireframes, layout comparisons, architecture diagrams — show it in the browser companion rather than describing it (standing user preference: use it without asking). Decide per question: content the user understands better by *seeing* goes to the browser; requirements, trade-off lists, and conceptual choices stay in the terminal. When the user picks a direction, don't start building — ask whether they want to refine it further or it's good enough to fold into the design; their answer decides. Before first use in a session, read `visual-companion.md` in this skill directory.
