from sqlalchemy import Column, DateTime, Integer, String

from app.database.database import Base


class ServerAsset(Base):
    __tablename__ = "servers"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    ip = Column(String, nullable=False, unique=True, index=True)
    hostname = Column(String, default="")
    os_name = Column(String, default="")
    server_type = Column(String, default="linux")
    access_method = Column(String, default="ssh")
    username = Column(String, nullable=False)
    password = Column(String, nullable=False)
    port = Column(Integer, default=22)
    group_name = Column(String, default="default")
    enable = Column(Integer, default=1)
    status = Column(String, default="unknown")
    last_checked_at = Column(DateTime, nullable=True)
    last_error = Column(String, default="")
    cpu_usage = Column(Integer, default=0)
    memory_usage = Column(Integer, default=0)
    disk_usage = Column(Integer, default=0)
    response_time_ms = Column(Integer, default=0)
    core_ping_status = Column(String, default="unknown")
    router_ping_status = Column(String, default="unknown")
    uplink_core_switch_name = Column(String, default="")
    uplink_core_switch_port = Column(String, default="")
    server_switch_name = Column(String, default="")
    server_switch_port = Column(String, default="")
    topology_parent_id = Column(Integer, nullable=True)
    topology_located_at = Column(DateTime, nullable=True)
    topology_locate_status = Column(String, default="failed")
    topology_locate_reason = Column(String, default="")
    topology_locate_method = Column(String, default="")
    server_mac = Column(String, default="")
