from __future__ import annotations

import json
import os
import re
import smtplib
import sqlite3
from datetime import datetime
from email.mime.text import MIMEText
from email.utils import formataddr
from pathlib import Path
from urllib import request

from sqlalchemy.orm import Session

from app.database.database import DATABASE_URL
from app.models.alert import AlertEvent, AlertRuleState
from app.models.server import ServerAsset
from app.models.task import Task, TaskResult
from app.services import server_service

ALERT_LEVELS = {"INFO", "WARNING", "CRITICAL"}
ALERT_STATUSES = {"NEW", "ACK", "RECOVERED", "CLOSED"}
SERVER_CPU_THRESHOLD = 85
SERVER_MEMORY_THRESHOLD = 85
SERVER_DISK_THRESHOLD = 90
NETWORK_CPU_THRESHOLD = 85
NETWORK_MEMORY_THRESHOLD = 85
NETWORK_DISK_THRESHOLD = 90
DEBOUNCE_HITS = 3


def _now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def ensure_schema() -> None:
    db_path = DATABASE_URL.replace("sqlite:///", "", 1)
    full_path = Path.cwd() / db_path
    conn = sqlite3.connect(full_path)
    try:
        server_columns = {row[1] for row in conn.execute("PRAGMA table_info(servers)").fetchall()}
        missing_server_columns = {
            "cpu_usage": "ALTER TABLE servers ADD COLUMN cpu_usage INTEGER DEFAULT 0",
            "memory_usage": "ALTER TABLE servers ADD COLUMN memory_usage INTEGER DEFAULT 0",
            "disk_usage": "ALTER TABLE servers ADD COLUMN disk_usage INTEGER DEFAULT 0",
            "response_time_ms": "ALTER TABLE servers ADD COLUMN response_time_ms INTEGER DEFAULT 0",
            "core_ping_status": "ALTER TABLE servers ADD COLUMN core_ping_status TEXT DEFAULT 'unknown'",
            "router_ping_status": "ALTER TABLE servers ADD COLUMN router_ping_status TEXT DEFAULT 'unknown'",
        }
        for column, ddl in missing_server_columns.items():
            if column not in server_columns:
                conn.execute(ddl)
        conn.commit()
    finally:
        conn.close()


def _severity_rank(level: str) -> int:
    return {"INFO": 0, "WARNING": 1, "CRITICAL": 2}.get(str(level or "").upper(), 0)


def _pick_higher_severity(first: str, second: str) -> str:
    return first if _severity_rank(first) >= _severity_rank(second) else second


def _safe_int(value) -> int | None:
    if value is None or value == "":
        return None
    try:
        return int(float(str(value).strip().rstrip("%")))
    except Exception:
        return None


def _extract_metric(text: str, labels: list[str]) -> int | None:
    for label in labels:
        match = re.search(rf"{label}\s*=\s*([0-9]+(?:\.[0-9]+)?)", text, re.IGNORECASE)
        if match:
            return _safe_int(match.group(1))
    return None


def _send_email_notification(subject: str, body: str) -> str:
    host = os.getenv("ALERT_SMTP_HOST", "").strip()
    port = int(os.getenv("ALERT_SMTP_PORT", "25") or 25)
    username = os.getenv("ALERT_SMTP_USER", "").strip()
    password = os.getenv("ALERT_SMTP_PASSWORD", "").strip()
    sender = os.getenv("ALERT_EMAIL_FROM", "").strip()
    recipients = [item.strip() for item in os.getenv("ALERT_EMAIL_TO", "").split(",") if item.strip()]

    if not host or not sender or not recipients:
        return "email skipped: missing smtp configuration"

    message = MIMEText(body, "plain", "utf-8")
    message["Subject"] = subject
    message["From"] = formataddr(("告警中心", sender))
    message["To"] = ", ".join(recipients)

    server = smtplib.SMTP(host, port, timeout=10)
    try:
        server.ehlo()
        if username and password:
            try:
                server.starttls()
                server.ehlo()
            except Exception:
                pass
            server.login(username, password)
        server.sendmail(sender, recipients, message.as_string())
        return f"email sent to {', '.join(recipients)}"
    finally:
        try:
            server.quit()
        except Exception:
            pass


