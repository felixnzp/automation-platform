from __future__ import annotations

from app.automation.script_runner import map_audit_rows_to_results, run_audit_script


# Keep the unified interface: run(devices, params)
def run(devices, params):
    if not devices:
        return []

    rows, trace = run_audit_script(devices, params or {})
    return map_audit_rows_to_results(devices, rows, trace)