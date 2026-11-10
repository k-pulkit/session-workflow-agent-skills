#!/usr/bin/env python3
"""Local web UI for the session workflow files.

Renders the markdown under <root>/.claude/sessions as a small app: a
minimal dashboard (progress, journal tail, lessons due), file views, quiz
forms on explainers, answer boxes on draft markers, and lesson practice.
Deliberately thin — deeper learning tooling lives in the separate Session
Workbench app, not here. The markdown files stay the source of truth. The
UI writes only two things: quiz answer files (learnings/*.answers.md) and
`A:` lines in drafts, plus archive-only file moves.

Standard library only. Run:
    python3 session_ui.py --root /path/to/workspace [--port 8765]
"""

import argparse
import datetime
import json
import mimetypes
import os
import re
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

HERE = Path(__file__).resolve().parent
ROOT = Path.cwd()
SESSIONS = ROOT / ".claude" / "sessions"
DEFAULT_SESSION = ""

CORE_ORDER = ["Plan.md", "Design.md", "Journal.md", "Lessons.md", "reference.md", "Spec.md", "PlanDone.md", "DesignDone.md"]
MARKER = re.compile(r"\[(DECIDE|YOU)\]")
ANY_MARKER = re.compile(r"\[(DECIDE|YOU|ASSUME|VERIFY)\]")
STEP = re.compile(r"^\s*- \[( |x)\]", re.M)
STEP_TYPE = re.compile(r"^\s*- \[[ x]\].*?\[(build(?:\+hole)?|quick|spike)\]", re.M)


class BadRequest(Exception):
    """Raised for a request that names a path or file it may not use."""


def session_dir(name):
    """Resolves a session name to its folder, refusing anything outside SESSIONS."""
    base = SESSIONS.resolve()
    d = (base / name).resolve()
    if base not in d.parents or not (d / "Plan.md").is_file():
        raise BadRequest(f"unknown session: {name}")
    return d


def session_file(name, rel):
    """Resolves a file inside a session folder; path traversal is refused."""
    d = session_dir(name)
    f = (d / rel).resolve()
    if d not in f.parents:
        raise BadRequest(f"path outside session: {rel}")
    return f


def read(p):
    try:
        return p.read_text(encoding="utf-8")
    except FileNotFoundError:
        return ""


def find_sessions():
    if not SESSIONS.is_dir():
        return []
    names = []
    for plan in SESSIONS.rglob("Plan.md"):
        rel = plan.parent.relative_to(SESSIONS)
        if not {"drafts", "learnings", "lenses", "archive"} & set(rel.parts):
            names.append(rel.as_posix())
    return sorted(names)


def plan_stats(d):
    open_text, done_text = read(d / "Plan.md"), read(d / "PlanDone.md")
    steps = STEP.findall(open_text) + STEP.findall(done_text)
    types = {}
    for t in STEP_TYPE.findall(open_text + "\n" + done_text):
        types[t] = types.get(t, 0) + 1
    nxt = next((ln.strip()[6:] for ln in open_text.splitlines()
                if ln.strip().startswith("- [ ]")), "")
    return {"done": steps.count("x"), "total": len(steps), "types": types, "next": nxt}


def parse_lessons(text):
    today = datetime.date.today().isoformat()
    items, cur = [], None
    for line in text.splitlines():
        if line.startswith("### "):
            cur = {"head": line[4:].strip(), "q": "", "a": "", "next": "", "streak": ""}
            items.append(cur)
        elif cur is not None:
            if line.startswith("Q:"):
                cur["q"] = line[2:].strip()
            elif line.startswith("A:"):
                cur["a"] = line[2:].strip()
            elif line.startswith("Review:"):
                n = re.search(r"next (\d{4}-\d\d-\d\d)", line)
                s = re.search(r"streak (\d+)", line)
                cur["next"] = n[1] if n else ""
                cur["streak"] = s[1] if s else ""
    for it in items:
        it["due"] = bool(it["next"]) and it["next"] <= today
    return items