def _send_wecom_notification(subject: str, body: str) -> str:
    webhook = os.getenv("ALERT_WECOM_WEBHOOK", "").strip()
    if not webhook:
        return "wecom skipped: webhook not configured"

    payload = json.dumps({"msgtype": "text", "text": {"content": f"{subject}\n{body}"}}, ensure_ascii=False).encode("utf-8")
    req = request.Request(webhook, data=payload, headers={"Content-Type": "application/json"})
    with request.urlopen(req, timeout=10) as resp:  # nosec - controlled webhook
        return f"wecom sent: http {resp.status}"


def _notify_alert(alert: AlertEvent) -> str:
    subject = f"[{alert.severity}] {alert.title}"
    body = "\n".join(
        [
            f"来源: {alert.source_type}",
            f"对象: {alert.source_name} ({alert.source_ip})",
            f"指标: {alert.metric_type}",
            f"当前值: {alert.current_value}",
            f"阈值: {alert.threshold_value}",
            f"状态: {alert.status}",
            f"时间: {alert.last_triggered_at}",
            f"说明: {alert.message}",
        ]
    )
    results = [_send_email_notification(subject, body)]
    try:
        results.append(_send_wecom_notification(subject, body))
    except Exception as exc:
        results.append(f"wecom failed: {exc}")
    return " | ".join(results)


def _server_candidates(db: Session) -> list[dict]:
    rows = server_service.list_servers(db, with_status=True)
    candidates = []
    for row in rows:
        if row.enable != 1:
            continue
        if row.status == "offline":
            candidates.append(
                {
                    "dedupe_key": f"server:{row.id}:offline",
                    "source_type": "server",
                    "source_id": str(row.id),
                    "source_name": row.name,
                    "source_ip": row.ip,
                    "metric_type": "offline",
                    "severity": "CRITICAL",
                    "current_value": row.status,
                    "threshold_value": "online",
                    "message": row.last_error or "服务器离线",
                    "title": f"服务器离线告警 - {row.name}",
                }
            )

        for metric_name, current_value, threshold in [
            ("cpu", row.cpu_usage, SERVER_CPU_THRESHOLD),
            ("memory", row.memory_usage, SERVER_MEMORY_THRESHOLD),
            ("disk", row.disk_usage, SERVER_DISK_THRESHOLD),
        ]:
            value = _safe_int(current_value)
            if value is None or value < threshold:
                continue
            severity = "CRITICAL" if value >= threshold + 10 else "WARNING"
            candidates.append(
                {
                    "dedupe_key": f"server:{row.id}:{metric_name}",
                    "source_type": "server",
                    "source_id": str(row.id),
                    "source_name": row.name,
                    "source_ip": row.ip,
                    "metric_type": metric_name,
                    "severity": severity,
                    "current_value": str(value),
                    "threshold_value": str(threshold),
                    "message": f"{metric_name.upper()} 使用率 {value}% 超过阈值 {threshold}%",
                    "title": f"服务器{metric_name.upper()}告警 - {row.name}",
                }
            )
    return candidates


