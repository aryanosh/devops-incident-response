from __future__ import annotations

import time
import random
from typing import Generator

import gradio as gr

# ── Simulated task data ──────────────────────────────────────────────────────

TASKS = {
    "easy_task": {
        "label": "easy — Single Service Crash",
        "difficulty": "easy",
        "root": "api_gateway",
        "max_steps": 8,
        "description": "The API gateway has crashed. Diagnose from logs and restore with the correct fix.",
        "steps": [
            ("read_logs(api_gateway)",                    0.04, False),
            ("diagnose(api_gateway, service_crash)",      0.08, False),
            ("apply_fix(api_gateway, restart_service)",   0.12, False),
            ("verify_health(api_gateway)",                0.04, True),
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
            ("read_logs(api_gateway)",                      0.03, False),
            ("inspect_dependencies(api_gateway)",           0.02, False),
            ("read_logs(order_service)",                    0.04, False),
            ("query_metrics(order_service)",                0.03, False),
            ("diagnose(order_service, memory_leak)",        0.08, False),
            ("apply_fix(order_service, memory_fix)",        0.12, False),
            ("verify_health(order_service)",                0.04, True),
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
            ("read_logs(api_gateway)",                    0.03, False),
            ("inspect_dependencies(api_gateway)",         0.02, False),
            ("read_logs(payment_service)",                0.03, False),
            ("inspect_dependencies(order_service)",       0.02, False),
            ("read_logs(database)",                       0.04, False),
            ("query_metrics(database)",                   0.03, False),
            ("diagnose(database, disk_full)",             0.08, False),
            ("apply_fix(database, clear_disk)",           0.12, False),
            ("verify_health(database)",                   0.04, True),
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
            ("read_logs(api_gateway)",                                    0.03, False),
            ("inspect_dependencies(api_gateway)",                         0.02, False),
            ("read_logs(payment_service)",                                0.03, False),
            ("query_metrics(payment_service)",                            0.03, False),
            ("read_logs(database)",                                       0.04, False),
            ("diagnose(database, disk_full)",                             0.08, False),
            ("apply_fix(database, clear_disk)",                           0.12, False),
            ("diagnose(payment_service, connection_pool_exhaustion)",     0.08, False),
            ("apply_fix(payment_service, drain_connections)",             0.12, False),
            ("verify_health(database)",                                   0.02, False),
            ("verify_health(payment_service)",                            0.04, True),
        ],
        "score": 0.658,
        "grader": {"root_identification": 0.80, "resolution": 1.0, "efficiency": 0.60, "safety": 0.85},
    },
}

REWARD_TABLE = [
    ("root_cause_investigation", "+0.04", "Inspecting the true failure service"),
    ("affected_service_investigation", "+0.03", "Tracing symptom dependencies"),
    ("correct_diagnosis", "+0.08", "Identifying the exact failure mode"),
    ("correct_fix", "+0.12", "Right remediation on right service"),
    ("successful_verification", "+0.04", "Confirmed service recovery"),
    ("invalid_action", "−0.03", "Wrong, redundant, or destructive actions"),
]

DEP_GRAPH = """
api_gateway  →  auth_service  →  user_service  →  database
             →  order_service →  payment_service →  database
                              →  database
"""

GRADER_WEIGHTS = {
    "root_identification": 0.35,
    "resolution": 0.30,
    "efficiency": 0.20,
    "safety": 0.15,
}

MODEL = "Qwen/Qwen2.5-72B-Instruct"

# ── CSS ──────────────────────────────────────────────────────────────────────

