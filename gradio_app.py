"""
DevOps Incident Response — Gradio UI
Matches the exact design shown in screenshots.
Variable MUST stay named `app` — server/app.py imports it.
"""

from __future__ import annotations
import time
import random
from typing import Generator
import gradio as gr

# ─────────────────────────────────────────────────────────────────────────────
# Task data
# ─────────────────────────────────────────────────────────────────────────────

TASKS = {
    "easy_task": {
        "label": "easy — Single Service Crash",
        "difficulty": "easy",
        "root": "api_gateway",
        "max_steps": 8,
        "description": "The API gateway has crashed. Diagnose from logs and restore with the correct fix.",
        "steps": [
            ("read_logs(api_gateway)",                   0.04, False),
            ("diagnose(api_gateway, service_crash)",     0.08, False),
            ("apply_fix(api_gateway, restart_service)",  0.12, False),
            ("verify_health(api_gateway)",               0.04, True),
        ],
        "score": 0.847,
        "grader": {"root_identification": 1.0, "resolution": 1.0, "efficiency": 1.0, "safety": 1.0},
    },
    "medium_task": {
        "label": "medium — Memory Leak in Order Service",
        "difficulty": "medium",
        "root": "order_service",
        "max_steps": 10,
        "description": "The order service is leaking memory, triggering OOM restarts and degraded checkout performance.",
        "steps": [
            ("read_logs(api_gateway)",                   0.03, False),
            ("inspect_dependencies(api_gateway)",        0.02, False),
            ("read_logs(order_service)",                 0.04, False),
            ("query_metrics(order_service)",             0.03, False),
            ("diagnose(order_service, memory_leak)",     0.08, False),
            ("apply_fix(order_service, memory_fix)",     0.12, False),
            ("verify_health(order_service)",             0.04, True),
        ],
        "score": 0.791,
        "grader": {"root_identification": 1.0, "resolution": 1.0, "efficiency": 0.85, "safety": 0.95},
    },
    "hard_task": {
        "label": "hard — Cascading DB Disk Saturation",
        "difficulty": "hard",
        "root": "database",
        "max_steps": 12,
        "description": "The database volume is full, causing cascading failures across payment, order, and API layers.",
        "steps": [
            ("read_logs(api_gateway)",                   0.03, False),
            ("inspect_dependencies(api_gateway)",        0.02, False),
            ("read_logs(payment_service)",               0.03, False),
            ("inspect_dependencies(order_service)",      0.02, False),
            ("read_logs(database)",                      0.04, False),
            ("query_metrics(database)",                  0.03, False),
            ("diagnose(database, disk_full)",            0.08, False),
            ("apply_fix(database, clear_disk)",          0.12, False),
            ("verify_health(database)",                  0.04, True),
        ],
        "score": 0.712,
        "grader": {"root_identification": 0.85, "resolution": 1.0, "efficiency": 0.72, "safety": 0.90},
    },
    "expert_task": {
        "label": "expert — Compound Multi-Root Failure",
        "difficulty": "expert",
        "root": "database + payment_service",
        "max_steps": 14,
        "description": "Two simultaneous root causes: disk saturation in database and connection pool exhaustion in payment_service.",
        "steps": [
            ("read_logs(api_gateway)",                                 0.03, False),
            ("inspect_dependencies(api_gateway)",                      0.02, False),
            ("read_logs(payment_service)",                             0.03, False),
            ("query_metrics(payment_service)",                         0.03, False),
            ("read_logs(database)",                                    0.04, False),
            ("diagnose(database, disk_full)",                          0.08, False),
            ("apply_fix(database, clear_disk)",                        0.12, False),
            ("diagnose(payment_service, connection_pool_exhaustion)",  0.08, False),
            ("apply_fix(payment_service, drain_connections)",          0.12, False),
            ("verify_health(database)",                                0.02, False),
            ("verify_health(payment_service)",                         0.04, True),
        ],
        "score": 0.658,
        "grader": {"root_identification": 0.80, "resolution": 1.0, "efficiency": 0.60, "safety": 0.85},
    },
}

MODEL = "Qwen/Qwen2.5-72B-Instruct"

# ─────────────────────────────────────────────────────────────────────────────
# CSS  — matches the screenshots exactly
# ─────────────────────────────────────────────────────────────────────────────

