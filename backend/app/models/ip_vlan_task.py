from sqlalchemy import Column, Integer, String, Text

from app.database.database import Base


class IpVlanChangeLog(Base):
    __tablename__ = "ip_vlan_change_logs"

    id = Column(Integer, primary_key=True, index=True)
    operator = Column(String, default="")
    target_ip = Column(String, nullable=False)
    target_mac = Column(String, default="")
    core_switch = Column(String, default="")
    access_switch = Column(String, default="")
    interface_name = Column(String, default="")
    port_type = Column(String, default="")
    port_status = Column(String, default="")
    port_description = Column(String, default="")
    old_vlan = Column(String, default="")
    new_vlan = Column(String, default="")
    status = Column(String, default="failed")
    message = Column(Text, default="")
    commands = Column(Text, default="")
    verify_result = Column(Text, default="")
    execute_time = Column(String, nullable=False)
