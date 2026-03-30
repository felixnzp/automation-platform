from __future__ import annotations

import re
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends
from netmiko import ConnectHandler
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.database.database import get_db
from app.models.device import Device
from app.models.server import ServerAsset
from app.models.server_inspection import ServerInspectionDetail
from app.models.task import Task, TaskResult
from app.services import server_service
from app.utils.network import ping_device

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])

ROLE_ROUTER = "router"
ROLE_CORE_SW = "core_switch"
ROLE_ACCESS_SW = "access_switch"
ROLE_UNKNOWN = "unknown"
SERVER_ROLE = "server"

_SSH_CACHE_LOCK = threading.Lock()
_SSH_CACHE: dict[str, dict] = {}
_SSH_CACHE_TTL_SECONDS = 120


def _parse_dt(value: str | None) -> datetime | None:
    if not value:
        return None
    text = str(value).strip()
    if not text:
        return None

    text = text.replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(text)
    except ValueError:
        pass

    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y/%m/%d %H:%M:%S"):
        try:
            return datetime.strptime(text, fmt)
        except ValueError:
            continue
    return None


def _fmt_dt(value: datetime | None) -> str:
    if not value:
        return ""
    return value.strftime("%Y-%m-%d %H:%M:%S")


def _infer_role(device: Device) -> str:
    bag = " ".join([
        str(device.name or ""),
        str(device.device_type or ""),
        str(device.group_name or ""),
        str(device.location or ""),
    ]).lower()

    if any(key in bag for key in ["sz-router", "router", "路由", "ar"]):
        return ROLE_ROUTER
    if any(key in bag for key in ["core", "核心"]):
        return ROLE_CORE_SW
    if any(key in bag for key in ["switch", "sw", "交换"]):
        return ROLE_ACCESS_SW
    return ROLE_UNKNOWN


def _infer_floor(device: Device) -> str:
    floor_group = getattr(device, "floor_group", None)
    if floor_group:
        fg = str(floor_group).strip().upper()
        if fg in {"17F", "18F"}:
            return fg

    name_first = str(device.name or "")
    m = re.search(r"(17F|18F)", name_first, re.IGNORECASE)
    if m:
        return m.group(1).upper()

    for text in [str(device.group_name or ""), str(device.location or "")]:
        m2 = re.search(r"(17F|18F)", text, re.IGNORECASE)
        if m2:
            return m2.group(1).upper()

    return "18F"


def _short_name(device: Device, floor: str) -> str:
    name = str(device.name or "").strip()
    m = re.search(r"(\d{1,2}F[-_ ]?SW\d+)", name, re.IGNORECASE)
    if m:
        return m.group(1).upper().replace("_", "-").replace(" ", "")

    idx = re.search(r"SW[-_ ]?(\d+)", name, re.IGNORECASE)
    if idx:
        return f"{floor}-SW{idx.group(1)}"

    if floor in {"17F", "18F"}:
        return f"{floor}-SW"
    return name[:12] if name else "SW"


def _ping_access_stable(ip: str) -> str:
    # Avoid false offline from one-shot ICMP loss.
    for _ in range(3):
        if ping_device(ip) == "online":
            return "online"
        time.sleep(0.2)
    return "offline"


