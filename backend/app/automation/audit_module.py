from datetime import datetime


# Simulated audit module. Replace with Netmiko logic later.
def run(devices, params):
    results = []
    for device in devices:
        now = datetime.now().isoformat(timespec="seconds")
        results.append(
            {
                "device_ip": device["ip"],
                "device_name": device["name"],
                "status": "success",
                "message": "audit completed",
                "start_time": now,
                "end_time": datetime.now().isoformat(timespec="seconds"),
            }
        )
    return results
