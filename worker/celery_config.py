"""
CortexPrime Worker — Celery configuration.

Reads broker and backend URLs from environment variables,
with sensible defaults for local development.
"""
import os

broker_url = os.getenv(
    "CELERY_BROKER_URL",
    os.getenv("RABBITMQ_URL", "amqp://cortex:cortex@cortex-rabbitmq:5672/cortex"),
)

result_backend = os.getenv(
    "CELERY_RESULT_BACKEND",
    os.getenv("REDIS_URL", "redis://:cortex@cortex-redis:6379/0"),
)

task_serializer = "json"
result_serializer = "json"
accept_content = ["json"]
timezone = "UTC"
enable_utc = True

task_track_started = True
task_acks_late = True
worker_prefetch_multiplier = 1

task_routes = {
    "worker.tasks.execute_mission": {"queue": "missions"},
    "worker.tasks.process_document": {"queue": "documents"},
    "worker.tasks.health_check": {"queue": "health"},
}

beat_schedule = {}
