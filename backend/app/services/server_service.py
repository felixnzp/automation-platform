from __future__ import annotations

import re
import socket
import time
from datetime import datetime, timedelta

import paramiko
import winrm
from sqlalchemy.orm import Session

from app.models.server import ServerAsset
from app.services.server_topology_locator import ensure_server_topology_columns, locate_and_persist_server

STATUS_CACHE_SECONDS = 30
CONNECT_TIMEOUT_SECONDS = 5
COMMAND_TIMEOUT_SECONDS = 8
CORE_PING_TARGET = "10.18.101.1"
ROUTER_PING_TARGET = "10.18.101.2"


def _translate_error_message(exc: Exception) -> str:
    message = str(exc or "").strip()
    lower = message.lower()

    rules = [
        ("the specified credentials were rejected by the server", "用户名或密码错误，服务器拒绝了当前凭据"),
        ("authentication failed", "认证失败，请检查用户名或密码"),
        ("access is denied", "访问被拒绝，请检查账号权限"),
        ("label empty or too long", "目标地址格式不正确，请检查IP地址是否填写有误"),
        ("getaddrinfo failed", "目标地址解析失败，请检查IP地址或主机名是否正确"),
        ("host unreachable", "目标主机不可达，请检查网络连通性"),
        ("timed out", "连接超时，请检查网络连通性或目标服务状态"),
        ("timeout", "连接超时，请检查网络连通性或目标服务状态"),
        ("no route to host", "无法到达目标主机，请检查网络路由"),
        ("name or service not known", "无法解析目标地址，请检查IP或DNS配置"),
        ("connection refused", "目标端口拒绝连接，请检查服务是否已开启"),
        ("actively refused", "目标端口拒绝连接，请检查服务是否已开启"),
        ("unable to connect", "无法连接到目标服务器，请检查网络和服务状态"),
        ("winrm hostname failed", "WinRM 执行 hostname 失败"),
        ("winrm metrics failed", "WinRM 执行性能采集失败"),
        ("ntlm authentication failed", "WinRM NTLM 认证失败，请检查用户名、密码或域配置"),
        ("kerberos", "Kerberos 认证失败，请检查认证配置"),
        ("error reading ssh protocol banner", "SSH 握手失败，请检查SSH服务是否正常"),
        ("banner timeout", "SSH 握手超时，请检查SSH服务响应"),
        ("no existing session", "SSH 会话建立失败，请检查网络、端口或认证配置"),
        ("unable to authenticate", "SSH 认证失败，请检查用户名或密码"),
        ("permission denied", "权限不足，请检查账号权限"),
        ("connection reset by peer", "连接被目标主机重置，请检查服务状态"),
        ("forcibly closed by the remote host", "连接被远端主机强制关闭，请检查服务状态"),
        ("max retries exceeded", "多次重试后仍无法连接，请检查网络和服务状态"),
        ("hostname", "执行 hostname 命令失败"),
    ]

    for pattern, translated in rules:
        if pattern in lower:
            return translated

    return message or "连接失败，请检查服务器配置和网络连通性"


def _translate_error_message_cn(exc: Exception) -> str:
    message = str(exc or "").strip()
    lower = message.lower()

    rules = [
        ("the specified credentials were rejected by the server", "用户名或密码错误，服务器拒绝了当前凭据"),
        ("authentication failed", "认证失败，请检查用户名或密码"),
        ("access is denied", "访问被拒绝，请检查账号权限"),
        ("label empty or too long", "目标地址格式不正确，请检查 IP 地址是否填写有误"),
        ("getaddrinfo failed", "目标地址解析失败，请检查 IP 地址或主机名是否正确"),
        ("host unreachable", "目标主机不可达，请检查网络连通性"),
        ("timed out", "连接超时，请检查网络连通性或目标服务状态"),
        ("timeout", "连接超时，请检查网络连通性或目标服务状态"),
        ("no route to host", "无法到达目标主机，请检查网络路由"),
        ("name or service not known", "无法解析目标地址，请检查 IP 或 DNS 配置"),
        ("connection refused", "目标端口拒绝连接，请检查服务是否已开启"),
        ("actively refused", "目标端口拒绝连接，请检查服务是否已开启"),
        ("unable to connect", "无法连接到目标服务器，请检查网络和服务状态"),
        ("winrm hostname failed", "WinRM 执行 hostname 失败"),
        ("winrm metrics failed", "WinRM 执行性能采集失败"),
        ("ntlm authentication failed", "WinRM NTLM 认证失败，请检查用户名、密码或域配置"),
        ("kerberos", "Kerberos 认证失败，请检查认证配置"),
        ("error reading ssh protocol banner", "SSH 握手失败，请检查 SSH 服务是否正常"),
        ("banner timeout", "SSH 握手超时，请检查 SSH 服务响应"),
        ("no existing session", "SSH 会话建立失败，请检查网络、端口或认证配置"),
        ("unable to authenticate", "SSH 认证失败，请检查用户名或密码"),
        ("permission denied", "权限不足，请检查账号权限"),
        ("connection reset by peer", "连接被目标主机重置，请检查服务状态"),
        ("forcibly closed by the remote host", "连接被远端主机强制关闭，请检查服务状态"),
        ("max retries exceeded", "多次重试后仍无法连接，请检查网络和服务状态"),
        ("hostname", "执行 hostname 命令失败"),
    ]

    for pattern, translated in rules:
        if pattern in lower:
            return translated

    return message or "连接失败，请检查服务器配置和网络连通性"


