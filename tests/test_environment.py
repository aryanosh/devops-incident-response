"""Tests for IncidentEnvironment core functionality."""

from __future__ import annotations

import pytest

from models import IncidentAction, IncidentObservation
from server.incident_environment import IncidentEnvironment


class TestEasyTask:
    """Tests for easy_task (single service crash)."""

    def test_easy_task_optimal_trajectory(self) -> None:
        """Test optimal path for easy task: investigate → diagnose → fix → verify."""
        env = IncidentEnvironment()
        obs = env.reset(task_id="easy_task")
        
        assert not obs.done
        assert len(obs.active_alerts) > 0
        assert any(alert.service == "api_gateway" for alert in obs.active_alerts)
        
        # Step 1: Read logs
        result = env.step(IncidentAction(action_type="read_logs", service="api_gateway"))
        assert result.success
        assert len(result.logs) > 0
        assert all(log.service == "api_gateway" for log in result.logs)
        
        # Step 2: Diagnose
        result = env.step(
            IncidentAction(
                action_type="diagnose",
                service="api_gateway",
                diagnosis="service_crash",
            )
        )
        assert result.success
        assert "correct diagnosis" in result.action_result.lower()
        
        # Step 3: Apply fix
        result = env.step(
            IncidentAction(
                action_type="apply_fix",
                service="api_gateway",
                fix="restart_service",
            )
        )
        assert result.success
        assert "fix successful" in result.action_result.lower()
        
        # Step 4: Verify health
        result = env.step(
            IncidentAction(action_type="verify_health", service="api_gateway")
        )
        assert result.success
        assert result.done
        
        state = env.state()
        assert state.is_resolved
        assert state.final_score >= 0.85, f"Expected score ≥0.85, got {state.final_score}"
        assert state.correct_diagnoses == 1
        assert state.correct_fixes == 1

    def test_easy_task_minimal_investigation(self) -> None:
        """Test that blind fix without investigation is penalized."""
        env = IncidentEnvironment()
        env.reset(task_id="easy_task")
        
        # Blind fix without investigation
        result = env.step(
            IncidentAction(
                action_type="apply_fix",
                service="api_gateway",
                fix="restart_service",
            )
        )
        assert result.success
        
        result = env.step(
            IncidentAction(action_type="verify_health", service="api_gateway")
        )
        
        state = env.state()
        blind_score = state.final_score
        
        # Compare with investigated fix
        env2 = IncidentEnvironment()
        env2.reset(task_id="easy_task", seed=42)
        env2.step(IncidentAction(action_type="read_logs", service="api_gateway"))
        env2.step(IncidentAction(action_type="query_metrics", service="api_gateway"))
        env2.step(
            IncidentAction(
                action_type="diagnose",
                service="api_gateway",
                diagnosis="service_crash",
            )
        )
        env2.step(
            IncidentAction(
                action_type="apply_fix",
                service="api_gateway",
                fix="restart_service",
            )
        )
        env2.step(IncidentAction(action_type="verify_health", service="api_gateway"))
        
        investigated_score = env2.state().final_score
        
        assert investigated_score > blind_score, (
            f"Investigated fix ({investigated_score:.4f}) should score higher "
            f"than blind fix ({blind_score:.4f})"
        )
        assert investigated_score - blind_score >= 0.15, (
            f"Score difference should be ≥0.15, got {investigated_score - blind_score:.4f}"
        )


