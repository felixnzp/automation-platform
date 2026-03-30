from __future__ import annotations

from datetime import datetime
import time
import threading
import logging

from sqlalchemy.orm import Session

from app.models.device import Device
from app.services import server_service
from app.services.server_topology_locator import ensure_server_topology_columns, locate_and_persist_server
from app.utils.network import ping_device

# These thresholds are for "topology health hint" only (UI highlight).
# They do not replace the dedicated server inspection task thresholds.
CPU_ALERT_THRESHOLD = 85
MEMORY_ALERT_THRESHOLD = 85
DISK_ALERT_THRESHOLD = 85

_CORE_PING_CACHE: dict[str, object] = {"checked_at": 0.0, "status": "unknown"}
_CORE_PING_TTL_SECONDS = 10.0

_TOPOLOGY_CACHE_LOCK = threading.Lock()
_TOPOLOGY_CACHE: dict[str, object] = {"checked_at": 0.0, "payload": None}
_TOPOLOGY_CACHE_TTL_SECONDS = 8.0  # Keep short; for overview first paint only.

logger = logging.getLogger("server_topology")


def _load_devices(db: Session) -> list[Device]:
    return db.query(Device).order_by(Device.id.asc()).all()


def _select_core_switch(rows: list[Device]) -> Device | None:
    for row in rows:
        if str(row.name or "").strip().lower() == "sz-csw":
            return row
    for row in rows:
        if str(row.ip or "").strip() == "10.18.100.1":
            return row
    return next((row for row in rows if "core" in str(row.group_name or "").lower()), None)


def _select_server_switches(rows: list[Device]) -> list[Device]:
    switches = [row for row in rows if str(row.name or "").strip().lower().startswith("server-sw")]
    switches.sort(key=lambda item: str(item.name or ""))
    return switches


def _normalize_locate_method(value: str) -> str:
    text = str(value or "").strip().lower()
    if text == "manual":
        return "手动"
    if text in {"success", "auto"}:
        return "自动"
    return "自动" if text else "-"


def _os_label(server: dict) -> str:
    for key in ("os_name", "os", "platform", "platform_name"):
        value = str(server.get(key) or "").strip()
        if value:
            return value

    server_type = str(server.get("server_type") or "").strip().lower()
    if server_type == "windows":
        return "Windows"
    if server_type == "linux":
        return "Linux"
    return "-"


def _topology_status(server: dict, core_status: str) -> tuple[str, str]:
    """
    Return (topology_status, reason)
    topology_status: normal / alarm / offline / unknown
    """
    if core_status == "offline":
        return "unknown", "受核心交换机状态影响"

    server_status = str(server.get("status") or "unknown").strip().lower()
    if server_status == "offline":
        return "offline", server.get("last_error") or "服务器不可达或巡检失败"
    if server_status == "online_abnormal":
        return "alarm", server.get("last_error") or "服务器在线但巡检异常"

    if not server.get("last_checked_at"):
        return "unknown", "未检测"

    core_ping = str(server.get("core_ping_status") or "unknown").strip().lower()
    cpu_usage = int(server.get("cpu_usage") or 0)
    memory_usage = int(server.get("memory_usage") or 0)
    disk_usage = int(server.get("disk_usage") or 0)

    if core_ping == "unknown":
        return "unknown", "未检测"
    if core_ping != "reachable":
        return "alarm", "核心交换机连通异常"
    if cpu_usage >= CPU_ALERT_THRESHOLD:
        return "alarm", f"CPU 使用率超过阈值 {CPU_ALERT_THRESHOLD}%"
    if memory_usage >= MEMORY_ALERT_THRESHOLD:
        return "alarm", f"内存使用率超过阈值 {MEMORY_ALERT_THRESHOLD}%"
    if disk_usage >= DISK_ALERT_THRESHOLD:
        return "alarm", f"磁盘使用率超过阈值 {DISK_ALERT_THRESHOLD}%"
    return "normal", "核心链路正常，主要指标未触发告警"


