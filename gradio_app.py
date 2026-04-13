"""
DevOps Incident Response — Premium Gradio UI
=============================================
A polished, hackathon-grade dashboard for the OpenEnv RL environment.

IMPORTANT: The Blocks instance MUST be named `app` — server/app.py imports it
via  `from gradio_app import app as gradio_ui`.
"""

from __future__ import annotations

import time
import random
from typing import Generator

import gradio as gr

# ─────────────────────────────────────────────────────────────────────────────
# Simulated task data  (mirrors the real environment exactly)
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

DIFF_COLORS = {"easy": "#22c55e", "medium": "#eab308", "hard": "#f97316", "expert": "#ef4444"}
DIFF_BG     = {"easy": "rgba(34,197,94,0.12)", "medium": "rgba(234,179,8,0.12)",
               "hard": "rgba(249,115,22,0.12)", "expert": "rgba(239,68,68,0.12)"}

# ─────────────────────────────────────────────────────────────────────────────
# CSS — Premium dark theme
# ─────────────────────────────────────────────────────────────────────────────

CSS = r"""
/* ── Google Fonts are loaded via HTML <link> ── */

/* ── Variables ── */
:root {
  --bg-primary:   #0a0c0f;
  --bg-secondary: #12151a;
  --bg-card:      #161a21;
  --bg-elevated:  #1e222a;
  --border:       rgba(255,255,255,0.07);
  --border-hover: rgba(255,255,255,0.15);
  --text-1:       #f0f2f5;
  --text-2:       #9ca3af;
  --text-3:       #6b7280;
  --accent:       #ef4444;
  --green:        #22c55e;
  --blue:         #3b82f6;
  --purple:       #a855f7;
  --mono:         'JetBrains Mono','IBM Plex Mono',monospace;
  --sans:         'Inter',system-ui,-apple-system,sans-serif;
  --display:      'Outfit','Inter',system-ui,sans-serif;
}

/* ── Resets ── */
*, *::before, *::after { box-sizing: border-box; }

body, .gradio-container {
  background: var(--bg-primary) !important;
  color: var(--text-1) !important;
  font-family: var(--sans) !important;
}

/* Kill Gradio's white wrapper cards */
.gradio-container .block,
.gradio-container .form,
.gradio-container .wrap {
  background: transparent !important;
  border: none !important;
  box-shadow: none !important;
  padding: 0 !important;
}
footer { display:none !important; }

/* ── Glass card mixin ── */
.glass {
  background: rgba(22,26,33,0.55) !important;
  backdrop-filter: blur(20px) saturate(1.4) !important;
  -webkit-backdrop-filter: blur(20px) saturate(1.4) !important;
  border: 1px solid var(--border) !important;
  border-radius: 14px !important;
  box-shadow: 0 8px 32px rgba(0,0,0,0.45), inset 0 1px 0 rgba(255,255,255,0.04) !important;
  transition: border-color .3s ease, transform .3s cubic-bezier(.16,1,.3,1) !important;
}
.glass:hover {
  border-color: var(--border-hover) !important;
}

/* ── Gradient border card ── */
.glow-card {
  position: relative;
  background: var(--bg-card) !important;
  border-radius: 14px !important;
  border: 1px solid var(--border) !important;
  overflow: hidden;
  transition: transform .3s cubic-bezier(.16,1,.3,1), border-color .3s ease !important;
}
.glow-card::before {
  content: '';
  position: absolute;
  inset: -1px;
  border-radius: 15px;
  padding: 1px;
  background: linear-gradient(135deg, rgba(168,85,247,.25), rgba(59,130,246,.15), transparent 60%);
  -webkit-mask: linear-gradient(#fff 0 0) content-box, linear-gradient(#fff 0 0);
  -webkit-mask-composite: xor;
  mask-composite: exclude;
  pointer-events: none;
  opacity: 0;
  transition: opacity .4s ease;
}
.glow-card:hover::before { opacity: 1; }
.glow-card:hover { transform: translateY(-2px); }

/* ── Header nav ── */
.top-bar {
  background: rgba(10,12,15,0.65) !important;
  backdrop-filter: blur(24px) saturate(1.6) !important;
  border-bottom: 1px solid var(--border);
  padding: 12px 28px;
  display: flex; align-items: center; justify-content: space-between;
  position: sticky; top: 0; z-index: 100;
}

/* ── Hero ── */
.hero {
  position: relative;
  padding: 64px 32px 48px;
  overflow: hidden;
}
.hero::before {
  content: '';
  position: absolute;
  top: -40%; left: -10%;
  width: 60%; height: 140%;
  background: radial-gradient(ellipse, rgba(168,85,247,0.08) 0%, transparent 70%);
  pointer-events: none;
  animation: heroGlow 8s ease-in-out infinite alternate;
}
.hero::after {
  content: '';
  position: absolute;
  top: -20%; right: -5%;
  width: 40%; height: 120%;
  background: radial-gradient(ellipse, rgba(239,68,68,0.06) 0%, transparent 70%);
  pointer-events: none;
  animation: heroGlow 6s ease-in-out infinite alternate-reverse;
}
@keyframes heroGlow {
  0%   { opacity: 0.6; transform: scale(1); }
  100% { opacity: 1;   transform: scale(1.1); }
}

.hero h1 {
  font-family: var(--display) !important;
  font-size: 44px; font-weight: 700; line-height: 1.1;
  letter-spacing: -0.03em;
  margin: 0 0 8px;
  position: relative; z-index: 1;
}
.hero h1 span {
  background: linear-gradient(135deg, #a855f7 0%, #ef4444 50%, #f97316 100%);
  -webkit-background-clip: text; -webkit-text-fill-color: transparent;
  background-clip: text;
}
.hero .subtitle {
  font-size: 16px; color: var(--text-2); line-height: 1.7;
  max-width: 540px; margin-bottom: 20px;
  position: relative; z-index: 1;
}
.hero .tags { display: flex; gap: 8px; flex-wrap: wrap; position: relative; z-index: 1; }
.hero .tag {
  font-family: var(--mono); font-size: 10px;
  padding: 4px 12px; border-radius: 6px;
  border: 1px solid var(--border); color: var(--text-3);
  transition: border-color .2s, color .2s;
}
.hero .tag:hover { border-color: var(--border-hover); color: var(--text-2); }
.hero .tag.active { border-color: var(--accent); color: var(--accent); }

/* ── Stat row ── */
.stats { display: grid; grid-template-columns: repeat(4,1fr); gap: 14px; margin: 0 32px 32px; }
.stat-card {
  padding: 20px 22px;
}
.stat-label {
  font-family: var(--mono); font-size: 10px; font-weight: 500;
  color: var(--text-3); text-transform: uppercase; letter-spacing: .1em;
  margin-bottom: 6px; display: flex; align-items: center; gap: 6px;
}
.stat-icon { font-size: 13px; }
.stat-value {
  font-family: var(--mono); font-size: 28px; font-weight: 600;
  color: var(--text-1);
}
.stat-value.green { color: var(--green); }
.stat-dots { display: flex; gap: 5px; margin-top: 8px; }
.stat-dot {
  width: 8px; height: 8px; border-radius: 50%;
  animation: pulse 2s ease-in-out infinite;
}
@keyframes pulse {
  0%, 100% { opacity: .7; transform: scale(1); }
  50%      { opacity: 1;  transform: scale(1.15); }
}

/* ── Tabs ── */
.tabs { background: transparent !important; }
.tab-nav {
  background: var(--bg-secondary) !important;
  border-bottom: 1px solid var(--border) !important;
  border-radius: 0 !important;
  padding: 0 28px !important;
}
.tab-nav button {
  font-family: var(--mono) !important; font-size: 12px !important;
  color: var(--text-3) !important; background: transparent !important;
  border: none !important; padding: 14px 18px !important;
  transition: color .2s !important; letter-spacing: .02em !important;
}
.tab-nav button:hover { color: var(--text-2) !important; }
.tab-nav button.selected {
  color: var(--text-1) !important;
  box-shadow: inset 0 -2px 0 var(--accent) !important;
}

/* ── Section card ── */
.section-card {
  background: var(--bg-card) !important;
  border: 1px solid var(--border) !important;
  border-radius: 14px !important;
  overflow: hidden;
  margin-bottom: 20px;
  transition: border-color .3s ease !important;
}
.section-card:hover { border-color: var(--border-hover) !important; }
.section-hdr {
  padding: 14px 20px;
  background: rgba(255,255,255,0.015);
  border-bottom: 1px solid var(--border);
  display: flex; align-items: center; justify-content: space-between;
}
.section-hdr .title {
  font-family: var(--mono); font-size: 11px; font-weight: 500;
  color: var(--text-3); text-transform: uppercase; letter-spacing: .08em;
}
.section-hdr .badge {
  font-family: var(--mono); font-size: 10px; color: var(--text-3);
}

/* ── Terminal ── */
#terminal-output textarea {
  background: #08090c !important;
  color: #c8d0da !important;
  font-family: var(--mono) !important;
  font-size: 12.5px !important;
  line-height: 2 !important;
  border: 1px solid var(--border) !important;
  border-radius: 12px !important;
  padding: 20px !important;
  box-shadow: inset 0 2px 12px rgba(0,0,0,0.4) !important;
  resize: none !important;
}

/* ── Buttons ── */
button.primary, button.lg {
  background: linear-gradient(135deg, #ef4444 0%, #dc2626 100%) !important;
  border: none !important; color: #fff !important;
  font-family: var(--mono) !important; font-size: 12px !important; font-weight: 500 !important;
  border-radius: 8px !important; padding: 10px 24px !important;
  box-shadow: 0 4px 14px rgba(239,68,68,0.3) !important;
  transition: transform .15s, box-shadow .15s !important;
  cursor: pointer !important;
}
button.primary:hover, button.lg:hover {
  transform: translateY(-1px) !important;
  box-shadow: 0 6px 20px rgba(239,68,68,0.4) !important;
}
button.secondary {
  background: var(--bg-elevated) !important;
  border: 1px solid var(--border) !important;
  color: var(--text-2) !important;
  font-family: var(--mono) !important; font-size: 12px !important;
  border-radius: 8px !important;
  transition: border-color .2s, color .2s !important;
}
button.secondary:hover {
  border-color: var(--border-hover) !important;
  color: var(--text-1) !important;
}

/* ── Score bars ── */
.score-row {
  display: flex; align-items: center; gap: 12px;
  margin-bottom: 14px; font-family: var(--mono); font-size: 11px;
}
.score-label { color: var(--text-3); min-width: 150px; }
.score-bar-bg {
  flex: 1; height: 6px; background: var(--bg-elevated);
  border-radius: 3px; overflow: hidden;
}
.score-bar-fill {
  height: 100%; border-radius: 3px;
  transition: width 1s cubic-bezier(.16,1,.3,1);
  box-shadow: 0 0 8px currentColor;
}
.score-num { color: var(--text-1); min-width: 40px; text-align: right; font-weight: 500; }

/* ── Reward table ── */
.rtable { width: 100%; border-collapse: collapse; }
.rtable td {
  padding: 10px 20px; border-bottom: 1px solid rgba(255,255,255,0.04);
  font-size: 12px; font-family: var(--mono);
}
.rtable tr:last-child td { border-bottom: none; }
.rtable .c-action { color: var(--text-1); font-weight: 500; }
.rtable .c-desc   { color: var(--text-3); }
.rval-pos {
  color: #4ade80; background: rgba(34,197,94,0.1);
  padding: 3px 10px; border-radius: 4px; font-weight: 500;
}
.rval-neg {
  color: #f87171; background: rgba(239,68,68,0.1);
  padding: 3px 10px; border-radius: 4px; font-weight: 500;
}

/* ── Route table ── */
.api-tbl { width: 100%; border-collapse: collapse; }
.api-tbl td {
  padding: 9px 20px; border-bottom: 1px solid rgba(255,255,255,0.04);
  font-family: var(--mono); font-size: 11px;
}
.api-tbl tr:last-child td { border-bottom: none; }
.m-get {
  background: rgba(34,197,94,0.12); color: #4ade80;
  padding: 2px 8px; border-radius: 4px; font-size: 9px; font-weight: 600;
}
.m-post {
  background: rgba(59,130,246,0.12); color: #60a5fa;
  padding: 2px 8px; border-radius: 4px; font-size: 9px; font-weight: 600;
}
.rp { color: var(--text-1); font-weight: 500; }
.rd { color: var(--text-3); }

/* ── Dep graph nodes ── */
.dn {
  display: inline-block; padding: 4px 12px; border-radius: 6px;
  font-family: var(--mono); font-size: 10px; margin: 3px;
  border: 1px solid; transition: transform .2s;
}
.dn:hover { transform: scale(1.05); }
.dn-r { border-color: rgba(239,68,68,0.4); color: #f87171; background: rgba(239,68,68,0.08); }
.dn-o { border-color: rgba(249,115,22,0.4); color: #fb923c; background: rgba(249,115,22,0.08); }
.dn-y { border-color: rgba(234,179,8,0.4);  color: #facc15; background: rgba(234,179,8,0.08); }
.dn-b { border-color: rgba(59,130,246,0.4); color: #60a5fa; background: rgba(59,130,246,0.08); }
.dn-arr { color: var(--text-3); font-family: var(--mono); font-size: 11px; margin: 0 4px; }

/* ── Task step flow ── */
.step-flow {
  display: flex; flex-direction: column; gap: 0; margin-top: 12px;
}
.step-item {
  display: flex; align-items: center; gap: 12px;
  padding: 10px 16px; position: relative;
  border-left: 2px solid var(--border);
  transition: background .2s;
}
.step-item:hover { background: rgba(255,255,255,0.02); }
.step-item:last-child { border-left-color: transparent; }
.step-num {
  width: 24px; height: 24px; border-radius: 50%;
  background: var(--bg-elevated); border: 1px solid var(--border);
  display: flex; align-items: center; justify-content: center;
  font-family: var(--mono); font-size: 10px; color: var(--text-3);
  flex-shrink: 0; position: relative; z-index: 1;
}
.step-action {
  font-family: var(--mono); font-size: 11px; color: var(--text-2); flex: 1;
}
.step-reward {
  font-family: var(--mono); font-size: 11px; font-weight: 500;
}

/* ── Difficulty badges ── */
.diff-badge {
  font-family: var(--mono); font-size: 10px; font-weight: 600;
  padding: 3px 10px; border-radius: 6px;
  text-transform: uppercase; letter-spacing: .06em;
}

/* ── Labels ── */
label span {
  color: var(--text-3) !important; font-size: 11px !important;
  font-family: var(--mono) !important;
}

/* ── Live dot ── */
@keyframes livePulse {
  0%, 100% { box-shadow: 0 0 0 0 rgba(34,197,94,0.5); }
  50%      { box-shadow: 0 0 0 4px rgba(34,197,94,0); }
}
.live-dot {
  width: 7px; height: 7px; border-radius: 50%;
  background: var(--green); display: inline-block;
  animation: livePulse 2s ease-in-out infinite;
}

/* ── Footer ── */
.ft {
  border-top: 1px solid var(--border);
  padding: 20px 32px; margin-top: 32px;
  display: flex; align-items: center; justify-content: space-between;
  font-family: var(--mono); font-size: 11px; color: var(--text-3);
}
.ft a { color: var(--text-3); text-decoration: none; transition: color .2s; }
.ft a:hover { color: var(--text-1); }
"""

