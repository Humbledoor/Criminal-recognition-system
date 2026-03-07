"""
Criminal record management API routes.
"""
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional
from database.database import get_db
from database.models import CriminalRecord, Person, AuditLog
from auth.auth import get_current_user, require_role

router = APIRouter(prefix="/api/records", tags=["Criminal Records"])


class RecordCreate(BaseModel):
    person_id: int
    crime_type: str
    crime_description: Optional[str] = None
    case_number: Optional[str] = None
    date_of_offense: Optional[str] = None
    arrest_date: Optional[str] = None
    conviction_status: Optional[str] = None
    sentence_details: Optional[str] = None
    law_enforcement_agency: Optional[str] = None
    court_name: Optional[str] = None
    officer_notes: Optional[str] = None
    # Fields to update on the person
    update_record_status: Optional[str] = None
    update_risk_level: Optional[str] = None


class RecordUpdate(BaseModel):
    crime_type: Optional[str] = None
    crime_description: Optional[str] = None
    case_number: Optional[str] = None
    date_of_offense: Optional[str] = None
    arrest_date: Optional[str] = None
    conviction_status: Optional[str] = None
    sentence_details: Optional[str] = None
    law_enforcement_agency: Optional[str] = None
    court_name: Optional[str] = None
    officer_notes: Optional[str] = None


@router.get("")
def list_records(
    person_id: int = None,
    skip: int = 0,
    limit: int = 50,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    query = db.query(CriminalRecord)
    if person_id:
        query = query.filter(CriminalRecord.person_id == person_id)
    total = query.count()
    records = query.order_by(CriminalRecord.last_updated.desc()).offset(skip).limit(limit).all()
    return {
        "total": total,
        "records": [_record_to_dict(r) for r in records],
    }


@router.get("/{record_id}")
def get_record(record_id: int, current_user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    record = db.query(CriminalRecord).filter(CriminalRecord.id == record_id).first()
    if not record:
        raise HTTPException(status_code=404, detail="Record not found")
    return _record_to_dict(record)


@router.post("")
def create_record(
    data: RecordCreate,
    current_user: dict = Depends(require_role("admin", "officer")),
    db: Session = Depends(get_db),
):
    # Verify person exists
    person = db.query(Person).filter(Person.id == data.person_id).first()
    if not person:
        raise HTTPException(status_code=404, detail="Person not found")

    record = CriminalRecord(
        person_id=data.person_id,
        crime_type=data.crime_type,
        crime_description=data.crime_description,
        case_number=data.case_number,
        date_of_offense=data.date_of_offense,
        arrest_date=data.arrest_date,
        conviction_status=data.conviction_status,
        sentence_details=data.sentence_details,
        law_enforcement_agency=data.law_enforcement_agency,
        court_name=data.court_name,
        officer_notes=data.officer_notes,
    )
    db.add(record)

    # Update person status if specified
    if data.update_record_status:
        person.record_status = data.update_record_status
    if data.update_risk_level:
        person.risk_level = data.update_risk_level
    person.updated_at = datetime.utcnow()

    # Audit log
    db.add(AuditLog(
        officer_id=current_user.get("officer_id"),
        action_type="Add",
        person_id=data.person_id,
        details=f"Added criminal record: {data.crime_type} (Case: {data.case_number})",
    ))

    db.commit()
    db.refresh(record)
    return _record_to_dict(record)


@router.put("/{record_id}")
def update_record(
    record_id: int,
    data: RecordUpdate,
    current_user: dict = Depends(require_role("admin", "officer")),
    db: Session = Depends(get_db),
):
    record = db.query(CriminalRecord).filter(CriminalRecord.id == record_id).first()
    if not record:
        raise HTTPException(status_code=404, detail="Record not found")

    for field, value in data.model_dump(exclude_unset=True).items():
        if value is not None:
            setattr(record, field, value)
    record.last_updated = datetime.utcnow()

    db.add(AuditLog(
        officer_id=current_user.get("officer_id"),
        action_type="Update",
        person_id=record.person_id,
        details=f"Updated record #{record_id}: {record.crime_type}",
    ))

    db.commit()
    return _record_to_dict(record)


def _record_to_dict(r: CriminalRecord) -> dict:
    return {
        "id": r.id,
        "person_id": r.person_id,
        "crime_type": r.crime_type,
        "crime_description": r.crime_description,
        "case_number": r.case_number,
        "date_of_offense": r.date_of_offense,
        "arrest_date": r.arrest_date,
        "conviction_status": r.conviction_status,
        "sentence_details": r.sentence_details,
        "law_enforcement_agency": r.law_enforcement_agency,
        "court_name": r.court_name,
        "officer_notes": r.officer_notes,
        "last_updated": r.last_updated.isoformat() if r.last_updated else None,
    }
