from datetime import timedelta

from sqlalchemy.orm import Session

from app.config import settings
from app.database import SessionLocal
from app.models import Log, Metric
from app.utils import utcnow


def cleanup_expired(db: Session, now=None) -> dict[str, int]:
    current = now or utcnow()
    metrics_cutoff = current - timedelta(days=settings.metrics_retention_days)
    logs_cutoff = current - timedelta(days=settings.logs_retention_days)
    metrics_deleted = (
        db.query(Metric).filter(Metric.timestamp < metrics_cutoff).delete(synchronize_session=False)
    )
    logs_deleted = (
        db.query(Log).filter(Log.timestamp < logs_cutoff).delete(synchronize_session=False)
    )
    db.commit()
    return {"metrics_deleted": metrics_deleted, "logs_deleted": logs_deleted}


def run_cleanup_once() -> dict[str, int]:
    db = SessionLocal()
    try:
        return cleanup_expired(db)
    finally:
        db.close()
