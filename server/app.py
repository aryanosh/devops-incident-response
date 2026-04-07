"""FastAPI application for the DevOps Incident Response environment."""

from __future__ import annotations

import uvicorn
from openenv.core.env_server import create_app

try:
    from ..models import IncidentAction, IncidentObservation
    from .incident_environment import IncidentEnvironment
except ImportError:
    from models import IncidentAction, IncidentObservation
    from server.incident_environment import IncidentEnvironment


app = create_app(
    IncidentEnvironment,
    IncidentAction,
    IncidentObservation,
    env_name="devops-incident-response",
    max_concurrent_envs=4,
)


def main(host: str = "0.0.0.0", port: int = 8000) -> None:
    uvicorn.run(app, host=host, port=port)
if __name__ == "__main__":
    main()
