from sqlalchemy.orm import Session

from app.models.device import Device


def list_devices(db: Session, keyword: str | None = None):
    query = db.query(Device)
    if keyword:
        like_pattern = f"%{keyword}%"
        query = query.filter(
            (Device.name.like(like_pattern))
            | (Device.ip.like(like_pattern))
            | (Device.group_name.like(like_pattern))
            | (Device.location.like(like_pattern))
        )
    return query.order_by(Device.id.desc()).all()


def create_device(db: Session, payload: dict):
    device = Device(**payload)
    db.add(device)
    db.commit()
    db.refresh(device)
    return device


def get_device(db: Session, device_id: int):
    return db.query(Device).filter(Device.id == device_id).first()


def update_device(db: Session, device_id: int, payload: dict):
    device = get_device(db, device_id)
    if not device:
        return None

    for key, value in payload.items():
        setattr(device, key, value)

    db.commit()
    db.refresh(device)
    return device


def delete_device(db: Session, device_id: int):
    device = get_device(db, device_id)
    if not device:
        return False

    db.delete(device)
    db.commit()
    return True


def list_devices_by_ids(db: Session, ids: list[int]):
    if not ids:
        return []
    return db.query(Device).filter(Device.id.in_(ids)).all()
