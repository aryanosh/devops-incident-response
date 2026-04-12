from __future__ import annotations

from typing import Any, Dict

import httpx


class DevOpsIncidentEnv:
    def __init__(self, base_url: str = "http://127.0.0.1:7860", timeout: float = 15.0) -> None:
        self.base_url = base_url.rstrip("/")
        self.client = httpx.Client(timeout=timeout, limits=httpx.Limits(max_keepalive_connections=5))

    def close(self) -> None:
        self.client.close()

    def tasks(self) -> Dict[str, Any]:
        response = self.client.get(f"{self.base_url}/tasks")
        response.raise_for_status()
        return response.json()

    def reset(self, task_id: str, seed: int = 12345) -> Dict[str, Any]:
        response = self.client.post(
            f"{self.base_url}/reset",
            json={"task_id": task_id, "seed": seed}
        )
        response.raise_for_status()
        return response.json()

    def step(self, action: Dict[str, Any]) -> Dict[str, Any]:
        response = self.client.post(
            f"{self.base_url}/step",
            json={"action": action}
        )
        response.raise_for_status()
        return response.json()

    def state(self) -> Dict[str, Any]:
        response = self.client.get(f"{self.base_url}/state")
        response.raise_for_status()
        return response.json()
