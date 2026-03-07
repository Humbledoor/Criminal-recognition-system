"""
Audit log viewing API routes.
"""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from database.database import get_db
from database.models import AuditLog, Officer, Person
from auth.auth import get_current_user, require_role

router = APIRouter(prefix="/api/audit", tags=["Audit Log"])


@router.get("")
def list_audit_logs(
    skip: int = 0,
    limit: int = 100,
    action_type: str = None,
    officer_id: int = None,
    current_user: dict = Depends(require_role("admin", "officer")),
    db: Session = Depends(get_db),
):
    query = db.query(AuditLog)
    if action_type:
        query = query.filter(AuditLog.action_type == action_type)
    if officer_id:
        query = query.filter(AuditLog.officer_id == officer_id)

    total = query.count()
    logs = query.order_by(AuditLog.timestamp.desc()).offset(skip).limit(limit).all()

    results = []
    for log in logs:
        officer = db.query(Officer).filter(Officer.id == log.officer_id).first()
        person = db.query(Person).filter(Person.id == log.person_id).first() if log.person_id else None
        results.append({
            "id": log.id,
            "officer_id": log.officer_id,
            "officer_name": officer.full_name if officer else "Unknown",
            "officer_badge": officer.badge_number if officer else None,
            "action_type": log.action_type,
            "timestamp": log.timestamp.isoformat() if log.timestamp else None,
            "person_id": log.person_id,
            "person_name": person.full_name if person else None,
            "details": log.details,
            "ip_address": log.ip_address,
        })

    return {"total": total, "logs": results}
