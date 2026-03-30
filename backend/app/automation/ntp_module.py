from __future__ import annotations

from app.automation.script_runner import map_ntp_rows_to_results, run_ntp_script


# Keep the unified interface: run(devices, params)
def run(devices, params):
    if not devices:
        return []

    rows, trace = run_ntp_script(devices, params or {})
    return map_ntp_rows_to_results(devices, rows, trace)