# ─────────────────────────────────────────────────────────────────────────────
# HTML fragments
# ─────────────────────────────────────────────────────────────────────────────

FONTS = (
    '<link rel="preconnect" href="https://fonts.googleapis.com">'
    '<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>'
    '<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700'
    '&family=JetBrains+Mono:wght@400;500;600'
    '&family=Outfit:wght@500;600;700&display=swap" rel="stylesheet">'
)

NAV_HTML = f"""
{FONTS}
<div class="top-bar">
  <div style="display:flex;align-items:center;gap:10px;">
    <div style="width:30px;height:30px;border-radius:8px;display:flex;align-items:center;justify-content:center;
                background:linear-gradient(135deg,#a855f7,#ef4444);">
      <svg width="14" height="14" viewBox="0 0 16 16" fill="none">
        <path d="M8 2L14 5.5V10.5L8 14L2 10.5V5.5L8 2Z" stroke="#fff" stroke-width="1.5" stroke-linejoin="round"/>
        <circle cx="8" cy="8" r="2" fill="#fff"/>
      </svg>
    </div>
    <div>
      <div style="font-family:var(--mono);font-size:13px;font-weight:600;color:var(--text-1)">devops-incident-response</div>
      <div style="font-family:var(--mono);font-size:10px;color:var(--text-3)">OpenEnv · RL Testbed</div>
    </div>
  </div>
  <div style="display:flex;align-items:center;gap:16px;">
    <span style="display:inline-flex;align-items:center;gap:6px;font-family:var(--mono);font-size:11px;color:var(--green)">
      <span class="live-dot"></span> API live
    </span>
    <span style="font-family:var(--mono);font-size:10px;color:var(--text-3);
                 border:1px solid var(--border);padding:3px 10px;border-radius:6px;">v1.0.0</span>
  </div>
</div>
"""

