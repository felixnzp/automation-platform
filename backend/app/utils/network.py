import platform
import subprocess


def ping_device(ip: str, timeout_ms: int = 800) -> str:
    if not ip:
        return "offline"

    system = platform.system().lower()
    timeout_sec = max(1, int(round(timeout_ms / 1000)))

    if "windows" in system:
        command = ["ping", "-n", "1", "-w", str(timeout_ms), ip]
    else:
        command = ["ping", "-c", "1", "-W", str(timeout_sec), ip]

    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=timeout_sec + 2,
            check=False,
        )
        return "online" if result.returncode == 0 else "offline"
    except Exception:
        return "offline"