CSS = """
/* ── Global resets ── */
* { box-sizing: border-box; }

body, .gradio-container {
    background: #0a0c0f !important;
    color: #e8eaed !important;
    font-family: 'DM Sans', 'Segoe UI', sans-serif !important;
}

/* Remove Gradio's default white card wrappers */
.gradio-container .block, .gradio-container .form {
    background: transparent !important;
    border: none !important;
    box-shadow: none !important;
    padding: 0 !important;
}

/* Header bar */
#header-bar {
    background: #111418;
    border-bottom: 1px solid rgba(255,255,255,0.07);
    padding: 14px 24px;
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-bottom: 0;
}

/* Hero section */
#hero-section {
    background: #0a0c0f;
    border-bottom: 1px solid rgba(255,255,255,0.07);
    padding: 40px 24px 32px;
    margin-bottom: 24px;
}

/* Stat cards */
.stat-row { display: flex; gap: 12px; margin-bottom: 24px; }

.stat-card {
    flex: 1;
    background: #111418;
    border: 1px solid rgba(255,255,255,0.07);
    border-radius: 8px;
    padding: 14px 18px;
}

.stat-label {
    font-size: 10px;
    color: #6b7280;
    font-family: 'IBM Plex Mono', monospace;
    letter-spacing: 0.08em;
    text-transform: uppercase;
    margin-bottom: 4px;
}

.stat-value {
    font-size: 22px;
    font-weight: 600;
    font-family: 'IBM Plex Mono', monospace;
    color: #e8eaed;
}

.stat-value.green { color: #22c55e; }

/* Terminal */
#terminal-output textarea, #terminal-output .output-class {
    background: #080a0d !important;
    color: #94a3b8 !important;
    font-family: 'IBM Plex Mono', monospace !important;
    font-size: 12px !important;
    border: 1px solid rgba(255,255,255,0.07) !important;
    border-radius: 10px !important;
    padding: 16px !important;
    line-height: 1.9 !important;
    resize: none !important;
}

/* Gradio buttons */
button.lg {
    background: #ef4444 !important;
    border: none !important;
    color: white !important;
    font-family: 'IBM Plex Mono', monospace !important;
    font-size: 12px !important;
    font-weight: 500 !important;
    border-radius: 6px !important;
    padding: 8px 20px !important;
    cursor: pointer !important;
    transition: opacity 0.15s !important;
}

button.lg:hover { opacity: 0.85 !important; }

button.secondary {
    background: transparent !important;
    border: 1px solid rgba(255,255,255,0.12) !important;
    color: #6b7280 !important;
    font-family: 'IBM Plex Mono', monospace !important;
    font-size: 12px !important;
}

/* Dropdowns */
select, .gr-dropdown select {
    background: #111418 !important;
    border: 1px solid rgba(255,255,255,0.12) !important;
    color: #e8eaed !important;
    border-radius: 6px !important;
    font-family: 'IBM Plex Mono', monospace !important;
    font-size: 12px !important;
}

/* Score bars */
.score-bar-container {
    background: #111418;
    border: 1px solid rgba(255,255,255,0.07);
    border-radius: 10px;
    padding: 16px;
}

.score-row {
    display: flex;
    align-items: center;
    gap: 10px;
    margin-bottom: 12px;
    font-size: 11px;
    font-family: 'IBM Plex Mono', monospace;
}

.score-row:last-child { margin-bottom: 0; }

.score-label { color: #6b7280; min-width: 140px; }

.score-bar-bg {
    flex: 1;
    height: 4px;
    background: #1a1f27;
    border-radius: 2px;
    overflow: hidden;
}

.score-bar-fill {
    height: 100%;
    border-radius: 2px;
    transition: width 0.8s ease;
}

.score-num { color: #e8eaed; min-width: 38px; text-align: right; }

/* Card sections */
.section-card {
    background: #111418;
    border: 1px solid rgba(255,255,255,0.07);
    border-radius: 10px;
    overflow: hidden;
    margin-bottom: 16px;
}

.section-header {
    padding: 12px 16px;
    border-bottom: 1px solid rgba(255,255,255,0.07);
    display: flex;
    align-items: center;
    justify-content: space-between;
}

.section-title {
    font-size: 11px;
    font-weight: 500;
    font-family: 'IBM Plex Mono', monospace;
    color: #6b7280;
    text-transform: uppercase;
    letter-spacing: 0.07em;
}

/* Reward table */
.reward-table { width: 100%; border-collapse: collapse; }

.reward-table td {
    padding: 8px 16px;
    border-bottom: 1px solid rgba(255,255,255,0.05);
    font-size: 12px;
    font-family: 'IBM Plex Mono', monospace;
}

.reward-table tr:last-child td { border-bottom: none; }

.reward-table .col-action { color: #e2e8f0; }
.reward-table .col-desc { color: #6b7280; }

.reward-val-pos {
    color: #4ade80;
    background: rgba(34,197,94,0.1);
    padding: 2px 8px;
    border-radius: 3px;
    font-weight: 500;
}

.reward-val-neg {
    color: #f87171;
    background: rgba(239,68,68,0.1);
    padding: 2px 8px;
    border-radius: 3px;
    font-weight: 500;
}

/* Route table */
.route-table { width: 100%; border-collapse: collapse; }

.route-table td {
    padding: 7px 16px;
    border-bottom: 1px solid rgba(255,255,255,0.05);
    font-size: 11px;
    font-family: 'IBM Plex Mono', monospace;
}

.route-table tr:last-child td { border-bottom: none; }

.method-get {
    background: rgba(34,197,94,0.12);
    color: #4ade80;
    padding: 2px 7px;
    border-radius: 3px;
    font-size: 9px;
    font-weight: 500;
}

.method-post {
    background: rgba(59,130,246,0.12);
    color: #60a5fa;
    padding: 2px 7px;
    border-radius: 3px;
    font-size: 9px;
    font-weight: 500;
}

.route-path { color: #e2e8f0; }
.route-desc { color: #6b7280; }

/* Dep graph */
.dep-node {
    display: inline-block;
    padding: 3px 10px;
    border-radius: 4px;
    border: 1px solid;
    font-size: 10px;
    font-family: 'IBM Plex Mono', monospace;
    margin: 2px;
}

.dn-red { border-color: rgba(239,68,68,0.4); color: #f87171; background: rgba(239,68,68,0.08); }
.dn-orange { border-color: rgba(249,115,22,0.4); color: #fb923c; background: rgba(249,115,22,0.08); }
.dn-yellow { border-color: rgba(234,179,8,0.4); color: #facc15; background: rgba(234,179,8,0.08); }
.dn-blue { border-color: rgba(59,130,246,0.4); color: #60a5fa; background: rgba(59,130,246,0.08); }

/* Task pills */
.diff-easy   { background: rgba(34,197,94,0.15);  color: #4ade80;  }
.diff-medium { background: rgba(234,179,8,0.15);  color: #facc15; }
.diff-hard   { background: rgba(249,115,22,0.15); color: #fb923c; }
.diff-expert { background: rgba(239,68,68,0.15);  color: #f87171; }

.diff-pill {
    display: inline-block;
    padding: 2px 8px;
    border-radius: 3px;
    font-size: 10px;
    font-family: 'IBM Plex Mono', monospace;
    font-weight: 500;
}

/* Live dot */
.live-dot {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    font-size: 11px;
    color: #22c55e;
    font-family: 'IBM Plex Mono', monospace;
}

/* Hide Gradio footer and extra chrome */
footer { display: none !important; }
.gr-prose { display: none !important; }
#component-0 { padding: 0 !important; }

/* Labels */
label span { color: #6b7280 !important; font-size: 11px !important; font-family: 'IBM Plex Mono', monospace !important; }

/* Gradio tab overrides */
.tabs { background: transparent !important; }
.tab-nav { background: #111418 !important; border-bottom: 1px solid rgba(255,255,255,0.07) !important; }
.tab-nav button {
    color: #6b7280 !important;
    font-family: 'IBM Plex Mono', monospace !important;
    font-size: 12px !important;
    background: transparent !important;
    border: none !important;
    padding: 10px 16px !important;
}
.tab-nav button.selected {
    color: #ef4444 !important;
    border-bottom: 2px solid #ef4444 !important;
}

/* Dataframes */
.gr-dataframe table { background: #111418 !important; }
.gr-dataframe td, .gr-dataframe th {
    font-family: 'IBM Plex Mono', monospace !important;
    font-size: 11px !important;
    color: #e8eaed !important;
    border-color: rgba(255,255,255,0.07) !important;
}
.gr-dataframe th { color: #6b7280 !important; background: #0a0c0f !important; }
"""

