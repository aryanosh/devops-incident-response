"""
Centralized constants for DevOps Incident Response Environment.
Reward values, grading weights, and configuration limits.
"""

# ============================================================================
# Step Reward Values
# ============================================================================

REWARD_LIST_SERVICES_FIRST_TIME = 0.015
REWARD_INSPECT_DEPENDENCIES = 0.02
REWARD_ROOT_CAUSE_INVESTIGATION = 0.04
REWARD_AFFECTED_SERVICE_INVESTIGATION = 0.03
REWARD_CORRECT_DIAGNOSIS_ROOT_CAUSE = 0.08
REWARD_CORRECT_DIAGNOSIS_AFFECTED_SERVICE = 0.03
REWARD_CORRECT_FIX = 0.12
REWARD_SUCCESSFUL_VERIFICATION = 0.04
REWARD_HEALTHY_SERVICE_VERIFY = 0.01
REWARD_INVALID_ACTION = -0.03

# ============================================================================
# Grader Score Weights
# ============================================================================

GRADER_WEIGHT_ROOT_IDENTIFICATION = 0.35
GRADER_WEIGHT_RESOLUTION = 0.30
GRADER_WEIGHT_EFFICIENCY = 0.20
GRADER_WEIGHT_SAFETY = 0.15

# ============================================================================
# Grader Thresholds & Penalties
# ============================================================================

GRADER_MIN_EFFICIENCY = 0.05
GRADER_PENALTY_PER_DESTRUCTIVE_ACTION = 0.5
GRADER_PENALTY_PER_INVALID_ACTION = 0.1

# ============================================================================
# Score Clamping Bounds
# ============================================================================

SCORE_FLOOR = 0.001
SCORE_CEILING = 0.999
REWARD_DISPLAY_MAX = 0.99
TRAJECTORY_REWARD_MAX = 0.999
TRAJECTORY_REWARD_MIN = -0.999

# ============================================================================
# Request & Timeout Configuration
# ============================================================================

HTTP_CLIENT_TIMEOUT = 15.0
HTTP_CLIENT_MAX_RETRIES = 2
STEP_TIMEOUT_SECONDS = 30.0

# ============================================================================
# Input Validation Limits
# ============================================================================

MAX_REASONING_LENGTH = 5000
MAX_SERVICE_NAME_LENGTH = 100
MAX_DIAGNOSIS_LENGTH = 100
MAX_FIX_LENGTH = 100

# ============================================================================
# Other Configuration
# ============================================================================

BASE_TIMESTAMP = "2026-01-01T12:00:00Z"
SECONDS_PER_HOUR = 86400
