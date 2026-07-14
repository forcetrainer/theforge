"""Tests for scripts/forge-run.py (Task 2: plan loop, dispatch, receipts, ledger).

Loaded via importlib since the script filename contains a hyphen. Task 3 tests
(review, rework cap, halt, resume, final review) are added later and are excluded
from this task's acceptance via `-k "not review and not resume"`; nothing here
uses those words in a node id.

The fake `codex` executable records its argv and replays scripted exit codes and
last-messages, so dispatch is observable without a live Codex CLI.
"""
import importlib.util
import json
import os
import pathlib
import shutil
import stat
import subprocess
import sys
import tempfile
import unittest

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
SCRIPT_PATH = REPO_ROOT / "scripts" / "forge-run.py"

_spec = importlib.util.spec_from_file_location("forge_run", SCRIPT_PATH)
forge_run = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(forge_run)


# A fake `codex` binary: appends its argv (JSON) to FORGE_FAKE_LOG, reads a
# per-call response from FORGE_FAKE_RESPONSES ([{"exit":int,"msg":str}, ...],
# index = prior log line count, clamped to last), writes msg to the
# --output-last-message path, and exits with the scripted code.
FAKE_CODEX_SRC = '''#!/usr/bin/env python3
import json, os, sys
argv = sys.argv[1:]
log = os.environ.get("FORGE_FAKE_LOG")
idx = 0
if log:
    if os.path.exists(log):
        with open(log) as f:
            idx = sum(1 for _ in f)
    with open(log, "a") as f:
        f.write(json.dumps(argv) + "\\n")
exit_code = 0
msg = ""
resp = os.environ.get("FORGE_FAKE_RESPONSES")
if resp and os.path.exists(resp):
    with open(resp) as f:
        responses = json.load(f)
    if responses:
        r = responses[idx] if idx < len(responses) else responses[-1]
        exit_code = r.get("exit", 0)
        msg = r.get("msg", "")
if "--output-last-message" in argv:
    p = argv[argv.index("--output-last-message") + 1]
    with open(p, "w") as f:
        f.write(msg)
sys.exit(exit_code)
'''


def write_fake_codex(dirpath):
    path = os.path.join(dirpath, "fake_codex.py")
    with open(path, "w") as f:
        f.write(FAKE_CODEX_SRC)
    st = os.stat(path)
    os.chmod(path, st.st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)
    return path


PLAN_PASS = """# Fixture Plan

**Goal:** Do the thing.

### Task 1: First task
- [ ] Done

**Files:**
- Modify: `foo.txt`

**Acceptance:** `true`

**Tier:** trivial

**Depends on:** nothing
"""

# Task 2 listed before Task 1 in the file; Task 2 depends on Task 1. A correct
# runner dispatches Task 1 first regardless of file order.
PLAN_DEPS = """# Fixture Plan

**Goal:** Do the thing.

### Task 2: Second task
- [ ] Done

**Acceptance:** `true`

**Tier:** trivial

**Depends on:** Task 1

### Task 1: First task
- [ ] Done

**Acceptance:** `true`

**Tier:** trivial

**Depends on:** nothing
"""

PLAN_ACC_FAIL = """# Fixture Plan

**Goal:** Do the thing.

### Task 1: First task
- [ ] Done

**Acceptance:** `false`

**Tier:** trivial

**Depends on:** nothing
"""

PLAN_BAD_HEADING = """# Fixture Plan

**Goal:** Do the thing.

## Task 1: Wrong level
- [ ] Done

**Acceptance:** `true`

**Tier:** trivial

**Depends on:** nothing
"""

PLAN_DUP = """# Fixture Plan

**Goal:** Do the thing.

### Task 1: First
- [ ] Done

**Acceptance:** `true`

**Tier:** trivial

**Depends on:** nothing

### Task 1: Second
- [ ] Done

**Acceptance:** `true`

**Tier:** trivial

**Depends on:** nothing
"""

MINIMAL_SPEC = "# Spec\n\nNothing referenced.\n"


