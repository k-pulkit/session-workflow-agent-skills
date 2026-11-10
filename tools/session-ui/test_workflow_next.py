#!/usr/bin/env python3
"""Tests for workflow_next.py. Run: python3 -m unittest test_workflow_next -v"""

import unittest

from workflow_next import step


class BuildLoop(unittest.TestCase):
    def test_spec_enter_no_logic(self):
        out = step({"type": "build", "stage": "SPEC", "event": "enter"})
        self.assertTrue(out["ok"])
        self.assertEqual(out["stage"], "SPEC")
        self.assertNotIn("hole: name a 10-40 line unit, give it a failing test", out["required_now"])

    def test_spec_enter_has_logic_requires_hole(self):
        out = step({"type": "build", "stage": "SPEC", "event": "enter", "has_logic": True})
        self.assertTrue(any("hole" in r for r in out["required_now"]))

    def test_spec_go_moves_to_build(self):
        out = step({"type": "build", "stage": "SPEC", "event": "go"})
        self.assertTrue(out["ok"])
        self.assertEqual(out["stage"], "BUILD")

    def test_spec_rejects_commit_before_go(self):
        out = step({"type": "build", "stage": "SPEC", "event": "commit"})
        self.assertFalse(out["ok"])
        self.assertEqual(out["stage"], "SPEC")
        self.assertEqual(out["error"], "bad_event")

    def test_build_enter_does_not_advance(self):
        out = step({"type": "build", "stage": "BUILD", "event": "enter"})
        self.assertTrue(out["ok"])
        self.assertEqual(out["stage"], "BUILD")
        self.assertEqual(out["required_now"], [])

    def test_build_hole_filled_moves_to_review(self):
        out = step({"type": "build", "stage": "BUILD", "event": "hole_filled"})
        self.assertTrue(out["ok"])
        self.assertEqual(out["stage"], "REVIEW")
        self.assertIn("trace_question", out["required_now"])

    def test_build_hole_waived_and_no_hole_also_move_to_review(self):
        for ev in ("hole_waived", "no_hole"):
            out = step({"type": "build", "stage": "BUILD", "event": ev})
            self.assertEqual(out["stage"], "REVIEW", ev)

    def test_build_fail_moves_to_debug(self):
        out = step({"type": "build", "stage": "BUILD", "event": "fail"})
        self.assertTrue(out["ok"])
        self.assertEqual(out["stage"], "DEBUG")
        self.assertIn("user_guess_first", out["required_now"])

    def test_debug_enter_does_not_advance(self):
        out = step({"type": "build", "stage": "DEBUG", "event": "enter"})
        self.assertTrue(out["ok"])
        self.assertEqual(out["stage"], "DEBUG")
        self.assertIn("user_guess_first", out["required_now"])

    def test_debug_cause_found_returns_to_build(self):
        out = step({"type": "build", "stage": "DEBUG", "event": "cause_found"})
        self.assertTrue(out["ok"])
        self.assertEqual(out["stage"], "BUILD")

    def test_debug_rejects_other_events(self):
        out = step({"type": "build", "stage": "DEBUG", "event": "commit"})
        self.assertFalse(out["ok"])
        self.assertEqual(out["stage"], "DEBUG")

    def test_review_enter_does_not_advance(self):
        out = step({"type": "build", "stage": "REVIEW", "event": "enter"})
        self.assertTrue(out["ok"])
        self.assertEqual(out["stage"], "REVIEW")
        self.assertIn("trace_question", out["required_now"])

    def test_review_batch_ready_stays_in_review_with_trace_question(self):
        out = step({"type": "build", "stage": "REVIEW", "event": "batch_ready"})
        self.assertTrue(out["ok"])
        self.assertEqual(out["stage"], "REVIEW")
        self.assertIn("trace_question", out["required_now"])

    def test_review_commit_more_batches_loops_back(self):
        out = step({"type": "build", "stage": "REVIEW", "event": "commit", "more_batches": True})
        self.assertTrue(out["ok"])
        self.assertEqual(out["stage"], "REVIEW")
        self.assertEqual(out["valid_next_events"], ["batch_ready"])

    def test_review_commit_last_batch_closes(self):
        out = step({"type": "build", "stage": "REVIEW", "event": "commit"})
        self.assertTrue(out["ok"])
        self.assertEqual(out["stage"], "CLOSE")
        self.assertIn("journal_line", out["required_now"])
        self.assertIn("plan_checkoff", out["required_now"])

    def test_close_rejects_further_calls(self):
        out = step({"type": "build", "stage": "CLOSE", "event": "commit"})
        self.assertFalse(out["ok"])
        self.assertEqual(out["error"], "already_closed")


class QuickLoop(unittest.TestCase):
    def test_default_start_is_build(self):
        out = step({"type": "quick", "event": "enter"})
        self.assertEqual(out["stage"], "BUILD")

    def test_done_behavior_change_requires_tests(self):
        out = step({"type": "quick", "stage": "BUILD", "event": "done", "behavior_change": True})
        self.assertTrue(out["ok"])
        self.assertEqual(out["stage"], "CLOSE")
        self.assertEqual(out["required_now"], ["tests_pass"])

    def test_done_no_behavior_change_requires_proof(self):
        out = step({"type": "quick", "stage": "BUILD", "event": "done", "behavior_change": False})
        self.assertEqual(out["required_now"], ["proof"])

    def test_done_defaults_to_behavior_change_true(self):
        out = step({"type": "quick", "stage": "BUILD", "event": "done"})
        self.assertEqual(out["required_now"], ["tests_pass"])


class SpikeLoop(unittest.TestCase):
    def test_timebox_up_closes_with_findings(self):
        out = step({"type": "spike", "stage": "BUILD", "event": "timebox_up"})
        self.assertTrue(out["ok"])
        self.assertEqual(out["stage"], "CLOSE")
        self.assertEqual(out["required_now"], ["findings_list"])


class BadInput(unittest.TestCase):
    def test_unknown_type(self):
        out = step({"type": "nope"})
        self.assertFalse(out["ok"])
        self.assertEqual(out["error"], "bad_type")
        self.assertEqual(out["stage"], "")  # always a string, never null

    def test_unknown_stage(self):
        out = step({"type": "build", "stage": "NOPE"})
        self.assertFalse(out["ok"])
        self.assertEqual(out["error"], "bad_stage")


if __name__ == "__main__":
    unittest.main()
