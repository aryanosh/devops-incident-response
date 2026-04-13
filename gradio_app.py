import gradio as gr
import subprocess
import threading
import time
import os

custom_css = """
body, .gradio-container {
    background-color: #0d1117 !important;
    color: #c9d1d9 !important;
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif !important;
}

/* Typography & Core Accents */
h1, h2, h3, h4, h5, h6 { color: #c9d1d9 !important; }
a { color: #58a6ff !important; text-decoration: none !important; }
.text-red { color: #ff5555 !important; }
.text-green { color: #3fb950 !important; }
.text-yellow { color: #d29922 !important; }
.text-orange { color: #f0883e !important; }
.text-muted { color: #8b949e !important; }

/* Badges */
.badge {
    display: inline-block;
    padding: 2px 8px;
    font-size: 12px;
    font-family: monospace;
    border-radius: 4px;
    border: 1px solid #30363d;
    margin-right: 8px;
    margin-bottom: 8px;
    color: #8b949e;
}
.badge-active { border-color: #ff5555; color: #ff5555; }

/* Grid Layout */
.dashboard-grid {
    display: grid;
    grid-template-columns: repeat(4, 1fr);
    gap: 16px;
    margin-top: 30px;
    margin-bottom: 30px;
}
.stat-box {
    background-color: #161b22;
    border: 1px solid #30363d;
    border-radius: 6px;
    padding: 16px;
    position: relative;
    box-shadow: 0 4px 6px rgba(0,0,0,0.3);
}
.stat-label {
    font-size: 12px;
    text-transform: uppercase;
    letter-spacing: 1px;
    color: #8b949e;
    margin-bottom: 8px;
}
.stat-value {
    font-size: 28px;
    font-family: monospace;
    font-weight: 600;
}

/* 2x2 Feature Grid */
.feature-grid {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 20px;
    margin-bottom: 30px;
}
.feature-card {
    background-color: #161b22;
    border: 1px solid #30363d;
    border-radius: 6px;
    padding: 20px;
}
.feature-header {
    display: flex;
    justify-content: space-between;
    font-size: 12px;
    text-transform: uppercase;
    letter-spacing: 1px;
    color: #8b949e;
    margin-bottom: 20px;
    border-bottom: 1px solid #30363d;
    padding-bottom: 10px;
}

/* Task List Items */
.task-item {
    display: flex;
    align-items: center;
    padding: 12px 0;
    border-bottom: 1px solid #2d333b;
}
.task-item:last-child { border-bottom: none; }
.task-badge {
    padding: 2px 6px;
    border-radius: 4px;
    font-size: 11px;
    font-family: monospace;
    min-width: 45px;
    text-align: center;
    margin-right: 15px;
}
.task-easy { border: 1px solid #3fb950; color: #3fb950; background: rgba(63, 185, 80, 0.1); }
.task-medium { border: 1px solid #d29922; color: #d29922; background: rgba(210, 153, 34, 0.1); }
.task-hard { border: 1px solid #f0883e; color: #f0883e; background: rgba(240, 136, 62, 0.1); }
.task-expert { border: 1px solid #f85149; color: #f85149; background: rgba(248, 81, 73, 0.1); }
.task-title { font-weight: 500; font-size: 14px; margin-bottom: 2px; }
.task-desc { font-size: 12px; color: #8b949e; font-family: monospace; }
.task-dash { margin-left: auto; color: #484f58; }

/* Reward List */
.reward-item {
    display: flex;
    justify-content: space-between;
    padding: 8px 0;
    font-family: monospace;
    font-size: 13px;
    border-bottom: 1px dashed #30363d;
}
.reward-item:last-child { border-bottom: none; }
.r-name { font-weight: bold; color: #c9d1d9; font-family: -apple-system, BlinkMacSystemFont, sans-serif; font-size:13px; }
.r-desc { color: #8b949e; }

/* Graph Components */
.graph-node {
    display: inline-block;
    padding: 4px 10px;
    border-radius: 4px;
    font-size: 12px;
    font-family: monospace;
    margin: 4px;
}
.gn-red { border: 1px solid #f85149; color: #f85149; }
.gn-orange { border: 1px solid #f0883e; color: #f0883e; }
.gn-yellow { border: 1px solid #d29922; color: #d29922; }
.gn-blue { border: 1px solid #58a6ff; color: #58a6ff; }
.gn-arrow { color: #484f58; margin: 0 4px; font-size: 10px; }
.graph-row { display: flex; align-items: center; margin-bottom: 8px; }

/* Grader Bars */
.grader-item { display: flex; align-items: center; margin-bottom: 15px; font-family: monospace; font-size: 12px; }
.grader-label { width: 150px; color: #8b949e; }
.grader-bar-bg { flex-grow: 1; height: 4px; background: #30363d; border-radius: 2px; margin: 0 15px; }
.grader-bar-fill { height: 100%; border-radius: 2px; }
.g-red { background: #f85149; width: 35%; }
.g-orange { background: #f0883e; width: 30%; }
.g-yellow { background: #d29922; width: 20%; }
.g-green { background: #3fb950; width: 15%; }
.grader-val { width: 30px; text-align: right; }

/* API Routes */
.api-section {
    background-color: #161b22;
    border: 1px solid #30363d;
    border-radius: 6px;
    padding: 20px;
    margin-top: 30px;
}
.api-item {
    display: flex;
    align-items: center;
    padding: 10px 0;
    border-bottom: 1px solid #2d333b;
    font-family: monospace;
    font-size: 13px;
}
.api-item:last-child { border-bottom: none; }
.api-method { padding: 4px 8px; border-radius: 4px; min-width: 40px; text-align: center; margin-right: 15px; font-weight: bold; font-size: 11px; }
.m-get { background: rgba(63, 185, 80, 0.1); color: #3fb950; }
.m-post { background: rgba(88, 166, 255, 0.1); color: #58a6ff; }
.api-path { color: #c9d1d9; font-weight: bold; width: 140px; }
.api-desc { color: #8b949e; margin-left: auto; }

/* Terminal */
.terminal-wrapper {
    background-color: #161b22;
    border: 1px solid #30363d;
    border-radius: 8px;
    overflow: hidden;
    margin-top: 10px;
}
.terminal-header {
    background-color: #21262d;
    padding: 8px 15px;
    display: flex;
    align-items: center;
    border-bottom: 1px solid #30363d;
}
.mac-dots {
    display: flex;
    gap: 6px;
}
.dot { width: 10px; height: 10px; border-radius: 50%; }
.dot-red { background-color: #ff5f56; }
.dot-yellow { background-color: #ffbd2e; }
.dot-green { background-color: #27c93f; }
.term-title { margin-left: auto; margin-right: auto; color: #8b949e; font-size: 11px; font-family: monospace; }
.term-body {
    background-color: #0d1117;
    padding: 15px;
    font-family: "Courier New", Courier, monospace;
    font-size: 13px;
    color: #8b949e;
    min-height: 150px;
    white-space: pre-wrap;
}

/* Nav */
.top-nav {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 20px 0;
    border-bottom: 1px solid #30363d;
    margin-bottom: 40px;
    font-family: monospace;
    font-size: 12px;
}
.nav-logo { display: flex; align-items: center; gap: 10px; }
.logo-icon { background: #ff5555; color: white; width: 24px; height: 24px; border-radius: 4px; display: flex; align-items: center; justify-content: center; font-weight: bold; border-radius: 6px;}

/* Inputs overrides */
.gradio-dropdown { background: #161b22 !important; border-color: #30363d !important; }
.run-btn { background: #ff5555 !important; border: none !important; color: white !important; font-family: monospace !important; font-weight: bold !important; border-radius: 6px !important; }
.clear-btn { background: transparent !important; border: 1px solid #30363d !important; color: #8b949e !important; font-family: monospace !important; border-radius: 6px !important; }
"""

