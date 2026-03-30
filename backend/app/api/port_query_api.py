from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.database.database import get_db
from app.services import ip_vlan_service


router = APIRouter(prefix="/api/port-query", tags=["port-query"])


class PortLocatePayload(BaseModel):
    queryType: str = Field(default="ip", description="ip/mac")
    queryValue: str = Field(default="", description="IP or MAC keyword")
    selectedMac: str = ""
    selectedCoreUplink: str = ""


class TrunkCheckPayload(BaseModel):
    taskId: str = ""
    targetVlan: int
    coreDeviceId: int
    coreUplinkPort: str
    accessSwitchId: int
    accessUplinkPort: str


class ChangeVlanPayload(BaseModel):
    taskId: str = ""
    ip: str = ""
    mac: str = ""
    accessSwitchId: int
    accessPort: str
    currentVlan: int | str = ""
    targetVlan: int
    coreDeviceId: int
    coreUplinkPort: str = ""
    accessUplinkPort: str = ""
    checkTrunkBeforeChange: bool = True
    autoFlapPort: bool = True
    operator: str = "unknown"


@router.post("/locate")
def locate_port(payload: PortLocatePayload, db: Session = Depends(get_db)):
    try:
        result = ip_vlan_service.port_query_locate(
            db,
            query_type=str(payload.queryType or "ip").strip().lower(),
            query_value=str(payload.queryValue or "").strip(),
            selected_mac=str(payload.selectedMac or "").strip(),
            selected_core_uplink=str(payload.selectedCoreUplink or "").strip(),
        )
        return {"code": 0, "message": "定位成功", "data": result}
    except ip_vlan_service.LocateTraceError as exc:
        raise HTTPException(status_code=400, detail={"code": "UNKNOWN_ERROR", "message": str(exc), "logs": getattr(exc, "logs", [])}) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail={"code": "PARAM_INVALID", "message": str(exc)}) from exc


@router.post("/check-trunk")
def check_trunk(payload: TrunkCheckPayload, db: Session = Depends(get_db)):
    try:
        result = ip_vlan_service.port_query_check_trunk(
            db,
            target_vlan=int(payload.targetVlan),
            core_device_id=int(payload.coreDeviceId),
            core_uplink_port=str(payload.coreUplinkPort or "").strip(),
            access_switch_id=int(payload.accessSwitchId),
            access_uplink_port=str(payload.accessUplinkPort or "").strip(),
            task_id=str(payload.taskId or "").strip(),
        )
        return {"code": 0, "message": "检查完成", "data": result}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail={"code": "TRUNK_CHECK_FAILED", "message": str(exc)}) from exc


@router.post("/change-vlan")
def change_vlan(payload: ChangeVlanPayload, db: Session = Depends(get_db)):
    try:
        result = ip_vlan_service.port_query_change_vlan(
            db,
            task_id=str(payload.taskId or "").strip(),
            ip=str(payload.ip or "").strip(),
            mac=str(payload.mac or "").strip(),
            access_switch_id=int(payload.accessSwitchId),
            access_port=str(payload.accessPort or "").strip(),
            current_vlan=str(payload.currentVlan or "").strip(),
            target_vlan=int(payload.targetVlan),
            core_device_id=int(payload.coreDeviceId),
            core_uplink_port=str(payload.coreUplinkPort or "").strip(),
            access_uplink_port=str(payload.accessUplinkPort or "").strip(),
            check_trunk_before_change=bool(payload.checkTrunkBeforeChange),
            auto_flap_port=bool(payload.autoFlapPort),
            operator=str(payload.operator or "unknown"),
        )
        return {"code": 0, "message": "VLAN 修改成功", "data": result}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail={"code": "VLAN_CHANGE_FAILED", "message": str(exc)}) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail={"code": "UNKNOWN_ERROR", "message": str(exc)}) from exc