def _network_candidates(db: Session) -> list[dict]:
    task_ids = (
        db.query(Task.id)
        .filter(Task.task_type == "audit")
        .order_by(Task.id.desc())
        .limit(10)
        .subquery()
    )
    rows = db.query(TaskResult).filter(TaskResult.task_id.in_(task_ids)).all()
    latest_by_device = {}
    for row in rows:
        latest_by_device.setdefault(row.device_ip, row)

    candidates = []
    for row in latest_by_device.values():
        text = str(row.message or "")
        if row.status == "failed":
            candidates.append(
                {
                    "dedupe_key": f"network:{row.device_ip}:offline",
                    "source_type": "network",
                    "source_id": row.device_ip,
                    "source_name": row.device_name,
                    "source_ip": row.device_ip,
                    "metric_type": "offline",
                    "severity": "CRITICAL",
                    "current_value": "failed",
                    "threshold_value": "success",
                    "message": text or "网络巡检失败",
                    "title": f"网络设备离线/巡检失败 - {row.device_name}",
                }
            )
            continue

        metrics = [
            ("cpu", _extract_metric(text, ["CPU", "cpu"]), NETWORK_CPU_THRESHOLD),
            ("memory", _extract_metric(text, ["内存", "MEM", "memory"]), NETWORK_MEMORY_THRESHOLD),
            ("disk", _extract_metric(text, ["磁盘", "disk"]), NETWORK_DISK_THRESHOLD),
        ]
        alert_items = re.search(r"告警=([^;]+)", text)
        overall_match = re.search(r"总评=([A-Z_]+)", text)
        overall = str(overall_match.group(1) if overall_match else "").upper()
        if overall == "CRITICAL":
            candidates.append(
                {
                    "dedupe_key": f"network:{row.device_ip}:overall",
                    "source_type": "network",
                    "source_id": row.device_ip,
                    "source_name": row.device_name,
                    "source_ip": row.device_ip,
                    "metric_type": "overall",
                    "severity": "CRITICAL",
                    "current_value": overall,
                    "threshold_value": "OK",
                    "message": alert_items.group(1).strip() if alert_items else text,
                    "title": f"网络巡检严重告警 - {row.device_name}",
                }
            )
        elif overall == "WARNING":
            candidates.append(
                {
                    "dedupe_key": f"network:{row.device_ip}:overall",
                    "source_type": "network",
                    "source_id": row.device_ip,
                    "source_name": row.device_name,
                    "source_ip": row.device_ip,
                    "metric_type": "overall",
                    "severity": "WARNING",
                    "current_value": overall,
                    "threshold_value": "OK",
                    "message": alert_items.group(1).strip() if alert_items else text,
                    "title": f"网络巡检告警 - {row.device_name}",
                }
            )

        for metric_name, value, threshold in metrics:
            if value is None or value < threshold:
                continue
            severity = "CRITICAL" if value >= threshold + 10 else "WARNING"
            candidates.append(
                {
                    "dedupe_key": f"network:{row.device_ip}:{metric_name}",
                    "source_type": "network",
                    "source_id": row.device_ip,
                    "source_name": row.device_name,
                    "source_ip": row.device_ip,
                    "metric_type": metric_name,
                    "severity": severity,
                    "current_value": str(value),
                    "threshold_value": str(threshold),
                    "message": f"{metric_name.upper()} 使用率 {value}% 超过阈值 {threshold}%",
                    "title": f"网络设备{metric_name.upper()}告警 - {row.device_name}",
                }
            )
    return candidates


def refresh_alerts(db: Session) -> None:
    candidates = _server_candidates(db) + _network_candidates(db)
    now = _now_iso()
    candidate_map = {item["dedupe_key"]: item for item in candidates}

    states = {item.dedupe_key: item for item in db.query(AlertRuleState).all()}

    for dedupe_key, payload in candidate_map.items():
        state = states.get(dedupe_key)
        if not state:
            state = AlertRuleState(
                dedupe_key=dedupe_key,
                source_type=payload["source_type"],
                source_id=payload["source_id"],
                source_name=payload["source_name"],
                source_ip=payload["source_ip"],
                metric_type=payload["metric_type"],
            )
            db.add(state)
            db.flush()
            states[dedupe_key] = state

        state.source_type = payload["source_type"]
        state.source_id = payload["source_id"]
        state.source_name = payload["source_name"]
        state.source_ip = payload["source_ip"]
        state.metric_type = payload["metric_type"]
        state.current_value = payload["current_value"]
        state.threshold_value = payload["threshold_value"]
        state.last_message = payload["message"]
        state.severity = _pick_higher_severity(payload["severity"], state.severity)
        state.consecutive_hits = int(state.consecutive_hits or 0) + 1
        state.last_seen_at = now

        active_alert = db.query(AlertEvent).filter(AlertEvent.id == int(state.active_alert_id or 0)).first() if state.active_alert_id else None
        if state.state == "closed":
            continue
        if state.consecutive_hits < DEBOUNCE_HITS:
            state.state = "debouncing"
            continue

        if active_alert and active_alert.status in {"NEW", "ACK"}:
            active_alert.last_triggered_at = now
            active_alert.occurrence_count = int(active_alert.occurrence_count or 0) + 1
            active_alert.message = payload["message"]
            active_alert.current_value = payload["current_value"]
            active_alert.threshold_value = payload["threshold_value"]
            active_alert.severity = _pick_higher_severity(payload["severity"], active_alert.severity)
            state.state = "active"
            continue

        alert = AlertEvent(
            source_type=payload["source_type"],
            source_id=payload["source_id"],
            source_name=payload["source_name"],
            source_ip=payload["source_ip"],
            metric_type=payload["metric_type"],
            severity=payload["severity"],
            status="NEW",
            title=payload["title"],
            message=payload["message"],
            current_value=payload["current_value"],
            threshold_value=payload["threshold_value"],
            dedupe_key=dedupe_key,
            first_triggered_at=now,
            last_triggered_at=now,
            occurrence_count=state.consecutive_hits,
            notify_channels="email,wecom",
        )
        db.add(alert)
        db.flush()
        alert.notify_result = _notify_alert(alert)
        state.active_alert_id = alert.id
        state.state = "active"

    for dedupe_key, state in states.items():
        if dedupe_key in candidate_map:
            continue
        if int(state.active_alert_id or 0) <= 0:
            state.consecutive_hits = 0
            state.state = "idle"
            continue

        alert = db.query(AlertEvent).filter(AlertEvent.id == int(state.active_alert_id or 0)).first()
        if alert and alert.status in {"NEW", "ACK"}:
            alert.status = "RECOVERED"
            alert.recovered_at = now
            alert.last_triggered_at = now
        state.consecutive_hits = 0
        state.state = "recovered"
        state.active_alert_id = 0

    db.commit()


