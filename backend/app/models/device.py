from sqlalchemy import Column, Integer, String

from app.database.database import Base


class Device(Base):
    __tablename__ = "devices"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    ip = Column(String, nullable=False, unique=True, index=True)
    username = Column(String, nullable=False)
    password = Column(String, nullable=False)
    port = Column(Integer, default=22)
    device_type = Column(String, default="huawei")
    group_name = Column(String, default="default")
    location = Column(String, default="unknown")
    enable = Column(Integer, default=1)
