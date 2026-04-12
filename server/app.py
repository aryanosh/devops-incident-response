from __future__ import annotations

from typing import Any, Dict

import uvicorn
from fastapi import FastAPI, Request

try:
    from ..baseline import choose_action
    from ..models import IncidentAction, IncidentObservation, ResetRequest, StepRequest
    from .environment import IncidentEnvironment
except ImportError:
    from baseline import choose_action
    from models import IncidentAction, IncidentObservation, ResetRequest, StepRequest
    from server.environment import IncidentEnvironment

app = FastAPI(title="devops_incident_env", version="1.0.0")
_SESSION_ENVIRONMENTS: Dict[str, IncidentEnvironment] = {}
_DEFAULT_SESSION = "default"


def _get_environment(request: Request) -> IncidentEnvironment:
    """Get or create environment for this request session."""
    session_id = request.headers.get("X-Session-ID", _DEFAULT_SESSION)
    if session_id not in _SESSION_ENVIRONMENTS:
        _SESSION_ENVIRONMENTS[session_id] = IncidentEnvironment()
    return _SESSION_ENVIRONMENTS[session_id]


def _current_observation(env: IncidentEnvironment) -> IncidentObservation:
    state = env.state()
    return env.build_observation(
        action_result="Current environment snapshot.",
        success=True,
        message="State snapshot.",
        step_number=state.step_count,
    )


@app.get("/")
def root(request: Request) -> Dict[str, Any]:
    env = _get_environment(request)
    return env.manifest()


@app.get("/health")
def health() -> Dict[str, str]:
    return {"status": "healthy"}


@app.get("/tasks")
def tasks(request: Request) -> Dict[str, Any]:
    env = _get_environment(request)
    return env.tasks_payload()


@app.get("/manifest")
def manifest(request: Request) -> Dict[str, Any]:
    env = _get_environment(request)
    return env.manifest()


@app.post("/reset")
def reset(request: Request, payload: ResetRequest | None = None) -> Dict[str, Any]:
    env = _get_environment(request)
    reset_request = payload or ResetRequest()
    return env.reset(task_id=reset_request.task_id, seed=reset_request.seed).model_dump()


@app.post("/step")
def step(request: Request, payload: Dict[str, Any]) -> Dict[str, Any]:
    env = _get_environment(request)
    # Accept both OpenEnv-style wrapped payloads and direct action payloads.
    action_payload = payload.get("action") if isinstance(payload, dict) and "action" in payload else payload
    action = IncidentAction(**action_payload)
    return env.step(action).model_dump()


@app.get("/state")
def state(request: Request) -> Dict[str, Any]:
    env = _get_environment(request)
    state_payload = env.state().model_dump()
    # Keep numeric output stable for validators that always check [0,1] range.
    if state_payload.get("final_score") is None:
        state_payload["final_score"] = 0.0
    return state_payload


@app.get("/grader")
def grader(request: Request) -> Dict[str, Any]:
    env = _get_environment(request)
    score, details = env.grade()
    return {
        "task_id": env.state().task_id,
        "score": score,
        "details": details,
    }


@app.get("/baseline")
def baseline(request: Request) -> Dict[str, Any]:
    env = _get_environment(request)
    action = choose_action(_current_observation(env).model_dump(), env.state().model_dump())
    return action.model_dump(exclude_none=True)


@app.get("/sample_action")
def sample_action(request: Request) -> Dict[str, Any]:
    env = _get_environment(request)
    action = choose_action(_current_observation(env).model_dump(), env.state().model_dump())
    return action.model_dump(exclude_none=True)


@app.get("/metadata")
def metadata(request: Request) -> Dict[str, str]:
    env = _get_environment(request)
    manifest_data = env.manifest()
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