def _latest_probe_state(device: Device, role: str, now: datetime) -> tuple[str, str, str]:
    ip = str(device.ip or "").strip()
    if not ip:
        return "unknown", "unknown", ""

    with _SSH_CACHE_LOCK:
        cached = _SSH_CACHE.get(ip)
        if cached and (now - cached.get("checked_at", now)).total_seconds() <= _SSH_CACHE_TTL_SECONDS:
            return cached.get("ssh", "unknown"), cached.get("ping", "offline"), _fmt_dt(cached.get("checked_at"))

    if role in {ROLE_ACCESS_SW, ROLE_UNKNOWN}:
        ping_state = _ping_access_stable(ip)
        checked_at = datetime.now()
        with _SSH_CACHE_LOCK:
            _SSH_CACHE[ip] = {
                "ssh": "skipped",
                "ping": ping_state,
                "checked_at": checked_at,
            }
        return "skipped", ping_state, _fmt_dt(checked_at)

    ping_state = ping_device(ip, timeout_ms=500)
    ssh_state = "unknown"

    # If ping is offline, skip SSH entirely to keep overview fast and avoid long SSH timeouts.
    if ping_state != "online":
        checked_at = datetime.now()
        with _SSH_CACHE_LOCK:
            _SSH_CACHE[ip] = {
                "ssh": "skipped",
                "ping": ping_state,
                "checked_at": checked_at,
            }
        return "skipped", ping_state, _fmt_dt(checked_at)

    if device.enable != 1:
        ssh_state = "unknown"
    elif not (device.username and device.password and device.port):
        ssh_state = "unknown"
    else:
        conn = None
        try:
            conn = ConnectHandler(
                device_type=str(device.device_type or "huawei"),
                host=ip,
                username=str(device.username or ""),
                password=str(device.password or ""),
                port=int(device.port or 22),
                conn_timeout=3,
                auth_timeout=3,
                banner_timeout=3,
                fast_cli=False,
                use_keys=False,
                allow_agent=False,
            )
            ssh_state = "success"
        except Exception:
            ssh_state = "failed"
        finally:
            if conn is not None:
                try:
                    conn.disconnect()
                except Exception:
                    pass

    checked_at = datetime.now()
    with _SSH_CACHE_LOCK:
        _SSH_CACHE[ip] = {
            "ssh": ssh_state,
            "ping": ping_state,
            "checked_at": checked_at,
        }

    return ssh_state, ping_state, _fmt_dt(checked_at)


def _fast_probe_state(device: dict) -> tuple[str, str, str]:
    ip = str(device.get("ip") or "").strip()
    if not ip:
        return "unknown", "unknown", ""

    checked_at = datetime.now()
    ping_state = ping_device(ip, timeout_ms=500)
    return "skipped", ping_state, _fmt_dt(checked_at)


def _calc_status(
    role: str,
    ssh_state: str,
    ping_state: str,
    latest_result: TaskResult | None,
    last_probe_time: str,
) -> tuple[str, str, str]:
    if role in {ROLE_ACCESS_SW, ROLE_UNKNOWN}:
        if ping_state == "online":
            reason = "接入设备Ping可达"
            if latest_result:
                reason += f"；最近任务状态: {latest_result.status}"
            return "normal", reason, last_probe_time

        if ping_state == "offline":
            reason = "接入设备Ping不可达"
            if latest_result:
                reason += f"；最近任务状态: {latest_result.status}"
            return "offline", reason, last_probe_time

        if latest_result:
            latest_time = _parse_dt(latest_result.end_time) or _parse_dt(latest_result.start_time)
            return "unknown", f"接入设备未检测；最近任务状态: {latest_result.status}", _fmt_dt(latest_time)
        return "unknown", "接入设备未检测", ""

    if ssh_state == "success":
        reason = "SSH可登录，设备在线"
        if latest_result:
            reason += f"；最近任务状态: {latest_result.status}"
        return "normal", reason, last_probe_time

    if ssh_state == "skipped" and ping_state == "online":
        reason = "Ping可达，快速状态正常"
        if latest_result:
            reason += f"；最近任务状态: {latest_result.status}"
        return "normal", reason, last_probe_time

    if ssh_state == "skipped" and ping_state != "online":
        reason = "Ping不可达，快速状态离线"
        if latest_result:
            reason += f"；最近任务状态: {latest_result.status}"
        return "offline", reason, last_probe_time

    if ssh_state == "failed" and ping_state == "online":
        reason = "Ping可达但SSH失败，设备异常"
        if latest_result:
            reason += f"；最近任务状态: {latest_result.status}"
        return "alarm", reason, last_probe_time

    if ssh_state == "failed" and ping_state != "online":
        reason = "SSH失败且Ping失败，设备离线"
        if latest_result:
            reason += f"；最近任务状态: {latest_result.status}"
        return "offline", reason, last_probe_time

    if latest_result:
        latest_time = _parse_dt(latest_result.end_time) or _parse_dt(latest_result.start_time)
        return "unknown", f"未完成实时检测；最近任务状态: {latest_result.status}", _fmt_dt(latest_time)
    return "unknown", "未检测", ""