HERO_HTML = """
<div class="hero">
  <h1>DevOps Incident <span>Response</span></h1>
  <p class="subtitle">
    RL Environment for AI Agent Evaluation — deterministic grading across four
    difficulty tiers with dense reward shaping, cascade-aware dependency graphs,
    and real-time scoring.
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

STATS_HTML = """
<div class="stats">
  <div class="glass stat-card">
    <div class="stat-label"><span class="stat-icon">📊</span> TASKS</div>
    <div class="stat-value">4</div>
    <div class="stat-dots">
      <span class="stat-dot" style="background:#22c55e;animation-delay:0s"></span>
      <span class="stat-dot" style="background:#eab308;animation-delay:.15s"></span>
      <span class="stat-dot" style="background:#f97316;animation-delay:.3s"></span>
      <span class="stat-dot" style="background:#ef4444;animation-delay:.45s"></span>
    </div>
  </div>
  <div class="glass stat-card">
    <div class="stat-label"><span class="stat-icon">⚡</span> ACTIONS</div>
    <div class="stat-value">7</div>
    <div class="stat-dots">
      <span class="stat-dot" style="background:#3b82f6;animation-delay:0s"></span>
      <span class="stat-dot" style="background:#3b82f6;animation-delay:.1s"></span>
      <span class="stat-dot" style="background:#3b82f6;animation-delay:.2s"></span>
    </div>
  </div>
  <div class="glass stat-card">
    <div class="stat-label"><span class="stat-icon">🎯</span> GRADER</div>
    <div class="stat-value green">DET</div>
  </div>
  <div class="glass stat-card">
    <div class="stat-label"><span class="stat-icon">🔌</span> PORT</div>
    <div class="stat-value" style="font-size:20px">8000</div>
  </div>
