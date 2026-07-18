from prometheus_client import start_http_server, Counter, Gauge, Histogram
import os

celery_tasks_total = Counter(
    "celery_tasks_total", "Total Celery tasks processed",
    ["task_name", "status"],
)
celery_task_duration_seconds = Histogram(
    "celery_task_duration_seconds", "Celery task duration in seconds",
    ["task_name"],
    buckets=[0.1, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0, 60.0, 120.0],
)
celery_queue_length = Gauge(
    "celery_queue_length", "Current Celery queue length",
    ["queue"],
)
worker_up = Gauge("worker_up", "Worker process health", multiprocess_mode="liveall")
worker_up.set(1)

PORT = int(os.getenv("WORKER_METRICS_PORT", "9100"))


def start_metrics_server() -> None:
    start_http_server(PORT)