class TestMediumTask:
    """Tests for medium_task (memory leak with cascading symptoms)."""

    def test_medium_task_root_cause_diagnosis(self) -> None:
        """Test that medium task requires finding order_service root cause."""
        env = IncidentEnvironment()
        obs = env.reset(task_id="medium_task")
        
        assert not obs.done
        assert len(obs.active_alerts) > 0
        
        # Investigate order_service (root cause)
        result = env.step(
            IncidentAction(action_type="read_logs", service="order_service")
        )
        assert result.success
        
        result = env.step(
            IncidentAction(action_type="query_metrics", service="order_service")
        )
        assert result.success
        assert result.metrics is not None
        assert result.metrics.service_name == "order_service"
        
        # Diagnose correctly
        result = env.step(
            IncidentAction(
                action_type="diagnose",
                service="order_service",
                diagnosis="memory_leak",
            )
        )
        assert result.success
        
        # Apply fix
        result = env.step(
            IncidentAction(
                action_type="apply_fix",
                service="order_service",
                fix="memory_fix",
            )
        )
        assert result.success
        
        # Verify
        result = env.step(
            IncidentAction(action_type="verify_health", service="order_service")
        )
        assert result.done
        
        state = env.state()
        assert state.is_resolved
        assert state.final_score >= 0.75

    def test_medium_task_symptom_vs_root_cause(self) -> None:
        """Test that fixing symptoms doesn't resolve the incident."""
        env = IncidentEnvironment()
        env.reset(task_id="medium_task")
        
        # Try to fix api_gateway (symptom, not root cause)
        result = env.step(
            IncidentAction(
                action_type="apply_fix",
                service="api_gateway",
                fix="increase_timeout",
            )
        )
        assert not result.success or "symptom" in result.action_result.lower()
        
        # Verify incident is not resolved
        state = env.state()
        assert not state.is_resolved


class TestHardTask:
    """Tests for hard_task (cascading failure chain)."""

    def test_hard_task_dependency_tracing(self) -> None:
        """Test that hard task requires dependency-aware investigation."""
        env = IncidentEnvironment()
        obs = env.reset(task_id="hard_task")
        
        assert not obs.done
        
        # Check dependencies first
        result = env.step(IncidentAction(action_type="check_dependencies"))
        assert result.success
        assert len(result.dependency_graph) > 0
        
        # Investigate database (root cause)
        result = env.step(IncidentAction(action_type="read_logs", service="database"))
        assert result.success
        
        result = env.step(
            IncidentAction(action_type="query_metrics", service="database")
        )
        assert result.success
        assert result.metrics is not None
        
        # Diagnose disk_full
        result = env.step(
            IncidentAction(
                action_type="diagnose",
                service="database",
                diagnosis="disk_full",
            )
        )
        assert result.success
        
        # Apply fix
        result = env.step(
            IncidentAction(
                action_type="apply_fix",
                service="database",
                fix="clear_disk",
            )
        )
        assert result.success
        
        # Verify
        result = env.step(
            IncidentAction(action_type="verify_health", service="database")
        )
        assert result.success
        assert result.done
        
        state = env.state()
        assert state.is_resolved
        assert state.final_score >= 0.70


