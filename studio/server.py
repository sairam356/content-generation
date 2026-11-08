"""Telugu Shorts Studio - local web UI over the existing skills and folders.

    python -m studio            (or studio.ps1)  ->  http://localhost:8787

Every action runs `claude -p "/skill ..."` exactly like watch-inbox.ps1, but with `--output-format stream-json`
so the page can show each tool call, each specialist agent and the final result live. Nothing is uploaded anywhere;
the server only reads/writes topics/, inbox/, ready/ and .state/studio/.
"""
from __future__ import annotations

import asyncio, json, os, re, shutil, subprocess, sys, threading, time, uuid
from collections import deque
from datetime import datetime
from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, StreamingResponse

ROOT = Path(__file__).resolve().parent.parent
STATE = ROOT / ".state" / "studio"
JOBS_DIR = STATE / "jobs"
for d in (ROOT / "inbox", ROOT / "ready", ROOT / "topics", JOBS_DIR):
    d.mkdir(parents=True, exist_ok=True)

AGENTS = ["designer", "taste", "end-viewer", "compliance", "reach", "comparison", "reviewer"]
TOOLS_ALL = ("Bash,Read,Write,Edit,Glob,Grep,Agent,WebSearch,WebFetch,"
             "mcp__claude_ai_Canva,mcp__claude_ai_Google_Drive,mcp__claude-in-chrome")
SKILLS = {  # kind -> (needs chrome, stage list shown in the UI)
    "edit":    (True,  ["transcribe", "plan", "render", "panel", "fixes", "verify", "thumbnail"]),
    "scout":   (False, ["watch", "analyse", "panel", "verdict"]),
    "topics":  (False, ["research", "scripts", "panel", "teleprompters"]),
    "script":  (False, ["research", "script", "panel", "teleprompter"]),
    "publish": (True,  ["compliance", "metadata", "pack"]),
}
STAGE_PATTERNS = [  # (regex on "<tool> <command/path>", stage) - first match wins
    (r"pipeline transcribe", "transcribe"),
    (r"pipeline (watch|inspect)", "watch"),
    (r"pipeline compose|fetch_bg", "render"),
    (r"pipeline review", "panel"),
    (r"pipeline verify", "verify"),
    (r"pipeline teleprompter", "teleprompters"),
    (r"^(Write|Edit) \S*plan\.json", "plan"),
    (r"mcp__claude_ai_Canva", "thumbnail"),
]


def _now() -> float:
    return time.time()


def _claude_cmd() -> list[str]:
    stub = os.environ.get("STUDIO_CLAUDE")  # dev: path to a stub that prints stream-json
    if stub:
        return [sys.executable, stub] if stub.endswith(".py") else [stub]
    exe = shutil.which("claude")
    if not exe:
        raise RuntimeError("claude CLI not found on PATH")
    return [exe]


