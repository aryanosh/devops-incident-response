from __future__ import annotations

from typing import Any, Dict

import uvicorn
from openenv.core.env_server.http_server import create_app
from fastapi import Body
from fastapi.routing import APIRoute

try:
    from ..baseline import choose_action
    from ..models import IncidentAction, IncidentObservation
    from .environment import IncidentEnvironment
except ImportError:
    from baseline import choose_action
    from models import IncidentAction, IncidentObservation
    from server.environment import IncidentEnvironment

_ENV = IncidentEnvironment()


def _env_factory() -> IncidentEnvironment:
    # Reuse a singleton environment instance for HTTP endpoint continuity.
    return _ENV


app = create_app(
    _env_factory,
    IncidentAction,
    IncidentObservation,
    env_name="devops_incident_env",
    max_concurrent_envs=10,
)


def _remove_route(path: str, method: str) -> None:
    method = method.upper()
    app.router.routes = [
        route
        for route in app.router.routes
        if not (
            isinstance(route, APIRoute)
            and route.path == path
            and method in route.methods
        )
    ]


# Override default OpenEnv wrappers to keep backward-compatible payloads.
_remove_route("/reset", "POST")
_remove_route("/step", "POST")
_remove_route("/state", "GET")


def _wrap_observation(observation: IncidentObservation) -> Dict[str, Any]:
    payload = observation.model_dump(exclude={"reward", "done", "metadata"})
    return {
        "observation": payload,
        "reward": observation.reward,
        "done": observation.done,
        "info": observation.metadata,
    }


@app.get("/")
def root() -> Dict[str, Any]:
    return _ENV.manifest()


@app.get("/tasks")
def tasks() -> Dict[str, Any]:
    return _ENV.tasks_payload()


@app.get("/manifest")
def manifest() -> Dict[str, Any]:
    return _ENV.manifest()


@app.post("/reset")
def reset(payload: Dict[str, Any] | None = Body(default=None)) -> Dict[str, Any]:
    request = payload or {}
    observation = _ENV.reset(task_id=request.get("task_id"), seed=request.get("seed"))
    return _wrap_observation(observation)


@app.post("/step")
def step(payload: Dict[str, Any]) -> Dict[str, Any]:
    action_payload = payload.get("action") if isinstance(payload, dict) and "action" in payload else payload
    action = IncidentAction(**action_payload)
    observation = _ENV.step(action)
    return _wrap_observation(observation)


@app.get("/state")
def state() -> Dict[str, Any]:
    payload = _ENV.state.model_dump()
    payload["final_score"] = max(0.001, min(0.999, float(payload.get("final_score") or 0.001)))
    return payload


@app.get("/grader")
def grader() -> Dict[str, Any]:
    score, details = _ENV.grade()
    score = max(0.001, min(0.999, float(score)))
    return {
        "task_id": _ENV.state.task_id,
        "score": score,
        "details": details,
    }


@app.get("/baseline")
def baseline() -> Dict[str, Any]:
    state = _ENV.state
    observation = _ENV.build_observation(
        action_result="Current environment snapshot.",
        success=True,
        message="State snapshot.",
        step_number=state.step_count,
        reward=None,
        done=state.done,
    )
    action = choose_action(observation.model_dump(), state.model_dump())
    return action.model_dump(exclude_none=True)


@app.get("/sample_action")
def sample_action() -> Dict[str, Any]:
    return baseline()


def main() -> int:
    uvicorn.run(app, host="0.0.0.0", port=8000)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
