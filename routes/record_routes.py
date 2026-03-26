"""
Criminal record management API routes.
Adapted for Firebase Firestore.
"""
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from google.cloud import firestore
from pydantic import BaseModel
from typing import Optional
from database.database import get_db, _next_id
from database.models import ActionType
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
    db: firestore.Client = Depends(get_db),
):
    records_ref = db.collection("criminal_records")
    query = records_ref
    
    if person_id:
        query = query.where("person_id", "==", person_id)
        
    query = query.order_by("last_updated", direction=firestore.Query.DESCENDING)
    docs = list(query.stream())
    
    total = len(docs)
    paginated_docs = docs[skip : skip + limit]
    
    records = []
    for doc in paginated_docs:
        records.append(_record_to_dict(doc.to_dict()))
        
    return {
        "total": total,
        "records": records,
    }


@router.get("/{record_id}")
def get_record(record_id: int, current_user: dict = Depends(get_current_user), db: firestore.Client = Depends(get_db)):
    doc_ref = db.collection("criminal_records").document(str(record_id))
    doc = doc_ref.get()
    
    if not doc.exists:
        raise HTTPException(status_code=404, detail="Record not found")
        
    return _record_to_dict(doc.to_dict())


@router.post("")
def create_record(
    data: RecordCreate,
    current_user: dict = Depends(require_role("admin", "officer")),
    db: firestore.Client = Depends(get_db),
):
    # Verify person exists
    person_ref = db.collection("persons").document(str(data.person_id))
    person_doc = person_ref.get()
    
    if not person_doc.exists:
        raise HTTPException(status_code=404, detail="Person not found")

    record_id = _next_id("criminal_records")
    record_data = {
        "id": record_id,
        "person_id": data.person_id,
        "crime_type": data.crime_type,
        "crime_description": data.crime_description,
        "case_number": data.case_number,
        "date_of_offense": data.date_of_offense,
        "arrest_date": data.arrest_date,
        "conviction_status": data.conviction_status,
        "sentence_details": data.sentence_details,
        "law_enforcement_agency": data.law_enforcement_agency,
        "court_name": data.court_name,
        "officer_notes": data.officer_notes,
        "last_updated": datetime.utcnow().isoformat(),
    }
    
    batch = db.batch()
    
    record_ref = db.collection("criminal_records").document(str(record_id))
    batch.set(record_ref, record_data)

    # Update person status if specified
    person_updates = {}
    if data.update_record_status:
        person_updates["record_status"] = data.update_record_status
    if data.update_risk_level:
        person_updates["risk_level"] = data.update_risk_level
        
    if person_updates:
        person_updates["updated_at"] = datetime.utcnow().isoformat()
        batch.update(person_ref, person_updates)

    # Audit log
    audit_id = _next_id("audit_log")
    audit_ref = db.collection("audit_log").document(str(audit_id))
    batch.set(audit_ref, {
        "id": audit_id,
        "officer_id": current_user.get("officer_id"),
        "action_type": ActionType.ADD.value,
        "person_id": data.person_id,
        "details": f"Added criminal record: {data.crime_type} (Case: {data.case_number})",
        "timestamp": datetime.utcnow().isoformat(),
        "ip_address": None
    })

    batch.commit()
    return _record_to_dict(record_data)


@router.put("/{record_id}")
def update_record(
    record_id: int,
    data: RecordUpdate,
    current_user: dict = Depends(require_role("admin", "officer")),
    db: firestore.Client = Depends(get_db),
):
    doc_ref = db.collection("criminal_records").document(str(record_id))
    doc = doc_ref.get()
    
    if not doc.exists:
        raise HTTPException(status_code=404, detail="Record not found")

    record_data = doc.to_dict()
    updates = data.model_dump(exclude_unset=True)
    updates["last_updated"] = datetime.utcnow().isoformat()
    
    batch = db.batch()
    batch.update(doc_ref, updates)
    record_data.update(updates)

    audit_id = _next_id("audit_log")
    audit_ref = db.collection("audit_log").document(str(audit_id))
    batch.set(audit_ref, {
        "id": audit_id,
        "officer_id": current_user.get("officer_id"),
        "action_type": ActionType.UPDATE.value,
        "person_id": record_data.get("person_id"),
        "details": f"Updated record #{record_id}: {record_data.get('crime_type')}",
        "timestamp": datetime.utcnow().isoformat(),
        "ip_address": None
    })

    batch.commit()
    return _record_to_dict(record_data)


def _record_to_dict(r: dict) -> dict:
    return {
        "id": r.get("id"),
        "person_id": r.get("person_id"),
        "crime_type": r.get("crime_type"),
        "crime_description": r.get("crime_description"),
        "case_number": r.get("case_number"),
        "date_of_offense": r.get("date_of_offense"),
        "arrest_date": r.get("arrest_date"),
        "conviction_status": r.get("conviction_status"),
        "sentence_details": r.get("sentence_details"),
        "law_enforcement_agency": r.get("law_enforcement_agency"),
        "court_name": r.get("court_name"),
        "officer_notes": r.get("officer_notes"),
        "last_updated": r.get("last_updated"),
    }
