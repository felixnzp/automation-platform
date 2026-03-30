from __future__ import annotations

import json
import re
import threading
import uuid
from datetime import datetime, timedelta
from pathlib import Path
import sqlite3

from netmiko import ConnectHandler
from sqlalchemy.orm import Session

from app.automation import audit_module, ntp_module
from app.database.database import SessionLocal
from app.models.server import ServerAsset
from app.models.server_inspection import ServerInspectionDetail
from app.models.server_switch_detect_log import ServerSwitchDetectLog
from app.models.task import ScheduledTask, Task, TaskResult
from app.services.device_service import list_devices, list_devices_by_ids
from app.services import server_service
from app.services.server_topology_locator import locate_and_persist_server
from app.utils.logger import error_logger, task_logger
from app.utils.network import ping_device

TASK_MODULE_MAP = {
    "audit": audit_module,
    "ntp": ntp_module,
}

SERVER_INSPECTION_TASK_TYPE = "server_inspection"
SERVER_SWITCH_DETECT_TASK_TYPE = "server_switch_detect"

TASK_TYPE_DEFS = [
    {
        "type": "audit",
        "label": "网络巡检",
        "params": [
            {"key": "timeout", "label": "连接超时(秒)", "type": "number", "default": 20},
            {"key": "mode", "label": "巡检模式", "type": "select", "default": "exec", "options": ["exec", "shell"]},
        ],
    },
    {
        "type": SERVER_INSPECTION_TASK_TYPE,
        "label": "服务器巡检",
        "params": [
            {
                "key": "inspect_items",
                "label": "巡检项",
                "type": "json",
                "default": {"cpu": True, "memory": True, "disk": True},
            },
            {
                "key": "threshold_config",
                "label": "阈值配置",
                "type": "json",
                "default": {
                    "cpu_warning": 80,
                    "cpu_critical": 90,
                    "memory_warning": 80,
                    "memory_critical": 90,
                    "disk_warning": 80,
                    "disk_critical": 90,
                },
            },
        ],
    },
    {
        "type": SERVER_SWITCH_DETECT_TASK_TYPE,
        "label": "服务器所属交换机检测",
        "params": [
            {"key": "force", "label": "强制重新检测", "type": "bool", "default": False},
            {"key": "trigger", "label": "触发方式", "type": "string", "default": "manual"},
        ],
    },
]

_RUNTIME_LOCK = threading.Lock()
_TASK_RUNTIME: dict[int, dict] = {}
_PRECHECK_LOCK = threading.Lock()
_PRECHECK_CACHE: dict[str, dict] = {}
_PRECHECK_TTL_MINUTES = 20
SCHEDULE_CYCLE_TYPES = {"daily", "weekly", "monthly", "cron"}
SCHEDULE_TARGET_MODES = {"all", "group", "custom"}
_SCHEDULER_THREAD: threading.Thread | None = None
_SCHEDULER_STOP = threading.Event()
_SCHEDULER_LOCK = threading.Lock()


def ensure_schema() -> None:
    """
    Ensure new columns exist for legacy SQLite DBs (no migrations in this project).
    """
    full_path = Path.cwd() / "automation.db"
    conn = sqlite3.connect(full_path)
    try:
        columns = {row[1] for row in conn.execute("PRAGMA table_info(scheduled_tasks)").fetchall()}
        if "params" not in columns:
            conn.execute("ALTER TABLE scheduled_tasks ADD COLUMN params TEXT DEFAULT '{}'")
        conn.commit()
    finally:
        conn.close()


def list_task_types() -> list[dict]:
    return TASK_TYPE_DEFS


def list_tasks(db: Session):
    return db.query(Task).order_by(Task.id.desc()).all()


def get_task(db: Session, task_id: int):
    return db.query(Task).filter(Task.id == task_id).first()


def _now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _parse_target_ids(raw_value: str | None) -> list[int]:
    if not raw_value:
        return []
    try:
        values = json.loads(raw_value)
    except Exception:
        return []

    result = []
    for item in values:
        try:
            result.append(int(item))
        except Exception:
            continue
    return list(dict.fromkeys(result))


def _serialize_target_ids(values: list[int] | None) -> str:
    cleaned = []
    for item in values or []:
        try:
            cleaned.append(int(item))
        except Exception:
            continue
    return json.dumps(list(dict.fromkeys(cleaned)), ensure_ascii=False)


def _scheduled_task_to_dict(row: ScheduledTask) -> dict:
    params = {}
    try:
        params = json.loads(row.params or "{}")
    except Exception:
        params = {}
    return {
        "id": row.id,
        "name": row.name,
        "task_type": row.task_type,
        "target_mode": row.target_mode,
        "target_group": row.target_group or "",
        "target_device_ids": _parse_target_ids(row.target_device_ids),
        "params": params,
        "cycle_type": row.cycle_type,
        "run_time": row.run_time,
        "cron_expr": row.cron_expr or "",
        "enabled": bool(row.enabled),
        "last_run_at": row.last_run_at or "",
        "created_at": row.created_at,
        "updated_at": row.updated_at,
    }


def _resolve_scheduled_device_ids(db: Session, row: ScheduledTask) -> list[int]:
    if row.task_type in {SERVER_INSPECTION_TASK_TYPE, SERVER_SWITCH_DETECT_TASK_TYPE}:
        if row.target_mode == "all":
            servers = server_service.list_servers(db, with_status=False)
            return [item.id for item in servers]
        if row.target_mode == "group":
            if not row.target_group:
                return []
            servers = server_service.list_servers(db, group_name=row.target_group, with_status=False)
            return [item.id for item in servers]
        return _parse_target_ids(row.target_device_ids)

    if row.target_mode == "all":
        return [item.id for item in list_devices(db)]
    if row.target_mode == "group":
        if not row.target_group:
            return []
        return [item.id for item in list_devices(db, group_name=row.target_group)]
    return _parse_target_ids(row.target_device_ids)


def _threshold_level(value: int | None, warning: int, critical: int) -> str:
    if value is None:
        return "failed"
    if value >= critical:
        return "critical"
    if value >= warning:
        return "warning"
    return "normal"


