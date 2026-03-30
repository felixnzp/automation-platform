from sqlalchemy import Column, ForeignKey, Integer, String
from sqlalchemy.orm import relationship

from app.database.database import Base


class ServerInspectionDetail(Base):
    __tablename__ = "server_inspection_details"

    id = Column(Integer, primary_key=True, index=True)
    task_id = Column(Integer, ForeignKey("tasks.id"), nullable=False, index=True)
    schedule_id = Column(Integer, nullable=True)

    server_id = Column(Integer, nullable=False)
    server_name = Column(String, nullable=False)
    server_ip = Column(String, nullable=False)

    cpu_usage = Column(Integer, nullable=True)
    memory_usage = Column(Integer, nullable=True)
    disk_usage = Column(Integer, nullable=True)

    cpu_status = Column(String, nullable=True)
    memory_status = Column(String, nullable=True)
    disk_status = Column(String, nullable=True)

    result_level = Column(String, nullable=False)  # normal/warning/critical
    result_message = Column(String, default="")
    executed_at = Column(String, nullable=False)

    task = relationship("Task")