# ── HTML helpers ─────────────────────────────────────────────────────────────

HEADER_HTML = """
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;500&family=DM+Sans:wght@400;500;600&display=swap" rel="stylesheet">
<div id="header-bar">
  <div style="display:flex;align-items:center;gap:10px;">
    <div style="width:28px;height:28px;background:#ef4444;border-radius:6px;display:flex;align-items:center;justify-content:center;">
      <svg width="14" height="14" viewBox="0 0 16 16" fill="none">
        <path d="M8 2L14 5.5V10.5L8 14L2 10.5V5.5L8 2Z" stroke="white" stroke-width="1.5" stroke-linejoin="round"/>
        <circle cx="8" cy="8" r="2" fill="white"/>
      </svg>
    </div>
    <div>
      <div style="font-family:'IBM Plex Mono',monospace;font-size:13px;font-weight:500;color:#e8eaed;">devops-incident-response</div>
      <div style="font-family:'IBM Plex Mono',monospace;font-size:10px;color:#6b7280;margin-top:-1px;">OpenEnv · RL Testbed</div>
    </div>
  </div>
  <div style="display:flex;align-items:center;gap:16px;">
    <span class="live-dot">
      <span style="width:6px;height:6px;border-radius:50%;background:#22c55e;display:inline-block;"></span>
      API live
    </span>
    <span style="font-family:'IBM Plex Mono',monospace;font-size:10px;color:#6b7280;border:1px solid rgba(255,255,255,0.12);padding:2px 8px;border-radius:4px;">v1.0.0</span>
  </div>
</div>
<div id="hero-section">
  <div style="font-family:'IBM Plex Mono',monospace;font-size:10px;color:#ef4444;letter-spacing:0.1em;text-transform:uppercase;margin-bottom:12px;">
    Meta PyTorch Hackathon · OpenEnv
  </div>
  <h1 style="font-size:32px;font-weight:600;line-height:1.2;margin-bottom:12px;color:#e8eaed;">
    SRE Triage <span style="color:#ef4444;">RL Environment</span>
  </h1>
  <p style="color:#6b7280;font-size:14px;max-width:560px;line-height:1.7;margin-bottom:16px;">
    A deterministic reinforcement learning testbed that stress-tests AI agents on production-style incident response — dependency tracing, root-cause diagnosis, and safe remediation across four difficulty tiers.
  </p>
  <div style="display:flex;gap:8px;flex-wrap:wrap;">
    <span style="font-family:'IBM Plex Mono',monospace;font-size:10px;padding:3px 10px;border-radius:4px;border:1px solid #ef4444;color:#ef4444;">openenv</span>
    <span style="font-family:'IBM Plex Mono',monospace;font-size:10px;padding:3px 10px;border-radius:4px;border:1px solid rgba(255,255,255,0.12);color:#6b7280;">devops</span>
    <span style="font-family:'IBM Plex Mono',monospace;font-size:10px;padding:3px 10px;border-radius:4px;border:1px solid rgba(255,255,255,0.12);color:#6b7280;">reinforcement-learning</span>
    <span style="font-family:'IBM Plex Mono',monospace;font-size:10px;padding:3px 10px;border-radius:4px;border:1px solid rgba(255,255,255,0.12);color:#6b7280;">ai-agents</span>
    <span style="font-family:'IBM Plex Mono',monospace;font-size:10px;padding:3px 10px;border-radius:4px;border:1px solid rgba(255,255,255,0.12);color:#6b7280;">sre</span>
  </div>
</div>
"""