def _max_level(levels: list[str]) -> str:
    order = {"normal": 0, "warning": 1, "critical": 2, "failed": 3}
    if not levels:
        return "failed"
    return max(levels, key=lambda x: order.get(x, 0))


def _server_inspection_levels(metrics: dict, params: dict) -> tuple[dict, str, str]:
    items = params.get("inspect_items") or {"cpu": True, "memory": True, "disk": True}
    thresholds = params.get("threshold_config") or {}
    cpu_warning = int(thresholds.get("cpu_warning", 80))
    cpu_critical = int(thresholds.get("cpu_critical", 90))
    memory_warning = int(thresholds.get("memory_warning", 80))
    memory_critical = int(thresholds.get("memory_critical", 90))
    disk_warning = int(thresholds.get("disk_warning", 80))
    disk_critical = int(thresholds.get("disk_critical", 90))

    cpu = int(metrics.get("cpu_usage")) if metrics.get("cpu_usage") is not None else None
    mem = int(metrics.get("memory_usage")) if metrics.get("memory_usage") is not None else None
    disk = int(metrics.get("disk_usage")) if metrics.get("disk_usage") is not None else None

    per_item = {}
    levels = []

    if items.get("cpu", True):
        per_item["cpu_status"] = _threshold_level(cpu, cpu_warning, cpu_critical)
        levels.append(per_item["cpu_status"])
    else:
        per_item["cpu_status"] = None

    if items.get("memory", True):
        per_item["memory_status"] = _threshold_level(mem, memory_warning, memory_critical)
        levels.append(per_item["memory_status"])
    else:
        per_item["memory_status"] = None

    if items.get("disk", True):
        per_item["disk_status"] = _threshold_level(disk, disk_warning, disk_critical)
        levels.append(per_item["disk_status"])
    else:
        per_item["disk_status"] = None

    overall = _max_level(levels)
    if overall == "normal":
        msg = "巡检指标正常"
    elif overall == "warning":
        msg = "存在告警项"
    elif overall == "critical":
        msg = "存在严重异常项"
    else:
        msg = "无法采集或连接失败"

    return per_item, overall, msg


def _run_server_inspection_worker(
    task_id: int,
    server_ids: list[int],
    params: dict,
    schedule_id: int | None = None,
) -> None:
    db = SessionLocal()
    try:
        servers = db.query(ServerAsset).filter(ServerAsset.id.in_(server_ids)).order_by(ServerAsset.id.asc()).all()
        total = len(servers)

        _runtime_set(
            task_id,
            {
                "task_id": task_id,
                "state": "running",
                "progress": 0,
                "total": total,
                "success": 0,
                "failed": 0,
                "skipped": 0,
                "logs": [f"[{datetime.now().strftime('%H:%M:%S')}] 任务开始执行"],
            },
        )

        task = db.query(Task).filter(Task.id == task_id).first()
        if not task:
            return

        success_count = 0
        fail_count = 0
        skip_count = 0

        for idx, server in enumerate(servers, start=1):
            started_at = datetime.now().isoformat(timespec="seconds")

            if server.enable != 1:
                skip_count += 1
                db.add(
                    TaskResult(
                        task_id=task_id,
                        device_ip=server.ip,
                        device_name=server.name,
                        status="skipped",
                        message="服务器已禁用，跳过巡检",
                        start_time=started_at,
                        end_time=datetime.now().isoformat(timespec="seconds"),
                    )
                )
                db.commit()
                _runtime_append_log(task_id, f"{server.name}({server.ip}) 跳过：已禁用")
            else:
                probe = server_service.probe_server(server)
                server_service._sync_probe_result(db, server, probe)  # keep server status fresh

                probe_ok = bool(probe.get("success"))
                items = (params or {}).get("inspect_items") or {"cpu": True, "memory": True, "disk": True}

                if not probe_ok:
                    # Execution failure only: offline / SSH/WinRM failed / script failed / metrics failed.
                    fail_count += 1
                    detail = ServerInspectionDetail(
                        task_id=task_id,
                        schedule_id=schedule_id,
                        server_id=server.id,
                        server_name=server.name,
                        server_ip=server.ip,
                        cpu_usage=None,
                        memory_usage=None,
                        disk_usage=None,
                        cpu_status="failed" if items.get("cpu", True) else None,
                        memory_status="failed" if items.get("memory", True) else None,
                        disk_status="failed" if items.get("disk", True) else None,
                        result_level="failed",
                        result_message=probe.get("error_reason") or "无法连接或指标获取失败",
                        executed_at=datetime.now().isoformat(timespec="seconds"),
                    )
                    db.add(detail)
                    status = "failed"
                    message = probe.get("error_reason") or "无法连接或指标获取失败"
                    cpu_usage = None
                    mem_usage = None
                    disk_usage = None
                    level = "failed"
                    msg = ""
                else:
                    per_item, level, msg = _server_inspection_levels(probe, params or {})
                    cpu_usage = probe.get("cpu_usage")
                    mem_usage = probe.get("memory_usage")
                    disk_usage = probe.get("disk_usage")

                    detail = ServerInspectionDetail(
                        task_id=task_id,
                        schedule_id=schedule_id,
                        server_id=server.id,
                        server_name=server.name,
                        server_ip=server.ip,
                        cpu_usage=int(cpu_usage) if cpu_usage is not None else None,
                        memory_usage=int(mem_usage) if mem_usage is not None else None,
                        disk_usage=int(disk_usage) if disk_usage is not None else None,
                        cpu_status=per_item.get("cpu_status"),
                        memory_status=per_item.get("memory_status"),
                        disk_status=per_item.get("disk_status"),
                        result_level=level,
                        result_message=probe.get("error_reason") or msg,
                        executed_at=datetime.now().isoformat(timespec="seconds"),
                    )
                    db.add(detail)

                    if level == "failed":
                        # Metrics missing even though probe succeeded.
                        fail_count += 1
                        status = "failed"
                    else:
                        success_count += 1
                        status = "success"

                    level_label = {
                        "normal": "正常",
                        "warning": "告警",
                        "critical": "严重",
                        "failed": "失败",
                        "unknown": "未知",
                    }.get(str(level or "unknown").lower(), "未知")
                    message = (
                        f"CPU={cpu_usage}% 内存={mem_usage}% 磁盘={disk_usage}% 结果={level_label} {probe.get('error_reason') or msg}"
                    ).strip()
                db.add(
                    TaskResult(
                        task_id=task_id,
                        device_ip=server.ip,
                        device_name=server.name,
                        status=status,
                        message=message,
                        start_time=started_at,
                        end_time=datetime.now().isoformat(timespec="seconds"),
                    )
                )
                db.commit()

                if status == "success":
                    level_label = {
                        "normal": "正常",
                        "warning": "告警",
                        "critical": "严重",
                        "failed": "失败",
                        "unknown": "未知",
                    }.get(str(level or "unknown").lower(), "未知")
                    _runtime_append_log(task_id, f"{server.name}({server.ip}) 完成：{level_label} {msg}".strip())
                else:
                    _runtime_append_log(task_id, f"{server.name}({server.ip}) 执行失败: {message}")

            progress = int(idx / total * 100) if total else 100
            _runtime_set(
                task_id,
                {
                    "progress": progress,
                    "success": success_count,
                    "failed": fail_count,
                    "skipped": skip_count,
                },
            )

        task.success = success_count
        task.failed = fail_count
        task.total = total
        task.end_time = datetime.now().isoformat(timespec="seconds")

        if fail_count == 0 and success_count > 0:
            task.status = "success"
        elif fail_count > 0 and success_count > 0:
            task.status = "partial_failed"
        elif fail_count > 0 and success_count == 0:
            task.status = "failed"
        else:
            task.status = "completed"

        db.commit()
        _runtime_set(
            task_id,
            {
                "state": "completed",
                "progress": 100,
                "success": success_count,
                "failed": fail_count,
                "skipped": skip_count,
                "status": task.status,
            },
        )
        _runtime_append_log(task_id, "任务执行完成")
    except Exception as exc:
        error_logger.exception("server inspection worker failed: %s", exc)
        _runtime_set(task_id, {"state": "failed"})
        _runtime_append_log(task_id, f"任务异常终止: {exc}")

        task = db.query(Task).filter(Task.id == task_id).first()
        if task:
            task.status = "failed"
            task.end_time = datetime.now().isoformat(timespec="seconds")
            db.commit()
    finally:
        db.close()


