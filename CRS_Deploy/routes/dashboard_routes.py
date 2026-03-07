"""
Dashboard statistics API routes.
"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func
from database.database import get_db
from database.models import Person, CriminalRecord, AuditLog, Officer
from auth.auth import get_current_user

router = APIRouter(prefix="/api/dashboard", tags=["Dashboard"])


@router.get("/stats")
def get_dashboard_stats(
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    total_persons = db.query(Person).count()
    total_records = db.query(CriminalRecord).count()
    total_searches = db.query(AuditLog).filter(AuditLog.action_type == "Search").count()
    total_officers = db.query(Officer).filter(Officer.is_active == 1).count()

    # Status distribution
    status_dist = {}
    for status, count in db.query(Person.record_status, func.count(Person.id)).group_by(Person.record_status).all():
        status_dist[status or "Unknown"] = count

    # Risk level distribution
    risk_dist = {}
    for risk, count in db.query(Person.risk_level, func.count(Person.id)).group_by(Person.risk_level).all():
        risk_dist[risk or "Unknown"] = count

    # Recent activity (last 20)
    recent_logs = db.query(AuditLog).order_by(AuditLog.timestamp.desc()).limit(20).all()
    recent_activity = []
    for log in recent_logs:
        officer = db.query(Officer).filter(Officer.id == log.officer_id).first()
        recent_activity.append({
            "id": log.id,
            "action_type": log.action_type,
            "officer_name": officer.full_name if officer else "Unknown",
            "details": log.details,
            "timestamp": log.timestamp.isoformat() if log.timestamp else None,
            "person_id": log.person_id,
        })

    # Crime type distribution
    crime_dist = {}
    for ctype, count in db.query(CriminalRecord.crime_type, func.count(CriminalRecord.id)).group_by(CriminalRecord.crime_type).all():
        crime_dist[ctype or "Unknown"] = count

    return {
        "total_persons": total_persons,
        "total_records": total_records,
        "total_searches": total_searches,
        "total_officers": total_officers,
        "status_distribution": status_dist,
        "risk_distribution": risk_dist,
        "crime_distribution": crime_dist,
        "recent_activity": recent_activity,
    }