STATS_HTML = """
<div class="stat-row">
  <div class="stat-card">
    <div class="stat-label">TASKS</div>
    <div class="stat-value">4</div>
  </div>
  <div class="stat-card">
    <div class="stat-label">SERVICES</div>
    <div class="stat-value">6</div>
  </div>
  <div class="stat-card">
    <div class="stat-label">GRADER</div>
    <div class="stat-value green">DET</div>
  </div>
  <div class="stat-card">
    <div class="stat-label">PORT</div>
    <div class="stat-value" style="font-size:18px;">8000</div>
  </div>
</div>
"""

DEP_GRAPH_HTML = """
<div class="section-card">
  <div class="section-header">
    <span class="section-title">Service dependency graph</span>
    <span style="font-size:10px;color:#6b7280;font-family:'IBM Plex Mono',monospace;">cascade-aware</span>
  </div>
  <div style="padding:16px;display:flex;flex-direction:column;gap:10px;">
    <div>
      <span class="dep-node dn-red">api_gateway</span>
      <span style="color:#6b7280;font-family:'IBM Plex Mono',monospace;font-size:11px;margin:0 4px;">→</span>
      <span class="dep-node dn-orange">auth_service</span>
      <span style="color:#6b7280;font-family:'IBM Plex Mono',monospace;font-size:11px;margin:0 4px;">+</span>
      <span class="dep-node dn-orange">order_service</span>
    </div>
    <div style="margin-left:16px;">
      <span class="dep-node dn-orange">order_service</span>
      <span style="color:#6b7280;font-family:'IBM Plex Mono',monospace;font-size:11px;margin:0 4px;">→</span>
      <span class="dep-node dn-yellow">payment_service</span>
      <span style="color:#6b7280;font-family:'IBM Plex Mono',monospace;font-size:11px;margin:0 4px;">+</span>
      <span class="dep-node dn-blue">database</span>
    </div>
    <div style="margin-left:16px;">
      <span class="dep-node dn-orange">auth_service</span>
      <span style="color:#6b7280;font-family:'IBM Plex Mono',monospace;font-size:11px;margin:0 4px;">→</span>
      <span class="dep-node dn-yellow">user_service</span>
      <span style="color:#6b7280;font-family:'IBM Plex Mono',monospace;font-size:11px;margin:0 4px;">→</span>
      <span class="dep-node dn-blue">database</span>
    </div>
    <div style="margin-left:16px;">
      <span class="dep-node dn-yellow">payment_service</span>
      <span style="color:#6b7280;font-family:'IBM Plex Mono',monospace;font-size:11px;margin:0 4px;">→</span>
      <span class="dep-node dn-blue">database</span>
    </div>
    <div style="margin-top:8px;padding-top:10px;border-top:1px solid rgba(255,255,255,0.05);font-size:10px;color:#6b7280;font-family:'IBM Plex Mono',monospace;">
      Agents must trace failures downstream — symptom-level fixes earn no resolution score.
    </div>
  </div>
</div>
"""

