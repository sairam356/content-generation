"""Stub `claude` for testing the Studio UI without credits: prints Claude Code stream-json for a fake /edit run.
Use:  STUDIO_CLAUDE=studio/dev/fake_claude.py python -m studio      (FAKE_SPEED=0.1 to run faster)"""
import json, os, sys, time, uuid

SP = float(os.environ.get("FAKE_SPEED", "1"))
prompt = sys.argv[sys.argv.index("-p") + 1] if "-p" in sys.argv else "/edit"
kind = prompt.split()[0].lstrip("/")
out = sys.stdout


def ev(d):
    out.write(json.dumps(d, ensure_ascii=False) + "\n"); out.flush()


def text(t):
    ev({"type": "assistant", "message": {"role": "assistant", "content": [{"type": "text", "text": t}]}})


def tool(name, inp, result, err=False, secs=0.6):
    tid = "toolu_" + uuid.uuid4().hex[:12]
    ev({"type": "assistant", "message": {"role": "assistant", "content": [{"type": "tool_use", "id": tid, "name": name, "input": inp}]}})
    time.sleep(secs * SP)
    ev({"type": "user", "message": {"role": "user", "content": [{"type": "tool_result", "tool_use_id": tid, "content": result, "is_error": err}]}})


def panel(rnd, fail_one=False):
    ids = {}
    for a in ["designer", "taste", "end-viewer", "compliance", "reach", "comparison"]:
        tid = "toolu_" + uuid.uuid4().hex[:12]; ids[a] = tid
        ev({"type": "assistant", "message": {"content": [{"type": "tool_use", "id": tid, "name": "Agent",
            "input": {"subagent_type": a, "model": "fable", "description": f"{a} r{rnd}", "prompt": "Review ready/demo.mp4 ..."}}]}})
    for a, tid in ids.items():
        time.sleep(1.2 * SP)
        err = fail_one and a == "comparison"
        body = "Error: model fable unavailable" if err else f"VERDICT: {'PASS' if rnd == 2 else 'FIX'} - {a} notes: hook ok, bg 4 off-topic." 
        ev({"type": "user", "message": {"content": [{"type": "tool_result", "tool_use_id": tid, "content": body, "is_error": err}]}})
    if fail_one:
        tool("Agent", {"subagent_type": "comparison", "model": "opus", "description": f"comparison r{rnd} (opus fallback)", "prompt": "..."},
             "VERDICT: PASS - format matches references", secs=1.0)
    tool("Agent", {"subagent_type": "reviewer", "model": "fable", "description": f"reviewer r{rnd}", "prompt": "merge"},
         f"VERDICT: {'SHIP WITH OWNER NOTES' if rnd == 2 else 'FIX FIRST'} - gates: 11/11 PASS" if rnd == 2 else "VERDICT: FIX FIRST - gates 9/11; actions: regen bg 4, 7; move hook start", secs=1.5)


ev({"type": "system", "subtype": "init", "session_id": uuid.uuid4().hex, "model": "claude-opus-5-5", "tools": ["Bash", "Agent"]})
text(f"Running {prompt}")
if kind == "edit":
    tool("Read", {"file_path": "memory/style.md"}, "ok")
    tool("Bash", {"command": "python -m pipeline transcribe inbox/demo/demo.mp4"}, "words.json written: 143 words, 6 silences", secs=2)
    tool("Write", {"file_path": "inbox/demo/plan.json"}, "ok")
    tool("Bash", {"command": "python -m pipeline compose inbox/demo/plan.json"}, "ready/demo.mp4 46.4s\nready/demo.mp4", secs=3)
    tool("Bash", {"command": "python -m pipeline review ready/demo.mp4"}, "review/report.json", secs=1)
    panel(1, fail_one=True)
    text("Round 1: 2 gates fail. Regenerating bg 4 and 7, moving hook start.")
    tool("Bash", {"command": "del build\\bg_4* build\\bg_7* && python -m pipeline compose inbox/demo/plan.json"}, "ready/demo.mp4", secs=3)
    tool("Bash", {"command": "python -m pipeline review ready/demo.mp4"}, "review/report.json", secs=1)
    panel(2)
    tool("Bash", {"command": "python -m pipeline verify ready/demo.mp4"}, "OK full decode 46.4s", secs=1)
    tool("mcp__claude_ai_Canva__create_design", {"title": "demo thumb"}, "design DAHx created (private)", secs=2)
    tool("mcp__claude_ai_Canva__export_design", {"format": "jpg"}, "exported ready/demo.jpg", secs=2)
    text("READY: ready/demo.mp4 (46.4 s). Thumbnail layout: topic. Owner notes: listen to the CTA.")
elif kind == "scout":
    tool("Bash", {"command": f"python -m pipeline watch {prompt.split()[1]}"}, ".state/refs/abc/analysis.json", secs=2)
    # real Claude Code launches these in the background: the tool_result is only "launched", the verdict comes
    # later as a <task-notification> user message
    launched = []
    for a, verdict in (("taste", "VERDICT: yes-with-changes - premium enough"), ("reach", "VERDICT: yes - hook travels")):
        tid, aid = "toolu_" + uuid.uuid4().hex[:12], uuid.uuid4().hex[:17]
        ev({"type": "assistant", "message": {"content": [{"type": "tool_use", "id": tid, "name": "Agent",
            "input": {"subagent_type": a, "model": "fable", "description": f"{a} r1 scout", "prompt": "..."}}]}})
        ev({"type": "user", "message": {"role": "user", "content": [{"type": "tool_result", "tool_use_id": tid, "content": [{"type": "text",
            "text": f"Async agent launched successfully. (internal metadata)\nagentId: {aid}\nThe agent is working in the background."}]}]}})
        launched.append((tid, aid, a, verdict))
    text("While the agents run, I'm reading the policy file myself.")
    time.sleep(SP * 2)
    for tid, aid, a, verdict in launched:
        ev({"type": "user", "message": {"role": "user", "content": f"<task-notification>\n<task-id>{aid}</task-id>\n<tool-use-id>{tid}</tool-use-id>"
            f"\n<status>completed</status>\n<summary>Agent \"{a} r1 scout\" finished</summary>\n<result>{verdict}\n\nDetails...</result>\n</task-notification>"}})
        time.sleep(SP)
    text("WHAT: a 40 s facts Short about pressure cookers.\nWHY VIRAL: a number in the hook.\nDO WE MAKE IT? yes-with-changes: our angle = the 1679 Papin story.\nCOMPLIANCE: no flags.\nNext: /script pressure cooker whistle 120°")
elif kind == "topics":
    tool("Bash", {"command": "python -m pipeline channels"}, ".state/channels.json", secs=2)
    for i in range(1, 3):
        tool("Write", {"file_path": f"topics/2026-11-09/0{i}-demo/script.json"}, "ok")
        tool("Bash", {"command": f"python -m pipeline teleprompter topics/2026-11-09/0{i}-demo/script.json"}, "teleprompter.html", secs=1)
    panel(1)
    text("| # | idea | hook |\n|1| demo | ... |")
else:
    text("done")
ev({"type": "result", "subtype": "success", "is_error": False, "result": "done", "num_turns": 12, "total_cost_usd": 0.0})
