from datetime import datetime


# Simulated SNMP config module. Replace with Netmiko logic later.
def run(devices, params):
    community = params.get("community", "public")
    message = f"snmp-agent community read {community}"

    results = []
    for device in devices:
        start_time = datetime.now().isoformat(timespec="seconds")
        results.append(
            {
                "device_ip": device["ip"],
                "device_name": device["name"],
                "status": "success",
                "message": message,
                "start_time": start_time,
                "end_time": datetime.now().isoformat(timespec="seconds"),
            }
        )
    return results
