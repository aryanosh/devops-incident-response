import gradio as gr
import requests
import json
import os
import time

API_URL = os.environ.get("API_URL", "http://localhost:8000")

STATUS_EMOJIS = {
    "healthy": "🟢",
    "degraded": "🟡",
    "critical": "🔴",
    "down": "💀",
    "recovering": "🔵"
}

SEVERITY_EMOJIS = {
    "critical": "🚨",
    "high": "🔥",
    "medium": "⚠️",
    "low": "ℹ️"
}

SERVICES = [
    "api_gateway", "order_service", "payment_service", "database", 
    "cache", "inventory_service", "notification_service"
]

DIAGNOSES = [
    "service_crash", "memory_leak", "disk_full", "connection_pool_exhaustion", 
    "high_latency", "config_drift", "certificate_expired"
]

FIXES = [
    "restart_service", "clear_cache", "scale_replicas", "rotate_credentials", 
    "rollback_deployment", "increase_connection_pool", "free_disk_space", "update_certificate"
]

TASKS = ["easy_task", "medium_task", "hard_task", "expert_task"]

def api_call(method, endpoint, payload=None):
    try:
        url = f"{API_URL}{endpoint}"
        if method == "GET":
            r = requests.get(url, timeout=10)
        elif method == "POST":
            r = requests.post(url, json=payload, timeout=20)
        else:
            return None, "Unsupported method"
        
        r.raise_for_status()
        return r.json(), None
    except Exception as e:
        return None, f"API Error: {str(e)}"

def format_alerts(alerts):
    if not alerts:
        return "✅ No active alerts"
    md = ""
    for a in alerts:
        sev = a.get("severity", "medium")
        emoji = SEVERITY_EMOJIS.get(sev, "⚠️")
        md += f"**{emoji} [{sev.upper()}] {a.get('service', 'System')}** - {a.get('title', '')}\n"
        md += f"_{a.get('description', '')}_\n\n"
    return md

def format_services(services):
    if not services:
        return "No service data available. Use 'List Services' action to discover services."
    md = "| Service | Status | Dependencies |\n|---|---|---|\n"
    for s in services:
        status = s.get("status", "unknown")
        emoji = STATUS_EMOJIS.get(status, "❓")
        deps = ", ".join(s.get("depends_on", [])) or "None"
        md += f"| {s.get('service_name')} | {emoji} {status} | {deps} |\n"
    return md

def format_logs(logs):
    if not logs:
        return "No logs available."
    res = ""
    for l in logs:
        res += f"[{l.get('timestamp')}] {l.get('level')} [{l.get('service')}] - {l.get('message')}\n"
    return res

def format_metrics(metrics):
    if not metrics:
        return "No metrics available."
    md = f"### Metrics for {metrics.get('service_name')}\n"
    md += f"- **CPU**: {metrics.get('cpu_percent')}% \n"
    md += f"- **Memory**: {metrics.get('memory_mb')}!MB / {metrics.get('memory_limit_mb')}!MB \n"
    md += f"- **Latency (p50/p99)**: {metrics.get('request_latency_p50_ms')}!ms / {metrics.get('request_latency_p99_ms')}!ms \n"
    md += f"- **Error Rate**: {metrics.get('error_rate_percent')}% \n"
    md += f"- **Status**: {STATUS_EMOJIS.get(metrics.get('status'), '')} {metrics.get('status')} \n"
    return md

def update_ui_from_obs(obs, reward, info, done):
    if not obs:
        return (
            "Error: No observation data.", "Error.", "", "Error", "Error", "Error", "Error"
        )
    
    alerts_md = format_alerts(obs.get("active_alerts", []))
    services_md = format_services(obs.get("service_summaries", []))
    logs_text = format_logs(obs.get("logs", []))
    metrics_md = format_metrics(obs.get("metrics"))
    
    step = obs.get("step_number", 0)
    max_steps = obs.get("max_steps", 10)
    
    prog_str = f"Step: {step} / {max_steps}"
    
    score_str = f"Cum Reward: {reward:.3f} | Done: {done}"
    if done and info and "final_score" in info:
        score_str += f"\nFinal Score: {info['final_score']:.3f}"
        
    action_msg = obs.get("message", "")
    success = obs.get("success", False)
    msg_prefix = "✅" if success else "❌"
    
    history_line = f"[{step}] {msg_prefix} {action_msg}"
    
    return alerts_md, services_md, logs_text, metrics_md, prog_str, score_str, history_line

def reset_incident(task_id):
    # Wait for API to be ready if it's spinning up
    for _ in range(5):
        if api_call("GET", "/health")[1] is None:
            break
        time.sleep(1)
        
    data, err = api_call("POST", "/reset", {"task_id": task_id, "seed": 42})
    if err:
        return f"🚨 Error: {err}", "Error", "", "Error", "0/0", "0.0", err, []
        
    obs = data.get("observation", {})
    r = data.get("reward", 0.0)
    info = data.get("info", {})
    done = data.get("done", False)
    
    alerts_md, services_md, logs_text, metrics_md, prog_str, score_str, history_line = update_ui_from_obs(obs, r, info, done)
    
    return alerts_md, services_md, logs_text, metrics_md, prog_str, score_str, history_line, [history_line]

