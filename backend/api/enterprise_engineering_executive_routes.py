"""
REST API for the Enterprise Engineering Executive.
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from backend.services.enterprise_engineering_executive import get_engineering_executive

router = APIRouter(prefix="/api/engineering-executive", tags=["engineering-executive"])


class TaskCreate(BaseModel):
    description: str
    repo_url: str = ""
    branch: str = ""


class PlanCreate(BaseModel):
    task_id: str


# ── Tasks ──

@router.post("/tasks")
async def create_task(body: TaskCreate):
    exec_service = get_engineering_executive()
    task = await exec_service.create_task(
        description=body.description,
        repo_url=body.repo_url,
        branch=body.branch,
    )
    return task


@router.get("/tasks")
async def list_tasks(status: str = ""):
    return await get_engineering_executive().list_tasks(status=status)


@router.get("/tasks/{task_id}")
async def get_task(task_id: str):
    task = await get_engineering_executive().get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return task


@router.delete("/tasks/{task_id}")
async def delete_task(task_id: str):
    deleted = await get_engineering_executive().delete_task(task_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Task not found")
    return {"status": "deleted"}


# ── Plans ──

@router.post("/plans")
async def create_plan(body: PlanCreate):
    exec_service = get_engineering_executive()
    plan = await exec_service.create_plan(task_id=body.task_id)
    if not plan:
        raise HTTPException(status_code=404, detail="Task not found")
    return plan


@router.get("/plans")
async def list_plans(status: str = ""):
    return await get_engineering_executive().list_plans(status=status)


@router.get("/plans/{plan_id}")
async def get_plan(plan_id: str):
    plan = await get_engineering_executive().get_plan(plan_id)
    if not plan:
        raise HTTPException(status_code=404, detail="Plan not found")
    return plan


@router.delete("/plans/{plan_id}")
async def delete_plan(plan_id: str):
    deleted = await get_engineering_executive().delete_plan(plan_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Plan not found")
    return {"status": "deleted"}


# ── Execution ──

@router.post("/plans/{plan_id}/execute")
async def execute_plan(plan_id: str):
    exec_service = get_engineering_executive()
    plan = await exec_service.execute_plan(plan_id)
    if not plan:
        raise HTTPException(status_code=404, detail="Plan not found")
    return plan


@router.get("/plans/{plan_id}/status")
async def get_execution_status(plan_id: str):
    status = await get_engineering_executive().get_execution_status(plan_id)
    if not status:
        raise HTTPException(status_code=404, detail="Plan not found")
    return status


# ── Reports ──

@router.post("/plans/{plan_id}/report")
async def generate_report(plan_id: str):
    exec_service = get_engineering_executive()
    report = await exec_service.generate_report(plan_id)
    if not report:
        raise HTTPException(status_code=404, detail="Plan not found")
    return report


@router.get("/reports")
async def list_reports():
    return await get_engineering_executive().list_reports()


@router.get("/reports/{report_id}")
async def get_report(report_id: str):
    report = await get_engineering_executive().get_report(report_id)
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")
    return report


# ── Dashboard ──

@router.get("/dashboard")
async def get_dashboard():
    return await get_engineering_executive().get_dashboard_stats()


# ── Supported Types ──

@router.get("/supported-types")
async def get_supported_types():
    from backend.services.enterprise_engineering_executive import SUPPORTED_TASK_TYPES
    return [
        {"type": k, "label": v["label"], "stages": v["stages"]}
        for k, v in SUPPORTED_TASK_TYPES.items()
    ]