class Job:
    def __init__(self, kind: str, prompt: str, label: str, meta: dict | None = None):
        self.id = datetime.now().strftime("%Y%m%d-%H%M%S") + "-" + kind
        self.kind, self.prompt, self.label = kind, prompt, label
        self.meta = meta or {}
        self.status = "running"            # running | success | failed
        self.started, self.ended = _now(), None
        self.stage = ""
        self.stages = {s: "pending" for s in SKILLS.get(kind, (False, []))[1]}
        self.round = 1
        self.agents: dict[str, dict] = {}  # "taste r1" -> {...}
        self.tools: dict[str, dict] = {}   # tool_use_id -> {name, agent, started}
        self.log: deque[str] = deque(maxlen=4000)
        self.events: list[dict] = []
        self.result_text = ""
        self.last_text = ""
        self.error = ""
        self.outputs: dict = {}
        self.subscribers: set[asyncio.Queue] = set()
        self.loop: asyncio.AbstractEventLoop | None = None

    # ---- state -> dict -------------------------------------------------------------------------------------------
    def snapshot(self, with_log: bool = False) -> dict:
        d = {"id": self.id, "kind": self.kind, "label": self.label, "prompt": self.prompt, "status": self.status,
             "started": self.started, "ended": self.ended, "stage": self.stage, "stages": self.stages,
             "round": self.round, "agents": self.agents, "result_text": self.result_text, "error": self.error,
             "outputs": self.outputs, "meta": self.meta}
        if with_log:
            d["log"] = list(self.log)
        return d

    def emit(self, ev: dict) -> None:
        ev["t"] = _now()
        self.events.append(ev)
        if self.loop:
            for q in list(self.subscribers):
                self.loop.call_soon_threadsafe(q.put_nowait, ev)

    def logline(self, line: str) -> None:
        line = line.rstrip()
        if not line:
            return
        self.log.append(line)
        self.emit({"type": "log", "line": line[:600]})

    def set_stage(self, stage: str) -> None:
        if stage not in self.stages:
            return
        for s in self.stages:
            if self.stages[s] == "running":
                self.stages[s] = "done"
        self.stages[stage] = "running"
        self.stage = stage
        self.emit({"type": "stage", "stage": stage, "stages": self.stages})

    def on_stage_hint(self, stage: str) -> None:
        """Map a pipeline step to the UI stage, tracking review rounds (render -> panel -> fixes -> panel ...)."""
        panel_seen = self.stages.get("panel") in ("done", "running")
        if stage == "render" and panel_seen and "fixes" in self.stages:
            stage = "fixes"
        if stage == "panel" and self.stages.get("panel") == "done":
            self.round += 1
        self.set_stage(stage)

    # ---- stream-json parsing -------------------------------------------------------------------------------------
    def handle(self, d: dict) -> None:
        t = d.get("type")
        if t == "system":
            self.logline(f"[claude] session {d.get('session_id', '')[:8]} model={d.get('model', '')}")
            return
        if t == "result":
            res = (d.get("result") or "").strip()
            self.result_text = (res if len(res) > 60 else (self.last_text or res))[:20000]
            if d.get("is_error") or d.get("subtype") not in (None, "success"):
                self.error = self.error or f"claude ended with {d.get('subtype')}"
            self.logline(f"[claude] result: {d.get('subtype')} turns={d.get('num_turns')} cost=${d.get('total_cost_usd', 0):.2f}")
            return
        msg = d.get("message") or {}
        content = msg.get("content")
        if isinstance(content, str):
            content = [{"type": "text", "text": content}]
        if not isinstance(content, list):
            return
        for c in content:
            if not isinstance(c, dict):
                continue
            ct = c.get("type")
            if ct == "text" and t == "assistant" and c.get("text", "").strip():
                self.last_text = c["text"].strip()
                for ln in c["text"].strip().splitlines()[:12]:
                    self.logline("  " + ln)
            elif ct == "tool_use":
                self.on_tool_use(c)
            elif ct == "tool_result":
                self.on_tool_result(c)

    def on_tool_use(self, c: dict) -> None:
        name, inp, tid = c.get("name", ""), c.get("input") or {}, c.get("id", "")
        if name in ("Agent", "Task"):
            agent = (inp.get("subagent_type") or "agent").lower()
            desc = inp.get("description") or ""
            m = re.search(r"\br(\d)\b", desc + " " + (inp.get("prompt") or "")[:200])
            rnd = int(m.group(1)) if m else self.round
            key = f"{agent} r{rnd}"
            if key in self.agents:  # re-dispatch (e.g. Fable -> Opus fallback): keep the failed card visible
                key = f"{key} #{sum(1 for k in self.agents if k.startswith(f'{agent} r{rnd}')) + 1}"
            self.agents[key] = {"agent": agent, "round": rnd, "status": "running", "started": _now(), "ended": None,
                                "model": inp.get("model") or "", "desc": desc[:120], "verdict": ""}
            self.tools[tid] = {"name": name, "agent": key, "started": _now()}
            if agent in AGENTS and self.stages.get("panel") != "running":
                self.on_stage_hint("panel")
            self.logline(f"[agent] {key} started ({inp.get('model') or 'default'}) - {desc}")
            self.emit({"type": "agent", "key": key, "data": self.agents[key]})
            return
        self.tools[tid] = {"name": name, "agent": None, "started": _now()}
        text = ""
        if name == "Bash":
            text = (inp.get("command") or "").replace("\n", " ")
        elif name in ("Read", "Write", "Edit", "Glob", "Grep"):
            text = inp.get("file_path") or inp.get("pattern") or ""
        elif name.startswith("mcp__"):
            text = json.dumps({k: v for k, v in inp.items() if k in ("design_id", "designId", "title", "format")})[:160]
        else:
            text = json.dumps(inp)[:160]
        probe = f"{name} {text}"
        for pat, stage in STAGE_PATTERNS:
            if re.search(pat, probe):
                self.on_stage_hint(stage)
                break
        self.logline(f"[{name}] {text[:300]}")

    def on_tool_result(self, c: dict) -> None:
        tid = c.get("tool_use_id", "")
        meta = self.tools.pop(tid, None)
        body = c.get("content")
        if isinstance(body, list):
            body = "\n".join(x.get("text", "") for x in body if isinstance(x, dict))
        body = str(body or "")
        err = bool(c.get("is_error"))
        if meta and meta.get("agent"):
            a = self.agents.get(meta["agent"])
            if a:
                a["status"] = "failed" if err else "done"
                a["ended"] = _now()
                a["verdict"] = _verdict(body)
                a["report"] = body[:6000]
                self.logline(f"[agent] {meta['agent']} {'FAILED' if err else 'done'} in {a['ended'] - a['started']:.0f}s: {a['verdict']}")
                self.emit({"type": "agent", "key": meta["agent"], "data": a})
            return
        if err:
            self.logline(f"[tool error] {body[:300]}")
            self.emit({"type": "tool_error", "text": body[:300]})
        elif meta and meta["name"] == "Bash" and body.strip():
            tail = body.strip().splitlines()[-1]
            self.logline(f"    -> {tail[:240]}")


