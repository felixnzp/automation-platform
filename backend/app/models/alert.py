from sqlalchemy import Column, Integer, String

from app.database.database import Base


class AlertEvent(Base):
    __tablename__ = "alerts"

    id = Column(Integer, primary_key=True, index=True)
    source_type = Column(String, nullable=False)
    source_id = Column(String, default="")
    source_name = Column(String, nullable=False)
    source_ip = Column(String, default="")
    metric_type = Column(String, nullable=False)
    severity = Column(String, nullable=False, default="INFO")
    status = Column(String, nullable=False, default="NEW")
    title = Column(String, nullable=False)
    message = Column(String, default="")
    current_value = Column(String, default="")
    threshold_value = Column(String, default="")
    dedupe_key = Column(String, nullable=False, index=True)
    first_triggered_at = Column(String, default="")
    last_triggered_at = Column(String, default="")
    acknowledged_at = Column(String, default="")
    acknowledged_by = Column(String, default="")
    recovered_at = Column(String, default="")
    closed_at = Column(String, default="")
    notify_channels = Column(String, default="")
    notify_result = Column(String, default="")
    occurrence_count = Column(Integer, default=1)


class AlertRuleState(Base):
    __tablename__ = "alert_rule_states"

    id = Column(Integer, primary_key=True, index=True)
    dedupe_key = Column(String, nullable=False, unique=True, index=True)
    source_type = Column(String, nullable=False)
    source_id = Column(String, default="")
    source_name = Column(String, nullable=False)
    source_ip = Column(String, default="")
    metric_type = Column(String, nullable=False)
    severity = Column(String, nullable=False, default="INFO")
    current_value = Column(String, default="")
    threshold_value = Column(String, default="")
    last_message = Column(String, default="")
    consecutive_hits = Column(Integer, default=0)
    active_alert_id = Column(Integer, default=0)
    last_seen_at = Column(String, default="")
    state = Column(String, default="idle")