def list_files(d):
    def entries(sub, pattern):
        folder = d / sub
        if not folder.is_dir():
            return []
        out = []
        for f in sorted(folder.rglob(pattern)):
            if f.is_file() and not f.name.endswith(".answers.md") and "node_modules" not in f.parts:
                out.append({"path": f.relative_to(d).as_posix(), "mtime": f.stat().st_mtime})
        return sorted(out, key=lambda e: -e["mtime"])

    core = [n for n in CORE_ORDER if (d / n).is_file()]
    core += sorted(f.name for f in d.glob("*.md") if f.name not in CORE_ORDER)
    return {"core": core, "core_mtime": {n: (d / n).stat().st_mtime for n in core}, "learnings": entries("learnings", "*.md"),
            "drafts": entries("drafts", "*.md"), "lenses": entries("lenses", "*")[:60]}


def session_summary(name):
    d = session_dir(name)
    journal = [ln for ln in read(d / "Journal.md").splitlines() if ln.startswith("- [")]
    lessons = parse_lessons(read(d / "Lessons.md"))
    return {"name": name, "plan": plan_stats(d),
            "journal_tail": journal[-10:], "lessons": lessons,
            "lessons_due": sum(1 for x in lessons if x["due"]), "files": list_files(d)}


def answers_path(p):
    return p.with_name(p.name[:-3] + ".answers.md")


def save_answers(name, rel, answers):
    """Writes the user's quiz answers next to an explainer."""
    p = session_file(name, rel)
    if "learnings" not in Path(rel).parts or "## Quiz" not in read(p):
        raise BadRequest("answers can only be saved for an explainer with a ## Quiz section")
    stamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    lines = [f"# Answers — {p.stem}", f"Answered: {stamp}", ""]
    for i, a in enumerate(answers, 1):
        body = (a or "").strip().splitlines() or [""]
        lines.append(f"{i}. {body[0]}")
        lines += ["   " + b for b in body[1:]]
    answers_path(p).write_text("\n".join(lines) + "\n", encoding="utf-8")
    return answers_path(p).relative_to(session_dir(name)).as_posix()


def open_markers(text):
    """Count [DECIDE]/[YOU] markers with no non-empty `A:` answer (header lines before the first ## are legend)."""
    lines = text.split("\n")
    first = next((i for i, l in enumerate(lines) if l.startswith("## ")), len(lines))
    n = 0
    for k in range(first + 1, len(lines)):
        if not MARKER.search(re.sub(r"`[^`]*`", "", lines[k])):
            continue
        answered = False
        for j in range(k + 1, len(lines)):
            s = lines[j].strip()
            if s.startswith("#") or ANY_MARKER.search(lines[j]):
                break
            if s.startswith("A:"):
                answered = bool(s[2:].strip())
                break
            if not s and not (j + 1 < len(lines) and lines[j + 1].startswith((" ", "\t"))):
                break
        n += not answered
    return n


def archive_old_drafts(name, keep=10):
    """Moves drafts beyond the `keep` newest into archive/<date>/drafts/, never ones still in review.

    Runs only when the user clicks the button in the UI. Nothing is deleted; each move is listed in
    archive/<date>/MANIFEST.md.
    """
    d = session_dir(name)
    drafts = sorted((f for f in (d / "drafts").glob("*.md") if f.is_file()), key=lambda f: -f.stat().st_mtime)
    moved, skipped = [], []
    today = datetime.date.today().isoformat()
    dest_dir = d / "archive" / today / "drafts"
    for f in drafts[keep:]:
        if open_markers(read(f)):
            skipped.append(f"drafts/{f.name} (open markers)")
            continue
        dest_dir.mkdir(parents=True, exist_ok=True)
        dest, i = dest_dir / f.name, 1
        while dest.exists():
            dest, i = dest_dir / f"{f.stem}-{i}{f.suffix}", i + 1
        f.rename(dest)
        moved.append(f"drafts/{f.name} -> {dest.relative_to(d).as_posix()}")
    if moved:
        with (d / "archive" / today / "MANIFEST.md").open("a", encoding="utf-8") as m:
            stamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
            m.write(f"\n## {stamp} — archive old drafts (session-ui button; kept the {keep} newest)\n")
            m.writelines(f"- {x}\n" for x in moved)
    return moved, skipped


