# Deferrals

## 2026-06-10 — Skill test harness
**Why:** Superpowers' `tests/` drives the `claude` CLI to verify skills trigger and behave; valuable for continual refinement but heavy to maintain.
**From:** Initial fork plan
**Follow-up:** revisit-when-first-month-of-real-use-shows-trigger-or-behavior-drift

## 2026-06-10 — systematic-debugging port
**Why:** Current models do hypothesis-driven debugging natively; keep the fork lean.
**From:** Initial fork plan
**Follow-up:** revisit-when-debugging-quality-regresses

## 2026-06-10 — Workflow script template for large-plan execution
**Why:** Planning skill describes the shape (implementer + combined review, pipelined); a reusable template is premature before a large plan actually runs.
**From:** Initial fork plan
**Follow-up:** revisit-when-first-large-plan-executes

## 2026-06-10 — Windows/cross-platform hook shim
**Why:** macOS-only environment; superpowers' run-hook.cmd complexity not needed.
**From:** Initial fork plan
**Follow-up:** drop

## 2026-06-10 — foundation-lacrosse legacy path migration
**Why:** Repo still has `docs/superpowers/`; skills offer a one-time `git mv docs/superpowers docs/theforge` when the flow next runs there. In-flight Phase 4a plan executes fine under either regime.
**From:** Initial fork plan
**Follow-up:** revisit-when-flow-next-used-in-foundation-lacrosse