header_html = """
<div class="top-nav">
    <div class="nav-logo">
        <div class="logo-icon">⬢</div>
        <div>
            <div style="color:#c9d1d9; font-weight:bold; font-size:14px; font-family:-apple-system, sans-serif;">devops-incident-response</div>
            <div style="color:#8b949e;">OpenEnv · RL Testbed</div>
        </div>
    </div>
    <div style="display:flex; align-items:center; gap:15px;">
        <div class="text-green">● API live</div>
        <div style="border:1px solid #30363d; padding:2px 8px; border-radius:4px; color:#8b949e;">v1.0.0</div>
    </div>
</div>

<div style="margin-bottom: 10px;">
    <span class="text-red" style="font-family:monospace; font-size:12px; letter-spacing:1px;">META PYTORCH HACKATHON · OPENENV</span>
</div>
<h1 style="font-size: 38px; margin-top: 0; margin-bottom: 15px; font-weight:700;">SRE Triage <span class="text-red">RL Environment</span></h1>
<p style="color:#8b949e; font-size:16px; max-width:700px; line-height:1.6; margin-bottom: 25px;">
    A deterministic reinforcement learning testbed that stress-tests AI agents on<br>
    production-style incident response — dependency tracing, root-cause<br>
    diagnosis, and safe remediation across four difficulty tiers.
</p>

<div>
    <span class="badge badge-active">openenv</span>
    <span class="badge">devops</span>
    <span class="badge">reinforcement-learning</span>
    <span class="badge">ai-agents</span>
    <span class="badge">sre</span>
</div>

<div class="dashboard-grid">
    <div class="stat-box">
        <div class="stat-label">Tasks</div>
        <div class="stat-value">4</div>
    </div>
    <div class="stat-box">
        <div class="stat-label">Services</div>
        <div class="stat-value">6</div>
    </div>
    <div class="stat-box">
        <div class="stat-label">Grader</div>
        <div class="stat-value text-green">DET</div>
    </div>
    <div class="stat-box">
        <div class="stat-label">Port</div>
        <div class="stat-value">8000</div>
    </div>
</div>
"""