CSS = """
@import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;500;600&display=swap');

/* ── Hard reset ── */
*, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }

body, .gradio-container {
    background: #0f1117 !important;
    color: #e2e8f0 !important;
    font-family: 'IBM Plex Mono', 'Courier New', monospace !important;
}

/* Kill ALL Gradio chrome */
.gradio-container .block,
.gradio-container .form,
.gradio-container .wrap,
.gradio-container > .main,
.gradio-container > .main > .wrap {
    background: transparent !important;
    border: none !important;
    box-shadow: none !important;
    padding: 0 !important;
    gap: 0 !important;
}
footer { display: none !important; }

/* ── Card (dark bordered box) ── */
.card {
    background: #161b22;
    border: 1px solid #21262d;
    border-radius: 8px;
    overflow: hidden;
}

/* ── Card header row ── */
.card-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 10px 16px;
    border-bottom: 1px solid #21262d;
    font-size: 11px;
    letter-spacing: 0.08em;
    text-transform: uppercase;
    color: #6b7280;
}

/* ── Top navbar ── */
.navbar {
    background: #0d1117;
    border-bottom: 1px solid #21262d;
    padding: 12px 24px;
    display: flex;
    align-items: center;
    justify-content: space-between;
}
.navbar .brand {
    display: flex;
    align-items: center;
    gap: 10px;
}
.navbar .logo-box {
    width: 26px; height: 26px;
    background: #f85149;
    border-radius: 6px;
    display: flex; align-items: center; justify-content: center;
    font-size: 13px;
}
.navbar .brand-name {
    font-size: 13px; font-weight: 600; color: #e2e8f0;
}
.navbar .brand-sub {
    font-size: 10px; color: #6b7280; margin-top: 1px;
}
.navbar .right {
    display: flex; align-items: center; gap: 14px; font-size: 11px;
}
.live-dot {
    display: inline-flex; align-items: center; gap: 6px; color: #3fb950;
}
.live-dot::before {
    content: '';
    display: inline-block;
    width: 7px; height: 7px;
    border-radius: 50%; background: #3fb950;
}
.version-badge {
    border: 1px solid #30363d; border-radius: 5px;
    padding: 2px 8px; color: #8b949e; font-size: 10px;
}

/* ── Hero section ── */
.hero {
    padding: 48px 28px 36px;
    background: #0f1117;
    border-bottom: 1px solid #21262d;
}
.hero .eyebrow {
    font-size: 11px; font-weight: 500;
    letter-spacing: 0.1em; text-transform: uppercase;
    color: #f85149; margin-bottom: 14px;
}
.hero h1 {
    font-size: 40px; font-weight: 700; line-height: 1.15;
    color: #f0f6fc; margin-bottom: 18px;
    font-family: 'IBM Plex Mono', monospace !important;
}
.hero h1 span { color: #f85149; }
.hero .desc {
    font-size: 14px; line-height: 1.75; color: #8b949e;
    max-width: 520px; margin-bottom: 22px;
}
.hero .tags { display: flex; gap: 8px; flex-wrap: wrap; }
.hero .tag {
    font-size: 11px; color: #8b949e;
    border: 1px solid #30363d; border-radius: 5px;
    padding: 4px 12px; transition: color .2s, border-color .2s;
}
.hero .tag.active { color: #f85149; border-color: #f85149; }

/* ── Stat grid ── */
.stat-grid {
    display: grid;
    grid-template-columns: repeat(4, 1fr);
    gap: 14px;
    padding: 24px 28px;
    background: #0f1117;
    border-bottom: 1px solid #21262d;
}
.stat-card {
    background: #161b22;
    border: 1px solid #21262d;
    border-radius: 8px;
    padding: 16px 18px;
}
.stat-card .lbl {
    font-size: 10px; color: #6b7280;
    letter-spacing: 0.08em; text-transform: uppercase;
    margin-bottom: 6px;
}
.stat-card .val {
    font-size: 26px; font-weight: 600; color: #e2e8f0;
}
.stat-card .val.green { color: #3fb950; }

/* ── Simulation controls ── */
.sim-controls {
    display: flex; align-items: center; gap: 10px;
    padding: 16px 28px;
    background: #0f1117;
    border-bottom: 1px solid #21262d;
}

/* Gradio Dropdown overrides */
.gradio-container select,
.gradio-container .wrap select,
.gradio-container input[type=text] {
    background: #1c2128 !important;
    border: 1px solid #30363d !important;
    border-radius: 6px !important;
    color: #e2e8f0 !important;
    font-family: 'IBM Plex Mono', monospace !important;
    font-size: 12px !important;
    padding: 8px 12px !important;
}

/* Run simulation button */
button.primary, button.lg {
    background: #f85149 !important;
    border: none !important;
    border-radius: 6px !important;
    color: #fff !important;
    font-family: 'IBM Plex Mono', monospace !important;
    font-size: 12px !important; font-weight: 500 !important;
    padding: 9px 20px !important;
    cursor: pointer !important;
    transition: background .15s !important;
}
button.primary:hover, button.lg:hover {
    background: #da3633 !important;
}

/* Clear button */
button.secondary {
    background: transparent !important;
    border: 1px solid #30363d !important;
    border-radius: 6px !important;
    color: #8b949e !important;
    font-family: 'IBM Plex Mono', monospace !important;
    font-size: 12px !important;
    padding: 9px 20px !important;
    transition: border-color .15s, color .15s !important;
}
button.secondary:hover {
    border-color: #8b949e !important;
    color: #e2e8f0 !important;
}

/* ── Terminal window ── */
.terminal-wrap {
    margin: 0 28px 0;
    background: #161b22;
    border: 1px solid #21262d;
    border-radius: 8px;
    overflow: hidden;
}
.terminal-titlebar {
    background: #1c2128;
    border-bottom: 1px solid #21262d;
    padding: 8px 14px;
    display: flex; align-items: center; gap: 8px;
}
.terminal-dots { display: flex; gap: 5px; }
.tdot {
    width: 11px; height: 11px; border-radius: 50%;
}
.tdot-r { background: #f85149; }
.tdot-y { background: #e3b341; }
.tdot-g { background: #3fb950; }
.terminal-title {
    margin: 0 auto;
    font-size: 11px; color: #6b7280;
}

/* Override Gradio textbox to look like terminal */
#terminal-output textarea {
    background: #0d1117 !important;
    color: #8b949e !important;
    font-family: 'IBM Plex Mono', monospace !important;
    font-size: 12px !important;
    line-height: 1.8 !important;
    border: none !important;
    border-radius: 0 !important;
    padding: 16px 18px !important;
    box-shadow: none !important;
    resize: none !important;
}
#terminal-output label { display: none !important; }
#terminal-output .wrap { padding: 0 !important; }
#terminal-output { margin: 0 !important; }

/* ── Main content sections ── */
.content-area {
    padding: 24px 28px;
    background: #0f1117;
}

/* ── Task list (in Environment tab left column) ── */
.task-list-card { margin-bottom: 0; }
.task-item {
    display: flex;
    align-items: center;
    padding: 14px 16px;
    border-bottom: 1px solid #21262d;
    gap: 14px;
    transition: background .15s;
}
.task-item:last-child { border-bottom: none; }
.task-item:hover { background: rgba(255,255,255,0.02); }
.task-badge {
    font-size: 10px; font-weight: 600; padding: 3px 8px;
    border-radius: 5px; min-width: 52px; text-align: center;
    letter-spacing: 0.04em;
}
.badge-easy   { background: rgba(63,185,80,0.15);  color: #3fb950; border: 1px solid rgba(63,185,80,0.3); }
.badge-medium { background: rgba(227,179,65,0.15); color: #e3b341; border: 1px solid rgba(227,179,65,0.3); }
.badge-hard   { background: rgba(249,115,22,0.15); color: #f97316; border: 1px solid rgba(249,115,22,0.3); }
.badge-expert { background: rgba(248,81,73,0.15);  color: #f85149; border: 1px solid rgba(248,81,73,0.3); }

.task-item .tinfo { flex: 1; }
.task-item .tname { font-size: 14px; font-weight: 500; color: #e2e8f0; margin-bottom: 3px; }
.task-item .tsub  { font-size: 11px; color: #6b7280; }
.task-item .tdash { color: #30363d; font-size: 14px; }
.task-item .tline { width: 2px; height: 100%; background: #f85149; align-self: stretch; border-radius: 2px; }

/* ── Reward table ── */
.reward-row {
    display: flex; align-items: center;
    padding: 10px 16px;
    border-bottom: 1px solid #21262d;
    font-size: 12px; gap: 12px;
}
.reward-row:last-child { border-bottom: none; }
.rname  { font-weight: 600; color: #e2e8f0; min-width: 160px; }
.rdesc  { color: #6b7280; flex: 1; }
.rval-pos { background: rgba(63,185,80,0.12); color: #3fb950; padding: 3px 10px; border-radius: 4px; font-weight: 600; }
.rval-neg { background: rgba(248,81,73,0.12); color: #f85149; padding: 3px 10px; border-radius: 4px; font-weight: 600; }

/* ── Dependency graph nodes ── */
.dep-row { display: flex; align-items: center; flex-wrap: wrap; gap: 2px; margin-bottom: 8px; }
.dep-row:last-child { margin-bottom: 0; }
.dn {
    display: inline-block;
    padding: 4px 10px; border-radius: 5px; font-size: 11px;
    border: 1px solid; font-family: 'IBM Plex Mono', monospace;
    margin: 2px;
}
.dn-r { border-color: rgba(248,81,73,.5);  color: #f85149; background: rgba(248,81,73,.08); }
.dn-o { border-color: rgba(249,115,22,.5); color: #f97316; background: rgba(249,115,22,.08); }
.dn-y { border-color: rgba(227,179,65,.5); color: #e3b341; background: rgba(227,179,65,.08); }
.dn-b { border-color: rgba(56,139,253,.5); color: #58a6ff; background: rgba(56,139,253,.08); }
.dn-arr { color: #6b7280; font-size: 11px; margin: 0 2px; }
.dn-plus { color: #6b7280; font-size: 12px; margin: 0 2px; }

/* ── Grader weights bars ── */
.gw-row {
    display: flex; align-items: center; gap: 12px;
    padding: 8px 0; font-size: 11px; color: #8b949e;
}
.gw-label { min-width: 130px; }
.gw-bar-bg { flex: 1; height: 4px; background: #21262d; border-radius: 2px; }
.gw-bar-fill { height: 100%; border-radius: 2px; }
.gw-pct { min-width: 32px; text-align: right; }

/* ── API routes ── */
.api-row {
    display: flex; align-items: center;
    padding: 9px 16px; border-bottom: 1px solid #21262d;
    font-size: 12px;
}
.api-row:last-child { border-bottom: none; }
.api-method {
    font-size: 10px; font-weight: 600; padding: 2px 7px;
    border-radius: 4px; min-width: 38px; text-align: center;
    margin-right: 14px;
}
.mget  { background: rgba(63,185,80,0.12);  color: #3fb950; }
.mpost { background: rgba(56,139,253,0.12); color: #58a6ff; }
.api-path { color: #e2e8f0; font-weight: 500; min-width: 130px; }
.api-desc { color: #6b7280; margin-left: auto; }

/* ── Score bars (simulation tab) ── */
.score-row {
    display: flex; align-items: center; gap: 12px;
    margin-bottom: 14px; font-size: 11px; color: #8b949e;
}
.score-label { min-width: 150px; }
.score-bar-bg {
    flex: 1; height: 5px; background: #21262d; border-radius: 3px; overflow: hidden;
}
.score-bar-fill { height: 100%; border-radius: 3px; transition: width 1s ease; }
.score-num { min-width: 38px; text-align: right; color: #e2e8f0; font-weight: 500; }

/* ── Gradio tab overrides ── */
.tabs { background: transparent !important; }
.tab-nav {
    background: #0d1117 !important;
    border-bottom: 1px solid #21262d !important;
    padding: 0 28px !important;
    border-radius: 0 !important;
}
.tab-nav button {
    font-family: 'IBM Plex Mono', monospace !important;
    font-size: 12px !important;
    color: #6b7280 !important;
    background: transparent !important;
    border: none !important;
    padding: 12px 16px !important;
    letter-spacing: .03em !important;
    transition: color .2s !important;
}
.tab-nav button:hover { color: #8b949e !important; }
.tab-nav button.selected {
    color: #e2e8f0 !important;
    box-shadow: inset 0 -2px 0 #f85149 !important;
}

/* Spacing helpers */
.row { display: flex; gap: 16px; }
.col { flex: 1; min-width: 0; }
.mb16 { margin-bottom: 16px; }

/* label hiding */
label > span:first-child { display: none !important; }
"""

