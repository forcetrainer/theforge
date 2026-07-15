"""End-to-end plan-loop subprocess runs, resume, and the --effort CLI path."""
import json
import os
import pathlib
import shutil
import stat
import subprocess
import sys
import tempfile
import types
import unittest

from _forge_support import *  # noqa: F401,F403


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
        # Every worker dispatch is the failed dependency (task 1), never the
        # dependent (task 2). A crashing worker consumes the rework cap, so task 1
        # is dispatched more than once (initial + one rework) — the invariant under
        # test is that task 2 is never reached, not the exact attempt count.
        self.assertTrue(log_lines)
        self.assertTrue(
            all("task-1-worker-last" in ln for ln in log_lines), log_lines
        )
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

    def test_run_writes_forge_gitignore(self):
        # Receipts spec (2026-07-13 amendment): on run-dir creation the runner
        # writes a self-ignoring `.forge/.gitignore` containing `*` — no
        # target-repo setup required.
        plan = self._plan(PLAN_PASS)
        res = self._run(plan)
        self.assertEqual(res.returncode, 0, res.stderr)
        gitignore_path = os.path.join(self.d, ".forge", ".gitignore")
        self.assertTrue(os.path.exists(gitignore_path))
        with open(gitignore_path) as f:
            content = f.read()
        self.assertEqual(content.strip(), "*")

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


class ResumeTests(unittest.TestCase):
    """Re-invocation with an existing --run-dir skips tasks whose latest receipt
    status is ``passed`` and resumes at the incomplete/escalated one. Trivial
    tasks + worker-crash escalation keep this off the git path."""

    def setUp(self):
        self.d = tempfile.mkdtemp(prefix="forge-run-resume-")
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

    def _run(self, plan_path, responses):
        # Fresh log every invocation so the fake's response index starts at 0 and
        # the log reflects only this invocation's dispatches.
        if os.path.exists(self.log):
            os.remove(self.log)
        env = os.environ.copy()
        env["FORGE_FAKE_LOG"] = self.log
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

    def test_resume_skips_passed_tasks_and_resumes_at_escalated(self):
        plan = self._plan(PLAN_TWO_TRIVIAL)  # task 2 depends on task 1
        # Run 1: task 1 passes, task 2 crashes both attempts -> escalated, exit 2.
        res1 = self._run(plan, responses=[
            {"exit": 0, "msg": ""},  # task 1 worker
            {"exit": 1, "msg": ""},  # task 2 worker attempt 1
            {"exit": 1, "msg": ""},  # task 2 worker attempt 2
        ])
        self.assertEqual(res1.returncode, 2, res1.stderr)
        # Run 2 (same run-dir): task 1 is skipped (passed receipt); task 2 resumes
        # and now passes.
        res2 = self._run(plan, responses=[{"exit": 0, "msg": ""}])
        self.assertEqual(res2.returncode, 0, res2.stderr)
        joined = "\n".join(ln for ln in open(self.log).read().splitlines())
        self.assertNotIn("task-1-worker-last", joined)  # task 1 not re-dispatched
        self.assertIn("task-2-worker-last", joined)     # task 2 resumed
        with open(os.path.join(self.run_dir, "run.json")) as f:
            summary = json.load(f)
        self.assertEqual(summary["status"], "passed")
        with open(plan) as f:
            content = f.read()
        self.assertIn("[x] Done", content)

    def test_resume_forwards_to_run_plan_with_declared_signature(self):
        # resume(plan_path, spec_path, run_dir) is the documented re-invocation
        # entry: it forwards to run_plan with the production defaults (codex on
        # PATH, cwd = getcwd()). Guards against signature drift and dead code.
        calls = []
        orig = forge_run.run_plan

        def _record(*a, **k):
            calls.append(a)
            return 0

        forge_run.run_plan = _record
        try:
            rc = forge_run.resume("plan.md", "spec.md", "/run/dir")
        finally:
            forge_run.run_plan = orig
        self.assertEqual(rc, 0)
        self.assertEqual(len(calls), 1)
        args = calls[0]
        self.assertEqual(args[0], "plan.md")
        self.assertEqual(args[1], "spec.md")
        self.assertEqual(args[2], "/run/dir")
        self.assertEqual(args[3], "codex")
        self.assertEqual(args[4], os.getcwd())


class EffortOverrideCliTests(unittest.TestCase):
    """CLI --effort N=LEVEL applies only to task N's worker dispatch."""

    def setUp(self):
        self.d = tempfile.mkdtemp(prefix="forge-run-effort-")
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

    def _run(self, plan_path, extra_args=(), responses=None):
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
             "--codex-bin", self.fake, *extra_args],
            cwd=self.d, capture_output=True, text=True, env=env,
        )

    def test_override_changes_effort_for_only_that_task(self):
        plan = self._plan(PLAN_DEPS)  # task 1 (trivial) then task 2 depends on it
        res = self._run(plan, extra_args=["--effort", "1=max"])
        self.assertEqual(res.returncode, 0, res.stderr)
        argvs = _log_argvs(self.log)
        t1 = _find_dispatch(argvs, "task-1-worker-last")
        t2 = _find_dispatch(argvs, "task-2-worker-last")
        self.assertIsNotNone(t1)
        self.assertIsNotNone(t2)
        self.assertIn("model_reasoning_effort=max", t1)
        self.assertIn("model_reasoning_effort=medium", t2)  # trivial default, unaffected

    def test_ultra_effort_rejected_cli_exits_one_naming_cause(self):
        plan = self._plan(PLAN_PASS)
        res = self._run(plan, extra_args=["--effort", "1=ultra"])
        self.assertEqual(res.returncode, 1, res.stderr)
        self.assertIn("ultra", res.stderr.lower())

    def test_unknown_task_number_rejected_cli_exits_one_naming_cause(self):
        plan = self._plan(PLAN_PASS)  # only task 1 exists
        res = self._run(plan, extra_args=["--effort", "99=max"])
        self.assertEqual(res.returncode, 1, res.stderr)
        self.assertIn("99", res.stderr)
