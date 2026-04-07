# client.py
# ============================================================
# DevOps Incident Response - Environment Client
# ============================================================

from openenv.core import EnvClient
from typing import Any, Generic, TypeVar

try:
    from .models import IncidentAction, IncidentObservation, IncidentState
except ImportError:
    from models import IncidentAction, IncidentObservation, IncidentState


# 🔧 Generic type for StepResult
T = TypeVar("T")


# 🔧 Custom StepResult (replacement for missing OpenEnv class)
class StepResult(Generic[T]):
    def __init__(self, observation: T, reward: float, done: bool):
        self.observation = observation
        self.reward = reward
        self.done = done


class DevOpsIncidentEnv(EnvClient[IncidentAction, IncidentObservation, IncidentState]):
    """
    Client for the DevOps Incident Response environment.
    Handles communication with the FastAPI server.
    """

    def _step_payload(self, action: IncidentAction) -> dict:
        """Serialize action to HTTP payload dict."""
        return action.model_dump(exclude_none=True)

    def _parse_result(self, payload: dict) -> StepResult[IncidentObservation]:
        """Parse server response into StepResult."""
        # Handle both wrapped {"observation": {...}} and flat response
        obs_data = payload.get("observation", payload)
        obs = IncidentObservation(**obs_data)

        return StepResult(
            observation=obs,
            reward=payload.get("reward", obs.reward),
            done=payload.get("done", obs.done),
        )

    def _parse_state(self, payload: dict) -> IncidentState:
        """Deserialize state from server payload."""
        return IncidentState(**payload)