# ─────────────────────────────────────────────────────────────────────────────
# Static HTML blocks
# ─────────────────────────────────────────────────────────────────────────────

NAV_HTML = """
<div class="navbar">
  <div class="brand">
    <div class="logo-box">⬡</div>
    <div>
      <div class="brand-name">devops-incident-response</div>
      <div class="brand-sub">OpenEnv · RL Testbed</div>
    </div>
  </div>
  <div class="right">
    <span class="live-dot">&nbsp;API live</span>
    <span class="version-badge">v1.0.0</span>
  </div>
</div>
"""

HERO_HTML = """
<div class="hero">
  <div class="eyebrow">Meta PyTorch Hackathon &nbsp;·&nbsp; OpenEnv</div>
  <h1>SRE Triage <span>RL Environment</span></h1>
  <p class="desc">
    A deterministic reinforcement learning testbed that stress-tests AI agents on
    production-style incident response — dependency tracing, root-cause
    diagnosis, and safe remediation across four difficulty tiers.
  </p>
  <div class="tags">
    <span class="tag active">openenv</span>
    <span class="tag">devops</span>
    <span class="tag">reinforcement-learning</span>
    <span class="tag">ai-agents</span>
    <span class="tag">sre</span>
  </div>
</div>
"""

STAT_GRID_HTML = """
<div class="stat-grid">
  <div class="stat-card"><div class="lbl">Tasks</div><div class="val">4</div></div>
  <div class="stat-card"><div class="lbl">Services</div><div class="val">6</div></div>
  <div class="stat-card"><div class="lbl">Grader</div><div class="val green">DET</div></div>
  <div class="stat-card"><div class="lbl">Port</div><div class="val" style="font-size:20px">8000</div></div>
</div>
"""

