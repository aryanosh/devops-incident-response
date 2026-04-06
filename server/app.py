# server/app.py
# ============================================================
# DevOps Incident Response - FastAPI Application
# ============================================================

try:
    from ..models import IncidentAction, IncidentObservation
    from .incident_environment import IncidentEnvironment
except ImportError:
    from models import IncidentAction, IncidentObservation
    from server.incident_environment import IncidentEnvironment

from openenv.core.env_server import create_app

# Create the FastAPI app using OpenEnv's factory
# Pass the CLASS (not an instance) to support concurrent sessions
app = create_app(
    IncidentEnvironment,       # Environment class
    IncidentAction,            # Action type
    IncidentObservation,       # Observation type
    env_name="devops-incident-env",
)