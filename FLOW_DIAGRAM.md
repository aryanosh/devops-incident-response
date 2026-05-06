# DevOps Incident Response - Visual Flow Diagram

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                        DEVOPS INCIDENT RESPONSE FLOW                            │
└─────────────────────────────────────────────────────────────────────────────────┘

                                    ┌──────────────┐
                                    │   AI AGENT   │
                                    │ (LLM-based)  │
                                    └──────┬───────┘
                                           │
                        ┌──────────────────┼──────────────────┐
                        │                  │                  │
                  ┌─────▼─────┐     ┌────────────┐     ┌──────▼──────┐
                  │  Browser   │     │  Python    │     │   Remote    │
                  │   (Gradio  │     │  Client    │     │   API User  │
                  │  Dashboard)│     │(inference) │     │ (Evaluator) │
                  └─────┬─────┘     └────┬───────┘     └──────┬──────┘
                        │                │                    │
                        └────────────────┼────────────────────┘
                                        │
                                 ┌──────▼──────┐
                                 │  HTTP API   │
                                 │  (FastAPI)  │
                                 │  Port 8000  │
                                 └──────┬──────┘
                                        │
        ┌───────────────────────────────┼───────────────────────────────┐
        │                               │                               │
   ┌────▼────┐                    ┌────▼────┐                    ┌─────▼────┐
   │   GET   │                    │   POST  │                    │   GET    │
   │ Routes  │                    │ Routes  │                    │ /ui      │
   │ (Meta)  │                    │ (Action)│                    │(Gradio)  │
   └────┬────┘                    └────┬────┘                    └──────────┘
        │                             │
   ┌────┴────────────────────────┐   │
   │  • /health                  │   │
   │  • /tasks                   │   │
   │  • /manifest                │   │
   │  • /state                   │   │  ┌──────────────────────────┐
   │  • /grader                  │   ├─►│  /reset (Initialize)     │
   │  • /baseline                │   │  │  /step (Submit Action)   │
   │  • /sample_action           │   │  └──────────────┬───────────┘
   └─────────────────────────────┘   │                 │
                                      └─────────────────┘
                                              │
                                        ┌─────▼──────────┐
                                        │   Environment  │
                                        │    Instance    │
                                        │  (Manages      │
                                        │   Episode)     │
                                        └─────┬──────────┘
                                              │
                        ┌─────────────────────┼─────────────────────┐
                        │                     │                     │
                        │                     │                     │
                   ┌────▼───┐           ┌────▼────┐          ┌─────▼────┐
                   │  State │           │ Reward  │          │  Episode │
                   │Tracking│           │Emission │          │  Grader  │
                   └────────┘           └────┬────┘          └─────┬────┘
                                             │                     │
                                 ┌───────────▼──────────┐   ┌──────▼────────┐
                                 │  Per-Step Rewards    │   │ Final Score   │
                                 │  • Logging bonus     │   │ Components:   │
                                 │  • Diagnosis bonus   │   │ • Root ID 35% │
                                 │  • Fix reward +0.12  │   │ • Resolution  │
                                 │  • Penalties         │   │   30%         │
                                 └──────────────────────┘   │ • Efficiency  │
                                                             │   20%         │
                                                             │ • Safety 15%  │
                                                             └───────────────┘

┌────────────────────────────────────────────────────────────────────────────────┐
│                        SERVICE DEPENDENCY GRAPH                                │
└────────────────────────────────────────────────────────────────────────────────┘

                              api_gateway (Upstream)
                             /              \
                            /                \
                    auth_service          order_service (Affected)
                         |                 /          \
                         |                /            \
                    user_service     payment_service    |
                         |                |             |
                         └─────────┬──────┴─────────────┘
                                   │
                              database (Root Cause)
                         (Disk Full / Memory Leak)

┌────────────────────────────────────────────────────────────────────────────────┐
│                           TASK DIFFICULTY LADDER                               │
└────────────────────────────────────────────────────────────────────────────────┘

    EASY (🟢)              MEDIUM (🟡)           HARD (🔴)             EXPERT (🟣)
    ────────               ────────              ────────              ────────
    Symptom =          Root cause            Dependency             Multi-root
    Root cause         != symptom            chain tracing          coordination

    Single             Memory                Disk saturated       Two independent
    service            leak in               at database but      failures:
    crash              order_service         symptoms at          • Database disk
                                             api_gateway &        • Payment service
    Baseline:          Baseline:             order_service          disconnection
    0.800              0.860
                                             Baseline:            Baseline:
                                             0.117                0.117

┌────────────────────────────────────────────────────────────────────────────────┐
│                          AGENT ACTION SEQUENCE                                 │
└────────────────────────────────────────────────────────────────────────────────┘

    Step 1                Step 2-5               Step 6              Step 7-8
    ──────                ────────               ──────              ────────
    list_services()    read_logs()         diagnose()          apply_fix() &
                       query_metrics()     ┌──────────┐         verify_health()
    Discovery          inspect_              │ Correct  │
                       dependencies()        │ Root +   │
                                             │ Failure  │
                       ┌─────────────────┐   │ Mode?    │
                       │ Collect data    │   └──┬───────┘
                       │ about each      │      │
                       │ service         │      ├─► YES: +0.08
                       └─────────────────┘      │
                                                ├─► NO: +0.03
                                                │  (symptom match)
                                                └─► WRONG: -0.03

┌────────────────────────────────────────────────────────────────────────────────┐
│                         INFRASTRUCTURE & DEPLOYMENT                            │
└────────────────────────────────────────────────────────────────────────────────┘

    Source Code (Python 99.6%)        Docker Container         HuggingFace Space
    ┌──────────────────────┐          ┌──────────────────┐    ┌────────────────┐
    │ • server/            │          │ FROM             │    │ Live Demo      │
    │   - app.py (FastAPI) │────────►│ python:3.11-slim │   │ URL:            │
    │   - environment.py   │          │                  │    │ hf.space        │
    │ • tasks.py           │          │ EXPOSE 8000      │    │                │
    │ • grader.py          │          │ RUN install      │    │ Health ping:   │
    │ • models.py          │          │ CMD python       │    │ every 10 min   │
    │ • baseline.py        │          └──────────────────┘    └────────────────┘
    │ • inference.py       │
    │ • gradio_app.py      │
    │ • constants.py       │
    └──────────────────────┘
```

## Key Flow Points:

1. **Initialization**: Agent calls `/reset` with task ID + seed to start an episode
2. **Observation Loop**: Each `/step` returns full state (logs, metrics, alerts, dependencies)
3. **Action Selection**: Agent picks from: `list_services`, `read_logs`, `query_metrics`, `diagnose`, `apply_fix`, `verify_health`, `inspect_dependencies`
4. **Reward Shaping**: Dense per-step rewards guide agent toward **root cause**, not surface symptoms
5. **Dependency Tracing**: Hard/Expert tasks reward correct traversal of the service chain
6. **Grading**: Final score combines root ID (35%) + resolution (30%) + efficiency (20%) + safety (15%)
7. **Deployment**: Docker → HuggingFace Space with automatic keepalive pings