REWARD_HTML = """
<div class="section-card">
  <div class="section-header">
    <span class="section-title">Reward system</span>
    <span style="font-size:10px;color:#6b7280;font-family:'IBM Plex Mono',monospace;">dense + deterministic final</span>
  </div>
  <table class="reward-table">
    <tr>
      <td class="col-action">root_cause_investigation</td>
      <td class="col-desc">Inspecting the true failure service</td>
      <td><span class="reward-val-pos">+0.04</span></td>
    </tr>
    <tr>
      <td class="col-action">affected_service_investigation</td>
      <td class="col-desc">Tracing symptom dependencies</td>
      <td><span class="reward-val-pos">+0.03</span></td>
    </tr>
    <tr>
      <td class="col-action">correct_diagnosis</td>
      <td class="col-desc">Identifying the exact failure mode</td>
      <td><span class="reward-val-pos">+0.08</span></td>
    </tr>
    <tr>
      <td class="col-action">correct_fix</td>
      <td class="col-desc">Right remediation on right service</td>
      <td><span class="reward-val-pos">+0.12</span></td>
    </tr>
    <tr>
      <td class="col-action">successful_verification</td>
      <td class="col-desc">Confirmed service recovery</td>
      <td><span class="reward-val-pos">+0.04</span></td>
    </tr>
    <tr>
      <td class="col-action">invalid_action</td>
      <td class="col-desc">Wrong, redundant, or destructive</td>
      <td><span class="reward-val-neg">−0.03</span></td>
    </tr>
  </table>
</div>
"""

