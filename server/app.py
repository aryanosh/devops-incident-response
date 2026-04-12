from __future__ import annotations

from typing import Any, Dict

import uvicorn
from fastapi import FastAPI

try:
    from ..baseline import choose_action
    from ..models import IncidentObservation, ResetRequest, StepRequest
    from .environment import IncidentEnvironment
except ImportError:
    from baseline import choose_action
    from models import IncidentObservation, ResetRequest, StepRequest
    from server.environment import IncidentEnvironment

app = FastAPI(title="devops_incident_env", version="1.0.0")
ENVIRONMENT = IncidentEnvironment()


def _current_observation() -> IncidentObservation:
    state = ENVIRONMENT.state()
    return ENVIRONMENT.build_observation(
        action_result="Current environment snapshot.",
        success=True,
        message="State snapshot.",
        step_number=state.step_count,
    )


@app.get("/")
def root() -> Dict[str, Any]:
    return ENVIRONMENT.manifest()


@app.get("/health")
def health() -> Dict[str, str]:
    return {"status": "healthy"}


@app.get("/tasks")
def tasks() -> Dict[str, Any]:
    return ENVIRONMENT.tasks_payload()


@app.get("/manifest")
def manifest() -> Dict[str, Any]:
    return ENVIRONMENT.manifest()


@app.post("/reset")
def reset(payload: ResetRequest | None = None) -> Dict[str, Any]:
    request = payload or ResetRequest()
    return ENVIRONMENT.reset(task_id=request.task_id, seed=request.seed).model_dump()


@app.post("/step")
def step(payload: StepRequest) -> Dict[str, Any]:
    return ENVIRONMENT.step(payload.action).model_dump()


@app.get("/state")
def state() -> Dict[str, Any]:
    return ENVIRONMENT.state().model_dump()


@app.get("/grader")
def grader() -> Dict[str, Any]:
    score, details = ENVIRONMENT.grade()
    return {
        "task_id": ENVIRONMENT.state().task_id,
        "score": score,
        "details": details,
    }


@app.get("/baseline")
def baseline() -> Dict[str, Any]:
    action = choose_action(_current_observation().model_dump(), ENVIRONMENT.state().model_dump())
    return action.model_dump(exclude_none=True)


@app.get("/sample_action")
def sample_action() -> Dict[str, Any]:
    action = choose_action(_current_observation().model_dump(), ENVIRONMENT.state().model_dump())
    return action.model_dump(exclude_none=True)


@app.get("/metadata")
def metadata() -> Dict[str, str]:
    manifest_data = ENVIRONMENT.manifest()
    return {
        "name": str(manifest_data["name"]),
        "description": str(manifest_data["description"]),
    }


@app.get("/schema")
def schema() -> Dict[str, Any]:
    try:
        from ..models import EnvironmentState, IncidentAction, IncidentObservation
    except ImportError:
        from models import EnvironmentState, IncidentAction, IncidentObservation

    return {
        "action": IncidentAction.model_json_schema(),
        "observation": IncidentObservation.model_json_schema(),
        "state": EnvironmentState.model_json_schema(),
    }


@app.post("/mcp")
def mcp() -> Dict[str, Any]:
    return {"jsonrpc": "2.0", "id": 1, "result": {"status": "ok"}}


def main() -> int:
    uvicorn.run(app, host="0.0.0.0", port=7860)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