features_html = """
<div class="feature-grid">

    <!-- TASKS -->
    <div class="feature-card">
        <div class="feature-header">
            <span>Tasks</span>
            <span>4 scenarios</span>
        </div>
        
        <div class="task-item">
            <div class="task-badge task-easy">easy</div>
            <div style="border-left: 2px solid #f85149; padding-left: 10px; flex-grow: 1;">
                <div class="task-title">Single Service Crash</div>
                <div class="task-desc">api_gateway · max 8 steps</div>
            </div>
            <div class="task-dash">—</div>
        </div>
        
        <div class="task-item">
            <div class="task-badge task-medium">medium</div>
            <div style="padding-left: 10px; flex-grow: 1;">
                <div class="task-title">Memory Leak in Order Service</div>
                <div class="task-desc">order_service · max 10 steps</div>
            </div>
            <div class="task-dash">—</div>
        </div>
        
        <div class="task-item">
            <div class="task-badge task-hard">hard</div>
            <div style="padding-left: 10px; flex-grow: 1;">
                <div class="task-title">Cascading DB Disk Saturation</div>
                <div class="task-desc">database → payment → order · max 12 steps</div>
            </div>
            <div class="task-dash">—</div>
        </div>
        
        <div class="task-item">
            <div class="task-badge task-expert">expert</div>
            <div style="padding-left: 10px; flex-grow: 1;">
                <div class="task-title">Compound Multi-Root Failure</div>
                <div class="task-desc">database + payment_service · max 14 steps</div>
            </div>
            <div class="task-dash">—</div>
        </div>
    </div>
    
    <!-- REWARD SYSTEM -->
    <div class="feature-card">
        <div class="feature-header">
            <span>Reward System</span>
            <span>dense + final</span>
        </div>
        
        <div class="reward-item">
            <div><span class="r-name">root investigation</span> <span class="r-desc">inspecting the true failure service</span></div>
            <div class="text-green">+0.04</div>
        </div>
        <div class="reward-item">
            <div><span class="r-name">affected service</span> <span class="r-desc">tracing symptom dependencies</span></div>
            <div class="text-green">+0.03</div>
        </div>
        <div class="reward-item">
            <div><span class="r-name">correct diagnosis</span> <span class="r-desc">identifying the exact failure mode</span></div>
            <div class="text-green">+0.08</div>
        </div>
        <div class="reward-item">
            <div><span class="r-name">correct fix</span> <span class="r-desc">right remediation, right service</span></div>
            <div class="text-green">+0.12</div>
        </div>
        <div class="reward-item">
            <div><span class="r-name">verification</span> <span class="r-desc">confirmed recovery</span></div>
            <div class="text-green">+0.04</div>
        </div>
        <div class="reward-item" style="margin-top:10px;">
            <div><span class="r-name">invalid action</span> <span class="r-desc">wrong, redundant, or destructive</span></div>
            <div class="text-red">-0.03</div>
        </div>
    </div>
    
    <!-- SERVICE DEPENDENCY GRAPH -->
    <div class="feature-card">
        <div class="feature-header">
            <span>Service Dependency Graph</span>
            <span></span>
        </div>
        
        <div class="graph-row">
            <div class="graph-node gn-red">api_gateway</div>
            <div class="gn-arrow">→</div>
            <div class="graph-node gn-orange">auth_service</div>
            <div class="gn-arrow">+</div>
            <div class="graph-node gn-orange">order_service</div>
        </div>
        
        <div class="graph-row" style="padding-left: 25px;">
            <div class="graph-node gn-yellow">order_service</div>
            <div class="gn-arrow">→</div>
            <div class="graph-node gn-yellow">payment_service</div>
            <div class="gn-arrow">+</div>
            <div class="graph-node gn-blue">database</div>
        </div>
        
        <div class="graph-row" style="padding-left: 25px;">
            <div class="graph-node gn-yellow">auth_service</div>
            <div class="gn-arrow">→</div>
            <div class="graph-node gn-yellow">user_service</div>
            <div class="gn-arrow">→</div>
            <div class="graph-node gn-blue">database</div>
        </div>
        
        <div class="graph-row" style="padding-left: 25px;">
            <div class="graph-node gn-yellow">payment_service</div>
            <div class="gn-arrow">→</div>
            <div class="graph-node gn-blue">database</div>
        </div>
        
        <div style="font-family:monospace; font-size:11px; color:#8b949e; margin-top:30px;">
            Agents must trace root causes downstream, not patch surface symptoms.
        </div>
    </div>
    
    <!-- GRADER WEIGHTS -->
    <div class="feature-card">
        <div class="feature-header">
            <span>Grader Weights</span>
            <span>score: —</span>
        </div>
        
        <div class="grader-item" style="margin-top:20px;">
            <div class="grader-label">root identification</div>
            <div class="grader-bar-bg"><div class="grader-bar-fill g-red"></div></div>
            <div class="grader-val">35%</div>
        </div>
        
        <div class="grader-item">
            <div class="grader-label">resolution</div>
            <div class="grader-bar-bg"><div class="grader-bar-fill g-orange"></div></div>
            <div class="grader-val">30%</div>
        </div>
        
        <div class="grader-item">
            <div class="grader-label">efficiency</div>
            <div class="grader-bar-bg"><div class="grader-bar-fill g-yellow"></div></div>
            <div class="grader-val">20%</div>
        </div>
        
        <div class="grader-item">
            <div class="grader-label">safety</div>
            <div class="grader-bar-bg"><div class="grader-bar-fill g-green"></div></div>
            <div class="grader-val">15%</div>
        </div>
        
        <div style="font-family:monospace; font-size:11px; color:#8b949e; margin-top:35px;">
            Final score clamped strictly within (0.001, 0.999)
        </div>
    </div>
    
</div>
"""