TERM_HEADER_HTML = """
<div class="terminal-titlebar">
  <div class="terminal-dots">
    <span class="tdot tdot-r"></span>
    <span class="tdot tdot-y"></span>
    <span class="tdot tdot-g"></span>
  </div>
  <span class="terminal-title">inference.py — devops_incident_env</span>
</div>
"""

# Task list for Environment tab
TASK_LIST_HTML = """
<div class="card task-list-card">
  <div class="card-header">
    <span>Tasks</span>
    <span>4 scenarios</span>
  </div>

  <div class="task-item">
    <div style="width:3px;height:40px;background:#f85149;border-radius:2px;flex-shrink:0"></div>
    <span class="task-badge badge-easy">easy</span>
    <div class="tinfo">
      <div class="tname">Single Service Crash</div>
      <div class="tsub">api_gateway &nbsp;·&nbsp; max 8 steps</div>
    </div>
    <span class="tdash">—</span>
  </div>

  <div class="task-item">
    <div style="width:3px;height:40px;background:transparent;border-radius:2px;flex-shrink:0"></div>
    <span class="task-badge badge-medium">medium</span>
    <div class="tinfo">
      <div class="tname">Memory Leak in Order Service</div>
      <div class="tsub">order_service &nbsp;·&nbsp; max 10 steps</div>
    </div>
    <span class="tdash">—</span>
  </div>

  <div class="task-item">
    <div style="width:3px;height:40px;background:transparent;border-radius:2px;flex-shrink:0"></div>
    <span class="task-badge badge-hard">hard</span>
    <div class="tinfo">
      <div class="tname">Cascading DB Disk Saturation</div>
      <div class="tsub">database + payment + order &nbsp;·&nbsp; max 12 steps</div>
    </div>
    <span class="tdash">—</span>
  </div>

  <div class="task-item">
    <div style="width:3px;height:40px;background:transparent;border-radius:2px;flex-shrink:0"></div>
    <span class="task-badge badge-expert">expert</span>
    <div class="tinfo">
      <div class="tname">Compound Multi-Root Failure</div>
      <div class="tsub">database + payment_service &nbsp;·&nbsp; max 14 steps</div>
    </div>
    <span class="tdash">—</span>
  </div>
</div>
"""

