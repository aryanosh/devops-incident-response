from __future__ import annotations

from fastapi.testclient import TestClient

from models import IncidentAction
from server.app import app
from server.environment import IncidentEnvironment


def test_tasks_endpoint_lists_four_tasks() -> None:
    client = TestClient(app)
    payload = client.get("/tasks").json()
    assert payload["count"] == 4
    assert [task["task_id"] for task in payload["tasks"]] == [
        "easy_task",
        "medium_task",
        "hard_task",
        "expert_task",
    ]


def test_reset_and_state_are_consistent() -> None:
    env = IncidentEnvironment()
    result = env.reset(task_id="medium_task", seed=123)
    assert result.observation.step_number == 0
    assert result.info["task_id"] == "medium_task"
    assert env.state().task_id == "medium_task"


def test_deterministic_logs_for_same_seed() -> None:
    env1 = IncidentEnvironment()
    env2 = IncidentEnvironment()
    env1.reset(task_id="easy_task", seed=55)
    env2.reset(task_id="easy_task", seed=55)
    result1 = env1.step(IncidentAction(action_type="read_logs", service="api_gateway"))
    result2 = env2.step(IncidentAction(action_type="read_logs", service="api_gateway"))
    assert result1.observation.logs[0].message == result2.observation.logs[0].message


def test_scores_are_strictly_inside_zero_one() -> None:
    env = IncidentEnvironment()
    env.reset(task_id="easy_task", seed=1)
    env.step(IncidentAction(action_type="read_logs", service="api_gateway"))
    env.step(IncidentAction(action_type="query_metrics", service="api_gateway"))
    env.step(
        IncidentAction(
            action_type="diagnose",
            service="api_gateway",
            diagnosis="service_crash",
        )
    )
    env.step(
        IncidentAction(
            action_type="apply_fix",
            service="api_gateway",
            fix="restart_service",
        )
    )
    env.step(IncidentAction(action_type="verify_health", service="api_gateway"))
    score = env.state().final_score
    assert score is not None
    assert 0.0 < score < 1.0


def test_grader_endpoint_exposes_clamped_score() -> None:
    client = TestClient(app)
    client.post("/reset", json={"task_id": "easy_task", "seed": 1})
    client.post("/step", json={"action": {"action_type": "list_services"}})
    payload = client.get("/grader").json()
    assert 0.0 < payload["score"] < 1.0
    assert "details" in payload


def test_health_endpoint_reports_healthy() -> None:
    client = TestClient(app)
    payload = client.get("/health").json()
    assert payload == {"status": "healthy"}
