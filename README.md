---
title: DevOps Incident Response Environment
emoji: 🔥
colorFrom: red
colorTo: blue
sdk: docker
pinned: false
app_port: 8000
base_path: /web
tags:
  - openenv
  - reinforcement-learning
  - devops
---

# 🔥 DevOps Incident Response — OpenEnv Environment

A production-grade Reinforcement Learning environment where AI agents learn to detect,
diagnose, and resolve incidents in a 6-service distributed microservices system.

## Architecture

```
api_gateway → auth_service → user_service
     ↓                            ↓
order_service → payment_service → database
```

## Action Space

| Action | Parameters | Description |
|--------|-----------|-------------|
| read_logs | service | Read logs from a service |
| query_metrics | service | Get CPU/memory/latency metrics |
| diagnose | service, diagnosis | Submit root cause diagnosis |
| apply_fix | service, fix | Apply remediation |
| verify_health | service | Check if service recovered |

## Tasks

| Task | Difficulty | Scenario |
|------|-----------|---------|
| easy_task | 🟢 Easy | Single service crash (api_gateway) |
| medium_task | 🟡 Medium | Memory leak (order_service) |
| hard_task | 🔴 Hard | Cascading disk failure from database |

## Reward Function

4-component reward: Accuracy (35%) + Completeness (25%) + Efficiency (20%) + Quality (20%)

## Local Setup

```bash
docker build -t devops-incident:latest -f server/Dockerfile .
docker run -p 8000:8000 devops-incident:latest
```

## Hackathon

Meta PyTorch OpenEnv Hackathon x Scaler School of Technology 2026