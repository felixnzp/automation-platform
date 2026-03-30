from __future__ import annotations

import ipaddress
import json
import threading
import uuid
from datetime import datetime, timedelta
from pathlib import Path

from netmiko import ConnectHandler
from sqlalchemy.orm import Session

from app.database.database import SessionLocal
from app.models.config_task import ConfigJob, ConfigJobResult
from app.models.task import Task, TaskResult
from app.services.device_service import list_devices, list_devices_by_ids
from app.utils.logger import error_logger, task_logger
from app.utils.network import ping_device

INTENT_DEFS = [
    {
        "intent": "ntp",
        "label": "NTP配置",
        "params": [
            {"key": "timezone", "label": "时区名称", "required": True, "default": "BJ"},
            {"key": "offset", "label": "时区偏移", "required": True, "default": "08:00:00"},
            {"key": "ntp_server", "label": "NTP服务器", "required": True, "default": "10.18.101.2"},
            {"key": "timeout", "label": "连接超时(秒)", "required": False, "default": 20},
        ],
    },
    {
        "intent": "snmp",
        "label": "SNMP配置",
        "params": [
            {"key": "community", "label": "团体字", "required": True, "default": "public"},
            {"key": "timeout", "label": "连接超时(秒)", "required": False, "default": 20},
        ],
    },
    {
        "intent": "syslog",
        "label": "Syslog配置",
        "params": [
            {"key": "server_ip", "label": "日志服务器IP", "required": True, "default": "10.18.101.10"},
            {"key": "source_ip", "label": "源地址(可选)", "required": False, "default": ""},
            {"key": "timeout", "label": "连接超时(秒)", "required": False, "default": 20},
        ],
    },
]

_RUNTIME_LOCK = threading.Lock()
_RUNTIME: dict[int, dict] = {}
_PRECHECK_LOCK = threading.Lock()
_PRECHECK_CACHE: dict[str, dict] = {}
_PRECHECK_TTL_MINUTES = 20

BACKUP_DIR = Path(__file__).resolve().parents[2] / "logs" / "config_backups"
BACKUP_DIR.mkdir(parents=True, exist_ok=True)


def list_intents() -> list[dict]:
    # Syslog配置已从配置中心移除：过滤掉 syslog，避免前端出现冗余入口。
    return [item for item in INTENT_DEFS if str(item.get("intent", "")).lower() != "syslog"]


def list_jobs(db: Session) -> list[ConfigJob]:
    return db.query(ConfigJob).order_by(ConfigJob.id.desc()).all()


def get_job(db: Session, job_id: int) -> ConfigJob | None:
    return db.query(ConfigJob).filter(ConfigJob.id == job_id).first()


def _now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _safe_int(value, default=20) -> int:
    try:
        return int(value)
    except Exception:
        return default


def _detect_role(device_payload: dict) -> str:
    name = str(device_payload.get("name", "")).lower()
    group_name = str(device_payload.get("group_name", "")).lower()
    location = str(device_payload.get("location", "")).lower()
    text = " ".join([name, group_name, location])

    if "router" in text or "路由" in text:
        return "router"
    if "core" in text or "核心" in text or "csw" in text:
        return "core_switch"
    if "access" in text or "接入" in text or "sw" in text:
        return "access_switch"
    return "access_switch"


def _cleanup_precheck_cache() -> None:
    now = datetime.now()
    with _PRECHECK_LOCK:
        expired_keys = [
            key
            for key, value in _PRECHECK_CACHE.items()
            if now - value.get("created_at", now) > timedelta(minutes=_PRECHECK_TTL_MINUTES)
        ]
        for key in expired_keys:
            _PRECHECK_CACHE.pop(key, None)


