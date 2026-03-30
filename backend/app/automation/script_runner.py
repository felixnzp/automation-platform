from __future__ import annotations

import csv
import subprocess
import sys
import tempfile
import uuid
from datetime import datetime
from pathlib import Path

LEGACY_ROOT = Path(r"D:\network-automation")
AUDIT_SCRIPT = LEGACY_ROOT / "huawei_audit.py"
NTP_SCRIPT = LEGACY_ROOT / "huawei_ntp_config.py"

RUN_ROOT = Path(__file__).resolve().parents[2] / "logs" / "script_runs"
RUN_ROOT.mkdir(parents=True, exist_ok=True)


def _write_device_csv(devices: list[dict]) -> Path:
    tmp_file = tempfile.NamedTemporaryFile(
        mode="w",
        suffix=".csv",
        prefix="devices_",
        encoding="utf-8",
        newline="",
        delete=False,
    )
    writer = csv.DictWriter(
        tmp_file,
        fieldnames=["host", "port", "username", "password", "device_type", "group", "location", "enabled"],
    )
    writer.writeheader()
    for d in devices:
        writer.writerow(
            {
                "host": d.get("ip", ""),
                "port": d.get("port", 22),
                "username": d.get("username", ""),
                "password": d.get("password", ""),
                "device_type": d.get("device_type", "huawei"),
                "group": d.get("group_name", ""),
                "location": d.get("location", ""),
                "enabled": "true",
            }
        )
    tmp_file.flush()
    tmp_file.close()
    return Path(tmp_file.name)


def _mk_run_dir(kind: str) -> Path:
    ts = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    run_dir = RUN_ROOT / kind / f"run_{ts}_{uuid.uuid4().hex[:8]}"
    run_dir.mkdir(parents=True, exist_ok=True)
    return run_dir


def _latest_csv_file(folder: Path, pattern: str) -> Path | None:
    files = list(folder.glob(pattern))
    if not files:
        return None
    return max(files, key=lambda p: p.stat().st_mtime)


def _read_csv(path: Path) -> list[dict]:
    for enc in ("utf-8-sig", "utf-8", "gbk", "cp936", "latin-1"):
        try:
            with path.open("r", encoding=enc, newline="") as f:
                rows = list(csv.DictReader(f))
            cleaned = []
            for row in rows:
                cleaned.append({str(k).lstrip("\ufeff"): v for k, v in row.items()})
            return cleaned
        except Exception:
            continue
    return []


def _decode_bytes(raw: bytes) -> str:
    if not raw:
        return ""
    for enc in ("utf-8", "utf-8-sig", "gbk", "cp936", "latin-1"):
        try:
            return raw.decode(enc)
        except Exception:
            continue
    return raw.decode("utf-8", errors="ignore")


def _clean_trace(text: str, max_len: int = 1600) -> str:
    t = (text or "").replace("\r\n", "\n").strip()
    return t[-max_len:]


def _pick(row: dict, *keys: str, default: str = "") -> str:
    for k in keys:
        if k in row and str(row.get(k, "")).strip() != "":
            return str(row.get(k, "")).strip()
    return default


def run_audit_script(devices: list[dict], params: dict) -> tuple[list[dict], str]:
    outdir = _mk_run_dir("audit")
    device_csv = _write_device_csv(devices)
    timeout = int(params.get("script_timeout", 600))

    cmd = [
        sys.executable,
        str(AUDIT_SCRIPT),
        "-host",
        str(device_csv),
        "-o",
        str(outdir),
        "-v",
    ]
    proc = subprocess.run(
        cmd,
        cwd=str(LEGACY_ROOT),
        capture_output=True,
        text=False,
        timeout=timeout,
        check=False,
    )

    table_file = _latest_csv_file(outdir, "inspection_table_*.csv")
    rows = _read_csv(table_file) if table_file else []

    stdout_text = _decode_bytes(proc.stdout)
    stderr_text = _decode_bytes(proc.stderr)
    trace = _clean_trace(stdout_text + ("\n" + stderr_text if stderr_text else ""))
    return rows, trace


