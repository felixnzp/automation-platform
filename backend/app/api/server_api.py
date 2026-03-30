from typing import Literal

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database.database import get_db
from app.services import server_service
from app.services.server_import_service import confirm_import, preview_import
from app.services.server_topology_service import build_server_topology
from app.services import task_service

router = APIRouter(prefix="/api/servers", tags=["servers"])


class ServerPayload(BaseModel):
    name: str
    ip: str
    hostname: str = ""
    server_type: Literal["linux", "windows"] = "linux"
    access_method: str = ""
    username: str
    password: str
    port: int | None = None
    group_name: str = "default"
    enable: int = 1
    auto_locate_topology: bool | None = None


class ImportConfirmPayload(BaseModel):
    preview_id: str


@router.get("")
def get_servers(
    keyword: str | None = Query(default=None),
    group_name: str | None = Query(default=None),
    with_status: bool = Query(default=True),
    db: Session = Depends(get_db),
):
    rows = server_service.list_servers(db, keyword, group_name, with_status=with_status)
    return [server_service.serialize_server(row) for row in rows]


@router.get("/groups")
def get_server_groups(db: Session = Depends(get_db)):
    return server_service.list_server_groups(db)


@router.get("/topology")
def get_server_topology(
    with_status: bool = Query(
        default=False,
        description="是否实时探测服务器状态/指标。默认 false（快速首屏，只读取数据库已有状态）。",
    ),
    auto_locate: bool = Query(
        default=False,
        description="是否在本次请求中对未定位服务器执行 ARP/LLDP 自动定位。默认 false（避免阻塞）。",
    ),
    skeleton: bool = Query(default=False),
    db: Session = Depends(get_db),
):
    # Fast-first: default does NOT probe servers and does NOT auto locate topology.
    return build_server_topology(db, with_status=with_status, auto_locate=auto_locate, include_servers=not skeleton)


@router.post("")
def add_server(payload: ServerPayload, db: Session = Depends(get_db)):
    model = payload.model_dump(exclude_unset=True)
    auto_locate = model.pop("auto_locate_topology", True)
    row = server_service.create_server(db, model, auto_locate_topology=auto_locate)
    task_id = None
    if auto_locate:
        try:
            queued = task_service.execute_task(
                db,
                task_service.SERVER_SWITCH_DETECT_TASK_TYPE,
                [row.id],
                params={"trigger": "create", "force": False},
                precheck_id=None,
            )
            task_id = queued.get("task_id")
        except Exception:
            task_id = None
    return {"id": row.id, "switch_detect_task_id": task_id}


@router.post("/test-connection")
def test_server_connection_with_payload(payload: ServerPayload):
    # NOTE: `ServerPayload` contains UI-only fields like `auto_locate_topology` that are not part of the
    # ServerAsset ORM model. Strip them to avoid 500s during test connection.
    model = payload.model_dump(exclude_unset=True)
    model.pop("auto_locate_topology", None)
    return server_service.test_connection_payload(model)


@router.post("/import/preview")
async def import_server_preview(file: UploadFile = File(...), db: Session = Depends(get_db)):
    content = await file.read()
    try:
        return preview_import(db, file.filename or "", content)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/import/confirm")
def import_server_confirm(payload: ImportConfirmPayload, db: Session = Depends(get_db)):
    try:
        return confirm_import(db, payload.preview_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.put("/{server_id}")
def update_server(server_id: int, payload: ServerPayload, db: Session = Depends(get_db)):
    model = payload.model_dump(exclude_unset=True)
    auto_locate = model.pop("auto_locate_topology", False)
    row = server_service.update_server(db, server_id, model, auto_locate_topology=auto_locate)
    if not row:
        raise HTTPException(status_code=404, detail="Server not found")
    task_id = None
    if auto_locate and row.enable == 1:
        try:
            queued = task_service.execute_task(
                db,
                task_service.SERVER_SWITCH_DETECT_TASK_TYPE,
                [row.id],
                params={"trigger": "manual", "force": True},
                precheck_id=None,
            )
            task_id = queued.get("task_id")
        except Exception:
            task_id = None
    return {"message": "updated", "switch_detect_task_id": task_id}


@router.post("/{server_id}/relocate-topology")
def relocate_server_topology(server_id: int, db: Session = Depends(get_db)):
    row = server_service.get_server(db, server_id)
    if not row:
        raise HTTPException(status_code=404, detail="Server not found")
    try:
        queued = task_service.execute_task(
            db,
            task_service.SERVER_SWITCH_DETECT_TASK_TYPE,
            [row.id],
            params={"trigger": "manual", "force": True},
            precheck_id=None,
        )
        return {"task_id": queued.get("task_id"), "status": queued.get("status", "running")}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/{server_id}/detect-switch")
def detect_server_switch(server_id: int, db: Session = Depends(get_db)):
    row = server_service.get_server(db, server_id)
    if not row:
        raise HTTPException(status_code=404, detail="Server not found")
    try:
        queued = task_service.execute_task(
            db,
            task_service.SERVER_SWITCH_DETECT_TASK_TYPE,
            [row.id],
            params={"trigger": "manual", "force": True},
            precheck_id=None,
        )
        return {"task_id": queued.get("task_id"), "status": queued.get("status", "running")}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


class DetectBatchPayload(BaseModel):
    server_ids: list[int] = []
    force: bool = True


@router.post("/detect-switch/batch")
def detect_server_switch_batch(payload: DetectBatchPayload, db: Session = Depends(get_db)):
    ids = [int(x) for x in (payload.server_ids or []) if str(x).strip()]
    if not ids:
        raise HTTPException(status_code=400, detail="请选择至少一台服务器")
    try:
        queued = task_service.execute_task(
            db,
            task_service.SERVER_SWITCH_DETECT_TASK_TYPE,
            ids,
            params={"trigger": "batch", "force": bool(payload.force)},
            precheck_id=None,
        )
        return {"task_id": queued.get("task_id"), "status": queued.get("status", "running"), "total": queued.get("total", 0)}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.delete("/{server_id}")
def remove_server(server_id: int, db: Session = Depends(get_db)):
    ok = server_service.delete_server(db, server_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Server not found")
    return {"message": "deleted"}


@router.post("/{server_id}/test-connection")
def test_server_connection(server_id: int, db: Session = Depends(get_db)):
    result = server_service.test_connection(db, server_id)
    if not result:
        raise HTTPException(status_code=404, detail="Server not found")
    return result
