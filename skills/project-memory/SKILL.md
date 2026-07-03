---
name: project-memory
description: Use when logging a decision made about the system, recording deferred work, or updating the project roadmap — and as the format reference for docs/forge/ROADMAP.md, DECISIONS.md, and DEFERRALS.md.
---

# Project Memory

Three append-friendly files under `docs/forge/` give the project durable memory across sessions. Entries are terse, newest first. Create each file on its first entry — no empty scaffolds. Commit memory updates with the work that produced them.

## DECISIONS.md — read before building, written when decided

One entry per decision about the system:

```markdown
## 2026-06-10 — Use SQLite for local persistence
**Why:** Single-user app, no server; simplest thing that supports the query needs.
**Where:** docs/forge/specs/2026-06-10-storage-design.md
```

Log when: an approach is chosen during brainstorming, a design decision is locked during planning, or a decision crystallizes ad-hoc mid-session ("let's log that").

**Read before any feature build.** New work must not contradict logged decisions. On conflict, surface it to the user — never silently override. Reversing a decision gets a new entry that names the one it supersedes.

## DEFERRALS.md — what we consciously didn't do

```markdown
## 2026-06-10 — Skipped retry backoff on the sync client
**Why:** Single-user, local network; failures are rare and manual retry is fine.
**From:** docs/forge/plans/2026-06-10-sync.md, Task 3
**Follow-up:** roadmap | drop | revisit-when-<condition>
```

**Agency rule:** during execution, agents may defer **non-spec scope only** — nice-to-haves, refactors, edge polish they judge out of scope — with an entry here. Anything the spec requires is never silently deferred; flag it to the user at the review gate instead. List all new deferrals in the end-of-plan summary.

## ROADMAP.md — phases of larger systems

Created **only** when brainstorming decomposes work into multiple sub-projects or phases. One line each:

```markdown
- [in-progress] Phase 2: Sync engine — bidirectional sync with conflict log ([spec](specs/...), [plan](plans/...))
- [planned] Phase 3: Sharing — read-only share links
```

Statuses: `planned | in-progress | done | deferred`. Planning marks a phase `in-progress` at kickoff and `done` at completion. Deferrals with `roadmap` follow-up add a `deferred` line.

## Legacy

A repo with `docs/superpowers/` and no `docs/forge/`: offer a one-time `git mv docs/superpowers docs/forge` rather than reading both paths forever.