def _safe_percent(value) -> int:
    try:
        return max(0, min(100, int(round(float(value)))))
    except Exception:
        return 0


def _linux_ping_status(client: paramiko.SSHClient, target: str) -> str:
    output = _run_ssh_command(client, f"ping -c 1 -W 1 {target} >/dev/null 2>&1 && echo reachable || echo unreachable")
    return "reachable" if "reachable" in output.lower() else "unreachable"


def _extract_probe_state(text: str, label: str) -> str:
    match = re.search(rf"{label}\s*=\s*(\w+)", text, re.IGNORECASE)
    if not match:
        return "unknown"
    return "reachable" if match.group(1).strip().lower() in {"1", "true", "ok", "reachable"} else "unreachable"


def _extract_number(text: str, label: str) -> int:
    match = re.search(rf"{label}\s*=\s*(\d+(?:\.\d+)?)", text, re.IGNORECASE)
    return _safe_percent(match.group(1) if match else 0)


def _parse_linux_cpu(text: str) -> int:
    idle_match = re.search(r"(\d+(?:\.\d+)?)\s*id", text)
    if idle_match:
        return _safe_percent(100 - float(idle_match.group(1)))
    generic_match = re.search(r"(\d+(?:\.\d+)?)", text)
    return _safe_percent(generic_match.group(1) if generic_match else 0)


def _normalize_server_payload(payload: dict) -> dict:
    normalized = dict(payload)
    server_type = str(normalized.get("server_type") or "linux").strip().lower()
    access_method = str(normalized.get("access_method") or "").strip().lower()

    if server_type not in {"linux", "windows"}:
        server_type = "linux"

    if access_method not in {"ssh", "winrm"}:
        access_method = "winrm" if server_type == "windows" else "ssh"

    normalized["server_type"] = server_type
    normalized["access_method"] = access_method

    if not normalized.get("port"):
        normalized["port"] = 5985 if access_method == "winrm" else 22

    if "hostname" in normalized:
        normalized["hostname"] = str(normalized.get("hostname") or "").strip()

    if "group_name" in normalized:
        group_name = str(normalized.get("group_name") or "").strip()
        if group_name not in {"Windows", "Linux"}:
            group_name = "Windows" if server_type == "windows" else "Linux"
        normalized["group_name"] = group_name

    return normalized


def _build_temp_server(payload: dict) -> ServerAsset:
    normalized = _normalize_server_payload(payload)
    return ServerAsset(**normalized)


def _tcp_probe(ip: str, port: int, timeout: int = CONNECT_TIMEOUT_SECONDS) -> None:
    with socket.create_connection((ip, port), timeout=timeout):
        return None


def _open_ssh_client(server: ServerAsset) -> paramiko.SSHClient:
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(
        hostname=server.ip,
        port=server.port,
        username=server.username,
        password=server.password,
        timeout=CONNECT_TIMEOUT_SECONDS,
        auth_timeout=CONNECT_TIMEOUT_SECONDS,
        banner_timeout=CONNECT_TIMEOUT_SECONDS,
        look_for_keys=False,
        allow_agent=False,
    )
    return client


def _run_ssh_command(client: paramiko.SSHClient, command: str) -> str:
    _, stdout, stderr = client.exec_command(command, timeout=COMMAND_TIMEOUT_SECONDS)
    output = stdout.read().decode("utf-8", errors="ignore").strip()
    error = stderr.read().decode("utf-8", errors="ignore").strip()
    if not output and error:
        raise RuntimeError(error)
    return output