</div>
"""

DEP_GRAPH_HTML = """
<div class="section-card">
  <div class="section-hdr">
    <span class="title">Service Dependency Graph</span>
    <span class="badge">cascade-aware</span>
  </div>
  <div style="padding:20px;display:flex;flex-direction:column;gap:12px">
    <div>
      <span class="dn dn-r">api_gateway</span>
      <span class="dn-arr">→</span>
      <span class="dn dn-o">auth_service</span>
      <span class="dn-arr">+</span>
      <span class="dn dn-o">order_service</span>
    </div>
    <div style="margin-left:20px">
      <span class="dn dn-o">order_service</span>
      <span class="dn-arr">→</span>
      <span class="dn dn-y">payment_service</span>
      <span class="dn-arr">+</span>
      <span class="dn dn-b">database</span>
    </div>
    <div style="margin-left:20px">
      <span class="dn dn-o">auth_service</span>
      <span class="dn-arr">→</span>
      <span class="dn dn-y">user_service</span>
      <span class="dn-arr">→</span>
      <span class="dn dn-b">database</span>
    </div>
    <div style="margin-left:20px">
      <span class="dn dn-y">payment_service</span>
      <span class="dn-arr">→</span>
      <span class="dn dn-b">database</span>
    </div>
    <div style="margin-top:12px;padding-top:12px;border-top:1px solid var(--border);
                font-family:var(--mono);font-size:10px;color:var(--text-3)">
      Agents must trace failures downstream — symptom-level fixes earn no resolution score.
    </div>
  </div>