def _parse_iso_datetime(value: str | None) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        return datetime.fromisoformat(text)
    except ValueError:
        return None


def _parse_run_time(value: str | None) -> tuple[int, int] | None:
    text = str(value or "").strip()
    match = re.fullmatch(r"([01]?\d|2[0-3]):([0-5]\d)", text)
    if not match:
        return None
    return int(match.group(1)), int(match.group(2))


def _cron_value_matches(token: str, value: int, minimum: int, maximum: int) -> bool:
    token = token.strip()
    if token == "*":
        return True

    if "/" in token:
        base, step_text = token.split("/", 1)
        try:
            step = int(step_text)
        except ValueError:
            return False
        if step <= 0:
            return False

        if base == "*":
            return (value - minimum) % step == 0

        if "-" in base:
            start_text, end_text = base.split("-", 1)
            try:
                start = int(start_text)
                end = int(end_text)
            except ValueError:
                return False
            return start <= value <= end and (value - start) % step == 0
        return False

    if "-" in token:
        start_text, end_text = token.split("-", 1)
        try:
            start = int(start_text)
            end = int(end_text)
        except ValueError:
            return False
        return start <= value <= end

    try:
        numeric = int(token)
    except ValueError:
        return False
    return minimum <= numeric <= maximum and value == numeric


def _cron_field_matches(field: str, value: int, minimum: int, maximum: int) -> bool:
    return any(
        _cron_value_matches(part, value, minimum, maximum)
        for part in str(field or "").split(",")
        if part.strip()
    )


def _cron_weekday(now: datetime) -> int:
    # Cron uses 0/7=Sunday, 1=Monday ... 6=Saturday.
    return (now.weekday() + 1) % 7


def _cron_matches(expr: str, now: datetime) -> bool:
    parts = [part for part in str(expr or "").split() if part]
    if len(parts) != 5:
        return False

    minute, hour, day, month, weekday = parts
    return (
        _cron_field_matches(minute, now.minute, 0, 59)
        and _cron_field_matches(hour, now.hour, 0, 23)
        and _cron_field_matches(day, now.day, 1, 31)
        and _cron_field_matches(month, now.month, 1, 12)
        and _cron_field_matches(weekday, _cron_weekday(now), 0, 7)
    )


def _schedule_slot_key(row: ScheduledTask, now: datetime) -> str:
    return f"{row.id}:{now.strftime('%Y-%m-%d %H:%M')}"


def _should_run_schedule(row: ScheduledTask, now: datetime) -> bool:
    if not bool(row.enabled):
        return False
    if row.task_type not in TASK_MODULE_MAP and row.task_type != SERVER_INSPECTION_TASK_TYPE:
        return False

    run_time = _parse_run_time(row.run_time)
    if row.cycle_type != "cron" and not run_time:
        return False

    last_run = _parse_iso_datetime(row.last_run_at)
    if last_run and _schedule_slot_key(row, last_run) == _schedule_slot_key(row, now):
        return False

    if row.cycle_type == "cron":
        return _cron_matches(row.cron_expr or "", now)

    hour, minute = run_time
    if now.hour != hour or now.minute != minute:
        return False

    anchor = _parse_iso_datetime(row.updated_at) or _parse_iso_datetime(row.created_at) or now
    if row.cycle_type == "daily":
        return True
    if row.cycle_type == "weekly":
        return now.weekday() == anchor.weekday()
    if row.cycle_type == "monthly":
        return now.day == anchor.day
    return False


