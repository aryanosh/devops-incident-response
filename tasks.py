from __future__ import annotations

from typing import Dict, List

try:
    from .models import TaskDefinition
except ImportError:
    from models import TaskDefinition

ALL_SERVICES: List[str] = [
    "api_gateway",
    "auth_service",
    "user_service",
    "order_service",
    "payment_service",
    "database",
]

SERVICE_DEPENDENCY_GRAPH: Dict[str, List[str]] = {
    "api_gateway": ["auth_service", "order_service"],
    "auth_service": ["user_service"],
    "user_service": ["database"],
    "order_service": ["payment_service", "database"],
    "payment_service": ["database"],
    "database": [],
}

VALID_ACTION_TYPES: List[str] = [
    "read_logs",
    "query_metrics",
    "diagnose",
    "apply_fix",
    "verify_health",
    "list_services",
    "inspect_dependencies",
]

VALID_DIAGNOSES: List[str] = [
    "service_crash",
    "memory_leak",
    "high_latency",
    "connection_pool_exhaustion",
    "disk_full",
    "certificate_expired",
    "config_drift",
]

VALID_FIXES: List[str] = [
    "restart_service",
    "memory_fix",
    "clear_disk",
    "scale_up",
    "rollback_config",
    "renew_certificate",
    "drain_connections",
    "clear_cache",
]

LOG_TEMPLATES: Dict[str, List[tuple[str, str]]] = {
    "service_crash": [
        ("FATAL", "Main worker exited unexpectedly with signal 11"),
        ("ERROR", "Readiness probe failed: connection refused"),
        ("FATAL", "Process supervisor detected crash loop after 5 restarts"),
        ("ERROR", "Upstream requests failing because process is not listening"),
        ("FATAL", "Container terminated with exit code 137"),
        ("ERROR", "Socket bind failed after process teardown"),
        ("WARN", "CrashLoopBackOff detected for deployment replicas"),
        ("ERROR", "No healthy workers available to accept traffic"),
    ],
    "memory_leak": [
        ("WARN", "Resident memory climbed to 92% of limit over 15m"),
        ("ERROR", "OOM killer terminated worker after allocation failure"),
        ("WARN", "Garbage collection pause exceeded 2400ms threshold"),
        ("ERROR", "Allocator unable to reserve memory for request context"),
        ("WARN", "Heap growth trend is non-linear and still increasing"),
        ("ERROR", "Request queue backlog growing under memory pressure"),
        ("WARN", "Container restarted after repeated OOM events"),
        ("ERROR", "Memory usage did not fall after full GC cycle"),
    ],
    "high_latency": [
        ("WARN", "P99 latency breached SLO: 4230ms > 250ms"),
        ("WARN", "Thread pool saturation reached 100/100 workers"),
        ("ERROR", "Client requests timing out waiting for upstream response"),
        ("WARN", "Latency regression observed across dependent RPC calls"),
        ("ERROR", "Timeout while awaiting downstream checkout dependency"),
        ("WARN", "Queue depth increasing faster than service throughput"),
        ("ERROR", "Slow requests exceed alert threshold for 10m"),
        ("WARN", "Autoscaler lagging behind burst traffic demand"),
    ],
    "connection_pool_exhaustion": [
        ("ERROR", "Database connection pool exhausted: 100/100 in use"),
        ("WARN", "Average wait time for pool checkout is 5100ms"),
        ("ERROR", "Request aborted because no DB connection became available"),
        ("WARN", "Long-lived transactions are holding pool slots"),
        ("ERROR", "Pool starvation causing circuit breaker to open"),
        ("WARN", "Retry storm detected against backing datastore"),
        ("ERROR", "Timed out acquiring pooled connection"),
        ("WARN", "Connection leak suspected in payment workflow"),
    ],
    "disk_full": [
        ("ERROR", "No space left on device while writing WAL segment"),
        ("FATAL", "Database checkpoint failed: disk allocation error"),
        ("ERROR", "Temporary file creation failed during query execution"),
        ("WARN", "Filesystem usage at 99.2% on primary volume"),
        ("ERROR", "Archive log shipping stalled because target volume is full"),
        ("FATAL", "Write-ahead logging suspended due to disk pressure"),
        ("WARN", "Background vacuum cannot complete on saturated disk"),
        ("ERROR", "Replication lag increasing after storage write failures"),
    ],
    "certificate_expired": [
        ("ERROR", "TLS handshake failed: certificate has expired"),
        ("WARN", "Peer verification rejected x509 chain"),
        ("ERROR", "mTLS connection refused due to expired server cert"),
        ("WARN", "Certificate validity window ended 2 days ago"),
        ("ERROR", "x509: certificate is not valid at current time"),
        ("WARN", "Ingress reports SSL validation errors for upstream"),
        ("ERROR", "Secure client connections are being terminated early"),
        ("WARN", "Renewal job missed last scheduled execution"),
    ],
    "config_drift": [
        ("ERROR", "Loaded DB_HOST does not match expected cluster endpoint"),
        ("WARN", "Feature flag state differs from deployment baseline"),
        ("ERROR", "Invalid configuration schema version detected on startup"),
        ("WARN", "Service env vars differ across replicas"),
        ("ERROR", "Canary and production pods are using different config hashes"),
        ("WARN", "Unexpected toggle enabled unsafe code path"),
        ("ERROR", "Configuration validation failed for payment connector"),
        ("WARN", "Manual change detected outside deployment pipeline"),
    ],
    "healthy": [
        ("INFO", "Health check OK for all worker threads"),
        ("INFO", "Processed requests within normal latency envelope"),
        ("DEBUG", "Connection reuse remains within target range"),
        ("INFO", "Background jobs completed successfully"),
        ("DEBUG", "Cache hit ratio steady above 93%"),
        ("INFO", "No error budget burn detected in the last interval"),
        ("DEBUG", "Resource utilization remains within baseline"),
        ("INFO", "Heartbeat and readiness probes are passing"),
    ],
}

