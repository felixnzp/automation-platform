from __future__ import annotations

import re
import threading
from datetime import datetime

from netmiko import ConnectHandler
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.models.device import Device
from app.models.server import ServerAsset

SERVER_SWITCH_FALLBACK = "未定位服务器"
INTERFACE_PATTERN = re.compile(r"((?:X?GigabitEthernet|GE|XGE|10GE|Eth-Trunk)\S+)", re.IGNORECASE)
MAC_PATTERN = re.compile(r"([0-9a-fA-F]{4}[-:.][0-9a-fA-F]{4}[-:.][0-9a-fA-F]{4}|[0-9a-fA-F]{2}(?::[0-9a-fA-F]{2}){5})")

_COLUMNS_READY_LOCK = threading.Lock()
_COLUMNS_READY = False

def ensure_server_topology_columns(db: Session) -> None:
    global _COLUMNS_READY
    # Avoid running PRAGMA/DDL/COMMIT for every request.
    if _COLUMNS_READY:
        return
    with _COLUMNS_READY_LOCK:
        if _COLUMNS_READY:
            return
    rows = db.execute(text("PRAGMA table_info(servers)")).fetchall()
    columns = {row[1] for row in rows}
    ddl_map = {
        "os_name": "ALTER TABLE servers ADD COLUMN os_name TEXT DEFAULT ''",
        "uplink_core_switch_name": "ALTER TABLE servers ADD COLUMN uplink_core_switch_name TEXT DEFAULT ''",
        "uplink_core_switch_port": "ALTER TABLE servers ADD COLUMN uplink_core_switch_port TEXT DEFAULT ''",
        "server_switch_name": "ALTER TABLE servers ADD COLUMN server_switch_name TEXT DEFAULT ''",
        "server_switch_port": "ALTER TABLE servers ADD COLUMN server_switch_port TEXT DEFAULT ''",
        "topology_parent_id": "ALTER TABLE servers ADD COLUMN topology_parent_id INTEGER",
        "topology_located_at": "ALTER TABLE servers ADD COLUMN topology_located_at DATETIME",
        "topology_locate_status": "ALTER TABLE servers ADD COLUMN topology_locate_status TEXT DEFAULT 'failed'",
        "topology_locate_reason": "ALTER TABLE servers ADD COLUMN topology_locate_reason TEXT DEFAULT ''",
        "topology_locate_method": "ALTER TABLE servers ADD COLUMN topology_locate_method TEXT DEFAULT ''",
        "server_mac": "ALTER TABLE servers ADD COLUMN server_mac TEXT DEFAULT ''",
    }
    did_ddl = False
    for column, ddl in ddl_map.items():
        if column not in columns:
            db.execute(text(ddl))
            did_ddl = True
    if did_ddl:
        db.commit()
    _COLUMNS_READY = True


def _safe_int(value, default: int = 22) -> int:
    try:
        return int(value)
    except Exception:
        return default


def _select_core_switch(db: Session) -> Device | None:
    rows = db.query(Device).order_by(Device.id.asc()).all()
    for row in rows:
        if str(row.name or "").strip().lower() == "sz-csw":
            return row
    for row in rows:
        if str(row.ip or "").strip() == "10.18.100.1":
            return row
    return next((row for row in rows if "core" in str(row.group_name or "").lower()), None)


def _select_server_switches(db: Session) -> list[Device]:
    rows = db.query(Device).order_by(Device.id.asc()).all()
    switches = [row for row in rows if str(row.name or "").strip().lower().startswith("server-sw")]
    switches.sort(key=lambda item: str(item.name or ""))
    return switches


def _connect_device(device: Device, timeout: int = 10):
    return ConnectHandler(
        device_type=device.device_type or "huawei",
        host=device.ip,
        username=device.username,
        password=device.password,
        port=_safe_int(device.port, 22),
        fast_cli=False,
        use_keys=False,
        allow_agent=False,
        conn_timeout=max(timeout, 5),
        banner_timeout=max(timeout, 5),
        auth_timeout=max(timeout, 5),
    )


def _run_show(conn, command: str, timeout: int = 12) -> str:
    return conn.send_command(command, read_timeout=max(timeout, 8)) or ""


def _normalize_mac(mac_text: str) -> str:
    text = str(mac_text or "").strip().lower().replace(":", "").replace("-", "").replace(".", "")
    if len(text) != 12:
        return str(mac_text or "").strip().lower()
    return f"{text[0:4]}-{text[4:8]}-{text[8:12]}"


def _extract_mac(output: str) -> str:
    match = MAC_PATTERN.search(output or "")
    return _normalize_mac(match.group(1)) if match else ""


def _extract_arp_line(output: str, server_ip: str) -> str:
    for line in (output or "").splitlines():
        if server_ip in line:
            return line.strip()
    return ""


def _extract_interface_from_arp_line(line: str) -> str:
    matches = INTERFACE_PATTERN.findall(line or "")
    if not matches:
        return ""
    return matches[-1]


