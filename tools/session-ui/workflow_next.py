#!/usr/bin/env python3
"""Stateless rules for the session-workflow build loop: "where am I" -> "what's next".

Encodes the loop once, in code, so a session-* skill does not re-derive the
stage rules from memory of a long CLAUDE.md each turn. Reads and writes
nothing: no file, no session path, no events.jsonl. Pure function of its
input JSON to its output JSON.

    workflow_next.py '{"type": "build", "stage": "SPEC", "event": "go"}'
    echo '{"type": "quick", "stage": "BUILD", "event": "done", "behavior_change": false}' | workflow_next.py

Input fields:
  type   "build" | "quick" | "spike"   (required)
  stage  current stage name. Omit on the very first call for this step;
         defaults to SPEC for build, BUILD for quick/spike.
  event  what just happened. Omit (or use "enter") to ask what's required at
         the current stage without advancing it.
  has_logic        build/SPEC only: does this step touch real logic (decides
                   whether a hole is required). Default false.
  behavior_change  quick/BUILD "done" only: default true.
  more_batches     build/REVIEW "commit" only: another batch still to review.
                   Default false (this is the last batch).

Output fields: ok, stage (always a string; "" when `type` itself was invalid,
since there's no stage machine to place it in), required_now (list; non-empty
at SPEC, REVIEW, DEBUG, and on arrival at CLOSE — at BUILD, it's empty, so
check valid_next_events there instead), message, valid_next_events. A bad
(type, stage, event) combination returns ok: false with the same stage, an
error, and the events that *would* have been valid, so the caller can
self-correct instead of guessing.

This is advisory, not a hard gate: nothing in Claude Code forces a skill to
call this script, or to obey a nonzero exit if it does. Its job is removing
the chance the rules are misremembered or quietly reinterpreted under
pressure, not making skipping impossible.

Standard library only, matching every other tool in this folder.
"""

import json
import sys

STAGES = {
    "build": ["SPEC", "BUILD", "REVIEW", "DEBUG", "CLOSE"],
    "quick": ["BUILD", "CLOSE"],
    "spike": ["BUILD", "CLOSE"],
}
DEFAULT_START = {"build": "SPEC", "quick": "BUILD", "spike": "BUILD"}


def _spec_required(has_logic):
    req = ["design_questions(1-2)", "file_plan"]
    if has_logic:
        req.append("hole: name a 10-40 line unit, give it a failing test")
    return req


def _result(ok, stage, required_now, message, valid_next_events, error=None):
    out = {"ok": ok, "stage": stage, "required_now": required_now, "message": message,
           "valid_next_events": valid_next_events}
    if error is not None:
        out["error"] = error
    return out


def step(data):
    """One transition. `data` is the parsed input dict. Returns the output dict."""
    wf_type = data.get("type")
    if wf_type not in STAGES:
        return _result(False, data.get("stage") or "", [], f"unknown type {wf_type!r}; use build, quick or spike.",
                        [], error="bad_type")

    stage = data.get("stage") or DEFAULT_START[wf_type]
    if stage not in STAGES[wf_type]:
        return _result(False, stage, [], f"unknown stage {stage!r} for type {wf_type}.", [],
                        error="bad_stage")

    event = data.get("event") or "enter"

    if wf_type == "build":
        return _step_build(stage, event, data)
    if wf_type == "quick":
        return _step_quick(stage, event, data)
    return _step_spike(stage, event, data)


