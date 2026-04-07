"""Client for interacting with the DevOps Incident Response environment."""

from __future__ import annotations

from openenv.core.env_client import EnvClient
from openenv.core.client_types import StepResult

try:
    from .models import IncidentAction, IncidentObservation, IncidentState
except ImportError:
    from models import IncidentAction, IncidentObservation, IncidentState


class DevOpsIncidentEnv(EnvClient[IncidentAction, IncidentObservation, IncidentState]):
    """WebSocket client for the incident response environment."""

    def _step_payload(self, action: IncidentAction) -> dict:
        return action.model_dump(exclude_none=True)

    def _parse_result(self, payload: dict) -> StepResult[IncidentObservation]:
        observation_data = payload.get("observation", payload)
        observation = IncidentObservation(**observation_data)
        return StepResult(
            observation=observation,
            reward=payload.get("reward", observation.reward),
            done=payload.get("done", observation.done),
        )

    def _parse_state(self, payload: dict) -> IncidentState:
        return IncidentState(**payload)