OWNED = {"Plan.md", "PlanDone.md", "Design.md", "DesignDone.md", "Journal.md", "Lessons.md", "reference.md"}


def trash_file(name, rel):
    """Soft delete from the UI: moves a draft or an unowned top-level file to archive/<date>/deleted/.

    Files owned by a workflow skill are refused. Nothing is erased; the move is listed in
    archive/<date>/MANIFEST.md, so the file can be moved back by hand.
    """
    d = session_dir(name)
    p = session_file(name, rel)
    parts = Path(rel).parts
    if not p.is_file() or not (parts[0] == "drafts" and len(parts) == 2 or len(parts) == 1):
        raise BadRequest("only drafts and top-level session files can be deleted here")
    if p.name in OWNED:
        raise BadRequest(f"{p.name} belongs to a workflow skill and cannot be deleted from the UI")
    today = datetime.date.today().isoformat()
    dest_dir = d / "archive" / today / "deleted" / Path(rel).parent
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest, i = dest_dir / p.name, 1
    while dest.exists():
        dest, i = dest_dir / f"{p.stem}-{i}{p.suffix}", i + 1
    p.rename(dest)
    with (d / "archive" / today / "MANIFEST.md").open("a", encoding="utf-8") as m:
        m.write(f"- {datetime.datetime.now():%Y-%m-%d %H:%M} deleted in session-ui: {rel} -> {dest.relative_to(d).as_posix()}\n")
    return dest.relative_to(d).as_posix()


def answer_marker(name, rel, line_no, orig, answer):
    """Inserts an `A:` line after the block of a [DECIDE]/[YOU] marker in a draft.

    The marker line must still match `orig`, so a draft edited since the page
    loaded is never written at the wrong place.
    """
    if not (rel.startswith("drafts/") and rel.endswith(".draft.md")):
        raise BadRequest("markers can only be answered in drafts/*.draft.md")
    p = session_file(name, rel)
    lines = read(p).split("\n")
    k = line_no - 1
    if not (0 <= k < len(lines)) or lines[k] != orig or not MARKER.search(orig):
        raise BadRequest("the draft changed since it was loaded; reload and try again")
    text = " ".join((answer or "").split())
    # The marker's block runs to the next blank line, heading or marker. An empty "A:" placeholder in it
    # (or right after a blank line, as list items with sub-bullets often have) is filled in place.
    j, empty = k + 1, None
    while j < len(lines) and not lines[j].lstrip().startswith("#") and not ANY_MARKER.search(lines[j]):
        s = lines[j].strip()
        if s.startswith("A:"):
            if s[2:].strip():
                raise BadRequest("this marker already has an answer; edit the draft to change it")
            empty = j
            break
        if not s and (j + 1 >= len(lines) or not lines[j + 1].startswith((" ", "\t"))):
            break
        j += 1
    if empty is not None:
        lines[empty] = re.match(r"\s*", lines[empty])[0] + f"A: {text}"
        p.write_text("\n".join(lines), encoding="utf-8")
        return
    indent = re.match(r"\s*", orig)[0]
    if re.match(r"\s*([-*+]|\d+\.)\s", orig):
        indent += "  "
    lines.insert(j, f"{indent}A: {text}")
    p.write_text("\n".join(lines), encoding="utf-8")