def _latest_audit_hint(db: Session, device_ip: str) -> str:
    row = (
        db.query(TaskResult, Task)
        .join(Task, Task.id == TaskResult.task_id)
        .filter(Task.task_type == "audit", TaskResult.device_ip == device_ip)
        .order_by(Task.id.desc())
        .first()
    )
    if not row:
        return "暂无巡检记录"
    result, task = row
    return f"最近巡检[{task.start_time}] 状态:{result.status}"


def _validate_ip(value: str, field: str) -> None:
    try:
        ipaddress.ip_address(value)
    except Exception as exc:
        raise ValueError(f"{field}不是合法IP地址") from exc


def _validate_params(intent: str, params: dict) -> None:
    if intent == "ntp":
        if not str(params.get("timezone", "")).strip():
            raise ValueError("时区名称不能为空")
        if not str(params.get("offset", "")).strip():
            raise ValueError("时区偏移不能为空")
        _validate_ip(str(params.get("ntp_server", "")).strip(), "NTP服务器")
    elif intent == "snmp":
        community = str(params.get("community", "")).strip()
        if not community:
            raise ValueError("SNMP团体字不能为空")
        if len(community) < 3:
            raise ValueError("SNMP团体字长度不能少于3")
    elif intent == "syslog":
        _validate_ip(str(params.get("server_ip", "")).strip(), "Syslog服务器")
        source_ip = str(params.get("source_ip", "")).strip()
        if source_ip:
            _validate_ip(source_ip, "源地址")
    else:
        raise ValueError("不支持的配置意图")


def _render_templates(intent: str, role: str, params: dict, device_payload: dict) -> dict:
    if intent == "ntp":
        commands = [
            f"clock timezone {params['timezone']} add {params['offset']}",
            f"ntp-service unicast-server {params['ntp_server']}",
        ]
        verify_cmds = [
            "display current-configuration | include clock timezone",
            "display current-configuration | include ntp-service unicast-server",
        ]
        rollback_cmds = [
            "undo ntp-service unicast-server",
            f"undo clock timezone {params['timezone']}",
        ]
        if role == "router" and device_payload.get("ip") == params.get("ntp_server"):
            commands = []
            verify_cmds = ["display current-configuration | include ntp-service"]
            rollback_cmds = []
        return {"commands": commands, "verify_cmds": verify_cmds, "rollback_cmds": rollback_cmds}

    if intent == "snmp":
        commands = [
            "snmp-agent",
            f"snmp-agent community read {params['community']}",
        ]
        verify_cmds = ["display current-configuration | include snmp-agent community"]
        rollback_cmds = [f"undo snmp-agent community read {params['community']}"]
        return {"commands": commands, "verify_cmds": verify_cmds, "rollback_cmds": rollback_cmds}

    if intent == "syslog":
        commands = [
            "info-center enable",
            f"info-center loghost {params['server_ip']}",
        ]
        if str(params.get("source_ip", "")).strip():
            commands.append(f"info-center source {params['source_ip']}")
        verify_cmds = ["display current-configuration | include info-center loghost"]
        rollback_cmds = [f"undo info-center loghost {params['server_ip']}"]
        return {"commands": commands, "verify_cmds": verify_cmds, "rollback_cmds": rollback_cmds}

    return {"commands": [], "verify_cmds": [], "rollback_cmds": []}


def _ssh_login(device_payload: dict, timeout: int):
    return ConnectHandler(
        device_type=device_payload.get("device_type", "huawei"),
        host=device_payload.get("ip", ""),
        username=device_payload.get("username", ""),
        password=device_payload.get("password", ""),
        port=_safe_int(device_payload.get("port", 22), 22),
        fast_cli=False,
        use_keys=False,
        allow_agent=False,
        conn_timeout=max(timeout, 5),
        banner_timeout=max(timeout, 5),
        auth_timeout=max(timeout, 5),
    )