def _build_server_rows(
    db: Session,
    now: datetime,
    latest_result_by_ip: dict[str, TaskResult],
) -> tuple[list[dict], dict]:
    # Refresh server connectivity status (cached in DB, refresh interval is short).
    rows = server_service.list_servers(db, with_status=True)
    server_rows: list[dict] = []
    online_count = 0
    offline_count = 0
    normal_count = 0
    warning_count = 0
    critical_count = 0
    unknown_count = 0

    server_ids = [item.id for item in rows]
    latest_inspections: dict[int, ServerInspectionDetail] = {}
    if server_ids:
        subq = (
            db.query(
                ServerInspectionDetail.server_id.label("server_id"),
                func.max(ServerInspectionDetail.id).label("max_id"),
            )
            .filter(ServerInspectionDetail.server_id.in_(server_ids))
            .group_by(ServerInspectionDetail.server_id)
            .subquery()
        )
        latest_rows = (
            db.query(ServerInspectionDetail)
            .join(subq, ServerInspectionDetail.id == subq.c.max_id)
            .all()
        )
        latest_inspections = {row.server_id: row for row in latest_rows}

    for item in rows:
        latest_result = latest_result_by_ip.get(item.ip)
        dashboard_status = item.status or "unknown"
        reason = item.last_error or "最近检测成功"

        # 在线/离线只反映“是否可通信”，不与健康（CPU/内存/磁盘）混在一起。
        # 可通信：online / online_abnormal / alarm / unknown(可按需调整)
        is_offline = str(dashboard_status).lower() == "offline"
        if is_offline:
            offline_count += 1
        else:
            online_count += 1

        # 健康等级（正常/告警/严重）来自最近一次服务器巡检结果。
        inspection = latest_inspections.get(item.id)
        level = str(getattr(inspection, "result_level", "") or "").lower()
        if not is_offline:
            if level == "normal":
                normal_count += 1
            elif level == "warning":
                warning_count += 1
            elif level in {"critical", "failed"}:
                critical_count += 1
            else:
                unknown_count += 1

        server_rows.append(
            {
                "id": item.id,
                "name": item.name,
                "ip": item.ip,
                "hostname": item.hostname or "",
                "role": SERVER_ROLE,
                "server_type": item.server_type,
                "access_method": item.access_method,
                "group_name": item.group_name,
                "status": dashboard_status,
                "status_reason": reason,
                "last_check_time": _fmt_dt(item.last_checked_at),
                "last_error": item.last_error or "",
                "latest_task_status": latest_result.status if latest_result else "",
                "username": item.username,
                "password": item.password,
                "port": item.port,
                "enable": item.enable,
                "inspection_level": level or "unknown",
                "inspection_time": getattr(inspection, "executed_at", "") if inspection else "",
            }
        )

    return server_rows, {
        "total_devices": len(rows),
        "online_devices": online_count,
        "offline_devices": offline_count,
        "normal_devices": normal_count,
        "warning_devices": warning_count,
        "critical_devices": critical_count,
        "unknown_devices": unknown_count,
        # 兼容旧字段：告警总数 = 告警 + 严重
        "alarm_devices": warning_count + critical_count,
    }


def _task_target_type(task_type: str | None) -> str:
    """Infer task target view: network/server.

    We currently treat server inspection as the only server task type.
    """
    if str(task_type or "").lower() == "server_inspection":
        return "server"
    return "network"


