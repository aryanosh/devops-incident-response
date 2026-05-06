# DevOps Incident Response — Architecture

## 🏗️ System Overview

```
┌─────────────────────────────────────┐
│  AI Agent / User Interface          │
├─────────────────────────────────────┤
│         Gradio UI + REST API        │
│         (Port 8000)                 │
├─────────────────────────────────────┤
│          FastAPI Server             │
│  • /reset, /step, /grader           │
│  • /tasks, /state                   │
├─────────────────────────────────────┤
│     Core RL Environment             │
│  • tasks.py (scenarios)             │
│  • grader.py (scoring)              │
├─────────────────────────────────────┤
│   Mock Microservice System          │
│  (6 services + logs/metrics)        │
└─────────────────────────────────────┘
```

## 🔧 Key Files

| File | Purpose |
|------|---------|
| `gradio_app.py` | Web UI dashboard |
| `models.py` | Data schemas (Action, Observation) |
| `tasks.py` | Scenario definitions & service graph |
| `grader.py` | Final score calculation |
| `baseline.py` | Rule-based agent reference |
| `inference.py` | LLM agent evaluation |
| `constants.py` | Rewards & weights |

## 📊 4 Task Difficulty Levels

```
Easy      → Single service crash (api_gateway)
Medium    → Memory leak in order_service
Hard      → Disk full in database (hidden root cause)
Expert    → Dual root causes (disk + payment failure)
```

## 🎯 How a Step Works

```
1. Agent submits action (read_logs, diagnose, apply_fix, etc.)
2. Environment processes action
3. Returns: observation + reward + done flag
4. Repeat until max steps or episode done
5. Final grader score: 4-part weighted sum
   • Root Cause ID (35%)
   • Resolution (30%)
   • Efficiency (20%)
   • Safety (15%)
```

## 🏢 Microservice Dependency Graph

```
api_gateway
├── auth_service → user_service → database
└── order_service → payment_service → database
```

**Key Challenge:** Visible alerts appear on upstream services, but root cause is often downstream in `database`.

## 📈 Reward Structure

- Investigating root cause service: **+0.04**
- Correct diagnosis: **+0.08**
- Correct fix: **+0.12**
- Wrong action: **-0.03** penalty

## 🚀 Quick Start

```bash
# Run environment
docker run -p 8000:8000 devops_incident_env

# Run agent
python inference.py

# Run baseline
python eval_baseline.py

# Run tests
pytest tests/ -v
```

## 📦 Dependencies

- **FastAPI** – REST API
- **Gradio** – Web UI
- **Pydantic** – Data validation
- **PyTorch** (optional) – For advanced agents

---

**Live Demo:** https://huggingface.co/spaces/aryanosh/devops-incident-response