def _verify_applied(conn, intent: str, params: dict, verify_cmds: list[str]) -> tuple[bool, str]:
    output_text = []
    for cmd in verify_cmds:
        output_text.append(conn.send_command(cmd, read_timeout=20))
    merged = "\n".join(output_text)

    if intent == "ntp":
        ok = params["ntp_server"] in merged
    elif intent == "snmp":
        ok = params["community"] in merged
    elif intent == "syslog":
        ok = params["server_ip"] in merged
    else:
        ok = False
    return ok, merged[-2000:]


def _runtime_set(job_id: int, patch: dict) -> None:
    with _RUNTIME_LOCK:
        runtime = _RUNTIME.setdefault(job_id, {})
        runtime.update(patch)


def _runtime_append(job_id: int, line: str) -> None:
    with _RUNTIME_LOCK:
        runtime = _RUNTIME.setdefault(job_id, {})
        logs = runtime.setdefault("logs", [])
        logs.append(f"[{datetime.now().strftime('%H:%M:%S')}] {line}")
        if len(logs) > 400:
            runtime["logs"] = logs[-400:]


def precheck(db: Session, intent: str, device_ids: list[int], params: dict) -> dict:
    if str(intent or "").lower() not in {"ntp", "snmp"}:
        raise ValueError("不支持的配置功能")
    _validate_params(intent, params or {})
    timeout = _safe_int(params.get("timeout", 20), 20)
    devices = list_devices_by_ids(db, device_ids)

    details = []
    executable_ids = []
    summary = {"total": len(devices), "executable": 0, "skipped": 0, "failed": 0}

    for d in devices:
        payload = {
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
        role = _detect_role(payload)
        audit_hint = _latest_audit_hint(db, d.ip)

        if int(d.enable or 0) != 1:
            summary["skipped"] += 1
            details.append(
                {
                    "device_id": d.id,
                    "device_name": d.name,
                    "device_ip": d.ip,
                    "role": role,
                    "status": "skipped",
                    "message": "设备已禁用，跳过",
                    "audit_hint": audit_hint,
                    "commands": [],
                }
            )
            continue

        online = ping_device(d.ip) == "online"
        if not online:
            summary["failed"] += 1
            details.append(
                {
                    "device_id": d.id,
                    "device_name": d.name,
                    "device_ip": d.ip,
                    "role": role,
                    "status": "failed",
                    "message": "设备离线",
                    "audit_hint": audit_hint,
                    "commands": [],
                }
            )
            continue

        try:
            conn = _ssh_login(payload, timeout)
            conn.disconnect()
        except Exception as exc:
            summary["failed"] += 1
            details.append(
                {
                    "device_id": d.id,
                    "device_name": d.name,
                    "device_ip": d.ip,
                    "role": role,
                    "status": "failed",
                    "message": f"SSH登录失败: {exc}",
                    "audit_hint": audit_hint,
                    "commands": [],
                }
            )
            continue

        rendered = _render_templates(intent, role, params, payload)
        if not rendered["commands"]:
            summary["skipped"] += 1
            details.append(
                {
                    "device_id": d.id,
                    "device_name": d.name,
                    "device_ip": d.ip,
                    "role": role,
                    "status": "skipped",
                    "message": "模板判定无需下发",
                    "audit_hint": audit_hint,
                    "commands": rendered["commands"],
                }
            )
            continue

        summary["executable"] += 1
        executable_ids.append(d.id)
        details.append(
            {
                "device_id": d.id,
                "device_name": d.name,
                "device_ip": d.ip,
                "role": role,
                "status": "executable",
                "message": "检查通过，可执行配置",
                "audit_hint": audit_hint,
                "commands": rendered["commands"],
            }
        )

    precheck_id = uuid.uuid4().hex
    _cleanup_precheck_cache()
    with _PRECHECK_LOCK:
        _PRECHECK_CACHE[precheck_id] = {
            "created_at": datetime.now(),
            "intent": intent,
            "params": params,
            "executable_ids": executable_ids,
            "details": details,
            "summary": summary,
        }

    return {
        "precheck_id": precheck_id,
        "intent": intent,
        "summary": summary,
        "details": details,
        "executable_ids": executable_ids,
    }


def _run_worker(job_id: int, intent: str, device_ids: list[int], params: dict, auto_rollback: bool) -> None:
    db = SessionLocal()
    try:
        devices = list_devices_by_ids(db, device_ids)
        total = len(devices)
        _runtime_set(
            job_id,
            {
                "state": "running",
                "progress": 0,
                "total": total,
                "success": 0,
                "failed": 0,
                "skipped": 0,
                "logs": [f"[{datetime.now().strftime('%H:%M:%S')}] 配置任务开始执行"],
            },
        )

        success_count = 0
        fail_count = 0
        skip_count = 0

        job = db.query(ConfigJob).filter(ConfigJob.id == job_id).first()
        if not job:
            return

        timeout = _safe_int(params.get("timeout", 20), 20)

        for idx, d in enumerate(devices, start=1):
            start_at = _now_iso()
            payload = {
                "id": d.id,
                "name": d.name,
                "ip": d.ip,
                "username": d.username,
                "password": d.password,
                "port": d.port,
                "device_type": d.device_type,
                "group_name": d.group_name,
                "location": d.location,
            }
            role = _detect_role(payload)
            rendered = _render_templates(intent, role, params, payload)
            command_preview = "\n".join(rendered["commands"])

            if not rendered["commands"]:
                skip_count += 1
                db.add(
                    ConfigJobResult(
                        job_id=job_id,
                        device_id=d.id,
                        device_name=d.name,
                        device_ip=d.ip,
                        role=role,
                        status="skipped",
                        message="模板判定无需下发",
                        rollback_status="not_needed",
                        start_time=start_at,
                        end_time=_now_iso(),
                        command_preview=command_preview,
                    )
                )
                db.commit()
                _runtime_append(job_id, f"{d.name}({d.ip}) 跳过：无需下发")
                continue

            conn = None
            backup_file = ""
            verify_output = ""
            rollback_status = "not_needed"
            status = "failed"
            message = ""
            try:
                conn = _ssh_login(payload, timeout)
                try:
                    conn.send_command("screen-length 0 temporary")
                except Exception:
                    pass

                running_config = conn.send_command("display current-configuration", read_timeout=60)
                backup_file = str(BACKUP_DIR / f"job{job_id}_{d.ip}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.cfg")
                Path(backup_file).write_text(running_config, encoding="utf-8")
                _runtime_append(job_id, f"{d.name}({d.ip}) 配置备份完成")

                conn.send_config_set(rendered["commands"], read_timeout=40)
                verify_ok, verify_output = _verify_applied(conn, intent, params, rendered["verify_cmds"])
                if verify_ok:
                    status = "success"
                    message = "配置下发成功，验证通过"
                    success_count += 1
                    _runtime_append(job_id, f"{d.name}({d.ip}) 配置成功")
                else:
                    message = "配置已下发但验证失败"
                    if auto_rollback and rendered["rollback_cmds"]:
                        try:
                            conn.send_config_set(rendered["rollback_cmds"], read_timeout=40)
                            rollback_status = "success"
                            _runtime_append(job_id, f"{d.name}({d.ip}) 验证失败，已执行回滚")
                        except Exception as rb_exc:
                            rollback_status = f"failed: {rb_exc}"
                            _runtime_append(job_id, f"{d.name}({d.ip}) 回滚失败: {rb_exc}")
                    fail_count += 1
            except Exception as exc:
                fail_count += 1
                message = f"执行异常: {exc}"
                _runtime_append(job_id, f"{d.name}({d.ip}) 执行失败: {exc}")
            finally:
                if conn is not None:
                    try:
                        conn.disconnect()
                    except Exception:
                        pass

            db.add(
                ConfigJobResult(
                    job_id=job_id,
                    device_id=d.id,
                    device_name=d.name,
                    device_ip=d.ip,
                    role=role,
                    status=status,
                    message=message,
                    backup_file=backup_file,
                    rollback_status=rollback_status,
                    start_time=start_at,
                    end_time=_now_iso(),
                    command_preview=command_preview,
                    verify_output=verify_output[-2000:] if verify_output else "",
                )
            )
            db.commit()

            progress = int(idx / total * 100) if total else 100
            _runtime_set(
                job_id,
                {
                    "progress": progress,
                    "success": success_count,
                    "failed": fail_count,
                    "skipped": skip_count,
                },
            )

        job.total = total
        job.success = success_count
        job.failed = fail_count
        job.skipped = skip_count
        job.end_time = _now_iso()
        if fail_count == 0 and success_count > 0:
            job.status = "success"
        elif fail_count > 0 and success_count > 0:
            job.status = "partial_failed"
        elif fail_count > 0:
            job.status = "failed"
        else:
            job.status = "completed"
        db.commit()

        _runtime_set(
            job_id,
            {
                "state": "completed",
                "progress": 100,
                "success": success_count,
                "failed": fail_count,
                "skipped": skip_count,
                "status": job.status,
            },
        )
        _runtime_append(job_id, "配置任务执行完成")
        task_logger.info("config job=%s intent=%s success=%s failed=%s skipped=%s", job_id, intent, success_count, fail_count, skip_count)
    except Exception as exc:
        error_logger.exception("config worker failed: %s", exc)
        _runtime_set(job_id, {"state": "failed", "status": "failed"})
        _runtime_append(job_id, f"任务异常终止: {exc}")
    finally:
        db.close()


def execute(db: Session, intent: str, device_ids: list[int], params: dict, precheck_id: str | None, auto_rollback: bool) -> dict:
    if str(intent or "").lower() not in {"ntp", "snmp"}:
        raise ValueError("不支持的配置意图")
    _validate_params(intent, params or {})

    selected_ids = list(device_ids or [])
    if precheck_id:
        _cleanup_precheck_cache()
        with _PRECHECK_LOCK:
            pre = _PRECHECK_CACHE.get(precheck_id)
        if not pre:
            raise ValueError("预检查记录不存在或已过期")
        if pre.get("intent") != intent:
            raise ValueError("预检查配置意图不一致")
        selected_ids = pre.get("executable_ids", [])

    job = ConfigJob(
        intent=intent,
        start_time=_now_iso(),
        end_time="",
        status="running",
        total=len(selected_ids),
        success=0,
        failed=0,
        skipped=0,
        params_json=json.dumps(params or {}, ensure_ascii=False),
    )
    db.add(job)
    db.commit()
    db.refresh(job)

    worker = threading.Thread(target=_run_worker, args=(job.id, intent, selected_ids, params or {}, auto_rollback), daemon=True)
    worker.start()
    return {"job_id": job.id, "status": "running", "total": len(selected_ids)}


def get_progress(db: Session, job_id: int) -> dict:
    with _RUNTIME_LOCK:
        runtime = _RUNTIME.get(job_id)
    if runtime:
        return {
            "job_id": job_id,
            "state": runtime.get("state", "running"),
            "status": runtime.get("status", "running"),
            "progress": runtime.get("progress", 0),
            "total": runtime.get("total", 0),
            "success": runtime.get("success", 0),
            "failed": runtime.get("failed", 0),
            "skipped": runtime.get("skipped", 0),
            "logs": runtime.get("logs", []),
        }

    job = get_job(db, job_id)
    if not job:
        raise ValueError("配置任务不存在")
    return {
        "job_id": job.id,
        "state": "completed" if job.end_time else "running",
        "status": job.status,
        "progress": 100 if job.end_time else 0,
        "total": job.total,
        "success": job.success,
        "failed": job.failed,
        "skipped": job.skipped,
        "logs": [],
    }