REWARD_HTML = """
<div class="card mt16" style="margin-top:16px">
  <div class="card-header">
    <span>Reward System</span>
    <span>dense + final</span>
  </div>
  <div class="reward-row"><span class="rname">root investigation</span><span class="rdesc">inspecting the true failure service</span><span class="rval-pos">+0.04</span></div>
  <div class="reward-row"><span class="rname">affected service</span><span class="rdesc">tracing symptom dependencies</span><span class="rval-pos">+0.03</span></div>
  <div class="reward-row"><span class="rname">correct diagnosis</span><span class="rdesc">identifying the exact failure mode</span><span class="rval-pos">+0.08</span></div>
  <div class="reward-row"><span class="rname">correct fix</span><span class="rdesc">right remediation, right service</span><span class="rval-pos">+0.12</span></div>
  <div class="reward-row"><span class="rname">verification</span><span class="rdesc">confirmed recovery</span><span class="rval-pos">+0.04</span></div>
  <div class="reward-row"><span class="rname">invalid action</span><span class="rdesc">wrong, redundant, or destructive</span><span class="rval-neg">-0.03</span></div>
</div>
"""

DEP_GRAPH_HTML = """
<div class="card">
  <div class="card-header">
    <span>Service Dependency Graph</span>
  </div>
  <div style="padding:18px 16px">
    <div class="dep-row">
      <span class="dn dn-r">api_gateway</span>
      <span class="dn-arr">→</span>
      <span class="dn dn-o">auth_service</span>
      <span class="dn-plus">+</span>
      <span class="dn dn-o">order_service</span>
    </div>
    <div class="dep-row" style="margin-left:20px">
      <span class="dn dn-y">order_service</span>
      <span class="dn-arr">→</span>
      <span class="dn dn-y">payment_service</span>
      <span class="dn-plus">+</span>
      <span class="dn dn-b">database</span>
    </div>
    <div class="dep-row" style="margin-left:20px">
      <span class="dn dn-o">auth_service</span>
      <span class="dn-arr">→</span>
      <span class="dn dn-y">user_service</span>
      <span class="dn-arr">→</span>
      <span class="dn dn-b">database</span>
    </div>
    <div class="dep-row" style="margin-left:20px">
      <span class="dn dn-y">payment_service</span>
      <span class="dn-arr">→</span>
      <span class="dn dn-b">database</span>
    </div>
    <div style="margin-top:14px;padding-top:12px;border-top:1px solid #21262d;
                font-size:11px;color:#6b7280">
      Agents must trace root causes downstream, not patch surface symptoms.
    </div>
  </div>
</div>
"""