def _trigger_due_schedules() -> None:
    db = SessionLocal()
    try:
        now = datetime.now()
        rows = db.query(ScheduledTask).order_by(ScheduledTask.id.asc()).all()
        for row in rows:
            if not _should_run_schedule(row, now):
                continue

            device_ids = _resolve_scheduled_device_ids(db, row)
            row.last_run_at = now.isoformat(timespec="seconds")
            row.updated_at = now.isoformat(timespec="seconds")
            db.commit()

            if not device_ids:
                task_logger.warning("scheduled task %s skipped: no devices matched", row.id)
                continue

            try:
                params = {}
                try:
                    params = json.loads(row.params or "{}")
                except Exception:
                    params = {}
                result = execute_task(db, row.task_type, device_ids, params=params, precheck_id=None, schedule_id=row.id)
                task_logger.info(
                    "scheduled task triggered schedule_id=%s task_id=%s type=%s total=%s",
                    row.id,
                    result.get("task_id"),
                    row.task_type,
                    result.get("total"),
                )
            except Exception as exc:
                error_logger.exception("scheduled task trigger failed schedule_id=%s: %s", row.id, exc)
    finally:
        db.close()


def _scheduler_loop() -> None:
    task_logger.info("scheduled task loop started")
    while not _SCHEDULER_STOP.wait(15):
        try:
            _trigger_due_schedules()
        except Exception as exc:
            error_logger.exception("scheduled task loop failed: %s", exc)
    task_logger.info("scheduled task loop stopped")


def start_schedule_worker() -> None:
    global _SCHEDULER_THREAD
    with _SCHEDULER_LOCK:
        if _SCHEDULER_THREAD and _SCHEDULER_THREAD.is_alive():
            return
        _SCHEDULER_STOP.clear()
        _SCHEDULER_THREAD = threading.Thread(target=_scheduler_loop, name="task-scheduler", daemon=True)
        _SCHEDULER_THREAD.start()


def stop_schedule_worker() -> None:
    global _SCHEDULER_THREAD
    with _SCHEDULER_LOCK:
        _SCHEDULER_STOP.set()
        thread = _SCHEDULER_THREAD
        _SCHEDULER_THREAD = None

    if thread and thread.is_alive():
        thread.join(timeout=3)


def list_scheduled_tasks(db: Session) -> list[dict]:
    rows = db.query(ScheduledTask).order_by(ScheduledTask.id.desc()).all()
    return [_scheduled_task_to_dict(row) for row in rows]