ROUTES_HTML = """
<div class="section-card">
  <div class="section-header">
    <span class="section-title">API routes</span>
    <span style="font-size:10px;color:#6b7280;font-family:'IBM Plex Mono',monospace;">port 8000</span>
  </div>
  <table class="route-table">
    <tr><td><span class="method-get">GET</span></td><td class="route-path">/</td><td class="route-desc">environment manifest</td></tr>
    <tr><td><span class="method-get">GET</span></td><td class="route-path">/health</td><td class="route-desc">liveness check</td></tr>
    <tr><td><span class="method-get">GET</span></td><td class="route-path">/tasks</td><td class="route-desc">list all task definitions</td></tr>
    <tr><td><span class="method-post">POST</span></td><td class="route-path">/reset</td><td class="route-desc">start episode {task_id, seed}</td></tr>
    <tr><td><span class="method-post">POST</span></td><td class="route-path">/step</td><td class="route-desc">execute action → observation + reward</td></tr>
    <tr><td><span class="method-get">GET</span></td><td class="route-path">/state</td><td class="route-desc">full environment state</td></tr>
    <tr><td><span class="method-get">GET</span></td><td class="route-path">/grader</td><td class="route-desc">deterministic episode score</td></tr>
    <tr><td><span class="method-get">GET</span></td><td class="route-path">/baseline</td><td class="route-desc">rule-based baseline action</td></tr>
    <tr><td><span class="method-get">GET</span></td><td class="route-path">/sample_action</td><td class="route-desc">example valid action payload</td></tr>
  </table>
</div>
"""

# ── Simulation logic ──────────────────────────────────────────────────────────

def make_score_bars_html(task_key: str) -> str:
    g = TASKS[task_key]["grader"]
    bars = [
        ("root identification", g["root_identification"], "#ef4444"),
        ("resolution",          g["resolution"],          "#f97316"),
        ("efficiency",          g["efficiency"],          "#eab308"),
        ("safety",              g["safety"],              "#22c55e"),
    ]
    rows = ""
    for label, val, color in bars:
        pct = int(val * 100)
        rows += f"""
        <div class="score-row">
          <span class="score-label">{label}</span>
          <div class="score-bar-bg">
            <div class="score-bar-fill" style="width:{pct}%;background:{color};"></div>
          </div>
          <span class="score-num">{pct}%</span>
        </div>"""
    score = TASKS[task_key]["score"]
    return f"""
    <div class="section-card">
      <div class="section-header">
        <span class="section-title">Grader breakdown</span>
        <span style="font-size:11px;color:#e8eaed;font-family:'IBM Plex Mono',monospace;">score: {score:.3f}</span>
      </div>
      <div style="padding:16px;">{rows}
        <div style="margin-top:10px;font-size:10px;color:#6b7280;font-family:'IBM Plex Mono',monospace;border-top:1px solid rgba(255,255,255,0.05);padding-top:10px;">
          Final score clamped strictly within (0.001, 0.999)
        </div>
      </div>
    </div>"""


def run_simulation(task_key: str) -> Generator:
    task = TASKS[task_key]
    steps = task["steps"]
    score = task["score"]
    terminal = ""

    def emit(line: str, bars_html: str = "") -> tuple:
        return terminal, bars_html or make_score_bars_html(task_key)

    terminal += f"$ python inference.py --task {task_key}\n"
    yield emit(terminal)
    time.sleep(0.3)

    terminal += f"[START] task={task_key} env=devops_incident_env model={MODEL}\n"
    yield emit(terminal)
    time.sleep(0.25)

    rewards = []
    for i, (action, reward, done) in enumerate(steps, 1):
        time.sleep(0.35 + random.random() * 0.2)
        done_str = "true" if done else "false"
        terminal += f"[STEP] step={i} action={action} reward={reward:.2f} done={done_str} error=null\n"
        rewards.append(reward)
        yield emit(terminal)

    time.sleep(0.35)
    reward_str = ",".join(f"{r:.2f}" for r in rewards)
    terminal += f"[END] success=true steps={len(steps)} rewards={reward_str}\n"
    yield emit(terminal)

    time.sleep(0.25)
    terminal += f"grader score: {score:.3f}\n"
    yield emit(terminal)


def clear_terminal(task_key: str) -> tuple:
    return "$ python inference.py  # select a task and click Run\n", make_score_bars_html(task_key)