def list_alerts(
    db: Session,
    severity: str | None = None,
    status: str | None = None,
    source_type: str | None = None,
    keyword: str | None = None,
) -> list[dict]:
    refresh_alerts(db)

    query = db.query(AlertEvent)
    if severity and severity.upper() in ALERT_LEVELS:
        query = query.filter(AlertEvent.severity == severity.upper())
    if status and status.upper() in ALERT_STATUSES:
        query = query.filter(AlertEvent.status == status.upper())
    if source_type:
        query = query.filter(AlertEvent.source_type == source_type.lower())
    if keyword:
        like = f"%{keyword}%"
        query = query.filter(
            (AlertEvent.source_name.like(like))
            | (AlertEvent.source_ip.like(like))
            | (AlertEvent.title.like(like))
            | (AlertEvent.message.like(like))
        )

    rows = query.order_by(AlertEvent.id.desc()).all()
    return [serialize_alert(row) for row in rows]


def serialize_alert(row: AlertEvent) -> dict:
    return {
        "id": row.id,
        "source_type": row.source_type,
        "source_id": row.source_id,
        "source_name": row.source_name,
        "source_ip": row.source_ip,
        "metric_type": row.metric_type,
        "severity": row.severity,
        "status": row.status,
        "title": row.title,
        "message": row.message,
        "current_value": row.current_value,
        "threshold_value": row.threshold_value,
        "dedupe_key": row.dedupe_key,
        "first_triggered_at": row.first_triggered_at,
        "last_triggered_at": row.last_triggered_at,
        "acknowledged_at": row.acknowledged_at,
        "acknowledged_by": row.acknowledged_by,
        "recovered_at": row.recovered_at,
        "closed_at": row.closed_at,
        "notify_channels": row.notify_channels,
        "notify_result": row.notify_result,
        "occurrence_count": row.occurrence_count,
    }


def bulk_update_status(db: Session, alert_ids: list[int], action: str, operator: str = "unknown") -> dict:
    normalized_action = str(action or "").upper()
    if normalized_action not in {"ACK", "CLOSED"}:
        raise ValueError("仅支持 ACK 或 CLOSED 操作")
    if not alert_ids:
        raise ValueError("请选择至少一条告警")

    rows = db.query(AlertEvent).filter(AlertEvent.id.in_(alert_ids)).all()
    now = _now_iso()
    affected = 0
    for row in rows:
        if normalized_action == "ACK" and row.status == "NEW":
            row.status = "ACK"
            row.acknowledged_at = now
            row.acknowledged_by = operator
            affected += 1
        elif normalized_action == "CLOSED" and row.status in {"NEW", "ACK", "RECOVERED"}:
            row.status = "CLOSED"
            row.closed_at = now
            state = db.query(AlertRuleState).filter(AlertRuleState.dedupe_key == row.dedupe_key).first()
            if state:
                state.state = "closed"
                state.active_alert_id = row.id
            affected += 1
    db.commit()
    return {"updated": affected}