def build_server_topology(
    db: Session,
    *,
    with_status: bool = False,
    auto_locate: bool = False,
    include_servers: bool = True,
) -> dict:
    """
    Fast-first topology builder.

    - with_status=False: do NOT probe servers; only use persisted fields.
    - auto_locate=False: do NOT run ARP/LLDP locate inside this request.
    - include_servers=False: return skeleton (core + server switches) without querying servers table.
    """
    t0 = time.perf_counter()

    # Cache only the fast-first full payload. This avoids repeated DB reads under lock contention.
    if include_servers and (not with_status) and (not auto_locate):
        ts = time.time()
        with _TOPOLOGY_CACHE_LOCK:
            cached_at = float(_TOPOLOGY_CACHE.get("checked_at") or 0.0)
            cached_payload = _TOPOLOGY_CACHE.get("payload")
            if cached_payload and (ts - cached_at) <= _TOPOLOGY_CACHE_TTL_SECONDS:
                return cached_payload  # type: ignore[return-value]

    ensure_server_topology_columns(db)

    now = datetime.now().isoformat(timespec="seconds")
    device_rows = _load_devices(db)
    core = _select_core_switch(device_rows)
    # Cache core ping to avoid spawning a ping process too frequently.
    core_status = "unknown"
    if core and core.ip:
        ts = time.time()
        if (ts - float(_CORE_PING_CACHE.get("checked_at") or 0.0)) <= _CORE_PING_TTL_SECONDS:
            core_status = str(_CORE_PING_CACHE.get("status") or "unknown")
        else:
            core_status = ping_device(core.ip, timeout_ms=400)
            _CORE_PING_CACHE["checked_at"] = ts
            _CORE_PING_CACHE["status"] = core_status

    switch_rows = _select_server_switches(device_rows)
    switch_lookup = {str(row.name or "").strip(): row for row in switch_rows}

    if not include_servers:
        payload = {
            "generated_at": now,
            "skeleton": True,
            "stats": {
                "total_servers": 0,
                "normal_servers": 0,
                "alarm_servers": 0,
                "offline_servers": 0,
                "unknown_servers": 0,
            },
            "nodes": {
                "core": {
                    "name": getattr(core, "name", "核心交换机"),
                    "ip": getattr(core, "ip", ""),
                    "status": core_status,
                    "status_reason": "服务器网络核心节点",
                    "node_type": "core_switch",
                },
                "server_switches": [
                    {
                        "name": str(row.name or "").strip() or "-",
                        "ip": getattr(row, "ip", "") if row else "",
                        "status": core_status,
                        "status_reason": "follow core",
                        "server_count": 0,
                        "servers": [],
                        "node_type": "server_switch",
                    }
                    for row in switch_rows
                ],
            },
            "servers": [],
        }

        elapsed_ms = int(round((time.perf_counter() - t0) * 1000))
        if elapsed_ms >= 500:
            logger.info("build_server_topology(skeleton) took %sms", elapsed_ms)
        return payload

    server_rows = server_service.list_servers(db, with_status=with_status)

    normal_count = 0
    alarm_count = 0
    offline_count = 0
    unknown_count = 0

    unknown_group_name = "未识别服务器"
    groups: dict[str, list[dict]] = {name: [] for name in switch_lookup.keys()}
    groups.setdefault(unknown_group_name, [])
    server_items: list[dict] = []

    for row in server_rows:
        if auto_locate and row.enable == 1 and not str(row.server_switch_name or "").strip():
            locate_and_persist_server(db, row, locate_method="auto")

        serialized = server_service.serialize_server(row)
        switch_name = str(serialized.get("server_switch_name") or "").strip()
        switch_device = switch_lookup.get(switch_name) if switch_name else None
        topology_status, status_reason = _topology_status(serialized, core_status)

        if topology_status == "normal":
            normal_count += 1
        elif topology_status == "alarm":
            alarm_count += 1
        elif topology_status == "offline":
            offline_count += 1
        else:
            unknown_count += 1

        item = {
            **serialized,
            "assigned_switch": switch_name or "-",
            "assigned_switch_ip": getattr(switch_device, "ip", "") if switch_device else "",
            "core_uplink_interface": serialized.get("uplink_core_switch_port", ""),
            "topology_status": topology_status,
            "topology_reason": status_reason,
            "assignment_reason": serialized.get("topology_locate_reason", ""),
            "node_type": "server",
            "device_type": "server",
            "locate_method_label": _normalize_locate_method(
                serialized.get("topology_locate_method") or serialized.get("topology_locate_status")
            ),
            "os_name": _os_label(serialized),
        }
        server_items.append(item)

        groups.setdefault(switch_name or unknown_group_name, []).append(item)

    switch_nodes = []
    for switch_name in [*switch_lookup.keys()]:
        linked = groups.get(switch_name, [])
        switch_device = switch_lookup.get(switch_name)
        switch_nodes.append(
            {
                "name": switch_name,
                "ip": getattr(switch_device, "ip", "") if switch_device else "",
                "status": core_status,
                "status_reason": "follow core",
                "server_count": len(linked),
                "servers": linked,
                "node_type": "server_switch",
            }
        )

    # Include the fallback group only when needed to avoid UI noise.
    unknown_linked = groups.get(unknown_group_name, [])
    if unknown_linked:
        switch_nodes.append(
            {
                "name": unknown_group_name,
                "ip": "",
                "status": "alarm",
                "status_reason": "未完成所属交换机识别",
                "server_count": len(unknown_linked),
                "servers": unknown_linked,
                "node_type": "unknown_group",
            }
        )

    payload = {
        "generated_at": now,
        "skeleton": False,
        "stats": {
            "total_servers": len(server_rows),
            "normal_servers": normal_count,
            "alarm_servers": alarm_count,
            "offline_servers": offline_count,
            "unknown_servers": unknown_count,
        },
        "nodes": {
            "core": {
                "name": getattr(core, "name", "核心交换机"),
                "ip": getattr(core, "ip", ""),
                "status": core_status,
                "status_reason": "服务器网络核心节点",
                "node_type": "core_switch",
            },
            "server_switches": switch_nodes,
        },
        "servers": server_items,
    }

    if (not with_status) and (not auto_locate):
        with _TOPOLOGY_CACHE_LOCK:
            _TOPOLOGY_CACHE["checked_at"] = time.time()
            _TOPOLOGY_CACHE["payload"] = payload

    elapsed_ms = int(round((time.perf_counter() - t0) * 1000))
    if elapsed_ms >= 500:
        logger.info(
            "build_server_topology(full) took %sms (servers=%s, switches=%s, core_status=%s)",
            elapsed_ms,
            len(server_rows),
            len(switch_rows),
            core_status,
        )

    return payload