def vscode_prefix():
    distro = os.environ.get("WSL_DISTRO_NAME")
    return f"vscode://vscode-remote/wsl+{distro}" if distro else "vscode://file"


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def send(self, code, body, ctype="application/json"):
        data = body if isinstance(body, bytes) else (
            json.dumps(body) if ctype == "application/json" else body).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", ctype + ("; charset=utf-8" if "text" in ctype or "json" in ctype else ""))
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        u = urlparse(self.path)
        q = {k: v[0] for k, v in parse_qs(u.query).items()}
        try:
            if u.path in ("/", "/index.html"):
                return self.send(200, (HERE / "index.html").read_bytes(), "text/html")
            if u.path.startswith("/vendor/"):
                # Local copies of browser libraries (mermaid), so the page works offline and behind proxies.
                f = (HERE / "vendor" / Path(u.path).name).resolve()
                if f.parent != (HERE / "vendor").resolve() or not f.is_file():
                    raise BadRequest("no such vendor file")
                return self.send(200, f.read_bytes(), "text/javascript")
            if u.path == "/api/help":
                # help.md (diagrams, types, words) + the live tables from session-flow's help mode (single source).
                skill = read(Path.home() / ".claude" / "skills" / "session-flow" / "SKILL.md")
                skill = re.sub(r"\A---\n.*?\n---\n", "", skill, flags=re.S)
                keep = [sec for sec in re.split(r"(?m)^(?=\| Skill \| Use when \| Say \|)", skill)
                        if sec.startswith(("| Skill | Use when | Say |", "**Called for you:**"))]
                text = read(HERE / "help.md") + "\n\n" + "\n".join(keep)
                return self.send(200, {"text": text, "abs": str(HERE / "help.md")})
            if u.path == "/api/config":
                return self.send(200, {"root": str(ROOT), "vscode": vscode_prefix(), "session": DEFAULT_SESSION})
            if u.path == "/api/sessions":
                out = [{"name": n, "plan": plan_stats(SESSIONS / n)} for n in find_sessions()]
                return self.send(200, out)
            if u.path == "/api/session":
                return self.send(200, session_summary(q["s"]))
            if u.path == "/api/file":
                p = session_file(q["s"], q["p"])
                if not p.is_file():
                    raise BadRequest("no such file")
                res = {"text": read(p), "mtime": p.stat().st_mtime,
                       "abs": str(p), "answers": None}
                a = answers_path(p)
                if a.is_file():
                    res["answers"] = {"text": read(a), "mtime": a.stat().st_mtime}
                return self.send(200, res)
            if u.path == "/api/mtime":
                p = session_file(q["s"], q["p"])
                return self.send(200, {"mtime": p.stat().st_mtime if p.is_file() else 0})
            if u.path == "/raw":
                rel = q["p"]
                if Path(rel).parts[0] not in ("lenses", "learnings"):
                    raise BadRequest("raw view is for lenses/ and learnings/ only")
                p = session_file(q["s"], rel)
                ctype = mimetypes.guess_type(p.name)[0] or "text/plain"
                return self.send(200, p.read_bytes(), ctype)
            return self.send(404, {"error": "not found"})
        except (BadRequest, KeyError, FileNotFoundError) as e:
            return self.send(400, {"error": str(e)})

    def do_POST(self):
        u = urlparse(self.path)
        try:
            body = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))) or b"{}")
            if u.path == "/api/answers":
                saved = save_answers(body["s"], body["p"], body["answers"])
                return self.send(200, {"saved": saved})
            if u.path == "/api/trash":
                return self.send(200, {"moved_to": trash_file(body["s"], body["p"])})
            if u.path == "/api/archive-drafts":
                moved, skipped = archive_old_drafts(body["s"])
                return self.send(200, {"moved": moved, "skipped": skipped})
            if u.path == "/api/marker":
                answer_marker(body["s"], body["p"], int(body["line"]), body["orig"], body["answer"])
                return self.send(200, {"ok": True})
            return self.send(404, {"error": "not found"})
        except (BadRequest, KeyError, ValueError) as e:
            return self.send(400, {"error": str(e)})


def main():
    global ROOT, SESSIONS, DEFAULT_SESSION
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--root", default=os.getcwd(), help="workspace that holds .claude/sessions")
    ap.add_argument("--port", type=int, default=8765)
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--session", default="", help="session the page opens by default")
    args = ap.parse_args()
    ROOT = Path(args.root).resolve()
    SESSIONS = ROOT / ".claude" / "sessions"
    if not SESSIONS.is_dir():
        sys.exit(f"no .claude/sessions under {ROOT}")
    if args.session:
        if args.session not in find_sessions():
            sys.exit(f"unknown session: {args.session} (have: {', '.join(find_sessions())})")
        DEFAULT_SESSION = args.session
    server = ThreadingHTTPServer((args.host, args.port), Handler)
    print(f"session-ui: http://localhost:{args.port}  (root {ROOT}, default session {DEFAULT_SESSION or 'first'})", flush=True)
    server.serve_forever()


if __name__ == "__main__":
    main()