class ParsePlanTasksTests(unittest.TestCase):
    def _write(self, content):
        d = tempfile.mkdtemp(prefix="forge-run-parse-")
        self.addCleanup(shutil.rmtree, d, ignore_errors=True)
        p = os.path.join(d, "plan.md")
        with open(p, "w") as f:
            f.write(content)
        return p

    def test_parses_number_title_tier_depends_acceptance(self):
        tasks = forge_run.parse_plan_tasks(self._write(PLAN_DEPS))
        by_num = {t.number: t for t in tasks}
        self.assertEqual(set(by_num), {1, 2})
        self.assertEqual(by_num[1].title, "First task")
        self.assertEqual(by_num[1].tier, "trivial")
        self.assertEqual(by_num[1].depends_on, [])
        self.assertEqual(by_num[1].acceptance_commands, ["true"])
        self.assertEqual(by_num[2].depends_on, [1])

    def test_checkbox_line_points_at_done_line(self):
        p = self._write(PLAN_PASS)
        tasks = forge_run.parse_plan_tasks(p)
        with open(p) as f:
            lines = f.read().splitlines()
        idx = tasks[0].checkbox_line
        self.assertIn("[ ]", lines[idx])

    def test_wrong_level_heading_raises_naming_cause(self):
        with self.assertRaises(RuntimeError) as ctx:
            forge_run.parse_plan_tasks(self._write(PLAN_BAD_HEADING))
        msg = str(ctx.exception)
        self.assertIn("### Task 1:", msg)
        self.assertIn("## Task 1:", msg)

    def test_duplicate_task_number_raises_naming_cause(self):
        with self.assertRaises(RuntimeError) as ctx:
            forge_run.parse_plan_tasks(self._write(PLAN_DUP))
        self.assertIn("1", str(ctx.exception))
        self.assertIn("duplicate", str(ctx.exception).lower())


