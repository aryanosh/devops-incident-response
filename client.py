from __future__ import annotations

from typing import Any, Dict

import httpx


class DevOpsIncidentEnv:
    def __init__(self, base_url: str = "http://127.0.0.1:7860") -> None:
        self.base_url = base_url.rstrip("/")
        self.client = httpx.Client(timeout=10.0)

    def close(self) -> None:
        self.client.close()

    def tasks(self) -> Dict[str, Any]:
        return self.client.get(f"{self.base_url}/tasks").json()

    def reset(self, task_id: str, seed: int = 12345) -> Dict[str, Any]:
        return self.client.post(f"{self.base_url}/reset", json={"task_id": task_id, "seed": seed}).json()

    def step(self, action: Dict[str, Any]) -> Dict[str, Any]:
        return self.client.post(f"{self.base_url}/step", json={"action": action}).json()

    def state(self) -> Dict[str, Any]:
        return self.client.get(f"{self.base_url}/state").json()