GRADER_HTML = """
<div class="card">
  <div class="card-header">
    <span>Grader Weights</span>
    <span>score: —</span>
  </div>
  <div style="padding:18px 16px;">
    <div class="gw-row">
      <span class="gw-label">root identification</span>
      <div class="gw-bar-bg"><div class="gw-bar-fill" style="width:35%;background:#f85149"></div></div>
      <span class="gw-pct">35%</span>
    </div>
    <div class="gw-row">
      <span class="gw-label">resolution</span>
      <div class="gw-bar-bg"><div class="gw-bar-fill" style="width:30%;background:#f97316"></div></div>
      <span class="gw-pct">30%</span>
    </div>
    <div class="gw-row">
      <span class="gw-label">efficiency</span>
      <div class="gw-bar-bg"><div class="gw-bar-fill" style="width:20%;background:#e3b341"></div></div>
      <span class="gw-pct">20%</span>
    </div>
    <div class="gw-row">
      <span class="gw-label">safety</span>
      <div class="gw-bar-bg"><div class="gw-bar-fill" style="width:15%;background:#3fb950"></div></div>
      <span class="gw-pct">15%</span>
    </div>
    <div style="margin-top:14px;padding-top:12px;border-top:1px solid #21262d;
                font-size:11px;color:#6b7280">
      Final score clamped strictly within (0.001, 0.999)
    </div>
  </div>
</div>
"""

ROUTES_HTML = """
<div class="card" style="margin-bottom:0">
  <div class="card-header">
    <span>API Routes</span>
    <span>port 8000</span>
  </div>
  <div class="api-row"><span class="api-method mget">GET</span><span class="api-path">/</span><span class="api-desc">environment manifest</span></div>
  <div class="api-row"><span class="api-method mget">GET</span><span class="api-path">/health</span><span class="api-desc">liveness check</span></div>
  <div class="api-row"><span class="api-method mget">GET</span><span class="api-path">/tasks</span><span class="api-desc">list all task definitions</span></div>
  <div class="api-row"><span class="api-method mpost">POST</span><span class="api-path">/reset</span><span class="api-desc">start episode [task_id, seed]</span></div>
  <div class="api-row"><span class="api-method mpost">POST</span><span class="api-path">/step</span><span class="api-desc">execute action → observation + reward</span></div>
  <div class="api-row"><span class="api-method mget">GET</span><span class="api-path">/state</span><span class="api-desc">full environment state</span></div>
  <div class="api-row"><span class="api-method mget">GET</span><span class="api-path">/grader</span><span class="api-desc">deterministic episode score</span></div>
  <div class="api-row"><span class="api-method mget">GET</span><span class="api-path">/baseline</span><span class="api-desc">rule-based baseline action</span></div>
  <div class="api-row"><span class="api-method mget">GET</span><span class="api-path">/sample_action</span><span class="api-desc">example valid action payload</span></div>
</div>
"""

FOOTER_HTML = """
<div style="border-top:1px solid #21262d;padding:16px 28px;
            display:flex;align-items:center;justify-content:space-between;
            font-size:11px;color:#6b7280;margin-top:24px">
  <span>devops-incident-response &nbsp;·&nbsp; OpenEnv &nbsp;·&nbsp; aryanosh</span>
  <div style="display:flex;gap:20px">
    <a href="https://github.com/aryanosh/devops-incident-response" target="_blank"
       style="color:#6b7280;text-decoration:none">GitHub</a>
    <a href="/tasks" style="color:#6b7280;text-decoration:none">Tasks JSON</a>
    <a href="/" style="color:#6b7280;text-decoration:none">Manifest</a>
  </div>
</div>
"""