def _verdict(text: str) -> str:
    for pat in (r"(?im)^\W*(verdict|overall|gate[s]?)\b[^\n]*", r"(?im)^\W*(ship|pass|fail|block)[^\n]*"):
        m = re.search(pat, text)
        if m:
            return m.group(0).strip()[:200]
    first = next((ln.strip() for ln in text.splitlines() if ln.strip()), "")
    return first[:200]


class Runner:
    def __init__(self) -> None:
        self.jobs: dict[str, Job] = {}
        self.current: Job | None = None
        self.load_history()

    def load_history(self) -> None:
        for f in sorted(JOBS_DIR.glob("*.json")):
            try:
                d = json.loads(f.read_text(encoding="utf-8"))
                j = Job(d["kind"], d["prompt"], d["label"], d.get("meta"))
                j.id, j.status, j.started, j.ended = d["id"], d["status"], d["started"], d["ended"]
                j.stage, j.stages, j.round, j.agents = d["stage"], d["stages"], d["round"], d["agents"]
                j.result_text, j.error, j.outputs = d.get("result_text", ""), d.get("error", ""), d.get("outputs", {})
                j.log.extend(d.get("log", []))
                if j.status == "running":
                    j.status, j.error = "failed", "server restarted while running"
                self.jobs[j.id] = j
            except Exception as e:  # noqa: BLE001
                print("[studio] bad job file", f, e)

    def save(self, j: Job) -> None:
        (JOBS_DIR / f"{j.id}.json").write_text(json.dumps(j.snapshot(with_log=True), ensure_ascii=False), encoding="utf-8")

    def start(self, kind: str, args: str, label: str, meta: dict | None = None) -> Job:
        if self.current and self.current.status == "running":
            raise HTTPException(409, f"a job is already running: {self.current.id}")
        prompt = f"/{kind} {args}".strip()
        job = Job(kind, prompt, label, meta)
        job.loop = asyncio.get_event_loop()
        self.jobs[job.id] = job
        self.current = job
        threading.Thread(target=self._run, args=(job,), daemon=True).start()
        return job

    def _run(self, job: Job) -> None:
        chrome, _ = SKILLS.get(job.kind, (False, []))
        try:
            cmd = _claude_cmd()
        except RuntimeError as e:
            job.status, job.error, job.ended = "failed", str(e), _now()
            job.emit({"type": "done", "job": job.snapshot()}); self.save(job); return
        if not os.environ.get("STUDIO_CLAUDE"):
            cmd += ["--model", "opus", "-p", job.prompt, "--output-format", "stream-json", "--verbose",
                    "--permission-mode", "acceptEdits", "--allowedTools", TOOLS_ALL,
                    "--disallowedTools", "mcp__plugin_playwright_playwright"]
            if chrome:
                cmd.insert(1, "--chrome")
        else:
            cmd += ["-p", job.prompt]
        env = dict(os.environ, PYTHONUTF8="1", PYTHONIOENCODING="utf-8")
        venv = ROOT / ".venv" / ("Scripts" if os.name == "nt" else "bin")
        if venv.exists():
            env["PATH"] = str(venv) + os.pathsep + env.get("PATH", "")
        job.logline(f"[studio] $ {' '.join(cmd[:1])} {job.prompt}")
        job.emit({"type": "job", "job": job.snapshot()})
        try:
            proc = subprocess.Popen(cmd, cwd=str(ROOT), env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                    text=True, encoding="utf-8", errors="replace", bufsize=1)
        except OSError as e:
            job.status, job.error, job.ended = "failed", f"could not start claude: {e}", _now()
            job.emit({"type": "done", "job": job.snapshot()}); self.save(job); return
        job.meta["pid"] = proc.pid

        def pump_err():
            for line in proc.stderr:  # type: ignore[union-attr]
                job.logline("[stderr] " + line)
        threading.Thread(target=pump_err, daemon=True).start()
        last_save = _now()
        for line in proc.stdout:  # type: ignore[union-attr]
            line = line.strip()
            if not line:
                continue
            try:
                d = json.loads(line)
            except json.JSONDecodeError:
                job.logline(line); continue
            try:
                job.handle(d)
            except Exception as e:  # noqa: BLE001
                job.logline(f"[studio] parse error: {e}")
            if _now() - last_save > 10:
                self.save(job); last_save = _now()
        code = proc.wait()
        job.ended = _now()
        for s, v in job.stages.items():
            if v == "running":
                job.stages[s] = "done"
        for a in job.agents.values():
            if a["status"] == "running":
                a["status"], a["ended"] = "failed", _now()
        if job.kind == "edit":
            self._collect_edit(job)
        elif job.kind == "topics":
            job.outputs["topics"] = _latest_topics_date()
        if code != 0 and not job.error:
            job.error = f"claude exited with code {code}"
        job.status = "failed" if job.error else "success"
        job.logline(f"[studio] {job.status.upper()} in {job.ended - job.started:.0f}s" + (f": {job.error}" if job.error else ""))
        job.emit({"type": "done", "job": job.snapshot()})
        self.save(job)

    def _collect_edit(self, job: Job) -> None:
        vids = sorted((ROOT / "ready").glob("*.mp4"), key=lambda p: p.stat().st_mtime, reverse=True)
        vid = next((v for v in vids if v.stat().st_mtime > job.started - 60), None)
        if not vid:
            job.error = job.error or "no new video in ready/"; return
        job.set_stage("verify")
        py = sys.executable
        venv_py = ROOT / ".venv" / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
        if venv_py.exists():
            py = str(venv_py)
        r = subprocess.run([py, "-m", "pipeline", "verify", str(vid)], cwd=str(ROOT), capture_output=True, text=True,
                           encoding="utf-8", errors="replace", env=dict(os.environ, PYTHONUTF8="1"))
        job.logline(f"[verify] exit={r.returncode} {(r.stdout or r.stderr).strip()[-300:]}")
        job.stages["verify"] = "done"
        job.outputs["video"] = vid.name
        job.outputs["verified"] = r.returncode == 0
        if r.returncode != 0:
            job.error = "pipeline verify failed"
        if job.stages.get("thumbnail") == "pending":
            job.stages["thumbnail"] = "done" if (vid.with_suffix(".jpg")).exists() else "pending"


