"""
CortexPrime Worker — Celery task definitions.

Workers execute background missions: browser automation, voice processing,
document analysis, and long-running research tasks.
"""
from celery import Celery

app = Celery("cortexprime_worker")

app.config_from_object("worker.celery_config")

@app.task(bind=True, max_retries=3, default_retry_delay=60)
def execute_mission(self, mission_id: str, payload: dict) -> dict:
    from agents.mission_executor import MissionExecutor
    executor = MissionExecutor()
    result = executor.run(mission_id, payload)
    return result

@app.task(bind=True, max_retries=2, default_retry_delay=30)
def process_document(self, document_id: str, content: str) -> dict:
    from cognitive_core.document_processor import DocumentProcessor
    processor = DocumentProcessor()
    result = processor.process(document_id, content)
    return result

@app.task(bind=True)
def health_check(self) -> dict:
    return {"status": "healthy", "worker": "cortexprime-worker"}
