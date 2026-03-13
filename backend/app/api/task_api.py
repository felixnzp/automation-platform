from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.database.database import get_db
from app.models.task import Task
from app.services import task_service

router = APIRouter(prefix="/api/tasks", tags=["tasks"])


class TaskDeviceRequest(BaseModel):
    devices: list[int] = Field(default_factory=list)


class NtpRequest(TaskDeviceRequest):
    timezone: str = "BJ"
    offset: str = "08:00:00"
    ntp_server: str = "10.18.101.2"


class SnmpRequest(TaskDeviceRequest):
    community: str = "public"


def _task_to_dict(row: Task):
    return {
        "id": row.id,
        "task_type": row.task_type,
        "start_time": row.start_time,
        "end_time": row.end_time,
        "status": row.status,
        "total": row.total,
        "success": row.success,
        "failed": row.failed,
    }


@router.get("")
def list_task_history(db: Session = Depends(get_db)):
    rows = task_service.list_tasks(db)
    return [_task_to_dict(r) for r in rows]


@router.get("/{task_id}")
def get_task_detail(task_id: int, db: Session = Depends(get_db)):
    row = task_service.get_task(db, task_id)
    if not row:
        raise HTTPException(status_code=404, detail="Task not found")

    return {
        **_task_to_dict(row),
        "results": [
            {
                "id": item.id,
                "device_ip": item.device_ip,
                "device_name": item.device_name,
                "status": item.status,
                "message": item.message,
                "start_time": item.start_time,
                "end_time": item.end_time,
            }
            for item in row.results
        ],
    }


@router.post("/audit")
def execute_audit(payload: TaskDeviceRequest, db: Session = Depends(get_db)):
    task = task_service.run_task(db, "audit", payload.devices, {})
    return _task_to_dict(task)


@router.post("/ntp")
def execute_ntp(payload: NtpRequest, db: Session = Depends(get_db)):
    task = task_service.run_task(
        db,
        "ntp",
        payload.devices,
        {
            "timezone": payload.timezone,
            "offset": payload.offset,
            "ntp_server": payload.ntp_server,
        },
    )
    return _task_to_dict(task)


@router.post("/snmp")
def execute_snmp(payload: SnmpRequest, db: Session = Depends(get_db)):
    task = task_service.run_task(
        db,
        "snmp",
        payload.devices,
        {"community": payload.community},
    )
    return _task_to_dict(task)