def _latest_topics_date() -> str:
    ds = sorted(p.name for p in (ROOT / "topics").iterdir() if p.is_dir() and re.match(r"\d{4}-\d{2}-\d{2}", p.name))
    return ds[-1] if ds else ""


# ---- app ---------------------------------------------------------------------------------------------------------
app = FastAPI(title="Telugu Shorts Studio")
runner = Runner()


@app.get("/", response_class=HTMLResponse)
def index() -> str:
    return (Path(__file__).parent / "index.html").read_text(encoding="utf-8")


@app.get("/files/{path:path}")
def files(path: str):
    p = (ROOT / path).resolve()
    allowed = [ROOT / "topics", ROOT / "ready", ROOT / "inbox", ROOT / ".state"]
    if not any(str(p).startswith(str(a.resolve())) for a in allowed) or not p.is_file():
        raise HTTPException(404)
    return FileResponse(str(p))


@app.get("/api/topics")
def api_topics():
    out = []
    for day in sorted((ROOT / "topics").iterdir(), reverse=True):
        if not day.is_dir():
            continue
        ideas = []
        for idea in sorted(day.iterdir()):
            sj = idea / "script.json"
            if not idea.is_dir() or not sj.exists():
                continue
            try:
                s = json.loads(sj.read_text(encoding="utf-8"))
            except Exception:  # noqa: BLE001
                s = {}
            ideas.append({"folder": f"topics/{day.name}/{idea.name}", "slug": idea.name,
                          "title": s.get("title_te") or s.get("title") or idea.name,
                          "hook": (s.get("hook") or s.get("hook_te") or (s.get("beats") or [{}])[0].get("text_te", "") or "")[:160],
                          "category": s.get("category", ""), "channel_style": s.get("channel_style") or s.get("style", ""),
                          "approved": bool(s.get("approved")), "seconds": s.get("target_seconds") or s.get("duration_sec"),
                          "teleprompter": (idea / "teleprompter.html").exists(), "audio": (idea / "teleprompter.mp3").exists(),
                          "script_md": (idea / "script.md").exists(), "done": bool(s.get("recorded") or s.get("done"))})
        readme = day / "README.md"
        out.append({"date": day.name, "readme": f"topics/{day.name}/README.md" if readme.exists() else None, "ideas": ideas})
    return out


