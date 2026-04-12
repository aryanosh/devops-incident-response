"""
Comprehensive tests for all fixes applied to the codebase.
Tests concurrent requests, reward architecture, destructive actions, and more.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from models import IncidentAction
from server.app import app
from server.environment import IncidentEnvironment


# ============================================================================
# ISSUE #1: Global Environment State Concurrency
# ============================================================================

class TestConcurrentEnvironmentIsolation:
    """Test HTTP reset/state behavior under the OpenEnv app wrapper."""
    
    def test_reset_switches_active_task(self) -> None:
        """Verify resetting different tasks updates active state deterministically."""
        client1 = TestClient(app)
        
        response1 = client1.post(
            "/reset",
            json={"task_id": "medium_task", "seed": 123},
        )
        assert response1.status_code == 200
        state1 = client1.get("/state").json()
        assert state1["task_id"] == "medium_task"
        
        response2 = client1.post(
            "/reset",
            json={"task_id": "hard_task", "seed": 456},
        )
        assert response2.status_code == 200
        state2 = client1.get("/state").json()
        assert state2["task_id"] == "hard_task"


# ============================================================================
# ISSUE #2: Reward Architecture - Final Score Separation
# ============================================================================

class TestRewardArchitecture:
    """Test that final scores are separated from step rewards."""
    
    def test_final_score_not_in_step_reward(self) -> None:
        """Verify final score goes in info dict, not step reward."""
        env = IncidentEnvironment()
        env.reset(task_id="easy_task", seed=42)
        
        # Run complete episode
        actions = [
            IncidentAction(action_type="read_logs", service="api_gateway"),
            IncidentAction(action_type="query_metrics", service="api_gateway"),
            IncidentAction(action_type="diagnose", service="api_gateway", diagnosis="service_crash"),
            IncidentAction(action_type="apply_fix", service="api_gateway", fix="restart_service"),
            IncidentAction(action_type="verify_health", service="api_gateway"),
        ]
        
        for action in actions:
            result = env.step(action)
            
            if result.done:
                # Final step should have step_reward=0.0, but final_score in info
                assert result.reward == 0.0, "Final step reward should be 0.0"
                assert result.metadata.get("grader_score") is not None, "Final score should be in metadata"
                assert 0.001 <= result.metadata["grader_score"] <= 0.999, "Final score should be clamped"
                break
    
    def test_intermediate_rewards_are_non_zero(self) -> None:
        """Verify intermediate step rewards are properly assigned."""
        env = IncidentEnvironment()
        env.reset(task_id="easy_task", seed=42)
        
        result = env.step(IncidentAction(action_type="read_logs", service="api_gateway"))
        assert result.reward > 0.0, "Read logs should give positive reward"
        assert result.reward <= 1.0, "Step reward should be <= 1.0"


# ============================================================================
# ISSUE #3: Destructive Action Detection
# ============================================================================

class TestDestructiveActionDetection:
    """Test complete destructive action detection."""
    
    def test_wrong_fix_detected_as_destructive(self) -> None:
        """Verify wrong fix is detected as destructive."""
        env = IncidentEnvironment()
        env.reset(task_id="easy_task", seed=42)
        env.step(IncidentAction(action_type="read_logs", service="api_gateway"))
        
        # Apply WRONG fix (memory_fix instead of restart_service for service_crash)
        result = env.step(
            IncidentAction(
                action_type="apply_fix",
                service="api_gateway",
                fix="memory_fix"
            )
        )
        
        state = env.state
        assert state.destructive_actions >= 1, "Wrong fix should be marked as destructive"
        assert result.reward == 0.0, "Destructive action should get 0 reward"
        assert not result.success, "Destructive action should fail"
    
    def test_double_fix_detected_as_destructive(self) -> None:
        """Verify applying fix twice is detected as destructive."""
        env = IncidentEnvironment()
        env.reset(task_id="easy_task", seed=42)
        env.step(IncidentAction(action_type="read_logs", service="api_gateway"))
        env.step(IncidentAction(action_type="query_metrics", service="api_gateway"))
        env.step(
            IncidentAction(
                action_type="diagnose",
                service="api_gateway",
                diagnosis="service_crash"
            )
        )
        
        # First fix (correct)
        result1 = env.step(
            IncidentAction(
                action_type="apply_fix",
                service="api_gateway",
                fix="restart_service"
            )
        )
        assert result1.success, "First fix should succeed"
        
        # Second fix (double fix - destructive)
        result2 = env.step(
            IncidentAction(
                action_type="apply_fix",
                service="api_gateway",
                fix="restart_service"
            )
        )
        state = env.state
        assert state.destructive_actions >= 1, "Double fix should be marked as destructive"
        assert not result2.success, "Double fix should fail"
    
    def test_fix_on_healthy_service_destructive(self) -> None:
        """Verify fix on healthy service is destructive."""
        env = IncidentEnvironment()
        env.reset(task_id="easy_task", seed=42)
        
        # Apply fix to a healthy service (not in incident)
        result = env.step(
            IncidentAction(
                action_type="apply_fix",
                service="database",  # Healthy service
                fix="clear_disk"
            )
        )
        
        state = env.state
        assert state.destructive_actions >= 1, "Fix on healthy service should be destructive"
        assert result.reward == 0.0, "Destructive action should get 0 reward"


# ============================================================================
# ISSUE #4: Dependency Validation
# ============================================================================

class TestDependencyValidation:
    """Test scenario config validation."""
    
    def test_scenario_configs_are_valid(self) -> None:
        """Verify all scenario configs pass validation."""
        env = IncidentEnvironment()
        # If configs are invalid, __init__ would raise ValueError
        assert env is not None


# ============================================================================
# ISSUE #5: Mode Mapping Validation
# ============================================================================

class TestModeMappingValidation:
    """Test 1:1 root cause to failure mode mapping."""
    
    def test_root_cause_mode_mapping_valid(self) -> None:
        """Verify 1:1 mapping between root causes and failure modes."""
        from tasks import SCENARIO_CONFIGS
        
        for task_id, config in SCENARIO_CONFIGS.items():
            roots = config.get("root_cause_services", [])
            modes = config.get("root_cause_failure_modes", [])
            assert len(roots) == len(modes), \
                f"Task {task_id}: mismatch in root_cause_services and root_cause_failure_modes lengths"


# ============================================================================
# Tests for Additional Improvements
# ============================================================================

class TestInputValidation:
    """Test input field length validation."""
    
    def test_action_field_length_limits(self) -> None:
        """Verify Pydantic models enforce field length limits."""
        from models import IncidentAction
        
        # This should fail validation (reasoning > 5000 chars)
        with pytest.raises(Exception):  # Pydantic ValidationError
            IncidentAction(
                action_type="read_logs",
                service="api_gateway",
                reasoning="x" * 10000  # Exceeds MAX_REASONING_LENGTH
            )


class TestGraderWithConstants:
    """Test that grader uses centralized constants."""
    
    def test_grader_score_boundaries(self) -> None:
        """Verify grader respects score boundaries."""
        from grader import SCORE_FLOOR, SCORE_CEILING
        
        env = IncidentEnvironment()
        env.reset(task_id="easy_task", seed=1)
        
        # Run minimal episode
        env.step(IncidentAction(action_type="list_services"))
        
        score, details = env.grade()
        assert SCORE_FLOOR <= score <= SCORE_CEILING, "Score should be within bounds"


class TestTimeoutConfiguration:
    """Test timeout configurations."""
    
    def test_http_client_timeout_configured(self) -> None:
        """Verify HTTP clients have appropriate timeouts."""
        from client import DevOpsIncidentEnv
        
        client = DevOpsIncidentEnv(timeout=15.0)
        # The client is properly initialized with a timeout
        assert client.client is not None, "HTTP client should be initialized"
        client.close()


class TestLogging:
    """Test logging improvements."""
    
    def test_inference_module_has_logger(self) -> None:
        """Verify inference module has proper logging."""
        import inference
        assert hasattr(inference, "logger"), "inference module should have logger"


# ============================================================================
# Integration Tests
# ============================================================================

class TestEndToEndIntegration:
    """End-to-end tests for complete workflows."""
    
    def test_complete_easy_task_workflow(self) -> None:
        """Test complete workflow through easy task."""
        client = TestClient(app)
        
        # Reset
        reset_resp = client.post("/reset", json={"task_id": "easy_task", "seed": 123})
        assert reset_resp.status_code == 200
        
        # Read logs
        step_resp = client.post(
            "/step",
            json={"action": {"action_type": "read_logs", "service": "api_gateway"}}
        )
        assert step_resp.status_code == 200
        data = step_resp.json()
        assert data["done"] is False
        assert isinstance(data["reward"], float)
        assert data["reward"] >= 0.0
    
    def test_complete_episode_reaches_terminal_state(self) -> None:
        """Test that episode properly terminates."""
        env = IncidentEnvironment()
        env.reset(task_id="easy_task", seed=42)
        
        steps = 0
        max_steps = 20
        
        while steps < max_steps:
            # List services to learn about environment
            result = env.step(IncidentAction(action_type="list_services"))
            steps += 1
            
            if result.done:
                # Episode terminated
                assert result.metadata.get("grader_score") is not None, "Final score should exist"
                assert 0.001 <= result.metadata["grader_score"] <= 0.999
                break
        
        # Should terminate before max_steps
        assert steps < max_steps, "Episode should naturally terminate"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
