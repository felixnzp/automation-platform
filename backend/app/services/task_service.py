from datetime import datetime

from sqlalchemy.orm import Session

from app.automation import audit_module, ntp_module, snmp_module
from app.models.task import Task, TaskResult
from app.services.device_service import list_devices_by_ids
from app.utils.logger import task_logger


MODULE_MAP = {
    "audit": audit_module,
    "ntp": ntp_module,
    "snmp": snmp_module,
}


def list_tasks(db: Session):
    return db.query(Task).order_by(Task.id.desc()).all()


def get_task(db: Session, task_id: int):
    return db.query(Task).filter(Task.id == task_id).first()


def run_task(db: Session, task_type: str, device_ids: list[int], params: dict | None = None):
    if task_type not in MODULE_MAP:
        raise ValueError("Unsupported task type")

    params = params or {}
    devices = list_devices_by_ids(db, device_ids)
    start_time = datetime.now().isoformat(timespec="seconds")

    task = Task(
        task_type=task_type,
        start_time=start_time,
        status="running",
        total=len(devices),
        success=0,
        failed=0,
    )
    db.add(task)
    db.commit()
    db.refresh(task)

    module = MODULE_MAP[task_type]
    device_payload = [
        {
            "id": d.id,
            "name": d.name,
            "ip": d.ip,
            "username": d.username,
            "password": d.password,
            "port": d.port,
            "device_type": d.device_type,
        }
        for d in devices
    ]

    results = module.run(device_payload, params)

    success_count = 0
    fail_count = 0
    for item in results:
        is_success = item.get("status") == "success"
        success_count += 1 if is_success else 0
        fail_count += 0 if is_success else 1

        result_row = TaskResult(
            task_id=task.id,
            device_ip=item.get("device_ip", ""),
            device_name=item.get("device_name", ""),
            status=item.get("status", "failed"),
            message=item.get("message", ""),
            start_time=item.get("start_time", start_time),
            end_time=item.get("end_time", datetime.now().isoformat(timespec="seconds")),
        )
        db.add(result_row)

    task.success = success_count
    task.failed = fail_count
    task.end_time = datetime.now().isoformat(timespec="seconds")
    task.status = "success" if fail_count == 0 else "partial_failed"

    db.commit()
    db.refresh(task)

    task_logger.info(
        "task_id=%s type=%s total=%s success=%s failed=%s",
        task.id,
        task.task_type,
        task.total,
        task.success,
        task.failed,
    )
    return task
