from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database.database import get_db
from app.services import device_service
from app.services.device_import_service import confirm_import, preview_import
from app.utils.network import ping_device
from concurrent.futures import ThreadPoolExecutor, as_completed

router = APIRouter(prefix="/api/devices", tags=["devices"])


class DevicePayload(BaseModel):
    name: str
    ip: str
    username: str
    password: str
    port: int = 22
    device_type: str = "huawei"
    group_name: str = "default"
    location: str = "unknown"
    enable: int = 1


class ImportConfirmPayload(BaseModel):
    preview_id: str


@router.get("")
def get_devices(
    keyword: str | None = Query(default=None),
    group_name: str | None = Query(default=None),
    with_status: bool = Query(default=True),
    db: Session = Depends(get_db),
):
    rows = device_service.list_devices(db, keyword, group_name)
    payload_rows = [
        {
            "id": d.id,
            "name": d.name,
            "ip": d.ip,
            "username": d.username,
            "password": d.password,
            "port": d.port,
            "device_type": d.device_type,
            "group_name": d.group_name,
            "location": d.location,
            "enable": d.enable,
            "status": "unknown",
        }
        for d in rows
    ]

    if not with_status or not payload_rows:
        return payload_rows

    # Speed: compute ping status concurrently; a sequential ping per device can be very slow
    # when there are offline devices.
    max_workers = min(32, max(4, len(payload_rows)))
    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        future_map = {
            pool.submit(ping_device, row.get("ip") or "", 400): row
            for row in payload_rows
            if row.get("enable") == 1 and row.get("ip")
        }
        for future in as_completed(future_map):
            row = future_map[future]
            try:
                row["status"] = future.result()
            except Exception:
                row["status"] = "offline"

    # Disabled devices are treated as offline for quick status.
    for row in payload_rows:
        if row.get("enable") != 1:
            row["status"] = "offline"

    return payload_rows


@router.post("")
def add_device(payload: DevicePayload, db: Session = Depends(get_db)):
    row = device_service.create_device(db, payload.model_dump())
    return {"id": row.id}


@router.post("/import/preview")
async def import_preview(file: UploadFile = File(...), db: Session = Depends(get_db)):
    content = await file.read()
    try:
        return preview_import(db, file.filename or "", content)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/import/confirm")
def import_confirm(payload: ImportConfirmPayload, db: Session = Depends(get_db)):
    try:
        return confirm_import(db, payload.preview_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.put("/{device_id}")
def update_device(device_id: int, payload: DevicePayload, db: Session = Depends(get_db)):
    row = device_service.update_device(db, device_id, payload.model_dump())
    if not row:
        raise HTTPException(status_code=404, detail="Device not found")
    return {"message": "updated"}


@router.delete("/{device_id}")
def remove_device(device_id: int, db: Session = Depends(get_db)):
    ok = device_service.delete_device(db, device_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Device not found")
    return {"message": "deleted"}