def run_ntp_script(devices: list[dict], params: dict) -> tuple[list[dict], str]:
    outdir = _mk_run_dir("ntp")
    device_csv = _write_device_csv(devices)
    timeout = int(params.get("script_timeout", 900))
    ntp_server = params.get("ntp_server", "10.18.101.2")

    cmd = [
        sys.executable,
        str(NTP_SCRIPT),
        "-host",
        str(device_csv),
        "-s",
        str(ntp_server),
        "-o",
        str(outdir),
        "-v",
    ]
    proc = subprocess.run(
        cmd,
        cwd=str(LEGACY_ROOT),
        capture_output=True,
        text=False,
        timeout=timeout,
        check=False,
    )

    result_file = _latest_csv_file(outdir, "ntp_result_*.csv")
    rows = _read_csv(result_file) if result_file else []

    stdout_text = _decode_bytes(proc.stdout)
    stderr_text = _decode_bytes(proc.stderr)
    trace = _clean_trace(stdout_text + ("\n" + stderr_text if stderr_text else ""))
    return rows, trace


def map_audit_rows_to_results(devices: list[dict], rows: list[dict], trace: str) -> list[dict]:
    now = datetime.now().isoformat(timespec="seconds")
    rows_by_host = {}
    for r in rows:
        host = _pick(r, "host", "ip", "device_ip", "管理IP")
        if host:
            rows_by_host[str(host).strip()] = r

    results = []
    for d in devices:
        host = str(d.get("ip", "")).strip()
        row = rows_by_host.get(host)
        if not row:
            results.append(
                {
                    "device_ip": host,
                    "device_name": d.get("name", ""),
                    "status": "failed",
                    "message": f"巡检脚本未返回该设备结果。trace: {_clean_trace(trace, 260)}",
                    "start_time": now,
                    "end_time": datetime.now().isoformat(timespec="seconds"),
                }
            )
            continue

        overall = _pick(row, "overall", "设备健康总评", "总评", default="FAILED").upper()
        cpu = _pick(row, "cpu", "CPU", default="-")
        mem = _pick(row, "mem", "MEM", "memory", default="-")
        ntp = _pick(row, "ntp", "NTP", default="-")
        alerts = _pick(row, "alert_items", "alerts", "异常项", default="-")

        is_success = overall in {"OK", "WARNING", "CRITICAL", "PASS", "SUCCESS"}
        msg = f"总评={overall}; CPU={cpu}; 内存={mem}; NTP={ntp}; 告警={alerts}"
        results.append(
            {
                "device_ip": host,
                "device_name": d.get("name", ""),
                "status": "success" if is_success else "failed",
                "message": msg,
                "start_time": now,
                "end_time": datetime.now().isoformat(timespec="seconds"),
            }
        )

    return results


def map_ntp_rows_to_results(devices: list[dict], rows: list[dict], trace: str) -> list[dict]:
    now = datetime.now().isoformat(timespec="seconds")
    rows_by_host = {}
    for r in rows:
        host = _pick(r, "host", "ip", "device_ip", "管理IP")
        if host:
            rows_by_host[str(host).strip()] = r

    results = []
    for d in devices:
        host = str(d.get("ip", "")).strip()
        row = rows_by_host.get(host)
        if not row:
            results.append(
                {
                    "device_ip": host,
                    "device_name": d.get("name", ""),
                    "status": "failed",
                    "message": f"NTP脚本未返回该设备结果。trace: {_clean_trace(trace, 260)}",
                    "start_time": now,
                    "end_time": datetime.now().isoformat(timespec="seconds"),
                }
            )
            continue

        status_text = _pick(row, "status", "状态", default="FAILED").upper()
        desc = _pick(row, "message", "说明", default="-")
        is_success = status_text in {"OK", "CHANGED", "SKIPPED", "SUCCESS"}
        msg = f"状态={status_text}; 说明={desc}"
        results.append(
            {
                "device_ip": host,
                "device_name": d.get("name", ""),
                "status": "success" if is_success else "failed",
                "message": msg,
                "start_time": now,
                "end_time": datetime.now().isoformat(timespec="seconds"),
            }
        )

    return results