def perform_action(action_type, service=None, diagnosis=None, fix=None, history=[]):
    payload = {
        "action": {
            "action_type": action_type,
            "service": service if service else None,
            "diagnosis": diagnosis if diagnosis else None,
            "fix": fix if fix else None
        }
    }
    data, err = api_call("POST", "/step", payload)
    if err:
        error_line = f"🚨 Action Failed: {err}"
        return "Error", "Error", "", "Error", "Error", "Error", error_line, history + [error_line]
        
    obs = data.get("observation", {})
    r = data.get("reward", 0.0)
    info = data.get("info", {})
    done = data.get("done", False)
    
    alerts_md, services_md, logs_text, metrics_md, prog_str, score_str, history_line = update_ui_from_obs(obs, r, info, done)
    
    new_history = history + [history_line]
    history_md = "\n".join(new_history[::-1]) # Reverse to show newest first
    
    if done:
        state_data, _ = api_call("GET", "/grader")
        if state_data:
            score_str += f"\n\n**Grader Breakdown:**\n```json\n{json.dumps(state_data, indent=2)}\n```"
            
    return alerts_md, services_md, logs_text, metrics_md, prog_str, score_str, history_md, new_history

# Gradio UI definition
with gr.Blocks(theme=gr.themes.Monochrome(), title="DevOps Incident Response Env") as app:
    gr.Markdown("# 🚀 DevOps Incident Response OpenEnv")
    gr.Markdown("Resolve the active incident by diagnosing and fixing the degraded services within the step limit.")
    
    history_state = gr.State([])
    
    with gr.Row():
        with gr.Column(scale=1):
            task_dropdown = gr.Dropdown(choices=TASKS, value="easy_task", label="Select Task Severity")
            start_btn = gr.Button("🔥 Start Incident", variant="primary")
        with gr.Column(scale=1):
            progress_md = gr.Markdown("### Step: 0 / 0", label="Progress")
            score_md = gr.Markdown("### Cum Reward: 0.0", label="Score")
            
    with gr.Row():
        with gr.Column(scale=1):
            alerts_panel = gr.Markdown("No active alerts", label="Active Alerts")
        with gr.Column(scale=2):
            services_panel = gr.Markdown("No services listed", label="Service Status")
            
    with gr.Row():
        with gr.Column(scale=1, variant="panel"):
            gr.Markdown("### 🛠️ Actions")
            action_service = gr.Dropdown(choices=SERVICES, label="Target Service")
            
            with gr.Row():
                btn_list = gr.Button("List Services")
                btn_deps = gr.Button("Inspect Dependencies")
            
            with gr.Row():
                btn_logs = gr.Button("Read Logs")
                btn_metrics = gr.Button("Query Metrics")
                
            action_diagnosis = gr.Dropdown(choices=DIAGNOSES, label="Diagnosis")
            btn_diagnose = gr.Button("Diagnose")
            
            action_fix = gr.Dropdown(choices=FIXES, label="Remediation")
            btn_fix = gr.Button("Apply Fix")
            
            btn_verify = gr.Button("Verify Health", variant="secondary")
            
        with gr.Column(scale=2):
            gr.Markdown("### 📊 Logs & Metrics")
            with gr.Tabs():
                with gr.Tab("Logs"):
                    logs_panel = gr.Textbox(lines=10, max_lines=15, label="Service Logs", interactive=False)
                with gr.Tab("Metrics"):
                    metrics_panel = gr.Markdown("No metrics queried yet.")
                with gr.Tab("History"):
                    history_panel = gr.Markdown("No actions taken.")
                    
    # Wiring events
    start_btn.click(
        fn=reset_incident,
        inputs=[task_dropdown],
        outputs=[alerts_panel, services_panel, logs_panel, metrics_panel, progress_md, score_md, history_panel, history_state]
    )
    
    def mk_action_fn(action_name):
        return lambda s, d, f, h: perform_action(action_name, s, d, f, h)
        
    btn_list.click(fn=mk_action_fn("list_services"), inputs=[action_service, action_diagnosis, action_fix, history_state], outputs=[alerts_panel, services_panel, logs_panel, metrics_panel, progress_md, score_md, history_panel, history_state])
    btn_deps.click(fn=mk_action_fn("inspect_dependencies"), inputs=[action_service, action_diagnosis, action_fix, history_state], outputs=[alerts_panel, services_panel, logs_panel, metrics_panel, progress_md, score_md, history_panel, history_state])
    btn_logs.click(fn=mk_action_fn("read_logs"), inputs=[action_service, action_diagnosis, action_fix, history_state], outputs=[alerts_panel, services_panel, logs_panel, metrics_panel, progress_md, score_md, history_panel, history_state])
    btn_metrics.click(fn=mk_action_fn("query_metrics"), inputs=[action_service, action_diagnosis, action_fix, history_state], outputs=[alerts_panel, services_panel, logs_panel, metrics_panel, progress_md, score_md, history_panel, history_state])
    btn_diagnose.click(fn=mk_action_fn("diagnose"), inputs=[action_service, action_diagnosis, action_fix, history_state], outputs=[alerts_panel, services_panel, logs_panel, metrics_panel, progress_md, score_md, history_panel, history_state])
    btn_fix.click(fn=mk_action_fn("apply_fix"), inputs=[action_service, action_diagnosis, action_fix, history_state], outputs=[alerts_panel, services_panel, logs_panel, metrics_panel, progress_md, score_md, history_panel, history_state])
    btn_verify.click(fn=mk_action_fn("verify_health"), inputs=[action_service, action_diagnosis, action_fix, history_state], outputs=[alerts_panel, services_panel, logs_panel, metrics_panel, progress_md, score_md, history_panel, history_state])
    
if __name__ == "__main__":
    app.launch(server_name="0.0.0.0", server_port=7860)