class DispatchWorkerTests(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.mkdtemp(prefix="forge-run-dispatch-")
        self.addCleanup(shutil.rmtree, self.d, ignore_errors=True)
        self.fake = write_fake_codex(self.d)
        self.brief = os.path.join(self.d, "brief.md")
        with open(self.brief, "w") as f:
            f.write("# Task brief\n")

    def test_tier_resolution_emits_exact_model_effort_argv(self):
        for tier, (model, effort) in forge_run.TIER_MAP.items():
            run_dir = os.path.join(self.d, "run-" + tier)
            os.makedirs(run_dir, exist_ok=True)
            task = forge_run.Task(number=1, title="t", tier=tier)
            res = forge_run.dispatch_worker(task, self.brief, self.fake, run_dir)
            argv = res.argv
            self.assertIn("exec", argv)
            self.assertIn("-m", argv)
            self.assertIn(model, argv)
            self.assertIn("-c", argv)
            self.assertIn("model_reasoning_effort=" + effort, argv)
            self.assertIn("--output-last-message", argv)

    def test_ultra_never_appears_in_emitted_argv(self):
        for tier in forge_run.TIER_MAP:
            run_dir = os.path.join(self.d, "runu-" + tier)
            os.makedirs(run_dir, exist_ok=True)
            task = forge_run.Task(number=1, title="t", tier=tier)
            res = forge_run.dispatch_worker(task, self.brief, self.fake, run_dir)
            self.assertNotIn("ultra", " ".join(res.argv))

    def test_prompt_carries_contract_preamble_and_brief(self):
        run_dir = os.path.join(self.d, "run-prompt")
        os.makedirs(run_dir, exist_ok=True)
        task = forge_run.Task(number=1, title="t", tier="trivial")
        res = forge_run.dispatch_worker(task, self.brief, self.fake, run_dir)
        prompt = res.argv[-1]
        self.assertIn("# Task brief", prompt)
        self.assertIn("forge execution worker", prompt)

    def test_missing_contract_source_raises(self):
        empty = tempfile.mkdtemp(prefix="forge-run-noagents-")
        self.addCleanup(shutil.rmtree, empty, ignore_errors=True)
        old = os.environ.get("FORGE_AGENTS_DIR")
        os.environ["FORGE_AGENTS_DIR"] = empty
        self.addCleanup(
            lambda: os.environ.__setitem__("FORGE_AGENTS_DIR", old)
            if old is not None
            else os.environ.pop("FORGE_AGENTS_DIR", None)
        )
        run_dir = os.path.join(self.d, "run-noagents")
        os.makedirs(run_dir, exist_ok=True)
        task = forge_run.Task(number=1, title="t", tier="trivial")
        with self.assertRaises(RuntimeError):
            forge_run.dispatch_worker(task, self.brief, self.fake, run_dir)


class RunAcceptanceTests(unittest.TestCase):
    def test_success_and_failure_recorded_per_command(self):
        d = tempfile.mkdtemp(prefix="forge-run-acc-")
        self.addCleanup(shutil.rmtree, d, ignore_errors=True)
        task = forge_run.Task(
            number=1, title="t", tier="trivial",
            acceptance_commands=["true", "false"],
        )
        results = forge_run.run_acceptance(task, d)
        self.assertEqual([r.command for r in results], ["true", "false"])
        self.assertEqual(results[0].exit_code, 0)
        self.assertNotEqual(results[1].exit_code, 0)


class AnnotateLedgerTests(unittest.TestCase):
    def test_checks_box_and_appends_status(self):
        d = tempfile.mkdtemp(prefix="forge-run-ledger-")
        self.addCleanup(shutil.rmtree, d, ignore_errors=True)
        p = os.path.join(d, "plan.md")
        with open(p, "w") as f:
            f.write(PLAN_PASS)
        task = forge_run.parse_plan_tasks(p)[0]
        forge_run.annotate_ledger(p, task, "passed, 1 attempt(s)")
        with open(p) as f:
            content = f.read()
        self.assertIn("[x] Done", content)
        self.assertIn("passed, 1 attempt(s)", content)


class LoopSubprocessTests(unittest.TestCase):
    """End-to-end: invoke forge-run.py as a subprocess with a fake codex on the
    --codex-bin seam and the plan's dir as cwd (so acceptance commands run there)."""

    def setUp(self):
        self.d = tempfile.mkdtemp(prefix="forge-run-loop-")
        self.addCleanup(shutil.rmtree, self.d, ignore_errors=True)
        self.fake = write_fake_codex(self.d)
        self.spec = os.path.join(self.d, "spec.md")
        with open(self.spec, "w") as f:
            f.write(MINIMAL_SPEC)
        self.run_dir = os.path.join(self.d, "run")
        self.log = os.path.join(self.d, "fakelog")

    def _plan(self, content, name="plan.md"):
        p = os.path.join(self.d, name)
        with open(p, "w") as f:
            f.write(content)
        return p

    def _run(self, plan_path, responses=None):
        env = os.environ.copy()
        env["FORGE_FAKE_LOG"] = self.log
        if responses is not None:
            resp_path = os.path.join(self.d, "responses.json")
            with open(resp_path, "w") as f:
                json.dump(responses, f)
            env["FORGE_FAKE_RESPONSES"] = resp_path
        return subprocess.run(
            [sys.executable, str(SCRIPT_PATH), plan_path,
             "--spec", self.spec, "--run-dir", self.run_dir,
             "--codex-bin", self.fake],
            cwd=self.d, capture_output=True, text=True, env=env,
        )

    def test_help_exits_zero(self):
        res = subprocess.run(
            [sys.executable, str(SCRIPT_PATH), "--help"],
            capture_output=True, text=True,
        )
        self.assertEqual(res.returncode, 0, res.stderr)

    def test_passing_task_writes_receipt_with_all_fields_and_brief_sha(self):
        plan = self._plan(PLAN_PASS)
        res = self._run(plan)
        self.assertEqual(res.returncode, 0, res.stderr)
        receipt_path = os.path.join(self.run_dir, "task-1-attempt-1.json")
        with open(receipt_path) as f:
            receipt = json.load(f)
        for key in ("task_number", "title", "tier", "model", "effort",
                    "brief_path", "brief_sha256", "worker_exit_code",
                    "acceptance_results", "review_verdict", "attempt", "status"):
            self.assertIn(key, receipt)
        self.assertEqual(receipt["status"], "passed")
        self.assertEqual(receipt["tier"], "trivial")
        self.assertEqual(receipt["model"], "gpt-5.6-luna")
        self.assertEqual(receipt["effort"], "medium")
        import hashlib
        with open(receipt["brief_path"], "rb") as f:
            actual = hashlib.sha256(f.read()).hexdigest()
        self.assertEqual(receipt["brief_sha256"], actual)

    def test_run_json_summarizes_task_statuses(self):
        plan = self._plan(PLAN_PASS)
        res = self._run(plan)
        self.assertEqual(res.returncode, 0, res.stderr)
        with open(os.path.join(self.run_dir, "run.json")) as f:
            summary = json.load(f)
        self.assertEqual(summary["status"], "passed")
        statuses = {t["number"]: t["status"] for t in summary["tasks"]}
        self.assertEqual(statuses[1], "passed")

    def test_ledger_annotated_passed_with_attempts(self):
        plan = self._plan(PLAN_PASS)
        res = self._run(plan)
        self.assertEqual(res.returncode, 0, res.stderr)
        with open(plan) as f:
            content = f.read()
        self.assertIn("[x] Done", content)
        self.assertIn("passed, 1 attempt(s)", content)

    def test_depends_on_order_dependency_dispatched_first(self):
        plan = self._plan(PLAN_DEPS)
        res = self._run(plan)
        self.assertEqual(res.returncode, 0, res.stderr)
        with open(self.log) as f:
            log_lines = f.read().splitlines()
        # Each line is the argv of one worker dispatch; the --output-last-message
        # path names the task. Task 1 must be dispatched before Task 2.
        joined = "\n".join(log_lines)
        pos1 = joined.find("task-1-worker-last")
        pos2 = joined.find("task-2-worker-last")
        self.assertNotEqual(pos1, -1)
        self.assertNotEqual(pos2, -1)
        self.assertLess(pos1, pos2)

    def test_dependency_failure_halts_before_dependent_dispatched(self):
        # Task 1 (the dependency) fails; Task 2 depends on it and must never be
        # dispatched. Guards run_plan's break-on-escalation: a refactor that kept
        # looping would dispatch the dependent, and this test would catch it.
        plan = self._plan(PLAN_DEPS)
        res = self._run(plan, responses=[{"exit": 1, "msg": ""}])
        self.assertEqual(res.returncode, 2, res.stderr)
        with open(self.log) as f:
            log_lines = [ln for ln in f.read().splitlines() if ln.strip()]
        # Exactly one worker dispatch — the failed dependency, never the dependent.
        self.assertEqual(len(log_lines), 1, log_lines)
        self.assertIn("task-1-worker-last", log_lines[0])
        self.assertNotIn("task-2-worker-last", "\n".join(log_lines))
        # Task 2's worker last-message file is never created.
        self.assertFalse(
            os.path.exists(os.path.join(self.run_dir, "task-2-worker-last.txt"))
        )

    def test_worker_nonzero_exit_marks_attempt_failed_and_halts(self):
        plan = self._plan(PLAN_PASS)
        res = self._run(plan, responses=[{"exit": 1, "msg": ""}])
        self.assertEqual(res.returncode, 2, res.stderr)
        with open(os.path.join(self.run_dir, "task-1-attempt-1.json")) as f:
            receipt = json.load(f)
        self.assertEqual(receipt["worker_exit_code"], 1)
        self.assertNotEqual(receipt["status"], "passed")

    def test_acceptance_failure_marks_attempt_failed_and_halts(self):
        plan = self._plan(PLAN_ACC_FAIL)
        res = self._run(plan)
        self.assertEqual(res.returncode, 2, res.stderr)
        with open(os.path.join(self.run_dir, "task-1-attempt-1.json")) as f:
            receipt = json.load(f)
        self.assertNotEqual(receipt["status"], "passed")
        self.assertTrue(
            any(r["exit_code"] != 0 for r in receipt["acceptance_results"])
        )

    def test_malformed_plan_bad_heading_exits_one_naming_cause(self):
        plan = self._plan(PLAN_BAD_HEADING)
        res = self._run(plan)
        self.assertEqual(res.returncode, 1, res.stderr)
        self.assertIn("### Task 1:", res.stderr)

    def test_malformed_plan_duplicate_number_exits_one_naming_cause(self):
        plan = self._plan(PLAN_DUP)
        res = self._run(plan)
        self.assertEqual(res.returncode, 1, res.stderr)
        self.assertIn("duplicate", res.stderr.lower())

    def test_missing_contract_source_cli_exits_one_naming_cause(self):
        # Spec Tests bullet: "missing agents/*.md contract source exits 1" —
        # driven through the CLI (not just the unit-level dispatch_worker raise).
        plan = self._plan(PLAN_PASS)
        empty = os.path.join(self.d, "no-agents")
        os.makedirs(empty, exist_ok=True)
        env = os.environ.copy()
        env["FORGE_FAKE_LOG"] = self.log
        env["FORGE_AGENTS_DIR"] = empty
        res = subprocess.run(
            [sys.executable, str(SCRIPT_PATH), plan,
             "--spec", self.spec, "--run-dir", self.run_dir,
             "--codex-bin", self.fake],
            cwd=self.d, capture_output=True, text=True, env=env,
        )
        self.assertEqual(res.returncode, 1, res.stderr)
        self.assertIn("contract source", res.stderr.lower())


if __name__ == "__main__":
    unittest.main()