apis_html = """
<div class="api-section">
    <div class="feature-header">
        <span>API Routes</span>
        <span>port 8000</span>
    </div>
    
    <div class="api-item">
        <div class="api-method m-get">GET</div>
        <div class="api-path">/</div>
        <div class="api-desc">environment manifest</div>
    </div>
    
    <div class="api-item">
        <div class="api-method m-get">GET</div>
        <div class="api-path">/health</div>
        <div class="api-desc">liveness check</div>
    </div>
    
    <div class="api-item">
        <div class="api-method m-get">GET</div>
        <div class="api-path">/tasks</div>
        <div class="api-desc">list all task definitions</div>
    </div>
    
    <div class="api-item">
        <div class="api-method m-post">POST</div>
        <div class="api-path">/reset</div>
        <div class="api-desc">start episode {task_id, seed}</div>
    </div>
    
    <div class="api-item">
        <div class="api-method m-post">POST</div>
        <div class="api-path">/step</div>
        <div class="api-desc">execute action → observation + reward</div>
    </div>
    
    <div class="api-item">
        <div class="api-method m-get">GET</div>
        <div class="api-path">/state</div>
        <div class="api-desc">full environment state</div>
    </div>
    
    <div class="api-item">
        <div class="api-method m-get">GET</div>
        <div class="api-path">/grader</div>
        <div class="api-desc">deterministic episode score</div>
    </div>
    
    <div class="api-item">
        <div class="api-method m-get">GET</div>
        <div class="api-path">/baseline</div>
        <div class="api-desc">rule-based baseline action</div>
    </div>
    
    <div class="api-item">
        <div class="api-method m-get">GET</div>
        <div class="api-path">/sample_action</div>
        <div class="api-desc">example valid action payload</div>
    </div>
</div>

<div style="display:flex; justify-content:space-between; margin-top:40px; margin-bottom:20px; font-family:monospace; font-size:12px; color:#484f58;">
    <div>devops-incident-response · OpenEnv · aryanosh</div>
    <div style="display:flex; gap:15px;">
        <span>GitHub</span>
        <span>Tasks JSON</span>
        <span>Manifest</span>
    </div>
</div>
"""

