from sqlalchemy import Column, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship

from app.database.database import Base


class ConfigJob(Base):
    __tablename__ = "config_jobs"

    id = Column(Integer, primary_key=True, index=True)
    intent = Column(String, nullable=False)
    start_time = Column(String, nullable=False)
    end_time = Column(String, default="")
    status = Column(String, default="running")
    total = Column(Integer, default=0)
    success = Column(Integer, default=0)
    failed = Column(Integer, default=0)
    skipped = Column(Integer, default=0)
    params_json = Column(Text, default="{}")

    results = relationship("ConfigJobResult", back_populates="job", cascade="all, delete-orphan")


class ConfigJobResult(Base):
    __tablename__ = "config_job_results"

    id = Column(Integer, primary_key=True, index=True)
    job_id = Column(Integer, ForeignKey("config_jobs.id"), nullable=False)
    device_id = Column(Integer, nullable=False)
    device_name = Column(String, nullable=False)
    device_ip = Column(String, nullable=False)
    role = Column(String, default="")
    status = Column(String, nullable=False)
    message = Column(Text, default="")
    backup_file = Column(String, default="")
    rollback_status = Column(String, default="")
    start_time = Column(String, default="")
    end_time = Column(String, default="")
    command_preview = Column(Text, default="")
    verify_output = Column(Text, default="")

    job = relationship("ConfigJob", back_populates="results")