# ─────────────────────────────────────────────────────────────────────────────
# Dynamic HTML builders
# ─────────────────────────────────────────────────────────────────────────────

def make_score_bars_html(task_key: str) -> str:
    g = TASKS[task_key]["grader"]
    score = TASKS[task_key]["score"]
    bars = [
        ("root identification", g["root_identification"], "#f85149"),
        ("resolution",          g["resolution"],          "#f97316"),
        ("efficiency",          g["efficiency"],          "#e3b341"),
        ("safety",              g["safety"],              "#3fb950"),
    ]
    rows = ""
    for label, val, color in bars:
        pct = int(val * 100)
        rows += f"""
        <div class="score-row">
          <span class="score-label">{label}</span>
          <div class="score-bar-bg">
            <div class="score-bar-fill" style="width:{pct}%;background:{color}"></div>
          </div>
          <span class="score-num">{pct}%</span>
        </div>"""
    return f"""
    <div class="card" style="margin-top:16px">
      <div class="card-header">
        <span>Grader Breakdown</span>
        <span style="color:#e2e8f0;font-weight:600">score: {score:.3f}</span>
      </div>
      <div style="padding:16px">
        {rows}
        <div style="margin-top:12px;padding-top:10px;border-top:1px solid #21262d;
                    font-size:10px;color:#6b7280">
          Final score clamped strictly within (0.001, 0.999)
        </div>
      </div>
    </div>"""


def update_task_info(task_key: str) -> tuple:
    task = TASKS[task_key]
    diff = task["difficulty"]
    colors = {"easy": "#3fb950", "medium": "#e3b341", "hard": "#f97316", "expert": "#f85149"}
    bgs    = {"easy": "rgba(63,185,80,.15)", "medium": "rgba(227,179,65,.15)",
              "hard": "rgba(249,115,22,.15)", "expert": "rgba(248,81,73,.15)"}
    c = colors[diff]; bg = bgs[diff]
    info_html = f"""
    <div class="card" style="margin-bottom:16px">
      <div class="card-header">
        <span>Selected Task</span>
        <span style="color:{c};background:{bg};padding:2px 10px;border-radius:5px;font-size:10px;font-weight:600">{diff}</span>
      </div>
      <div style="padding:16px">
        <div style="font-size:15px;font-weight:600;color:#e2e8f0;margin-bottom:6px">
          {task['label'].split(' — ')[1]}
        </div>
        <div style="font-size:12px;color:#8b949e;margin-bottom:12px;line-height:1.7">
          {task['description']}
        </div>
        <div style="display:flex;gap:20px;font-size:10px;color:#6b7280">
          <span>root: <span style="color:#e2e8f0">{task['root']}</span></span>
          <span>max steps: <span style="color:#e2e8f0">{task['max_steps']}</span></span>
          <span>optimal: <span style="color:#e2e8f0">{len(task['steps'])}</span></span>
        </div>
      </div>
    </div>"""
    return info_html, make_score_bars_html(task_key)


def build_task_card(key: str, task: dict) -> str:
    diff = task["difficulty"]
    colors = {"easy": "#3fb950", "medium": "#e3b341", "hard": "#f97316", "expert": "#f85149"}
    bgs    = {"easy": "rgba(63,185,80,.15)", "medium": "rgba(227,179,65,.15)",
              "hard": "rgba(249,115,22,.15)", "expert": "rgba(248,81,73,.15)"}
    c = colors[diff]; bg = bgs[diff]

    steps_html = ""
    for i, (action, reward, done) in enumerate(task["steps"]):
        rc = "#3fb950" if reward > 0 else "#f85149"
        steps_html += f"""
        <div style="display:flex;align-items:center;padding:7px 0;
                    border-bottom:1px solid #21262d;font-size:11px">
          <span style="color:#6b7280;min-width:24px">{i+1:02d}</span>
          <span style="color:#8b949e;flex:1">{action}</span>
          <span style="color:{rc};font-weight:500">+{reward:.2f}</span>
        </div>"""

    return f"""
    <div class="card" style="margin-bottom:16px">
      <div class="card-header">
        <span>{key}</span>
        <span style="color:{c};background:{bg};padding:2px 10px;border-radius:5px;font-size:10px;font-weight:600">{diff}</span>
      </div>
      <div style="padding:16px">
        <div style="font-size:14px;font-weight:600;color:#e2e8f0;margin-bottom:6px">
          {task['label'].split(' — ')[1]}
        </div>
        <div style="font-size:12px;color:#8b949e;margin-bottom:12px;line-height:1.7">
          {task['description']}
        </div>
        <div style="display:flex;gap:20px;font-size:10px;color:#6b7280;margin-bottom:12px">
          <span>root: <span style="color:#e2e8f0">{task['root']}</span></span>
          <span>max_steps: <span style="color:#e2e8f0">{task['max_steps']}</span></span>
          <span>score: <span style="color:{c}">{task['score']:.3f}</span></span>
        </div>
        <div style="font-size:10px;color:#6b7280;text-transform:uppercase;letter-spacing:.08em;margin-bottom:4px">
          Optimal trace
        </div>
        {steps_html}
      </div>
    </div>"""


