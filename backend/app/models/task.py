from sqlalchemy import Column, ForeignKey, Integer, String
from sqlalchemy.orm import relationship

from app.database.database import Base


class Task(Base):
    __tablename__ = "tasks"

    id = Column(Integer, primary_key=True, index=True)
    task_type = Column(String, nullable=False)
    start_time = Column(String, nullable=False)
    end_time = Column(String, default="")
    status = Column(String, default="running")
    total = Column(Integer, default=0)
    success = Column(Integer, default=0)
    failed = Column(Integer, default=0)

    results = relationship("TaskResult", back_populates="task", cascade="all, delete-orphan")


class TaskResult(Base):
    __tablename__ = "task_results"

    id = Column(Integer, primary_key=True, index=True)
    task_id = Column(Integer, ForeignKey("tasks.id"), nullable=False)
    device_ip = Column(String, nullable=False)
    device_name = Column(String, nullable=False)
    status = Column(String, nullable=False)
    message = Column(String, default="")
    start_time = Column(String, default="")
    end_time = Column(String, default="")

    task = relationship("Task", back_populates="results")