SCENARIO_CONFIGS: Dict[str, Dict[str, object]] = {
    "easy_task": {
        "name": "Single Service Crash",
        "description": (
            "The API gateway has crashed and must be diagnosed from logs and "
            "restored with the correct fix."
        ),
        "difficulty": "easy",
        "max_steps": 8,
        "optimal_steps": 3,
        "root_cause_services": ["api_gateway"],
        "root_cause_failure_modes": ["service_crash"],
        "correct_fixes": {"api_gateway": "restart_service"},
        "affected_services": [],
        "symptom_modes": {},
        "primary_alerts": [
            {
                "severity": "critical",
                "service": "api_gateway",
                "title": "Gateway Unavailable",
                "description": (
                    "External traffic is failing with 502/503 errors because the gateway is down."
                ),
                "runbook_hint": "Check gateway process health and recent crash logs.",
            }
        ],
    },
    "medium_task": {
        "name": "Memory Leak in Order Service",
        "description": (
            "The order service is leaking memory, triggering OOM restarts and "
            "degraded checkout performance."
        ),
        "difficulty": "medium",
        "max_steps": 10,
        "optimal_steps": 4,
        "root_cause_services": ["order_service"],
        "root_cause_failure_modes": ["memory_leak"],
        "correct_fixes": {"order_service": "memory_fix"},
        "affected_services": ["api_gateway", "payment_service"],
        "symptom_modes": {
            "api_gateway": "high_latency",
            "payment_service": "connection_pool_exhaustion",
        },
        "primary_alerts": [
            {
                "severity": "high",
                "service": "order_service",
                "title": "Order Service Memory Pressure",
                "description": (
                    "Memory usage is approaching container limits with repeated OOM events."
                ),
                "runbook_hint": "Inspect memory behavior before applying a targeted fix.",
            },
            {
                "severity": "medium",
                "service": "api_gateway",
                "title": "Checkout Latency Elevated",
                "description": (
                    "Gateway latency increased because downstream order operations are unhealthy."
                ),
                "runbook_hint": "Differentiate symptoms from root cause.",
            },
        ],
    },
    "hard_task": {
        "name": "Cascading Failure from Database Disk Saturation",
        "description": (
            "The database volume is full, causing connection contention in payment, "
            "timeouts in order processing, and visible API failures."
        ),
        "difficulty": "hard",
        "max_steps": 12,
        "optimal_steps": 6,
        "root_cause_services": ["database"],
        "root_cause_failure_modes": ["disk_full"],
        "correct_fixes": {"database": "clear_disk"},
        "affected_services": ["payment_service", "order_service", "api_gateway"],
        "symptom_modes": {
            "payment_service": "connection_pool_exhaustion",
            "order_service": "high_latency",
            "api_gateway": "high_latency",
        },
        "primary_alerts": [
            {
                "severity": "critical",
                "service": "api_gateway",
                "title": "Gateway Error Spike",
                "description": (
                    "Customer-facing APIs are returning elevated 503 and timeout responses."
                ),
                "runbook_hint": (
                    "Trace dependencies instead of treating only the visible symptom."
                ),
            },
            {
                "severity": "critical",
                "service": "payment_service",
                "title": "Connection Pool Exhaustion",
                "description": (
                    "Payment workers are blocked waiting for database connections."
                ),
                "runbook_hint": "Inspect the dependency chain and database health.",
            },
        ],
    },
    "expert_task": {
        "name": "Compound Failure Across Database and Payment Plane",
        "description": (
            "The database is disk constrained and the payment service is also "
            "exhausting its connection pool, creating a multi-root incident that "
            "requires tracing both failure paths before the platform fully recovers."
        ),
        "difficulty": "expert",
        "max_steps": 14,
        "optimal_steps": 8,
        "root_cause_services": ["database", "payment_service"],
        "root_cause_failure_modes": ["disk_full", "connection_pool_exhaustion"],
        "correct_fixes": {
            "database": "clear_disk",
            "payment_service": "drain_connections",
        },
        "affected_services": ["order_service", "api_gateway"],
        "symptom_modes": {
            "order_service": "high_latency",
            "api_gateway": "high_latency",
        },
        "primary_alerts": [
            {
                "severity": "critical",
                "service": "api_gateway",
                "title": "Customer-Facing Errors Elevated",
                "description": (
                    "API traffic is timing out because both the payment and database paths are unhealthy."
                ),
                "runbook_hint": "Investigate both the visible symptom and the dependency chain.",
            },
            {
                "severity": "critical",
                "service": "payment_service",
                "title": "Payment Workers Stalled",
                "description": (
                    "Workers are blocked waiting on connections while the database is under storage pressure."
                ),
                "runbook_hint": "Resolve the storage and pool bottlenecks in the correct order.",
            },
        ],
    },
}


def get_task_definitions() -> List[TaskDefinition]:
    return [
        TaskDefinition(
            task_id=task_id,
            name=str(config["name"]),
            description=str(config["description"]),
            difficulty=str(config["difficulty"]),
            max_steps=int(config["max_steps"]),
        )
        for task_id, config in SCENARIO_CONFIGS.items()
    ]