# ─────────────────────────────────────────────────────────────────────────────
# Simulation
# ─────────────────────────────────────────────────────────────────────────────

def run_simulation(task_key: str) -> Generator:
    task   = TASKS[task_key]
    steps  = task["steps"]
    score  = task["score"]
    buf    = ""

    def _yield():
        return buf, make_score_bars_html(task_key)

    buf += f"$ python inference.py --task {task_key}\n"
    yield _yield(); time.sleep(0.3)

    buf += f"[START] task={task_key} env=devops_incident_env model={MODEL}\n"
    yield _yield(); time.sleep(0.25)

    rewards = []
    for i, (action, reward, done) in enumerate(steps, 1):
        time.sleep(0.35 + random.random() * 0.2)
        buf += f"[STEP] step={i} action={action} reward={reward:.2f} done={'true' if done else 'false'} error=null\n"
        rewards.append(reward)
        yield _yield()

    time.sleep(0.35)
    buf += f"[END] success=true steps={len(steps)} rewards={','.join(f'{r:.2f}' for r in rewards)}\n"
    yield _yield()

    time.sleep(0.25)
    buf += f"grader score: {score:.3f}\n"
    yield _yield()


def clear_terminal(task_key: str) -> tuple:
    return "$ python inference.py  # select a task and click Run\n", make_score_bars_html(task_key)


# ─────────────────────────────────────────────────────────────────────────────
# Gradio app  –  variable MUST be named `app`
# ─────────────────────────────────────────────────────────────────────────────

with gr.Blocks(css=CSS, title="DevOps Incident Response — OpenEnv") as app:

    gr.HTML(NAV_HTML)
    gr.HTML(HERO_HTML)
    gr.HTML(STAT_GRID_HTML)

    with gr.Tabs():

        # ══ Simulation ═══════════════════════════════════════════════════════
        with gr.Tab("Simulation"):

            with gr.Row():
                task_dd = gr.Dropdown(
                    choices=[(v["label"], k) for k, v in TASKS.items()],
                    value="easy_task",
                    label="", scale=3,
                )
                run_btn   = gr.Button("Run simulation", variant="primary", scale=1)
                clear_btn = gr.Button("Clear",          variant="secondary", scale=1)

            task_info = gr.HTML(update_task_info("easy_task")[0])

            # Terminal window: header + textbox
            gr.HTML(TERM_HEADER_HTML)
            terminal = gr.Textbox(
                value="$ python inference.py  # select a task and click Run\n",
                lines=14, max_lines=14, interactive=False,
                elem_id="terminal-output", label="",
            )

            score_html = gr.HTML(make_score_bars_html("easy_task"))

            task_dd.change(fn=update_task_info, inputs=task_dd, outputs=[task_info, score_html])
            run_btn.click(fn=run_simulation, inputs=task_dd, outputs=[terminal, score_html])
            clear_btn.click(fn=clear_terminal, inputs=task_dd, outputs=[terminal, score_html])

        # ══ Environment ══════════════════════════════════════════════════════
        with gr.Tab("Environment"):
            with gr.Row():
                with gr.Column():
                    gr.HTML(TASK_LIST_HTML)
                    gr.HTML(REWARD_HTML)
                with gr.Column():
                    gr.HTML(DEP_GRAPH_HTML)
                    gr.HTML(GRADER_HTML)
            gr.HTML(ROUTES_HTML)

        # ══ Tasks ════════════════════════════════════════════════════════════
        with gr.Tab("Tasks"):
            for key, task in TASKS.items():
                gr.HTML(build_task_card(key, task))

    gr.HTML(FOOTER_HTML)


if __name__ == "__main__":
    app.launch()
