from datetime import datetime


# Simulated NTP config module. Replace with Netmiko logic later.
def run(devices, params):
    timezone = params.get("timezone", "BJ")
    offset = params.get("offset", "08:00:00")
    ntp_server = params.get("ntp_server", "127.0.0.1")

    cmd1 = f"clock timezone {timezone} add {offset}"
    cmd2 = f"ntp-service unicast-server {ntp_server}"

    results = []
    for device in devices:
        start_time = datetime.now().isoformat(timespec="seconds")
        results.append(
            {
                "device_ip": device["ip"],
                "device_name": device["name"],
                "status": "success",
                "message": f"applied: {cmd1}; {cmd2}",
                "start_time": start_time,
                "end_time": datetime.now().isoformat(timespec="seconds"),
            }
        )
    return results
