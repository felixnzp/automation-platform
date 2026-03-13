from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database.database import get_db
from app.services import device_service

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


@router.get("")
def get_devices(keyword: str | None = Query(default=None), db: Session = Depends(get_db)):
    rows = device_service.list_devices(db, keyword)
    return [
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
        }
        for d in rows
    ]


@router.post("")
def add_device(payload: DevicePayload, db: Session = Depends(get_db)):
    row = device_service.create_device(db, payload.model_dump())
    return {"id": row.id}


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