def _probe_linux(server: ServerAsset) -> tuple[str, dict]:
    client = _open_ssh_client(server)
    try:
        hostname = _run_ssh_command(client, "hostname")
        if not hostname:
            raise RuntimeError("hostname 命令无返回")
        os_name = _run_ssh_command(
            client,
            "sh -c \"if [ -f /etc/os-release ]; then . /etc/os-release && printf '%s' \\\"${PRETTY_NAME:-$NAME}\\\"; "
            "elif command -v lsb_release >/dev/null 2>&1; then lsb_release -ds | tr -d '\\\"'; "
            "elif [ -f /etc/redhat-release ]; then cat /etc/redhat-release; "
            "else echo Linux; fi\"",
        )
        cpu_text = _run_ssh_command(client, "LC_ALL=C top -bn1 | grep 'Cpu(s)'")
        memory_text = _run_ssh_command(client, "free | awk '/Mem:/ {print ($3/$2)*100}'")
        disk_text = _run_ssh_command(client, "df -P / | awk 'NR==2 {gsub(/%/, \"\", $5); print $5}'")
        metrics = {
            "os_name": os_name or "Linux",
            "cpu_usage": _parse_linux_cpu(cpu_text),
            "memory_usage": _safe_percent(memory_text),
            "disk_usage": _safe_percent(disk_text),
            "core_ping_status": _linux_ping_status(client, CORE_PING_TARGET),
            "router_ping_status": _linux_ping_status(client, ROUTER_PING_TARGET),
        }
        return hostname, metrics
    finally:
        client.close()


def _probe_windows(server: ServerAsset) -> tuple[str, dict]:
    endpoint = f"http://{server.ip}:{server.port}/wsman"
    session = winrm.Session(target=endpoint, auth=(server.username, server.password), transport="ntlm")
    hostname_resp = session.run_cmd("hostname")
    hostname = hostname_resp.std_out.decode("utf-8", errors="ignore").strip()
    hostname_err = hostname_resp.std_err.decode("utf-8", errors="ignore").strip()
    if hostname_resp.status_code != 0:
        raise RuntimeError(hostname_err or f"WinRM hostname failed: {hostname_resp.status_code}")
    if not hostname:
        raise RuntimeError(hostname_err or "hostname 命令无返回")

    metrics_script = """
$cpu = (Get-CimInstance Win32_Processor | Measure-Object -Property LoadPercentage -Average).Average
$os = Get-CimInstance Win32_OperatingSystem
$osName = $os.Caption
$mem = [math]::Round((($os.TotalVisibleMemorySize - $os.FreePhysicalMemory) / $os.TotalVisibleMemorySize) * 100, 0)
$disks = Get-CimInstance Win32_LogicalDisk -Filter "DriveType=3" | Where-Object { $_.Size -gt 0 } | ForEach-Object {
  [math]::Round((($_.Size - $_.FreeSpace) / $_.Size) * 100, 0)
}
$disk = if ($disks) { ($disks | Measure-Object -Maximum).Maximum } else { 0 }
Write-Output "OSNAME=$osName"
Write-Output "CPU=$cpu"
Write-Output "MEM=$mem"
Write-Output "DISK=$disk"
try {
  $core = Test-Connection -ComputerName '10.18.101.1' -Count 1 -Quiet -ErrorAction Stop
} catch {
  $core = $false
}
try {
  $router = Test-Connection -ComputerName '10.18.101.2' -Count 1 -Quiet -ErrorAction Stop
} catch {
  $router = $false
}
Write-Output "CORE=$core"
Write-Output "ROUTER=$router"
"""
    metrics_resp = session.run_ps(metrics_script)
    metrics_out = metrics_resp.std_out.decode("utf-8", errors="ignore")
    metrics_err = metrics_resp.std_err.decode("utf-8", errors="ignore").strip()
    if metrics_resp.status_code != 0:
        raise RuntimeError(metrics_err or f"WinRM metrics failed: {metrics_resp.status_code}")

    metrics = {
        "os_name": re.search(r"OSNAME=(.+)", metrics_out).group(1).strip() if re.search(r"OSNAME=(.+)", metrics_out) else "Windows",
        "cpu_usage": _extract_number(metrics_out, "CPU"),
        "memory_usage": _extract_number(metrics_out, "MEM"),
        "disk_usage": _extract_number(metrics_out, "DISK"),
        "core_ping_status": _extract_probe_state(metrics_out, "CORE"),
        "router_ping_status": _extract_probe_state(metrics_out, "ROUTER"),
    }
    return hostname, metrics