def create_scheduled_task(db: Session, payload: dict) -> dict:
    task_type = str(payload.get("task_type", "")).strip()
    target_mode = str(payload.get("target_mode", "all")).strip()
    cycle_type = str(payload.get("cycle_type", "daily")).strip()
    name = str(payload.get("name", "")).strip()
    run_time = str(payload.get("run_time", "08:00")).strip()

    if task_type not in TASK_MODULE_MAP and task_type not in {SERVER_INSPECTION_TASK_TYPE, SERVER_SWITCH_DETECT_TASK_TYPE}:
        raise ValueError("不支持的任务类型")
    if target_mode not in SCHEDULE_TARGET_MODES:
        raise ValueError("不支持的目标设备选择方式")
    if cycle_type not in SCHEDULE_CYCLE_TYPES:
        raise ValueError("不支持的执行周期")
    if not name:
        raise ValueError("任务名称不能为空")
    if not run_time:
        raise ValueError("执行时间不能为空")

    target_group = str(payload.get("target_group", "")).strip()
    target_device_ids = payload.get("target_device_ids", [])
    cron_expr = str(payload.get("cron_expr", "")).strip()
    enabled = 1 if bool(payload.get("enabled", True)) else 0
    raw_params = payload.get("params") or {}
    try:
        params_text = json.dumps(raw_params, ensure_ascii=False)
    except Exception:
        params_text = "{}"

    if target_mode == "group" and not target_group:
        raise ValueError("按分组选择时必须提供分组")
    if target_mode == "custom" and not (target_device_ids or []):
        raise ValueError("自定义选择时至少选择一台设备")
    if cycle_type == "cron" and not cron_expr:
        raise ValueError("自定义Cron模式必须填写表达式")

    now = _now_iso()
    row = ScheduledTask(
        name=name,
        task_type=task_type,
        target_mode=target_mode,
        target_group=target_group,
        target_device_ids=_serialize_target_ids(target_device_ids),
        params=params_text,
        cycle_type=cycle_type,
        run_time=run_time,
        cron_expr=cron_expr,
        enabled=enabled,
        last_run_at="",
        created_at=now,
        updated_at=now,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return _scheduled_task_to_dict(row)


def update_scheduled_task(db: Session, schedule_id: int, payload: dict) -> dict:
    row = db.query(ScheduledTask).filter(ScheduledTask.id == schedule_id).first()
    if not row:
        raise ValueError("计划任务不存在")

    merged = {
        "name": payload.get("name", row.name),
        "task_type": payload.get("task_type", row.task_type),
        "target_mode": payload.get("target_mode", row.target_mode),
        "target_group": payload.get("target_group", row.target_group),
        "target_device_ids": payload.get("target_device_ids", _parse_target_ids(row.target_device_ids)),
        "params": payload.get("params", None),
        "cycle_type": payload.get("cycle_type", row.cycle_type),
        "run_time": payload.get("run_time", row.run_time),
        "cron_expr": payload.get("cron_expr", row.cron_expr),
        "enabled": payload.get("enabled", bool(row.enabled)),
    }

    task_type = str(merged["task_type"]).strip()
    target_mode = str(merged["target_mode"]).strip()
    cycle_type = str(merged["cycle_type"]).strip()
    name = str(merged["name"]).strip()
    run_time = str(merged["run_time"]).strip()
    target_group = str(merged["target_group"]).strip()
    target_device_ids = merged["target_device_ids"] or []
    cron_expr = str(merged["cron_expr"] or "").strip()

    if task_type not in TASK_MODULE_MAP and task_type not in {SERVER_INSPECTION_TASK_TYPE, SERVER_SWITCH_DETECT_TASK_TYPE}:
        raise ValueError("不支持的任务类型")
    if target_mode not in SCHEDULE_TARGET_MODES:
        raise ValueError("不支持的目标设备选择方式")
    if cycle_type not in SCHEDULE_CYCLE_TYPES:
        raise ValueError("不支持的执行周期")
    if not name:
        raise ValueError("任务名称不能为空")
    if not run_time:
        raise ValueError("执行时间不能为空")
    if target_mode == "group" and not target_group:
        raise ValueError("按分组选择时必须提供分组")
    if target_mode == "custom" and not target_device_ids:
        raise ValueError("自定义选择时至少选择一台设备")
    if cycle_type == "cron" and not cron_expr:
        raise ValueError("自定义Cron模式必须填写表达式")

    row.name = name
    row.task_type = task_type
    row.target_mode = target_mode
    row.target_group = target_group
    row.target_device_ids = _serialize_target_ids(target_device_ids)
    if merged.get("params") is not None:
        try:
            row.params = json.dumps(merged.get("params") or {}, ensure_ascii=False)
        except Exception:
            row.params = "{}"
    row.cycle_type = cycle_type
    row.run_time = run_time
    row.cron_expr = cron_expr
    row.enabled = 1 if bool(merged["enabled"]) else 0
    row.updated_at = _now_iso()
    db.commit()
    db.refresh(row)
    return _scheduled_task_to_dict(row)


def delete_scheduled_task(db: Session, schedule_id: int) -> bool:
    row = db.query(ScheduledTask).filter(ScheduledTask.id == schedule_id).first()
    if not row:
        return False
    db.delete(row)
    db.commit()
    return True


def run_scheduled_task_once(db: Session, schedule_id: int) -> dict:
    row = db.query(ScheduledTask).filter(ScheduledTask.id == schedule_id).first()
    if not row:
        raise ValueError("计划任务不存在")

    device_ids = _resolve_scheduled_device_ids(db, row)
    if not device_ids:
        raise ValueError("未匹配到可执行设备")

    params = {}
    try:
        params = json.loads(row.params or "{}")
    except Exception:
        params = {}
    result = execute_task(db, row.task_type, device_ids, params=params, precheck_id=None, schedule_id=row.id)
    row.last_run_at = _now_iso()
    row.updated_at = _now_iso()
    db.commit()
    return {
        "schedule_id": row.id,
        "task_id": result["task_id"],
        "status": result["status"],
        "total": result["total"],
    }


def _to_device_payload(device) -> dict:
    return {
        "id": device.id,
        "name": device.name,
        "ip": device.ip,
        "username": device.username,
        "password": device.password,
        "port": device.port,
        "device_type": device.device_type,
        "group_name": device.group_name,
        "location": device.location,
    }


def _cleanup_precheck_cache() -> None:
    now = datetime.now()
    with _PRECHECK_LOCK:
        expired = [
            key
            for key, value in _PRECHECK_CACHE.items()
            if now - value.get("created_at", now) > timedelta(minutes=_PRECHECK_TTL_MINUTES)
        ]
        for key in expired:
            _PRECHECK_CACHE.pop(key, None)


def _check_ssh_login(device_payload: dict, timeout: int) -> tuple[bool, str]:
    conn = None
    try:
        conn = ConnectHandler(
            device_type=device_payload.get("device_type", "huawei"),
            host=device_payload.get("ip", ""),
            username=device_payload.get("username", ""),
            password=device_payload.get("password", ""),
            port=int(device_payload.get("port", 22)),
            fast_cli=False,
            use_keys=False,
            allow_agent=False,
            conn_timeout=max(timeout, 5),
            banner_timeout=max(timeout, 5),
            auth_timeout=max(timeout, 5),
        )
        return True, "SSH登录成功"
    except Exception as exc:
        return False, f"SSH登录失败: {exc}"
    finally:
        if conn is not None:
            try:
                conn.disconnect()
            except Exception:
                pass


def _check_ntp_compliant(device_payload: dict, params: dict) -> tuple[bool, str]:
    ntp_server = params.get("ntp_server", "10.18.101.2")
    timezone = params.get("timezone", "BJ")
    offset = params.get("offset", "08:00:00")
    timeout = int(params.get("timeout", 20))

    if device_payload.get("ip") == ntp_server:
        return True, "设备是NTP服务器，按策略跳过"

    conn = None
    try:
        conn = ConnectHandler(
            device_type=device_payload.get("device_type", "huawei"),
            host=device_payload.get("ip", ""),
            username=device_payload.get("username", ""),
            password=device_payload.get("password", ""),
            port=int(device_payload.get("port", 22)),
            fast_cli=False,
            use_keys=False,
            allow_agent=False,
            conn_timeout=max(timeout, 5),
            banner_timeout=max(timeout, 5),
            auth_timeout=max(timeout, 5),
        )
        try:
            conn.send_command("screen-length 0 temporary")
        except Exception:
            pass

        tz_out = conn.send_command("display current-configuration | include clock timezone", read_timeout=max(timeout, 10))
        server_out = conn.send_command("display current-configuration | include ntp-service unicast-server", read_timeout=max(timeout, 10))

        tz_ok = bool(re.search(rf"clock\s+timezone\s+{re.escape(str(timezone))}\s+add\s+{re.escape(str(offset))}", tz_out, re.IGNORECASE))
        server_ok = bool(re.search(rf"ntp-service\s+unicast-server\s+{re.escape(str(ntp_server))}\b", server_out, re.IGNORECASE))

        if tz_ok and server_ok:
            return True, "当前配置已符合NTP要求"
        return False, "当前配置不符合NTP要求，需要下发配置"
    except Exception as exc:
        return False, f"NTP配置检查失败: {exc}"
    finally:
        if conn is not None:
            try:
                conn.disconnect()
            except Exception:
                pass


def precheck_task(db: Session, task_type: str, device_ids: list[int], params: dict | None = None) -> dict:
    if task_type not in TASK_MODULE_MAP and task_type not in {SERVER_INSPECTION_TASK_TYPE, SERVER_SWITCH_DETECT_TASK_TYPE}:
        raise ValueError("Unsupported task type")

    params = params or {}
    timeout = int(params.get("timeout", 20))

    if task_type in {SERVER_INSPECTION_TASK_TYPE, SERVER_SWITCH_DETECT_TASK_TYPE}:
        rows = db.query(ServerAsset).filter(ServerAsset.id.in_(device_ids or [])).order_by(ServerAsset.id.asc()).all()
        details = []
        executable_ids = []
        summary = {
            "total": len(rows),
            "executable": 0,
            "compliant": 0,
            "skipped": 0,
            "failed": 0,
        }

        for row in rows:
            if row.enable != 1:
                summary["skipped"] += 1
                details.append(
                    {
                        "device_id": row.id,
                        "device_name": row.name,
                        "device_ip": row.ip,
                        "online": False,
                        "ssh_ok": False,
                        "status": "skipped",
                        "message": "服务器已禁用",
                    }
                )
                continue

            summary["executable"] += 1
            executable_ids.append(row.id)
            details.append(
                {
                    "device_id": row.id,
                    "device_name": row.name,
                    "device_ip": row.ip,
                    "online": True,
                    "ssh_ok": True,
                    "status": "executable",
                    "message": "可执行服务器巡检" if task_type == SERVER_INSPECTION_TASK_TYPE else "可执行所属交换机检测",
                }
            )

        precheck_id = uuid.uuid4().hex
        with _PRECHECK_LOCK:
            _PRECHECK_CACHE[precheck_id] = {
                "created_at": datetime.now(),
                "task_type": task_type,
                "summary": summary,
                "details": details,
                "executable_ids": executable_ids,
            }

        return {
            "precheck_id": precheck_id,
            "summary": summary,
            "details": details,
        }

    devices = list_devices_by_ids(db, device_ids)

    details = []
    executable_ids = []
    summary = {
        "total": len(devices),
        "executable": 0,
        "compliant": 0,
        "skipped": 0,
        "failed": 0,
    }

    for d in devices:
        payload = _to_device_payload(d)
        online = ping_device(payload.get("ip", "")) == "online"
        if not online:
            summary["failed"] += 1
            details.append(
                {
                    "device_id": d.id,
                    "device_name": d.name,
                    "device_ip": d.ip,
                    "online": False,
                    "ssh_ok": False,
                    "status": "failed",
                    "message": "设备离线",
                }
            )
            continue

        if task_type == "audit":
            summary["executable"] += 1
            executable_ids.append(d.id)
            details.append(
                {
                    "device_id": d.id,
                    "device_name": d.name,
                    "device_ip": d.ip,
                    "online": True,
                    "ssh_ok": True,
                    "status": "executable",
                    "message": "设备在线，可执行巡检",
                }
            )
            continue

        ssh_ok, ssh_msg = _check_ssh_login(payload, timeout)
        if not ssh_ok:
            summary["failed"] += 1
            details.append(
                {
                    "device_id": d.id,
                    "device_name": d.name,
                    "device_ip": d.ip,
                    "online": True,
                    "ssh_ok": False,
                    "status": "failed",
                    "message": ssh_msg,
                }
            )
            continue

        if task_type == "ntp":
            compliant, msg = _check_ntp_compliant(payload, params)
            if payload.get("ip") == params.get("ntp_server", "10.18.101.2"):
                summary["skipped"] += 1
                details.append(
                    {
                        "device_id": d.id,
                        "device_name": d.name,
                        "device_ip": d.ip,
                        "online": True,
                        "ssh_ok": True,
                        "status": "skipped",
                        "message": msg,
                    }
                )
                continue

            if compliant:
                summary["compliant"] += 1
                details.append(
                    {
                        "device_id": d.id,
                        "device_name": d.name,
                        "device_ip": d.ip,
                        "online": True,
                        "ssh_ok": True,
                        "status": "compliant",
                        "message": msg,
                    }
                )
            else:
                summary["executable"] += 1
                executable_ids.append(d.id)
                details.append(
                    {
                        "device_id": d.id,
                        "device_name": d.name,
                        "device_ip": d.ip,
                        "online": True,
                        "ssh_ok": True,
                        "status": "executable",
                        "message": msg,
                    }
                )
        else:
            summary["executable"] += 1
            executable_ids.append(d.id)
            details.append(
                {
                    "device_id": d.id,
                    "device_name": d.name,
                    "device_ip": d.ip,
                    "online": True,
                    "ssh_ok": True,
                    "status": "executable",
                    "message": "检查通过，可执行任务",
                }
            )

    precheck_id = uuid.uuid4().hex
    _cleanup_precheck_cache()
    with _PRECHECK_LOCK:
        _PRECHECK_CACHE[precheck_id] = {
            "created_at": datetime.now(),
            "task_type": task_type,
            "params": params,
            "executable_ids": executable_ids,
            "summary": summary,
            "details": details,
        }

    return {
        "precheck_id": precheck_id,
        "task_type": task_type,
        "summary": summary,
        "details": details,
        "executable_ids": executable_ids,
    }


def _runtime_set(task_id: int, patch: dict) -> None:
    with _RUNTIME_LOCK:
        base = _TASK_RUNTIME.setdefault(task_id, {})
        base.update(patch)


def _runtime_append_log(task_id: int, line: str) -> None:
    with _RUNTIME_LOCK:
        runtime = _TASK_RUNTIME.setdefault(task_id, {})
        logs = runtime.setdefault("logs", [])
        logs.append(f"[{datetime.now().strftime('%H:%M:%S')}] {line}")
        if len(logs) > 200:
            runtime["logs"] = logs[-200:]


def _run_task_worker(
    task_id: int,
    task_type: str,
    device_ids: list[int],
    params: dict,
    schedule_id: int | None = None,
) -> None:
    if task_type == SERVER_INSPECTION_TASK_TYPE:
        _run_server_inspection_worker(task_id, device_ids, params, schedule_id=schedule_id)
        return
    if task_type == SERVER_SWITCH_DETECT_TASK_TYPE:
        _run_server_switch_detect_worker(task_id, device_ids, params, schedule_id=schedule_id)
        return

    db = SessionLocal()
    try:
        devices = list_devices_by_ids(db, device_ids)
        total = len(devices)

        _runtime_set(
            task_id,
            {
                "task_id": task_id,
                "state": "running",
                "progress": 0,
                "total": total,
                "success": 0,
                "failed": 0,
                "skipped": 0,
                "logs": [f"[{datetime.now().strftime('%H:%M:%S')}] 任务开始执行"],
            },
        )

        task = db.query(Task).filter(Task.id == task_id).first()
        if not task:
            return

        module = TASK_MODULE_MAP[task_type]
        success_count = 0
        fail_count = 0
        skip_count = 0

        for idx, d in enumerate(devices, start=1):
            payload = _to_device_payload(d)

            if task_type == "ntp" and payload.get("ip") == params.get("ntp_server", "10.18.101.2"):
                skip_count += 1
                row = TaskResult(
                    task_id=task_id,
                    device_ip=payload.get("ip", ""),
                    device_name=payload.get("name", ""),
                    status="skipped",
                    message="设备是NTP服务器，按策略跳过",
                    start_time=datetime.now().isoformat(timespec="seconds"),
                    end_time=datetime.now().isoformat(timespec="seconds"),
                )
                db.add(row)
                db.commit()
                _runtime_append_log(task_id, f"{payload.get('name')}({payload.get('ip')}) 跳过：NTP服务器")
            else:
                result_list = module.run([payload], params)
                result = result_list[0] if result_list else {
                    "device_ip": payload.get("ip", ""),
                    "device_name": payload.get("name", ""),
                    "status": "failed",
                    "message": "模块未返回结果",
                    "start_time": datetime.now().isoformat(timespec="seconds"),
                    "end_time": datetime.now().isoformat(timespec="seconds"),
                }

                status = result.get("status", "failed")
                if status == "success":
                    success_count += 1
                    _runtime_append_log(task_id, f"{result.get('device_name')}({result.get('device_ip')}) 执行成功")
                elif status == "skipped":
                    skip_count += 1
                    _runtime_append_log(task_id, f"{result.get('device_name')}({result.get('device_ip')}) 已跳过")
                else:
                    fail_count += 1
                    _runtime_append_log(task_id, f"{result.get('device_name')}({result.get('device_ip')}) 执行失败: {result.get('message')}")

                row = TaskResult(
                    task_id=task_id,
                    device_ip=result.get("device_ip", ""),
                    device_name=result.get("device_name", ""),
                    status=status,
                    message=result.get("message", ""),
                    start_time=result.get("start_time", datetime.now().isoformat(timespec="seconds")),
                    end_time=result.get("end_time", datetime.now().isoformat(timespec="seconds")),
                )
                db.add(row)
                db.commit()

            progress = int(idx / total * 100) if total else 100
            _runtime_set(
                task_id,
                {
                    "progress": progress,
                    "success": success_count,
                    "failed": fail_count,
                    "skipped": skip_count,
                },
            )

        task.success = success_count
        task.failed = fail_count
        task.total = total
        task.end_time = datetime.now().isoformat(timespec="seconds")

        if fail_count == 0 and success_count > 0:
            task.status = "success"
        elif fail_count > 0 and success_count > 0:
            task.status = "partial_failed"
        elif fail_count > 0 and success_count == 0:
            task.status = "failed"
        else:
            task.status = "completed"

        db.commit()

        _runtime_set(
            task_id,
            {
                "state": "completed",
                "progress": 100,
                "success": success_count,
                "failed": fail_count,
                "skipped": skip_count,
                "status": task.status,
            },
        )
        _runtime_append_log(task_id, "任务执行完成")

        task_logger.info(
            "task_id=%s type=%s total=%s success=%s failed=%s skipped=%s",
            task_id,
            task_type,
            total,
            success_count,
            fail_count,
            skip_count,
        )
    except Exception as exc:
        error_logger.exception("task worker failed: %s", exc)
        _runtime_set(task_id, {"state": "failed"})
        _runtime_append_log(task_id, f"任务异常终止: {exc}")

        task = db.query(Task).filter(Task.id == task_id).first()
        if task:
            task.status = "failed"
            task.end_time = datetime.now().isoformat(timespec="seconds")
            db.commit()
    finally:
        db.close()


def _extract_command_output(logs: list[dict], command_prefix: str) -> str:
    for item in logs or []:
        if str(item.get("command", "")).strip().startswith(command_prefix):
            return str(item.get("output", "") or "")
    return ""


def _run_server_switch_detect_worker(
    task_id: int,
    server_ids: list[int],
    params: dict,
    schedule_id: int | None = None,
) -> None:
    """
    Detect and persist server->(Server-SW) topology mapping by querying core switch:
    ARP -> port -> LLDP neighbor.

    This is intentionally handled in TaskCenter so we can have unified logs/results
    and both immediate/scheduled modes.
    """
    db = SessionLocal()
    try:
        rows = db.query(ServerAsset).filter(ServerAsset.id.in_(server_ids or [])).order_by(ServerAsset.id.asc()).all()
        total = len(rows)
        trigger = str((params or {}).get("trigger") or ("schedule" if schedule_id else "manual")).strip() or "manual"
        force = bool((params or {}).get("force") or False)

        _runtime_set(
            task_id,
            {
                "task_id": task_id,
                "state": "running",
                "progress": 0,
                "total": total,
                "success": 0,
                "failed": 0,
                "skipped": 0,
                "logs": [f"[{datetime.now().strftime('%H:%M:%S')}] 任务开始执行：服务器所属交换机检测"],
            },
        )

        task = db.query(Task).filter(Task.id == task_id).first()
        if not task:
            return

        success_count = 0
        fail_count = 0
        skip_count = 0

        for idx, server in enumerate(rows, start=1):
            if server.enable != 1:
                skip_count += 1
                row = TaskResult(
                    task_id=task_id,
                    device_ip=server.ip or "",
                    device_name=server.name or "",
                    status="skipped",
                    message="服务器已禁用，跳过检测",
                    start_time=datetime.now().isoformat(timespec="seconds"),
                    end_time=datetime.now().isoformat(timespec="seconds"),
                )
                db.add(row)
                db.commit()
                _runtime_append_log(task_id, f"{server.name}({server.ip}) 跳过：服务器已禁用")
                continue

            # If not forced and mapping exists, we still run (ARP may change). Force is reserved for future.
            _runtime_append_log(task_id, f"开始检测 {server.name}({server.ip}) 所属交换机...")
            result = locate_and_persist_server(db, server, locate_method="auto" if trigger == "create" else "manual")

            detect_status = str(result.get("topology_locate_status") or "failed").strip().lower()
            detect_reason = str(result.get("topology_locate_reason") or "").strip()
            logs = result.get("logs") or []
            arp_raw = _extract_command_output(logs, "display arp")
            lldp_raw = _extract_command_output(logs, "display lldp")

            access_switch_name = str(result.get("server_switch_name") or "").strip()
            core_uplink_port = str(result.get("uplink_core_switch_port") or "").strip()
            switch_port = str(result.get("server_switch_port") or "").strip()

            ok = detect_status in {"success", "manual"}
            status_text = "success" if ok else "failed"
            if ok:
                success_count += 1
                _runtime_append_log(task_id, f"{server.name}({server.ip}) 检测成功：{access_switch_name or '-'}")
            else:
                fail_count += 1
                _runtime_append_log(task_id, f"{server.name}({server.ip}) 检测失败：{detect_reason or '未知原因'}")

            db.add(
                ServerSwitchDetectLog(
                    task_id=task_id,
                    server_id=server.id,
                    server_name=server.name or "",
                    server_ip=server.ip or "",
                    detect_status="success" if ok else "failed",
                    detect_message=detect_reason or "",
                    access_switch_name=access_switch_name,
                    core_uplink_port=core_uplink_port,
                    switch_downlink_port=switch_port,
                    arp_raw=arp_raw or "",
                    lldp_raw=lldp_raw or "",
                    trigger_type=trigger,
                    created_at=datetime.now().isoformat(timespec="seconds"),
                )
            )

            row = TaskResult(
                task_id=task_id,
                device_ip=server.ip or "",
                device_name=server.name or "",
                status=status_text,
                message=detect_reason or ("检测成功" if ok else "检测失败"),
                start_time=datetime.now().isoformat(timespec="seconds"),
                end_time=datetime.now().isoformat(timespec="seconds"),
            )
            db.add(row)
            db.commit()

            progress = int(idx / total * 100) if total else 100
            _runtime_set(
                task_id,
                {
                    "progress": progress,
                    "success": success_count,
                    "failed": fail_count,
                    "skipped": skip_count,
                },
            )

        task.success = success_count
        task.failed = fail_count
        task.total = total
        task.end_time = datetime.now().isoformat(timespec="seconds")

        if fail_count == 0 and success_count > 0:
            task.status = "success"
        elif fail_count > 0 and success_count > 0:
            task.status = "partial_failed"
        elif fail_count > 0 and success_count == 0:
            task.status = "failed"
        else:
            task.status = "completed"

        db.commit()

        _runtime_set(
            task_id,
            {
                "state": "completed",
                "progress": 100,
                "success": success_count,
                "failed": fail_count,
                "skipped": skip_count,
                "status": task.status,
            },
        )
        _runtime_append_log(task_id, "任务执行完成")

        task_logger.info(
            "task_id=%s type=%s total=%s success=%s failed=%s skipped=%s",
            task_id,
            SERVER_SWITCH_DETECT_TASK_TYPE,
            total,
            success_count,
            fail_count,
            skip_count,
        )
    except Exception as exc:
        error_logger.exception("server switch detect worker failed: %s", exc)
        _runtime_set(task_id, {"state": "failed"})
        _runtime_append_log(task_id, f"任务异常终止: {exc}")
        task = db.query(Task).filter(Task.id == task_id).first()
        if task:
            task.status = "failed"
            task.end_time = datetime.now().isoformat(timespec="seconds")
            db.commit()
    finally:
        db.close()


def execute_task(
    db: Session,
    task_type: str,
    device_ids: list[int],
    params: dict | None = None,
    precheck_id: str | None = None,
    schedule_id: int | None = None,
) -> dict:
    if task_type not in TASK_MODULE_MAP and task_type not in {SERVER_INSPECTION_TASK_TYPE, SERVER_SWITCH_DETECT_TASK_TYPE}:
        raise ValueError("Unsupported task type")

    params = params or {}
    selected_ids = list(device_ids or [])

    if precheck_id:
        _cleanup_precheck_cache()
        with _PRECHECK_LOCK:
            precheck = _PRECHECK_CACHE.get(precheck_id)
        if not precheck:
            raise ValueError("预检查记录不存在或已过期")
        if precheck.get("task_type") != task_type:
            raise ValueError("任务类型与预检查记录不一致")
        selected_ids = precheck.get("executable_ids", [])

    task = Task(
        task_type=task_type,
        start_time=datetime.now().isoformat(timespec="seconds"),
        end_time="",
        status="running",
        total=len(selected_ids),
        success=0,
        failed=0,
    )
    db.add(task)
    db.commit()
    db.refresh(task)

    worker = threading.Thread(
        target=_run_task_worker,
        args=(task.id, task_type, selected_ids, params, schedule_id),
        daemon=True,
    )
    worker.start()

    return {
        "task_id": task.id,
        "status": "running",
        "total": len(selected_ids),
    }


def get_task_progress(db: Session, task_id: int) -> dict:
    with _RUNTIME_LOCK:
        runtime = _TASK_RUNTIME.get(task_id)

    if runtime:
        # If runtime cache is stale (e.g. thread finished but cache not updated),
        # fall back to DB end_time to prevent UI polling forever.
        state = str(runtime.get("state", "running") or "running")
        if state not in {"completed", "failed"}:
            task = get_task(db, task_id)
            if task and task.end_time:
                # Patch cache so next call is consistent.
                _runtime_set(
                    task_id,
                    {
                        "state": "completed",
                        "progress": 100,
                        "total": task.total,
                        "success": task.success,
                        "failed": task.failed,
                        "status": task.status,
                    },
                )
                with _RUNTIME_LOCK:
                    runtime = _TASK_RUNTIME.get(task_id) or runtime
        return {
            "task_id": task_id,
            "state": runtime.get("state", "running"),
            "progress": runtime.get("progress", 0),
            "total": runtime.get("total", 0),
            "success": runtime.get("success", 0),
            "failed": runtime.get("failed", 0),
            "skipped": runtime.get("skipped", 0),
            "logs": runtime.get("logs", []),
            "status": runtime.get("status", "running"),
        }

    task = get_task(db, task_id)
    if not task:
        raise ValueError("Task not found")

    details = task.results or []
    skipped = sum(1 for r in details if r.status == "skipped")
    return {
        "task_id": task_id,
        "state": "completed" if task.end_time else "running",
        "progress": 100 if task.end_time else 0,
        "total": task.total,
        "success": task.success,
        "failed": task.failed,
        "skipped": skipped,
        "logs": [],
        "status": task.status,
    }