@app.get("/api/ready")
def api_ready():
    out = []
    for v in sorted((ROOT / "ready").glob("*.mp4"), key=lambda p: p.stat().st_mtime, reverse=True):
        base = v.with_suffix("")
        md = base.with_suffix(".md")
        ver = Path(str(base) + ".verify.json")
        vj = None
        if ver.exists():
            try:
                vj = json.loads(ver.read_text(encoding="utf-8"))
            except Exception:  # noqa: BLE001
                vj = None
        out.append({"name": v.stem, "video": f"ready/{v.name}", "size": v.stat().st_size, "mtime": v.stat().st_mtime,
                    "thumb": f"ready/{base.name}.jpg" if base.with_suffix(".jpg").exists() else None,
                    "thumb_wide": f"ready/{base.name}_wide.jpg" if Path(str(base) + "_wide.jpg").exists() else None,
                    "md": md.read_text(encoding="utf-8", errors="replace") if md.exists() else "",
                    "verify": vj})
    return out


@app.get("/api/jobs")
def api_jobs():
    return [j.snapshot() for j in sorted(runner.jobs.values(), key=lambda j: j.started, reverse=True)]


@app.get("/api/jobs/{jid}")
def api_job(jid: str):
    j = runner.jobs.get(jid)
    if not j:
        raise HTTPException(404)
    return j.snapshot(with_log=True)