init_cmd = "$ python inference.py # select a task and click Run\n"

def run_simulation(task):
    if not task:
        task = "easy_task"
    
    task_id = task.split(" - ")[0].strip() + "_task"
    
    yield init_cmd + f"\n> Starting simulation for {task_id}...\n"
    time.sleep(0.5)
    
    try:
        import subprocess
        # Run eval_baseline.py to simulate the agent
        # We can intercept stdout, but it's easier to just run python eval_baseline.py
        # Or even better, run eval_baseline and show it live
        process = subprocess.Popen(["uv", "run", "python", "eval_baseline.py"], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        
        output = init_cmd + f"\n> Starting simulation for {task_id}...\n"
        for line in iter(process.stdout.readline, ''):
            output += line
            yield output
            time.sleep(0.2)
            
        process.stdout.close()
        process.wait()
        
        output += "\n[Simulation Complete]\n"
        yield output
    except Exception as e:
        yield init_cmd + f"\n> Error: {str(e)}\n"

def clear_terminal():
    return init_cmd

# Gradio Setup
with gr.Blocks(css=custom_css, title="SRE Triage RL Environment", theme=gr.themes.Base()) as app:
    
    # 1. Header & Stats
    gr.HTML(header_html)
    
    # 2. Controls
    with gr.Row(elem_id="controls-row"):
        task_dropdown = gr.Dropdown(
            choices=[
                "easy - single service crash",
                "medium - memory leak",
                "hard - cascading saturation",
                "expert - multi-root failure"
            ],
            value="easy - single service crash",
            show_label=False,
            container=False,
            scale=2,
            elem_classes=["gradio-dropdown"]
        )
        run_btn = gr.Button("Run simulation", elem_classes=["run-btn"], scale=1)
        clear_btn = gr.Button("Clear", elem_classes=["clear-btn"], scale=1)
    
    # 3. Terminal Emulator
    gr.HTML('<div class="terminal-wrapper"><div class="terminal-header"><div class="mac-dots"><div class="dot dot-red"></div><div class="dot dot-yellow"></div><div class="dot dot-green"></div></div><div class="term-title">inference.py — devops_incident_env</div></div>')
    
    terminal_output = gr.HTML(f'<div class="term-body">{init_cmd}</div>')
    
    gr.HTML('</div>') # end wrapper
    
    def stream_format(task):
        for out in run_simulation(task):
            yield f'<div class="term-body">{out}</div>'
    
    run_btn.click(fn=stream_format, inputs=[task_dropdown], outputs=[terminal_output])
    clear_btn.click(fn=lambda: f'<div class="term-body">{clear_terminal()}</div>', outputs=[terminal_output])
    
    # 4. Features grid
    gr.HTML(features_html)
    
    # 5. APIs and footer
    gr.HTML(apis_html)

if __name__ == "__main__":
    pass
    # app.launch(...) -> is handled by fastapi mount