class TestGraderScoring:
    """Tests for grader score variance and fairness."""

    def test_grader_score_separation(self) -> None:
        """Verify grader separates weak, partial, and optimal trajectories."""
        # Weak: blind fix
        env_weak = IncidentEnvironment()
        env_weak.reset(task_id="easy_task", seed=123)
        env_weak.step(
            IncidentAction(
                action_type="apply_fix",
                service="api_gateway",
                fix="restart_service",
            )
        )
        env_weak.step(
            IncidentAction(action_type="verify_health", service="api_gateway")
        )
        weak_score = env_weak.state().final_score
        
        # Partial: investigate but no diagnosis
        env_partial = IncidentEnvironment()
        env_partial.reset(task_id="easy_task", seed=123)
        env_partial.step(IncidentAction(action_type="read_logs", service="api_gateway"))
        env_partial.step(
            IncidentAction(
                action_type="apply_fix",
                service="api_gateway",
                fix="restart_service",
            )
        )
        env_partial.step(
            IncidentAction(action_type="verify_health", service="api_gateway")
        )
        partial_score = env_partial.state().final_score
        
        # Optimal: full investigation, diagnosis, fix, verify
        env_optimal = IncidentEnvironment()
        env_optimal.reset(task_id="easy_task", seed=123)
        env_optimal.step(
            IncidentAction(action_type="read_logs", service="api_gateway")
        )
        env_optimal.step(
            IncidentAction(action_type="query_metrics", service="api_gateway")
        )
        env_optimal.step(
            IncidentAction(
                action_type="diagnose",
                service="api_gateway",
                diagnosis="service_crash",
            )
        )
        env_optimal.step(
            IncidentAction(
                action_type="apply_fix",
                service="api_gateway",
                fix="restart_service",
            )
        )
        env_optimal.step(
            IncidentAction(action_type="verify_health", service="api_gateway")
        )
        optimal_score = env_optimal.state().final_score
        
        # Assert proper separation
        assert weak_score < partial_score < optimal_score, (
            f"Expected weak < partial < optimal, got {weak_score:.4f} < "
            f"{partial_score:.4f} < {optimal_score:.4f}"
        )
        assert optimal_score - weak_score >= 0.25, (
            f"Optimal-weak gap should be ≥0.25, got {optimal_score - weak_score:.4f}"
        )

    def test_grader_scores_in_valid_range(self) -> None:
        """Verify all grader scores are in [0.0, 1.0]."""
        for task_id in ["easy_task", "medium_task", "hard_task"]:
            env = IncidentEnvironment()
            env.reset(task_id=task_id)
            
            # Do random actions
            for _ in range(5):
                env.step(IncidentAction(action_type="list_services"))
            
            state = env.state()
            assert 0.0 <= state.final_score <= 1.0, (
                f"{task_id}: Score {state.final_score} outside [0.0, 1.0]"
            )

    def test_efficiency_component(self) -> None:
        """Test that efficiency score rewards optimal step count."""
        # Optimal path (4 steps)
        env1 = IncidentEnvironment()
        env1.reset(task_id="easy_task", seed=42)
        env1.step(IncidentAction(action_type="read_logs", service="api_gateway"))
        env1.step(
            IncidentAction(
                action_type="diagnose",
                service="api_gateway",
                diagnosis="service_crash",
            )
        )
        env1.step(
            IncidentAction(
                action_type="apply_fix",
                service="api_gateway",
                fix="restart_service",
            )
        )
        env1.step(IncidentAction(action_type="verify_health", service="api_gateway"))
        efficient_score = env1.state().final_score
        
        # Inefficient path (10 steps with redundant actions)
        env2 = IncidentEnvironment()
        env2.reset(task_id="easy_task", seed=42)
        for _ in range(3):
            env2.step(IncidentAction(action_type="list_services"))
        env2.step(IncidentAction(action_type="read_logs", service="api_gateway"))
        env2.step(IncidentAction(action_type="read_logs", service="api_gateway"))
        env2.step(
            IncidentAction(
                action_type="diagnose",
                service="api_gateway",
                diagnosis="service_crash",
            )
        )
        env2.step(
            IncidentAction(
                action_type="apply_fix",
                service="api_gateway",
                fix="restart_service",
            )
        )
        env2.step(IncidentAction(action_type="verify_health", service="api_gateway"))
        for _ in range(2):
            env2.step(IncidentAction(action_type="list_services"))
        inefficient_score = env2.state().final_score
        
        assert efficient_score > inefficient_score, (
            f"Efficient path ({efficient_score:.4f}) should score higher "
            f"than inefficient ({inefficient_score:.4f})"
        )


class TestSafetyPenalties:
    """Tests for safety penalties and destructive actions."""

    def test_destructive_action_penalty(self) -> None:
        """Test that fixing healthy services is penalized."""
        env = IncidentEnvironment()
        env.reset(task_id="easy_task")
        
        # Try to fix a healthy service
        result = env.step(
            IncidentAction(
                action_type="apply_fix",
                service="database",
                fix="restart_service",
            )
        )
        assert not result.success
        assert "dangerous" in result.action_result.lower() or "healthy" in result.action_result.lower()
        
        state = env.state()
        assert state.destructive_actions > 0

    def test_wrong_diagnosis_penalty(self) -> None:
        """Test that incorrect diagnoses are penalized."""
        env = IncidentEnvironment()
        env.reset(task_id="easy_task")
        
        # Wrong diagnosis
        result = env.step(
            IncidentAction(
                action_type="diagnose",
                service="api_gateway",
                diagnosis="memory_leak",  # Wrong, should be service_crash
            )
        )
        assert not result.success
        
        state = env.state()
        assert state.incorrect_diagnoses > 0
        assert state.correct_diagnoses == 0