@router.get("/overview")
def get_overview(db: Session = Depends(get_db)):
    now = datetime.now()

    devices = db.query(Device).order_by(Device.id.asc()).all()
    device_snapshots = [
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
        for d in devices
    ]
    # Avoid full-table scans when tasks/results grow large.
    tasks = db.query(Task).order_by(Task.id.desc()).limit(300).all()
    results = db.query(TaskResult).order_by(TaskResult.id.desc()).limit(1500).all()

    latest_result_by_ip: dict[str, TaskResult] = {}
    for row in results:
        if row.device_ip and row.device_ip not in latest_result_by_ip:
            latest_result_by_ip[row.device_ip] = row

    role_map = {d["id"]: _infer_role(type("DeviceRow", (), d)()) for d in device_snapshots}
    server_rows, server_stats = _build_server_rows(db, now, latest_result_by_ip)

    probe_map: dict[int, tuple[str, str, str]] = {}
    with ThreadPoolExecutor(max_workers=8) as pool:
        future_map = {pool.submit(_fast_probe_state, d): d["id"] for d in device_snapshots}
        for future in as_completed(future_map):
            dev_id = future_map[future]
            try:
                probe_map[dev_id] = future.result()
            except Exception:
                probe_map[dev_id] = ("unknown", "unknown", "")

    normal_count = 0
    offline_count = 0
    alarm_count = 0

    device_rows = []
    alerts = []

    for d in device_snapshots:
        role = role_map.get(d["id"], ROLE_UNKNOWN)
        floor = _infer_floor(type("DeviceRow", (), d)())
        latest_result = latest_result_by_ip.get(d["ip"])
        ssh_state, ping_state, probe_time = probe_map.get(d["id"], ("unknown", "offline", ""))

        status, reason, last_check_time = _calc_status(role, ssh_state, ping_state, latest_result, probe_time)

        if status == "normal":
            normal_count += 1
        elif status == "offline":
            offline_count += 1
        elif status == "alarm":
            alarm_count += 1

        row = {
            "id": d["id"],
            "name": d["name"],
            "short_name": _short_name(type("DeviceRow", (), d)(), floor),
            "ip": d["ip"],
            "role": role,
            "floor": floor,
            "group_name": d["group_name"],
            "location": d["location"],
            "device_type": d["device_type"],
            "status": status,
            "status_reason": reason,
            "last_check_time": last_check_time,
            "ping_status": ping_state,
            "ssh_status": ssh_state,
            "latest_task_status": (latest_result.status if latest_result else ""),
        }
        device_rows.append(row)

        if status in {"offline", "alarm"}:
            alerts.append(
                {
                    "device": f"{d['name']}({d['ip']})",
                    "time": last_check_time or _fmt_dt(now),
                    "type": "设备离线" if status == "offline" else "状态异常",
                    "severity": status,
                    "message": reason,
                }
            )

    for row in results[:80]:
        if str(row.status).lower() != "failed":
            continue
        t = _parse_dt(row.end_time) or _parse_dt(row.start_time) or now
        alerts.append(
            {
                "device": f"{row.device_name}({row.device_ip})",
                "time": _fmt_dt(t),
                "type": "任务失败",
                "severity": "alarm",
                "message": row.message or "任务执行失败",
            }
        )

    alerts_sorted = sorted(alerts, key=lambda x: x.get("time", ""), reverse=True)[:20]

    today = now.strftime("%Y-%m-%d")
    cutoff = now - timedelta(days=7)

    task_rows = [
        {
            "id": t.id,
            "task_type": t.task_type,
            "target_type": _task_target_type(t.task_type),
            "start_time": t.start_time,
            "end_time": t.end_time,
            "status": t.status,
            "total": t.total,
            "success": t.success,
            "failed": t.failed,
        }
        for t in tasks
    ]

    today_tasks = sum(1 for t in task_rows if str(t.get("start_time") or "").startswith(today))

    def _is_recent(row: dict) -> bool:
        t = _parse_dt(row.get("start_time")) or _parse_dt(row.get("end_time"))
        if not t:
            # If we can't parse, keep it to avoid hiding data unexpectedly.
            return True
        return t >= cutoff

    task_rows_recent = [row for row in task_rows if _is_recent(row)]
    recent_tasks_network = [row for row in task_rows_recent if row.get("target_type") == "network"]
    recent_tasks_server = [row for row in task_rows_recent if row.get("target_type") == "server"]

    return {
        "generated_at": _fmt_dt(now),
        "stats": {
            "total_devices": len(devices),
            "online_devices": normal_count,
            "offline_devices": offline_count,
            "alarm_devices": alarm_count,
            "today_tasks": today_tasks,
        },
        "network_stats": {
            "total_devices": len(devices),
            "online_devices": normal_count,
            "offline_devices": offline_count,
            "alarm_devices": alarm_count,
            "today_tasks": today_tasks,
        },
        "server_stats": {
            **server_stats,
            "today_tasks": today_tasks,
        },
        "topology": {
            "devices": device_rows,
            "hierarchy": ["公网", "SZ-Router", "核心交换机", "17F/18F 接入交换机"],
        },
        "servers": server_rows,
        "alerts": alerts_sorted,
        # Split recent tasks by view and keep only last 7 days.
        "recent_tasks_network": recent_tasks_network[:15],
        "recent_tasks_server": recent_tasks_server[:15],
        # Backward-compatible field (keep network view behavior).
        "recent_tasks": recent_tasks_network[:15],
    }


@router.get("/assets")
def get_assets(view: str = "network", status: str = "all", db: Session = Depends(get_db)):
    payload = get_overview(db)
    items = payload.get("topology", {}).get("devices", []) if view == "network" else payload.get("servers", [])

    if status and status != "all":
        items = [item for item in items if item.get("status") == status]

    return {
        "view": view,
        "status": status,
        "items": items,
        "generated_at": payload.get("generated_at"),
    }