</div>
"""

REWARD_HTML = """
<div class="section-card">
  <div class="section-hdr">
    <span class="title">Reward System</span>
    <span class="badge">dense + deterministic</span>
  </div>
  <table class="rtable">
    <tr><td class="c-action">root_cause_investigation</td><td class="c-desc">Inspecting the true failure service</td><td><span class="rval-pos">+0.04</span></td></tr>
    <tr><td class="c-action">affected_service</td><td class="c-desc">Tracing symptom dependencies</td><td><span class="rval-pos">+0.03</span></td></tr>
    <tr><td class="c-action">correct_diagnosis</td><td class="c-desc">Identifying the exact failure mode</td><td><span class="rval-pos">+0.08</span></td></tr>
    <tr><td class="c-action">correct_fix</td><td class="c-desc">Right remediation on right service</td><td><span class="rval-pos">+0.12</span></td></tr>
    <tr><td class="c-action">verification</td><td class="c-desc">Confirmed service recovery</td><td><span class="rval-pos">+0.04</span></td></tr>
    <tr><td class="c-action">invalid_action</td><td class="c-desc">Wrong, redundant, or destructive</td><td><span class="rval-neg">−0.03</span></td></tr>
  </table>
</div>
"""

ROUTES_HTML = """
<div class="section-card">
  <div class="section-hdr">
    <span class="title">API Routes</span>
    <span class="badge">port 8000</span>
  </div>
  <table class="api-tbl">
    <tr><td><span class="m-get">GET</span></td><td class="rp">/</td><td class="rd">environment manifest</td></tr>
    <tr><td><span class="m-get">GET</span></td><td class="rp">/health</td><td class="rd">liveness check</td></tr>
    <tr><td><span class="m-get">GET</span></td><td class="rp">/tasks</td><td class="rd">list all task definitions</td></tr>
    <tr><td><span class="m-post">POST</span></td><td class="rp">/reset</td><td class="rd">start episode {task_id, seed}</td></tr>
    <tr><td><span class="m-post">POST</span></td><td class="rp">/step</td><td class="rd">execute action → observation + reward</td></tr>
    <tr><td><span class="m-get">GET</span></td><td class="rp">/state</td><td class="rd">full environment state</td></tr>
    <tr><td><span class="m-get">GET</span></td><td class="rp">/grader</td><td class="rd">deterministic episode score</td></tr>
    <tr><td><span class="m-get">GET</span></td><td class="rp">/baseline</td><td class="rd">rule-based baseline action</td></tr>
    <tr><td><span class="m-get">GET</span></td><td class="rp">/sample_action</td><td class="rd">example valid action payload</td></tr>
  </table>
