"""Plan parsing, task ordering, and --effort override parsing."""
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


class ParseEffortOverridesTests(unittest.TestCase):
    """parse_effort_overrides: repeatable --effort N=LEVEL entries -> {int: str}.
    Malformed entries and disallowed levels (including 'ultra') raise naming the
    cause; task-number existence is validated later, against the parsed plan."""

    def test_parses_single_override(self):
        overrides = forge_run.parse_effort_overrides(["3=max"])
        self.assertEqual(overrides, {3: "max"})

    def test_parses_multiple_overrides(self):
        overrides = forge_run.parse_effort_overrides(["1=low", "2=xhigh"])
        self.assertEqual(overrides, {1: "low", 2: "xhigh"})

    def test_empty_or_none_yields_empty_dict(self):
        self.assertEqual(forge_run.parse_effort_overrides([]), {})
        self.assertEqual(forge_run.parse_effort_overrides(None), {})

    def test_malformed_entry_raises_naming_cause(self):
        with self.assertRaises(RuntimeError) as ctx:
            forge_run.parse_effort_overrides(["nope"])
        self.assertIn("nope", str(ctx.exception))

    def test_ultra_rejected_naming_cause(self):
        with self.assertRaises(RuntimeError) as ctx:
            forge_run.parse_effort_overrides(["1=ultra"])
        msg = str(ctx.exception)
        self.assertIn("ultra", msg)

    def test_unknown_level_rejected_naming_cause(self):
        with self.assertRaises(RuntimeError) as ctx:
            forge_run.parse_effort_overrides(["1=bogus"])
        self.assertIn("bogus", str(ctx.exception))