@app.get("/api/jobs/{jid}/events")
async def api_job_events(jid: str):
    j = runner.jobs.get(jid)
    if not j:
        raise HTTPException(404)

    async def gen():
        yield f"data: {json.dumps({'type': 'job', 'job': j.snapshot(with_log=True)}, ensure_ascii=False)}\n\n"
        if j.status != "running":
            yield f"data: {json.dumps({'type': 'done', 'job': j.snapshot()}, ensure_ascii=False)}\n\n"
            return
        q: asyncio.Queue = asyncio.Queue()
        j.loop = asyncio.get_event_loop()
        j.subscribers.add(q)
        try:
            while True:
                try:
                    ev = await asyncio.wait_for(q.get(), timeout=15)
                except asyncio.TimeoutError:
                    yield ": ping\n\n"; continue
                yield f"data: {json.dumps(ev, ensure_ascii=False)}\n\n"
                if ev.get("type") == "done":
                    return
        finally:
            j.subscribers.discard(q)
    return StreamingResponse(gen(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@app.post("/api/run")
async def api_run(body: dict):
    kind = body.get("kind", "")
    if kind not in SKILLS:
        raise HTTPException(400, f"unknown kind {kind}")
    args = (body.get("args") or "").strip()
    if kind in ("scout",) and not re.match(r"^https?://\S+$", args):
        raise HTTPException(400, "scout needs one URL")
    label = body.get("label") or f"/{kind} {args}"[:80]
    j = runner.start(kind, args, label, body.get("meta"))
    return j.snapshot()


@app.post("/api/upload")
async def api_upload(file: UploadFile = File(...), script: str = Form(""), layout: str = Form("")):
    ext = Path(file.filename or "rec.mp4").suffix.lower() or ".mp4"
    if ext not in (".mp4", ".mov", ".mkv", ".m4v", ".webm"):
        raise HTTPException(400, "video files only (mp4/mov/mkv/m4v/webm)")
    name = re.sub(r"[^\w-]+", "-", Path(file.filename or "recording").stem).strip("-") or "recording"
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    job_dir = ROOT / "inbox" / f"{stamp}-{name}"
    job_dir.mkdir(parents=True, exist_ok=True)
    rec = job_dir / f"{name}{ext}"
    with rec.open("wb") as f:
        while chunk := await file.read(1 << 20):
            f.write(chunk)
    args = f"inbox/{job_dir.name}/{rec.name}"
    if script:
        if " " in script or not (ROOT / script).exists():
            raise HTTPException(400, f"script not found: {script}")
        args += f" {script}"
    if layout:
        args += f" --layout {layout}"
    j = runner.start("edit", args, f"edit {rec.name}", {"recording": args.split()[0], "script": script, "layout": layout})
    return j.snapshot()


@app.get("/api/health")
def api_health():
    try:
        claude = " ".join(_claude_cmd())
    except RuntimeError as e:
        claude = f"MISSING: {e}"
    return {"root": str(ROOT), "claude": claude, "running": runner.current.id if runner.current and runner.current.status == "running" else None}


def main() -> None:
    import uvicorn
    port = int(os.environ.get("STUDIO_PORT", "8787"))
    print(f"[studio] {ROOT} -> http://localhost:{port}")
    uvicorn.run(app, host="127.0.0.1", port=port, log_level="warning")


if __name__ == "__main__":
    main()