def _normalize_port_name(name: str) -> str:
    return re.sub(r"\s+", "", str(name or "")).lower()


def _parse_lldp_match(output: str, arp_port: str) -> tuple[str, str]:
    target = _normalize_port_name(arp_port)
    matched_rows: list[list[str]] = []
    for raw in (output or "").splitlines():
        line = raw.strip()
        if not line or line.startswith("-") or line.lower().startswith("local"):
            continue
        parts = re.split(r"\s+", line)
        if len(parts) < 2:
            continue
        if _normalize_port_name(parts[0]) != target:
            continue
        matched_rows.append(parts)

    if not matched_rows:
        return "", ""

    preferred = next((row for row in matched_rows if "server-sw" in row[1].lower()), matched_rows[0])
    neighbor_name = preferred[1] if len(preferred) > 1 else ""
    neighbor_port = preferred[2] if len(preferred) > 2 else ""
    return neighbor_name, neighbor_port


def _apply_locate_result(server: ServerAsset, result: dict, switch_lookup: dict[str, Device]) -> None:
    switch_name = result.get("server_switch_name") or ""
    switch_device = switch_lookup.get(switch_name.lower()) if switch_name else None
    server.uplink_core_switch_name = result.get("uplink_core_switch_name", "") or ""
    server.uplink_core_switch_port = result.get("uplink_core_switch_port", "") or ""
    server.server_switch_name = switch_name or ""
    server.server_switch_port = result.get("server_switch_port", "") or ""
    server.topology_parent_id = switch_device.id if switch_device else None
    server.topology_located_at = datetime.now()
    server.topology_locate_status = result.get("topology_locate_status", "failed") or "failed"
    server.topology_locate_reason = result.get("topology_locate_reason", "") or ""
    server.topology_locate_method = result.get("topology_locate_method", "") or ""
    server.server_mac = result.get("server_mac", "") or ""


def locate_server_switch(db: Session, server_ip: str, locate_method: str = "auto") -> dict:
    ensure_server_topology_columns(db)

    result = {
        "server_ip": server_ip,
        "server_mac": "",
        "uplink_core_switch_name": "",
        "uplink_core_switch_port": "",
        "server_switch_name": "",
        "server_switch_port": "",
        "topology_parent_id": None,
        "topology_located_at": datetime.now().isoformat(timespec="seconds"),
        "topology_locate_status": "failed",
        "topology_locate_reason": "",
        "topology_locate_method": locate_method,
        "logs": [],
    }

    core = _select_core_switch(db)
    if not core:
        result["topology_locate_reason"] = "未配置核心交换机"
        return result

    result["uplink_core_switch_name"] = core.name or ""
    switch_rows = _select_server_switches(db)
    switch_lookup = {str(item.name or "").strip().lower(): item for item in switch_rows}

    try:
        with _connect_device(core, timeout=10) as conn:
            result["logs"].append({"device": core.name, "command": "ssh-connect", "output": f"SSH登录成功 {core.ip}"})
            arp_command = f"display arp | include {server_ip}"
            arp_output = _run_show(conn, arp_command)
            result["logs"].append({"device": core.name, "command": arp_command, "output": arp_output})
            arp_line = _extract_arp_line(arp_output, server_ip)
            if not arp_line:
                result["topology_locate_reason"] = "核心交换机ARP未命中"
                return result

            result["server_mac"] = _extract_mac(arp_line)
            arp_port = _extract_interface_from_arp_line(arp_line)
            result["uplink_core_switch_port"] = arp_port
            if not arp_port:
                result["topology_locate_reason"] = "ARP结果未解析出核心交换机端口"
                return result

            lldp_command = f"display lldp neighbor brief | include {arp_port}"
            lldp_output = _run_show(conn, lldp_command)
            result["logs"].append({"device": core.name, "command": lldp_command, "output": lldp_output})
            server_switch_name, server_switch_port = _parse_lldp_match(lldp_output, arp_port)
            if not server_switch_name:
                result["topology_locate_reason"] = "LLDP未匹配到服务器交换机"
                return result

            result["server_switch_name"] = server_switch_name
            result["server_switch_port"] = server_switch_port
            switch_device = switch_lookup.get(server_switch_name.lower())
            result["topology_parent_id"] = switch_device.id if switch_device else None
            result["topology_locate_status"] = "manual" if locate_method == "manual" else "success"
            result["topology_locate_reason"] = "根据核心交换机ARP与LLDP自动定位"
            return result
    except Exception as exc:
        result["topology_locate_reason"] = f"自动定位失败: {exc}"
        result["logs"].append({"device": core.name or "core", "command": "locate", "output": str(exc)})
        return result


def locate_and_persist_server(db: Session, server: ServerAsset, locate_method: str = "auto") -> dict:
    result = locate_server_switch(db, server.ip, locate_method=locate_method)
    switch_rows = _select_server_switches(db)
    switch_lookup = {str(item.name or "").strip().lower(): item for item in switch_rows}
    _apply_locate_result(server, result, switch_lookup)
    db.commit()
    db.refresh(server)
    return result