</div>
"""

ACTIONS_HTML = """
<div class="section-card">
  <div class="section-hdr">
    <span class="title">Valid Actions</span>
    <span class="badge">7 types</span>
  </div>
  <div style="padding:16px 20px;display:flex;flex-direction:column;gap:8px">
    <div style="display:flex;align-items:center;gap:8px">
      <span style="width:6px;height:6px;border-radius:50%;background:var(--blue)"></span>
      <span style="font-family:var(--mono);font-size:11px;color:var(--text-1)">read_logs</span>
      <span style="font-family:var(--mono);font-size:10px;color:var(--text-3);margin-left:auto">observe</span>
    </div>
    <div style="display:flex;align-items:center;gap:8px">
      <span style="width:6px;height:6px;border-radius:50%;background:var(--blue)"></span>
      <span style="font-family:var(--mono);font-size:11px;color:var(--text-1)">query_metrics</span>
      <span style="font-family:var(--mono);font-size:10px;color:var(--text-3);margin-left:auto">observe</span>
    </div>
    <div style="display:flex;align-items:center;gap:8px">
      <span style="width:6px;height:6px;border-radius:50%;background:var(--blue)"></span>
      <span style="font-family:var(--mono);font-size:11px;color:var(--text-1)">inspect_dependencies</span>
      <span style="font-family:var(--mono);font-size:10px;color:var(--text-3);margin-left:auto">observe</span>
    </div>
    <div style="display:flex;align-items:center;gap:8px">
      <span style="width:6px;height:6px;border-radius:50%;background:var(--blue)"></span>
      <span style="font-family:var(--mono);font-size:11px;color:var(--text-1)">list_services</span>
      <span style="font-family:var(--mono);font-size:10px;color:var(--text-3);margin-left:auto">observe</span>
    </div>
    <div style="display:flex;align-items:center;gap:8px">
      <span style="width:6px;height:6px;border-radius:50%;background:#eab308"></span>
      <span style="font-family:var(--mono);font-size:11px;color:var(--text-1)">diagnose</span>
      <span style="font-family:var(--mono);font-size:10px;color:var(--text-3);margin-left:auto">assess</span>
    </div>
    <div style="display:flex;align-items:center;gap:8px">
      <span style="width:6px;height:6px;border-radius:50%;background:#ef4444"></span>
      <span style="font-family:var(--mono);font-size:11px;color:var(--text-1)">apply_fix</span>
      <span style="font-family:var(--mono);font-size:10px;color:var(--text-3);margin-left:auto">remediate</span>
    </div>
    <div style="display:flex;align-items:center;gap:8px">
      <span style="width:6px;height:6px;border-radius:50%;background:var(--green)"></span>
      <span style="font-family:var(--mono);font-size:11px;color:var(--text-1)">verify_health</span>
      <span style="font-family:var(--mono);font-size:10px;color:var(--text-3);margin-left:auto">confirm</span>
    </div>
    <div style="margin-top:8px;padding-top:10px;border-top:1px solid var(--border);
                font-family:var(--mono);font-size:10px;color:var(--text-3)">
      POST /step with &#123;action_type, service, diagnosis?, fix?&#125;
    </div>
  </div>