class TestResetAndState:
    """Tests for environment reset and state management."""

    def test_reset_initializes_correctly(self) -> None:
        """Test that reset() properly initializes environment."""
        env = IncidentEnvironment()
        
        for task_id in ["easy_task", "medium_task", "hard_task"]:
            obs = env.reset(task_id=task_id)
            
            assert not obs.done
            assert obs.step_number == 0
            assert len(obs.active_alerts) > 0
            assert len(obs.service_summaries) == 6
            assert len(obs.dependency_graph) == 6
            
            state = env.state()
            assert state.task_id == task_id
            assert state.step_count == 0
            assert not state.is_resolved
            assert state.final_score == 0.0

    def test_state_tracking(self) -> None:
        """Test that state properly tracks actions."""
        env = IncidentEnvironment()
        env.reset(task_id="easy_task")
        
        env.step(IncidentAction(action_type="read_logs", service="api_gateway"))
        state = env.state()
        assert "api_gateway" in state.services_investigated
        assert "read_logs" in state.services_investigated["api_gateway"]
        
        env.step(
            IncidentAction(
                action_type="diagnose",
                service="api_gateway",
                diagnosis="service_crash",
            )
        )
        state = env.state()
        assert len(state.diagnoses_submitted) == 1
        assert state.correct_diagnoses == 1

    def test_deterministic_seeding(self) -> None:
        """Test that same seed produces same environment."""
        env1 = IncidentEnvironment()
        obs1 = env1.reset(task_id="easy_task", seed=12345)
        
        env2 = IncidentEnvironment()
        obs2 = env2.reset(task_id="easy_task", seed=12345)
        
        # Same alerts
        assert len(obs1.active_alerts) == len(obs2.active_alerts)
        
        # Same logs when queried
        result1 = env1.step(IncidentAction(action_type="read_logs", service="api_gateway"))
        result2 = env2.step(IncidentAction(action_type="read_logs", service="api_gateway"))
        
        assert len(result1.logs) == len(result2.logs)
        assert result1.logs[0].message == result2.logs[0].message


class TestObservationSpace:
    """Tests for observation space completeness."""

    def test_observation_has_required_fields(self) -> None:
        """Test that observations contain all required fields."""
        env = IncidentEnvironment()
        obs = env.reset(task_id="easy_task")
        
        # Required fields
        assert hasattr(obs, "action_result")
        assert hasattr(obs, "success")
        assert hasattr(obs, "message")
        assert hasattr(obs, "logs")
        assert hasattr(obs, "metrics")
        assert hasattr(obs, "service_summaries")
        assert hasattr(obs, "active_alerts")
        assert hasattr(obs, "dependency_graph")
        assert hasattr(obs, "step_number")
        assert hasattr(obs, "reward")
        assert hasattr(obs, "done")
        
        # Types
        assert isinstance(obs.active_alerts, list)
        assert isinstance(obs.service_summaries, list)
        assert isinstance(obs.dependency_graph, dict)

    def test_logs_observation(self) -> None:
        """Test that read_logs populates observation correctly."""
        env = IncidentEnvironment()
        env.reset(task_id="easy_task")
        
        result = env.step(IncidentAction(action_type="read_logs", service="api_gateway"))
        
        assert result.success
        assert len(result.logs) > 0
        assert all(hasattr(log, "timestamp") for log in result.logs)
        assert all(hasattr(log, "level") for log in result.logs)
        assert all(hasattr(log, "service") for log in result.logs)
        assert all(hasattr(log, "message") for log in result.logs)

    def test_metrics_observation(self) -> None:
        """Test that query_metrics populates observation correctly."""
        env = IncidentEnvironment()
        env.reset(task_id="easy_task")
        
        result = env.step(
            IncidentAction(action_type="query_metrics", service="api_gateway")
        )
        
        assert result.success
        assert result.metrics is not None
        assert result.metrics.service_name == "api_gateway"
        assert hasattr(result.metrics, "cpu_percent")
        assert hasattr(result.metrics, "memory_mb")
        assert hasattr(result.metrics, "request_latency_p50_ms")
        assert hasattr(result.metrics, "request_latency_p99_ms")
        assert hasattr(result.metrics, "error_rate_percent")
        assert hasattr(result.metrics, "status")