def update_task_info(task_key: str) -> tuple:
    task = TASKS[task_key]
    diff = task["difficulty"]
    diff_colors = {
        "easy": "#4ade80", "medium": "#facc15",
        "hard": "#fb923c", "expert": "#f87171"
    }
    color = diff_colors[diff]
    info_html = f"""
    <div class="section-card">
      <div class="section-header">
        <span class="section-title">Selected task</span>
        <span style="font-family:'IBM Plex Mono',monospace;font-size:10px;font-weight:500;
                     color:{color};background:rgba(255,255,255,0.05);padding:2px 8px;border-radius:3px;">
          {diff}
        </span>
      </div>
      <div style="padding:14px 16px;">
        <div style="font-size:14px;font-weight:500;color:#e8eaed;margin-bottom:6px;">{task['label'].split(' — ')[1]}</div>
        <div style="font-size:12px;color:#6b7280;margin-bottom:10px;line-height:1.6;">{task['description']}</div>
        <div style="display:flex;gap:16px;font-family:'IBM Plex Mono',monospace;font-size:10px;color:#6b7280;">
          <span>root: <span style="color:#e8eaed;">{task['root']}</span></span>
          <span>max steps: <span style="color:#e8eaed;">{task['max_steps']}</span></span>
          <span>optimal steps: <span style="color:#e8eaed;">{len(task['steps'])}</span></span>
        </div>
      </div>
    </div>"""
    score_html = make_score_bars_html(task_key)
    return info_html, score_html


# ── Build Gradio app ──────────────────────────────────────────────────────────