def probe_server(server: ServerAsset) -> dict:
    started = time.perf_counter()
    checked_at = datetime.now()
    try:
        _tcp_probe(server.ip, server.port)
    except Exception as exc:  # pragma: no cover
        elapsed_ms = int((time.perf_counter() - started) * 1000)
        return {
            "success": False,
            "status": "offline",
            "hostname": server.hostname or "",
            "os_name": server.os_name or ("Windows" if server.server_type == "windows" else "Linux"),
            "cpu_usage": server.cpu_usage or 0,
            "memory_usage": server.memory_usage or 0,
            "disk_usage": server.disk_usage or 0,
            "response_time_ms": elapsed_ms,
            "error_reason": _translate_error_message_cn(exc),
            "checked_at": checked_at,
            "core_ping_status": "unknown",
            "router_ping_status": "unknown",
        }

    try:
        if server.access_method == "winrm":
            hostname, metrics = _probe_windows(server)
        else:
            hostname, metrics = _probe_linux(server)
        elapsed_ms = int((time.perf_counter() - started) * 1000)
        return {
            "success": True,
            "status": "online",
            "hostname": hostname,
            "os_name": metrics.get("os_name") or server.os_name or ("Windows" if server.server_type == "windows" else "Linux"),
            "cpu_usage": metrics["cpu_usage"],
            "memory_usage": metrics["memory_usage"],
            "disk_usage": metrics["disk_usage"],
            "response_time_ms": elapsed_ms,
            "error_reason": "",
            "checked_at": checked_at,
            "core_ping_status": metrics.get("core_ping_status", "unknown"),
            "router_ping_status": metrics.get("router_ping_status", "unknown"),
        }
    except Exception as exc:  # pragma: no cover
        elapsed_ms = int((time.perf_counter() - started) * 1000)
        return {
            "success": False,
            "status": "online_abnormal",
            "hostname": server.hostname or "",
            "os_name": server.os_name or ("Windows" if server.server_type == "windows" else "Linux"),
            "cpu_usage": server.cpu_usage or 0,
            "memory_usage": server.memory_usage or 0,
            "disk_usage": server.disk_usage or 0,
            "response_time_ms": elapsed_ms,
            "error_reason": _translate_error_message_cn(exc),
            "checked_at": checked_at,
            "core_ping_status": "unknown",
            "router_ping_status": "unknown",
        }


def _should_refresh_status(server: ServerAsset) -> bool:
    if not server.last_checked_at:
        return True
    return datetime.now() - server.last_checked_at >= timedelta(seconds=STATUS_CACHE_SECONDS)


def _sync_probe_result(db: Session, server: ServerAsset, result: dict) -> ServerAsset:
    server.status = result["status"]
    server.hostname = result["hostname"] or server.hostname
    server.os_name = result.get("os_name") or server.os_name
    server.last_checked_at = result["checked_at"]
    server.last_error = result["error_reason"] or ""
    server.cpu_usage = int(result.get("cpu_usage") or 0)
    server.memory_usage = int(result.get("memory_usage") or 0)
    server.disk_usage = int(result.get("disk_usage") or 0)
    server.response_time_ms = int(result.get("response_time_ms") or 0)
    server.core_ping_status = result.get("core_ping_status") or "unknown"
    server.router_ping_status = result.get("router_ping_status") or "unknown"
    db.commit()
    db.refresh(server)
    return server


def serialize_server(server: ServerAsset) -> dict:
    return {
        "id": server.id,
        "name": server.name,
        "ip": server.ip,
        "hostname": server.hostname or "",
        "os_name": server.os_name or "",
        "server_type": server.server_type,
        "access_method": server.access_method,
        "username": server.username,
        "password": server.password,
        "port": server.port,
        "group_name": server.group_name,
        "enable": server.enable,
        "status": server.status or "unknown",
        "last_checked_at": server.last_checked_at.isoformat() if server.last_checked_at else None,
        "last_error": server.last_error or "",
        "cpu_usage": server.cpu_usage or 0,
        "memory_usage": server.memory_usage or 0,
        "disk_usage": server.disk_usage or 0,
        "response_time_ms": server.response_time_ms or 0,
        "core_ping_status": server.core_ping_status or "unknown",
        "router_ping_status": server.router_ping_status or "unknown",
        "uplink_core_switch_name": server.uplink_core_switch_name or "",
        "uplink_core_switch_port": server.uplink_core_switch_port or "",
        "server_switch_name": server.server_switch_name or "",
        "server_switch_port": server.server_switch_port or "",
        "topology_parent_id": server.topology_parent_id,
        "topology_located_at": server.topology_located_at.isoformat() if server.topology_located_at else None,
        "topology_locate_status": server.topology_locate_status or "failed",
        "topology_locate_reason": server.topology_locate_reason or "",
        "topology_locate_method": server.topology_locate_method or "",
        "server_mac": server.server_mac or "",
    }