def _step_build(stage, event, data):
    has_logic = bool(data.get("has_logic", False))

    if stage == "SPEC":
        if event == "enter":
            return _result(True, "SPEC", _spec_required(has_logic),
                            "Answer the design questions and name the file plan"
                            + (" and the hole." if has_logic else "."),
                            ["go"])
        if event == "go":
            return _result(True, "BUILD", [],
                            "Write everything except the hole (if any); stub it with a red test. "
                            "Call again with event=hole_filled, hole_waived, no_hole, or fail.",
                            ["hole_filled", "hole_waived", "no_hole", "fail"])
        return _result(False, "SPEC", [], f"event {event!r} does not fit stage SPEC.", ["go"],
                        error="bad_event")

    if stage == "BUILD":
        if event == "enter":
            return _result(True, "BUILD", [], "Waiting on the hole (if any) and the tests.",
                            ["hole_filled", "hole_waived", "no_hole", "fail"])
        if event in ("hole_filled", "hole_waived", "no_hole"):
            return _result(True, "REVIEW", ["trace_question"],
                            "Stage a batch (≤~300 code lines), then give a 3-line summary plus one "
                            "trace question anchored to a real line. Call again with event=batch_ready.",
                            ["batch_ready"])
        if event == "fail":
            return _result(True, "DEBUG", ["user_guess_first"],
                            "A test failed. The user guesses the cause first; the fix follows the hole "
                            "rule (the user writes it inside the hole, the agent writes it elsewhere). "
                            "Call again with event=cause_found.",
                            ["cause_found"])
        return _result(False, "BUILD", [], f"event {event!r} does not fit stage BUILD.",
                        ["hole_filled", "hole_waived", "no_hole", "fail"], error="bad_event")

    if stage == "DEBUG":
        if event == "enter":
            return _result(True, "DEBUG", ["user_guess_first"],
                            "Get the user's first guess at the cause before showing any evidence.",
                            ["cause_found"])
        if event == "cause_found":
            return _result(True, "BUILD", [], "Resume building.",
                            ["hole_filled", "hole_waived", "no_hole", "fail"])
        return _result(False, "DEBUG", ["user_guess_first"], f"event {event!r} does not fit stage DEBUG.",
                        ["cause_found"], error="bad_event")

    if stage == "REVIEW":
        if event == "enter":
            return _result(True, "REVIEW", ["trace_question"],
                            "Stage a batch and give its trace question. Call again with event=batch_ready.",
                            ["batch_ready", "commit"])
        if event == "batch_ready":
            return _result(True, "REVIEW", ["trace_question"],
                            "Ask the trace question in chat, then call again with event=commit.",
                            ["commit"])
        if event == "commit":
            more = bool(data.get("more_batches", False))
            if more:
                return _result(True, "REVIEW", ["trace_question"],
                                "Batch committed. Stage the next batch and give its trace question. "
                                "Call again with event=batch_ready.",
                                ["batch_ready"])
            return _result(True, "CLOSE", ["journal_line", "plan_checkoff"],
                            "Last batch committed. Write the Journal.md line and check off the Plan.md step.",
                            [])
        return _result(False, "REVIEW", ["trace_question"], f"event {event!r} does not fit stage REVIEW.",
                        ["batch_ready", "commit"], error="bad_event")

    if stage == "CLOSE":
        return _result(False, "CLOSE", [], "Step is already closed; nothing more to call here.", [],
                        error="already_closed")

    return _result(False, stage, [], f"no rule for build/{stage}.", [], error="no_rule")


def _step_quick(stage, event, data):
    if stage == "BUILD":
        if event == "enter":
            return _result(True, "BUILD", [], "Build from the Plan.md step text.", ["done"])
        if event == "done":
            behavior_change = bool(data.get("behavior_change", True))
            if behavior_change:
                return _result(True, "CLOSE", ["tests_pass"], "Run the tests; report the result.", [])
            return _result(True, "CLOSE", ["proof"],
                            "No behavior change: give one proof instead (build passes, tests unchanged, "
                            "AST/asset hash identical).", [])
        return _result(False, "BUILD", [], f"event {event!r} does not fit quick/BUILD.", ["done"],
                        error="bad_event")
    if stage == "CLOSE":
        return _result(False, "CLOSE", [], "Step is already closed; nothing more to call here.", [],
                        error="already_closed")
    return _result(False, stage, [], f"no rule for quick/{stage}.", [], error="no_rule")


def _step_spike(stage, event, data):
    if stage == "BUILD":
        if event == "enter":
            return _result(True, "BUILD", [], "Throwaway code against the time box.", ["timebox_up"])
        if event == "timebox_up":
            return _result(True, "CLOSE", ["findings_list"],
                            "Write the findings list; session-plan re-plans from it. The code is not merged.",
                            [])
        return _result(False, "BUILD", [], f"event {event!r} does not fit spike/BUILD.", ["timebox_up"],
                        error="bad_event")
    if stage == "CLOSE":
        return _result(False, "CLOSE", [], "Step is already closed; nothing more to call here.", [],
                        error="already_closed")
    return _result(False, stage, [], f"no rule for spike/{stage}.", [], error="no_rule")


def main(argv):
    raw = argv[1] if len(argv) > 1 else sys.stdin.read()
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as e:
        print(json.dumps({"ok": False, "error": f"bad json: {e}"}))
        return 1
    out = step(data)
    print(json.dumps(out, indent=2))
    return 0 if out["ok"] else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
