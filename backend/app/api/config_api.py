from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.database.database import get_db
from app.services import config_service, ip_vlan_service

router = APIRouter(prefix="/api/config", tags=["config-center"])


class ConfigPrecheckPayload(BaseModel):
    intent: str
    device_ids: list[int] = Field(default_factory=list)
    params: dict = Field(default_factory=dict)


class ConfigExecutePayload(ConfigPrecheckPayload):
    precheck_id: str | None = None
    auto_rollback: bool = True


class IpLocatePayload(BaseModel):
    query_type: str = "ip"
    target_ip: str = ""
    mac_keyword: str = ""
    selected_mac: str = ""
    selected_core_uplink: str = ""


class IpVlanExecutePayload(BaseModel):
    locate_data: dict = Field(default_factory=dict)
    new_vlan: int
    operator: str = "unknown"


class IpVlanValidatePayload(BaseModel):
    locate_data: dict = Field(default_factory=dict)
    new_vlan: int


def _job_to_dict(row):
    return {
        "id": row.id,
        "intent": row.intent,
        "start_time": row.start_time,
        "end_time": row.end_time,
        "status": row.status,
        "total": row.total,
        "success": row.success,
        "failed": row.failed,
        "skipped": row.skipped,
    }


@router.get("/intents")
def get_intents():
    return config_service.list_intents()


@router.post("/precheck")
def precheck(payload: ConfigPrecheckPayload, db: Session = Depends(get_db)):
    try:
        return config_service.precheck(db, payload.intent, payload.device_ids, payload.params or {})
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/execute")
def execute(payload: ConfigExecutePayload, db: Session = Depends(get_db)):
    try:
        return config_service.execute(
            db,
            payload.intent,
            payload.device_ids,
            payload.params or {},
            payload.precheck_id,
            payload.auto_rollback,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/jobs")
def list_jobs(db: Session = Depends(get_db)):
    return [_job_to_dict(item) for item in config_service.list_jobs(db)]


@router.get("/jobs/{job_id}")
def get_job(job_id: int, db: Session = Depends(get_db)):
    row = config_service.get_job(db, job_id)
    if not row:
        raise HTTPException(status_code=404, detail="配置任务不存在")
    return {
        **_job_to_dict(row),
        "results": [
            {
                "id": item.id,
                "device_id": item.device_id,
                "device_name": item.device_name,
                "device_ip": item.device_ip,
                "role": item.role,
                "status": item.status,
                "message": item.message,
                "backup_file": item.backup_file,
                "rollback_status": item.rollback_status,
                "start_time": item.start_time,
                "end_time": item.end_time,
                "command_preview": item.command_preview,
                "verify_output": item.verify_output,
            }
            for item in row.results
        ],
    }


@router.get("/jobs/{job_id}/progress")
def get_progress(job_id: int, db: Session = Depends(get_db)):
    try:
        return config_service.get_progress(db, job_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/ip-vlan/locate")
def locate_ip(payload: IpLocatePayload, db: Session = Depends(get_db)):
    try:
        if str(payload.query_type or "ip").lower() == "mac":
            return ip_vlan_service.locate_by_mac(
                db,
                payload.mac_keyword,
                selected_mac=payload.selected_mac,
                selected_core_uplink=payload.selected_core_uplink,
            )
        return ip_vlan_service.locate_ip(db, payload.target_ip)
    except ip_vlan_service.LocateTraceError as exc:
        raise HTTPException(status_code=400, detail={"message": str(exc), "logs": getattr(exc, "logs", [])}) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/ip-vlan/execute")
def execute_ip_vlan(payload: IpVlanExecutePayload, db: Session = Depends(get_db)):
    try:
        return ip_vlan_service.execute_vlan_change(
            db,
            payload.locate_data or {},
            int(payload.new_vlan),
            payload.operator,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        # Always return JSON so the frontend can show a readable error message.
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/ip-vlan/validate")
def validate_ip_vlan(payload: IpVlanValidatePayload, db: Session = Depends(get_db)):
    try:
        return ip_vlan_service.validate_target_vlan(
            db,
            payload.locate_data or {},
            int(payload.new_vlan),
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/ip-vlan/logs")
def list_ip_vlan_logs(limit: int = 50, db: Session = Depends(get_db)):
    return ip_vlan_service.list_logs(db, limit=limit)