with gr.Blocks(css=CSS, title="DevOps Incident Response — OpenEnv") as demo:

    gr.HTML(HEADER_HTML)
    gr.HTML(STATS_HTML)

    with gr.Tabs():

        # ── Tab 1: Simulation ──────────────────────────────────────────────
        with gr.Tab("Simulation"):
            with gr.Row():
                task_dropdown = gr.Dropdown(
                    choices=[(v["label"], k) for k, v in TASKS.items()],
                    value="easy_task",
                    label="Select task",
                    scale=3,
                )
                run_btn = gr.Button("Run simulation", variant="primary", scale=1)
                clear_btn = gr.Button("Clear", variant="secondary", scale=1)

            task_info_html = gr.HTML(update_task_info("easy_task")[0])

            terminal_out = gr.Textbox(
                value="$ python inference.py  # select a task and click Run\n",
                label="Terminal output",
                lines=14,
                max_lines=14,
                interactive=False,
                elem_id="terminal-output",
            )

            score_bars_html = gr.HTML(make_score_bars_html("easy_task"))

            # Wire up events
            task_dropdown.change(
                fn=update_task_info,
                inputs=task_dropdown,
                outputs=[task_info_html, score_bars_html],
            )

            run_btn.click(
                fn=run_simulation,
                inputs=task_dropdown,
                outputs=[terminal_out, score_bars_html],
            )

            clear_btn.click(
                fn=clear_terminal,
                inputs=task_dropdown,
                outputs=[terminal_out, score_bars_html],
            )

        # ── Tab 2: Environment ─────────────────────────────────────────────
        with gr.Tab("Environment"):
            with gr.Row():
                with gr.Column():
                    gr.HTML(DEP_GRAPH_HTML)
                    gr.HTML(REWARD_HTML)
                with gr.Column():
                    gr.HTML(ROUTES_HTML)
                    gr.HTML("""
                    <div class="section-card">
                      <div class="section-header">
                        <span class="section-title">Valid actions</span>
                      </div>
                      <div style="padding:12px 16px;display:flex;flex-direction:column;gap:6px;">
                        <div style="font-family:'IBM Plex Mono',monospace;font-size:11px;color:#e2e8f0;">read_logs</div>
                        <div style="font-family:'IBM Plex Mono',monospace;font-size:11px;color:#e2e8f0;">query_metrics</div>
                        <div style="font-family:'IBM Plex Mono',monospace;font-size:11px;color:#e2e8f0;">diagnose</div>
                        <div style="font-family:'IBM Plex Mono',monospace;font-size:11px;color:#e2e8f0;">apply_fix</div>
                        <div style="font-family:'IBM Plex Mono',monospace;font-size:11px;color:#e2e8f0;">verify_health</div>
                        <div style="font-family:'IBM Plex Mono',monospace;font-size:11px;color:#e2e8f0;">list_services</div>
                        <div style="font-family:'IBM Plex Mono',monospace;font-size:11px;color:#e2e8f0;">inspect_dependencies</div>
                        <div style="margin-top:8px;padding-top:8px;border-top:1px solid rgba(255,255,255,0.05);
                                    font-size:10px;color:#6b7280;font-family:'IBM Plex Mono',monospace;">
                          POST /step with {action_type, service, diagnosis?, fix?}
                        </div>
                      </div>
                    </div>
                    """)

        # ── Tab 3: Tasks ───────────────────────────────────────────────────
        with gr.Tab("Tasks"):
            for key, task in TASKS.items():
                diff = task["difficulty"]
                diff_colors = {
                    "easy": "#4ade80", "medium": "#facc15",
                    "hard": "#fb923c", "expert": "#f87171"
                }
                color = diff_colors[diff]
                steps_html = "".join(
                    f'<div style="font-family:\'IBM Plex Mono\',monospace;font-size:11px;'
                    f'color:#94a3b8;padding:3px 0;border-bottom:1px solid rgba(255,255,255,0.04);">'
                    f'<span style="color:#6b7280;margin-right:8px;">{i+1:02d}</span>{action}'
                    f'<span style="float:right;color:{"#4ade80" if reward > 0 else "#6b7280"};">+{reward:.2f}</span></div>'
                    for i, (action, reward, _) in enumerate(task["steps"])
                )
                gr.HTML(f"""
                <div class="section-card" style="margin-bottom:16px;">
                  <div class="section-header">
                    <span class="section-title">{key}</span>
                    <span style="font-family:'IBM Plex Mono',monospace;font-size:10px;font-weight:500;
                                 color:{color};background:rgba(255,255,255,0.05);padding:2px 8px;border-radius:3px;">
                      {diff}
                    </span>
                  </div>
                  <div style="padding:14px 16px;">
                    <div style="font-size:13px;font-weight:500;color:#e8eaed;margin-bottom:6px;">
                      {task['label'].split(' — ')[1]}
                    </div>
                    <div style="font-size:12px;color:#6b7280;margin-bottom:12px;line-height:1.6;">
                      {task['description']}
                    </div>
                    <div style="display:flex;gap:16px;font-family:'IBM Plex Mono',monospace;
                                font-size:10px;color:#6b7280;margin-bottom:12px;">
                      <span>root: <span style="color:#e8eaed;">{task['root']}</span></span>
                      <span>max_steps: <span style="color:#e8eaed;">{task['max_steps']}</span></span>
                      <span>benchmark score: <span style="color:{color};">{task['score']:.3f}</span></span>
                    </div>
                    <div style="font-size:10px;color:#6b7280;font-family:'IBM Plex Mono',monospace;
                                margin-bottom:6px;text-transform:uppercase;letter-spacing:0.06em;">
                      Optimal trace
                    </div>
                    {steps_html}
                  </div>
                </div>
                """)

    gr.HTML("""
    <div style="border-top:1px solid rgba(255,255,255,0.07);padding:16px 24px;
                display:flex;align-items:center;justify-content:space-between;
                font-family:'IBM Plex Mono',monospace;font-size:11px;color:#6b7280;margin-top:24px;">
      <span>devops-incident-response · OpenEnv · aryanosh</span>
      <div style="display:flex;gap:20px;">
        <a href="https://github.com/aryanosh/devops-incident-response" target="_blank"
           style="color:#6b7280;text-decoration:none;">GitHub</a>
        <a href="/tasks" style="color:#6b7280;text-decoration:none;">Tasks JSON</a>
        <a href="/manifest" style="color:#6b7280;text-decoration:none;">Manifest</a>
      </div>
    </div>
    """)


if __name__ == "__main__":
    demo.launch()