def list_servers(
    db: Session,
    keyword: str | None = None,
    group_name: str | None = None,
    with_status: bool = True,
):
    ensure_server_topology_columns(db)
    query = db.query(ServerAsset)

    if keyword:
        like_pattern = f"%{keyword}%"
        query = query.filter(
            (ServerAsset.name.like(like_pattern))
            | (ServerAsset.ip.like(like_pattern))
            | (ServerAsset.hostname.like(like_pattern))
        )

    if group_name:
        query = query.filter(ServerAsset.group_name == group_name)

    rows = query.order_by(ServerAsset.group_name.asc(), ServerAsset.id.desc()).all()
    if not with_status:
        return rows

    result = []
    for row in rows:
        if row.enable != 1:
            row.status = "offline"
            result.append(row)
            continue
        if _should_refresh_status(row):
            probe = probe_server(row)
            row = _sync_probe_result(db, row, probe)
        result.append(row)
    return result


def list_server_groups(db: Session):
    ensure_server_topology_columns(db)
    rows = db.query(ServerAsset.group_name).filter(ServerAsset.group_name.isnot(None)).all()
    return sorted({value for (value,) in rows if value})


def create_server(db: Session, payload: dict, auto_locate_topology: bool = True):
    ensure_server_topology_columns(db)
    server = ServerAsset(**_normalize_server_payload(payload))
    # Do not block API on topology locate. We mark pending and let TaskCenter handle detection.
    server.topology_locate_status = "pending"
    server.topology_locate_reason = "等待所属交换机检测"
    server.topology_locate_method = "auto" if auto_locate_topology else ""
    db.add(server)
    db.commit()
    db.refresh(server)
    return server


def get_server(db: Session, server_id: int):
    ensure_server_topology_columns(db)
    return db.query(ServerAsset).filter(ServerAsset.id == server_id).first()


def update_server(db: Session, server_id: int, payload: dict, auto_locate_topology: bool = False):
    server = get_server(db, server_id)
    if not server:
        return None

    original_ip = server.ip
    normalized = _normalize_server_payload(payload)
    for key, value in normalized.items():
        setattr(server, key, value)

    # If IP changed, clear previous mapping and mark pending.
    if original_ip != server.ip:
        server.uplink_core_switch_name = ""
        server.uplink_core_switch_port = ""
        server.server_switch_name = ""
        server.server_switch_port = ""
        server.topology_parent_id = None
        server.topology_locate_status = "pending"
        server.topology_locate_reason = "IP已变更，等待重新检测"
        server.topology_locate_method = "auto" if auto_locate_topology else ""

    # If user requests auto locate but we keep it async, mark pending.
    if auto_locate_topology and server.enable == 1:
        server.topology_locate_status = "pending"
        server.topology_locate_reason = "等待所属交换机检测"
        server.topology_locate_method = "auto"

    db.commit()
    db.refresh(server)
    return server


def delete_server(db: Session, server_id: int):
    ensure_server_topology_columns(db)
    server = get_server(db, server_id)
    if not server:
        return False
    db.delete(server)
    db.commit()
    return True


def test_connection(db: Session, server_id: int):
    ensure_server_topology_columns(db)
    server = get_server(db, server_id)
    if not server:
        return None
    result = probe_server(server)
    _sync_probe_result(db, server, result)
    return {
        "success": result["success"],
        "status": result["status"],
        "response_time_ms": result["response_time_ms"],
        "error_reason": result["error_reason"],
        "hostname": result["hostname"],
        "cpu_usage": result["cpu_usage"],
        "memory_usage": result["memory_usage"],
        "disk_usage": result["disk_usage"],
        "checked_at": result["checked_at"].isoformat(),
        "core_ping_status": result.get("core_ping_status", "unknown"),
        "router_ping_status": result.get("router_ping_status", "unknown"),
    }


def test_connection_payload(payload: dict):
    server = _build_temp_server(payload)
    result = probe_server(server)
    return {
        "success": result["success"],
        "status": result["status"],
        "response_time_ms": result["response_time_ms"],
        "error_reason": result["error_reason"],
        "hostname": result["hostname"],
        "cpu_usage": result["cpu_usage"],
        "memory_usage": result["memory_usage"],
        "disk_usage": result["disk_usage"],
        "checked_at": result["checked_at"].isoformat(),
        "core_ping_status": result.get("core_ping_status", "unknown"),
        "router_ping_status": result.get("router_ping_status", "unknown"),
    }


def relocate_server_topology(db: Session, server_id: int, locate_method: str = "manual"):
    server = get_server(db, server_id)
    if not server:
        return None
    return locate_and_persist_server(db, server, locate_method=locate_method)
