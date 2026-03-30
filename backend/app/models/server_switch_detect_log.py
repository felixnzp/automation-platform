from sqlalchemy import Column, Integer, String, Text

from app.database.database import Base


class ServerSwitchDetectLog(Base):
    """
    Per-server switch detection log entry.

    We keep this as a simple append-only table so operators can troubleshoot why a server
    was (not) mapped to Server-SW1/Server-SW2.
    """

    __tablename__ = "server_switch_detect_logs"

    id = Column(Integer, primary_key=True, index=True)
    task_id = Column(Integer, default=0)  # 0 means triggered outside task center (should be rare)
    server_id = Column(Integer, nullable=False, index=True)
    server_name = Column(String, nullable=False, default="")
    server_ip = Column(String, nullable=False, default="")

    detect_status = Column(String, nullable=False, default="failed")  # success/failed/manual_confirm
    detect_message = Column(String, nullable=False, default="")

    access_switch_name = Column(String, nullable=False, default="")
    core_uplink_port = Column(String, nullable=False, default="")
    switch_downlink_port = Column(String, nullable=False, default="")

    arp_raw = Column(Text, nullable=False, default="")
    lldp_raw = Column(Text, nullable=False, default="")

    trigger_type = Column(String, nullable=False, default="manual")  # create/manual/schedule/batch
    created_at = Column(String, nullable=False, default="")