</div>
"""

FOOTER_HTML = """
<div class="ft">
  <span>devops-incident-response · OpenEnv · aryanosh</span>
  <div style="display:flex;gap:20px">
    <a href="https://github.com/aryanosh/devops-incident-response" target="_blank">GitHub</a>
    <a href="/tasks">Tasks JSON</a>
    <a href="/">Manifest</a>
  </div>
</div>
"""

# ─────────────────────────────────────────────────────────────────────────────
# Dynamic HTML builders
# ─────────────────────────────────────────────────────────────────────────────

def make_score_bars_html(task_key: str) -> str:
    g = TASKS[task_key]["grader"]
    score = TASKS[task_key]["score"]
    items = [
        ("root identification", g["root_identification"], "#ef4444"),
        ("resolution",          g["resolution"],          "#f97316"),
        ("efficiency",          g["efficiency"],          "#eab308"),
        ("safety",              g["safety"],              "#22c55e"),
    ]
    rows = ""
    for label, val, color in items:
        pct = int(val * 100)
        rows += f"""
        <div class="score-row">
          <span class="score-label">{label}</span>
          <div class="score-bar-bg">
            <div class="score-bar-fill" style="width:{pct}%;background:{color};color:{color}"></div>
          </div>
          <span class="score-num">{pct}%</span>
        </div>"""
    return f"""
    <div class="section-card">
      <div class="section-hdr">
        <span class="title">Grader Breakdown</span>
        <span style="font-family:var(--mono);font-size:12px;font-weight:600;color:var(--text-1)">
          score: {score:.3f}
        </span>
      </div>
      <div style="padding:20px">{rows}
        <div style="margin-top:14px;padding-top:12px;border-top:1px solid var(--border);
                    font-family:var(--mono);font-size:10px;color:var(--text-3)">
          Final score clamped strictly within (0.001, 0.999)
        </div>
      </div>
    </div>"""


def update_task_info(task_key: str) -> tuple:
    task = TASKS[task_key]
    diff = task["difficulty"]
    color = DIFF_COLORS[diff]
    bg = DIFF_BG[diff]
    info_html = f"""
    <div class="section-card">
      <div class="section-hdr">
        <span class="title">Selected Task</span>
        <span class="diff-badge" style="color:{color};background:{bg}">{diff}</span>
      </div>
      <div style="padding:18px 20px">
        <div style="font-family:var(--display);font-size:16px;font-weight:600;color:var(--text-1);margin-bottom:8px">
          {task['label'].split(' — ')[1]}
        </div>
        <div style="font-size:13px;color:var(--text-2);margin-bottom:14px;line-height:1.7">
          {task['description']}
        </div>
        <div style="display:flex;gap:20px;font-family:var(--mono);font-size:10px;color:var(--text-3)">
          <span>root: <span style="color:var(--text-1)">{task['root']}</span></span>
          <span>max steps: <span style="color:var(--text-1)">{task['max_steps']}</span></span>
          <span>optimal: <span style="color:var(--text-1)">{len(task['steps'])}</span></span>
        </div>
      </div>
    </div>"""
    return info_html, make_score_bars_html(task_key)


def build_task_card_html(key: str, task: dict) -> str:
    diff = task["difficulty"]
    color = DIFF_COLORS[diff]
    bg = DIFF_BG[diff]

    steps_html = ""
    for i, (action, reward, _) in enumerate(task["steps"]):
        rcolor = "#4ade80" if reward > 0 else "#f87171"
        steps_html += f"""
        <div class="step-item">
          <div class="step-num" style="border-color:{color}">{i+1}</div>
          <div class="step-action">{action}</div>
          <div class="step-reward" style="color:{rcolor}">+{reward:.2f}</div>
        </div>"""

    return f"""
    <div class="glow-card" style="margin-bottom:20px">
      <div class="section-hdr">
        <span class="title">{key}</span>
        <span class="diff-badge" style="color:{color};background:{bg}">{diff}</span>
      </div>
      <div style="padding:20px">
        <div style="font-family:var(--display);font-size:15px;font-weight:600;color:var(--text-1);margin-bottom:6px">
          {task['label'].split(' — ')[1]}
        </div>
        <div style="font-size:12px;color:var(--text-2);margin-bottom:16px;line-height:1.7">
          {task['description']}
        </div>
        <div style="display:flex;gap:20px;font-family:var(--mono);font-size:10px;color:var(--text-3);margin-bottom:16px">
          <span>root: <span style="color:var(--text-1)">{task['root']}</span></span>
          <span>max_steps: <span style="color:var(--text-1)">{task['max_steps']}</span></span>
          <span>benchmark: <span style="color:{color}">{task['score']:.3f}</span></span>
        </div>
        <div style="font-family:var(--mono);font-size:10px;color:var(--text-3);
                    text-transform:uppercase;letter-spacing:.08em;margin-bottom:4px">
          Optimal Trace
        </div>
        <div class="step-flow">{steps_html}</div>
      </div>
    </div>"""


# ─────────────────────────────────────────────────────────────────────────────
# Simulation logic  (unchanged behaviour)
# ─────────────────────────────────────────────────────────────────────────────

def run_simulation(task_key: str) -> Generator:
    task = TASKS[task_key]
    steps = task["steps"]
    score = task["score"]
    terminal = ""

    terminal += f"$ python inference.py --task {task_key}\n"
    yield terminal, make_score_bars_html(task_key)
    time.sleep(0.3)

    terminal += f"[START] task={task_key} env=devops_incident_env model={MODEL}\n"
    yield terminal, make_score_bars_html(task_key)
    time.sleep(0.25)

    rewards = []
    for i, (action, reward, done) in enumerate(steps, 1):
        time.sleep(0.35 + random.random() * 0.2)
        done_str = "true" if done else "false"
        terminal += f"[STEP] step={i} action={action} reward={reward:.2f} done={done_str} error=null\n"
        rewards.append(reward)
        yield terminal, make_score_bars_html(task_key)

    time.sleep(0.35)
    reward_str = ",".join(f"{r:.2f}" for r in rewards)
    terminal += f"[END] success=true steps={len(steps)} rewards={reward_str}\n"
    yield terminal, make_score_bars_html(task_key)

    time.sleep(0.25)
    terminal += f"grader score: {score:.3f}\n"
    yield terminal, make_score_bars_html(task_key)


def clear_terminal(task_key: str) -> tuple:
    return "$ python inference.py  # select a task and click Run\n", make_score_bars_html(task_key)


# ─────────────────────────────────────────────────────────────────────────────
# Build Gradio app   (variable MUST be named `app`)
# ─────────────────────────────────────────────────────────────────────────────

with gr.Blocks(css=CSS, title="DevOps Incident Response — OpenEnv") as app:

    # ── Nav + Hero + Stats ──
    gr.HTML(NAV_HTML)
    gr.HTML(HERO_HTML)
    gr.HTML(STATS_HTML)

    with gr.Tabs():

        # ══ Tab 1: Simulation ═══════════════════════════════════════════════
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
                lines=14, max_lines=14,
                interactive=False,
                elem_id="terminal-output",
            )

            score_bars_html = gr.HTML(make_score_bars_html("easy_task"))

            task_dropdown.change(fn=update_task_info, inputs=task_dropdown,
                                outputs=[task_info_html, score_bars_html])
            run_btn.click(fn=run_simulation, inputs=task_dropdown,
                          outputs=[terminal_out, score_bars_html])
            clear_btn.click(fn=clear_terminal, inputs=task_dropdown,
                            outputs=[terminal_out, score_bars_html])

        # ══ Tab 2: Environment ══════════════════════════════════════════════
        with gr.Tab("Environment"):
            with gr.Row():
                with gr.Column():
                    gr.HTML(DEP_GRAPH_HTML)
                    gr.HTML(REWARD_HTML)
                with gr.Column():
                    gr.HTML(ROUTES_HTML)
                    gr.HTML(ACTIONS_HTML)

        # ══ Tab 3: Tasks ════════════════════════════════════════════════════
        with gr.Tab("Tasks"):
            for key, task in TASKS.items():
                gr.HTML(build_task_card_html(key, task))

    gr.HTML(FOOTER_HTML)


if __name__ == "__main__":
    app.launch()
