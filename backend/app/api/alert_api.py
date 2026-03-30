from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.database.database import get_db
from app.services import alert_service

router = APIRouter(prefix="/api/alerts", tags=["alerts"])


class AlertBulkPayload(BaseModel):
    alert_ids: list[int] = Field(default_factory=list)
    action: str
    operator: str = "unknown"


@router.get("")
def get_alerts(
    severity: str | None = Query(default=None),
    status: str | None = Query(default=None),
    source_type: str | None = Query(default=None),
    keyword: str | None = Query(default=None),
    db: Session = Depends(get_db),
):
    return alert_service.list_alerts(db, severity=severity, status=status, source_type=source_type, keyword=keyword)


@router.post("/bulk")
def bulk_update_alerts(payload: AlertBulkPayload, db: Session = Depends(get_db)):
    try:
        return alert_service.bulk_update_status(
            db,
            payload.alert_ids,
            payload.action,
            payload.operator,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
