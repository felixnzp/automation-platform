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


class ScheduledTask(Base):
    __tablename__ = "scheduled_tasks"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    task_type = Column(String, nullable=False)
    target_mode = Column(String, nullable=False, default="all")
    target_group = Column(String, default="")
    target_device_ids = Column(String, default="[]")
    # JSON string for task parameters (e.g. server inspection thresholds/items).
    params = Column(String, default="{}")
    cycle_type = Column(String, nullable=False, default="daily")
    run_time = Column(String, nullable=False, default="08:00")
    cron_expr = Column(String, default="")
    enabled = Column(Integer, default=1)
    last_run_at = Column(String, default="")
    created_at = Column(String, nullable=False)
    updated_at = Column(String, nullable=False)
