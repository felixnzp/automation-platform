from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.database.database import get_db
from app.models.server_inspection import ServerInspectionDetail
from app.models.task import Task
from app.services import task_service
from app.services.device_service import list_devices_by_ips
from app.models.server_switch_detect_log import ServerSwitchDetectLog

router = APIRouter(prefix="/api/tasks", tags=["tasks"])


class GenericTaskRequest(BaseModel):
    task_type: str
    devices: list[int] = Field(default_factory=list)
    device_ids: list[int] = Field(default_factory=list)
    device_ips: list[str] = Field(default_factory=list)
    params: dict = Field(default_factory=dict)


class ExecuteTaskRequest(GenericTaskRequest):
    precheck_id: str | None = None


class ScheduledTaskPayload(BaseModel):
    name: str
    task_type: str
    target_mode: str = "all"
    target_group: str = ""
    target_device_ids: list[int] = Field(default_factory=list)
    params: dict = Field(default_factory=dict)
    cycle_type: str = "daily"
    run_time: str = "08:00"
    cron_expr: str = ""
    enabled: bool = True


def _payload_dict(payload: BaseModel) -> dict:
    if hasattr(payload, "model_dump"):
        return payload.model_dump()
    return payload.dict()


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


def _resolve_device_ids(payload: GenericTaskRequest, db: Session) -> list[int]:
    if payload.device_ids:
        return list(dict.fromkeys(payload.device_ids))

    if payload.devices:
        return list(dict.fromkeys(payload.devices))

    if payload.device_ips:
        rows = list_devices_by_ips(db, payload.device_ips)
        return [row.id for row in rows]

    return []


@router.get("/types")
def get_task_types():
    return task_service.list_task_types()


@router.post("/precheck")
def precheck(payload: GenericTaskRequest, db: Session = Depends(get_db)):
    device_ids = _resolve_device_ids(payload, db)
    try:
        return task_service.precheck_task(db, payload.task_type, device_ids, payload.params)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/execute")
def execute(payload: ExecuteTaskRequest, db: Session = Depends(get_db)):
    device_ids = _resolve_device_ids(payload, db)
    try:
        return task_service.execute_task(
            db,
            payload.task_type,
            device_ids,
            payload.params,
            payload.precheck_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/progress/{task_id}")
def get_progress(task_id: int, db: Session = Depends(get_db)):
    try:
        return task_service.get_task_progress(db, task_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("")
def list_task_history(db: Session = Depends(get_db)):
    rows = task_service.list_tasks(db)
    return [_task_to_dict(r) for r in rows]


@router.get("/{task_id}")
def get_task_detail(task_id: int, db: Session = Depends(get_db)):
    row = task_service.get_task(db, task_id)
    if not row:
        raise HTTPException(status_code=404, detail="Task not found")

    payload = {
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

    if row.task_type == task_service.SERVER_INSPECTION_TASK_TYPE:
        details = (
            db.query(ServerInspectionDetail)
            .filter(ServerInspectionDetail.task_id == task_id)
            .order_by(ServerInspectionDetail.id.asc())
            .all()
        )
        payload["server_details"] = [
            {
                "id": d.id,
                "server_id": d.server_id,
                "server_name": d.server_name,
                "server_ip": d.server_ip,
                "cpu_usage": d.cpu_usage,
                "memory_usage": d.memory_usage,
                "disk_usage": d.disk_usage,
                "cpu_status": d.cpu_status,
                "memory_status": d.memory_status,
                "disk_status": d.disk_status,
                "result_level": d.result_level,
                "result_message": d.result_message,
                "executed_at": d.executed_at,
            }
            for d in details
        ]

    if row.task_type == task_service.SERVER_SWITCH_DETECT_TASK_TYPE:
        logs = (
            db.query(ServerSwitchDetectLog)
            .filter(ServerSwitchDetectLog.task_id == task_id)
            .order_by(ServerSwitchDetectLog.id.asc())
            .all()
        )
        payload["switch_detect_logs"] = [
            {
                "id": item.id,
                "server_id": item.server_id,
                "server_name": item.server_name,
                "server_ip": item.server_ip,
                "detect_status": item.detect_status,
                "detect_message": item.detect_message,
                "access_switch_name": item.access_switch_name,
                "core_uplink_port": item.core_uplink_port,
                "switch_downlink_port": item.switch_downlink_port,
                "arp_raw": item.arp_raw,
                "lldp_raw": item.lldp_raw,
                "trigger_type": item.trigger_type,
                "created_at": item.created_at,
            }
            for item in logs
        ]

    return payload


@router.get("/schedules/list")
def list_schedules(db: Session = Depends(get_db)):
    return task_service.list_scheduled_tasks(db)


@router.post("/schedules")
def create_schedule(payload: ScheduledTaskPayload, db: Session = Depends(get_db)):
    try:
        return task_service.create_scheduled_task(db, _payload_dict(payload))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.put("/schedules/{schedule_id}")
def update_schedule(schedule_id: int, payload: ScheduledTaskPayload, db: Session = Depends(get_db)):
    try:
        return task_service.update_scheduled_task(db, schedule_id, _payload_dict(payload))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.delete("/schedules/{schedule_id}")
def delete_schedule(schedule_id: int, db: Session = Depends(get_db)):
    ok = task_service.delete_scheduled_task(db, schedule_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Schedule task not found")
    return {"deleted": True}


@router.post("/schedules/{schedule_id}/run-once")
def run_schedule_once(schedule_id: int, db: Session = Depends(get_db)):
    try:
        return task_service.run_scheduled_task_once(db, schedule_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
