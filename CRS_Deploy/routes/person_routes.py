"""
Person management API routes.
"""
import os
import uuid
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from sqlalchemy.orm import Session
from database.database import get_db
from database.models import Person, AuditLog, CriminalRecord
from database.encryption import encrypt_embedding
from auth.auth import get_current_user, require_role
from face_pipeline.embedder import extract_embedding
from PIL import Image
import io

router = APIRouter(prefix="/api/persons", tags=["Persons"])

UPLOAD_DIR = os.path.join(os.path.dirname(__file__), "..", "data", "uploads")


@router.get("")
def list_persons(
    skip: int = 0,
    limit: int = 50,
    status: str = None,
    risk: str = None,
    search: str = None,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    query = db.query(Person)
    if status:
        query = query.filter(Person.record_status == status)
    if risk:
        query = query.filter(Person.risk_level == risk)
    if search:
        query = query.filter(Person.full_name.ilike(f"%{search}%"))
    total = query.count()
    persons = query.order_by(Person.updated_at.desc()).offset(skip).limit(limit).all()
    return {
        "total": total,
        "persons": [_person_to_dict(p) for p in persons]
    }


@router.get("/{person_id}")
def get_person(person_id: int, current_user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    person = db.query(Person).filter(Person.id == person_id).first()
    if not person:
        raise HTTPException(status_code=404, detail="Person not found")
    result = _person_to_dict(person)
    result["criminal_records"] = [
        {
            "id": r.id,
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
        for r in person.criminal_records
    ]
    return result


@router.post("")
async def create_person(
    full_name: str = Form(...),
    date_of_birth: str = Form(None),
    gender: str = Form(None),
    nationality: str = Form(None),
    address: str = Form(None),
    government_id_number: str = Form(None),
    record_status: str = Form("Clean"),
    risk_level: str = Form("Low"),
    photos: list[UploadFile] = File(None),
    current_user: dict = Depends(require_role("admin", "officer")),
    db: Session = Depends(get_db),
):
    person = Person(
        full_name=full_name,
        date_of_birth=date_of_birth,
        gender=gender,
        nationality=nationality,
        address=address,
        government_id_number=government_id_number,
        record_status=record_status,
        risk_level=risk_level,
    )

    # Handle multi-photo upload and embedding generation
    # More photos = more robust face matching (like phone face lock)
    if photos:
        from face_pipeline.embedder import extract_multi_embedding
        os.makedirs(UPLOAD_DIR, exist_ok=True)
        images_for_embedding = []

        for i, photo in enumerate(photos):
            if not photo.filename:
                continue
            ext = photo.filename.split(".")[-1] if "." in photo.filename else "jpg"
            filename = f"{uuid.uuid4()}.{ext}"
            filepath = os.path.join(UPLOAD_DIR, filename)

            contents = await photo.read()
            with open(filepath, "wb") as f:
                f.write(contents)

            # Use first photo as the primary image
            if i == 0:
                person.image_path = f"/data/uploads/{filename}"

            # Collect PIL images for multi-embedding
            try:
                img = Image.open(io.BytesIO(contents)).convert("RGB")
                images_for_embedding.append(img)
            except Exception:
                pass

        # Generate averaged embedding from ALL uploaded photos
        if images_for_embedding:
            try:
                embedding = extract_multi_embedding(images_for_embedding)
                if embedding:
                    person.face_embedding_encrypted = encrypt_embedding(embedding)
                    print(f"[PERSON] Generated robust embedding from {len(images_for_embedding)} photo(s) for {full_name}")
            except Exception as e:
                print(f"[PERSON] Embedding extraction failed: {e}")

    db.add(person)
    db.flush()

    # Log action
    photo_count = len(photos) if photos else 0
    db.add(AuditLog(
        officer_id=current_user.get("officer_id"),
        action_type="Add",
        person_id=person.id,
        details=f"Added person: {full_name} ({photo_count} photos)",
    ))
    db.commit()
    db.refresh(person)

    return _person_to_dict(person)


@router.put("/{person_id}")
async def update_person(
    person_id: int,
    full_name: str = Form(None),
    date_of_birth: str = Form(None),
    gender: str = Form(None),
    nationality: str = Form(None),
    address: str = Form(None),
    government_id_number: str = Form(None),
    record_status: str = Form(None),
    risk_level: str = Form(None),
    current_user: dict = Depends(require_role("admin", "officer")),
    db: Session = Depends(get_db),
):
    person = db.query(Person).filter(Person.id == person_id).first()
    if not person:
        raise HTTPException(status_code=404, detail="Person not found")

    if full_name is not None: person.full_name = full_name
    if date_of_birth is not None: person.date_of_birth = date_of_birth
    if gender is not None: person.gender = gender
    if nationality is not None: person.nationality = nationality
    if address is not None: person.address = address
    if government_id_number is not None: person.government_id_number = government_id_number
    if record_status is not None: person.record_status = record_status
    if risk_level is not None: person.risk_level = risk_level
    person.updated_at = datetime.utcnow()

    db.add(AuditLog(
        officer_id=current_user.get("officer_id"),
        action_type="Update",
        person_id=person.id,
        details=f"Updated person: {person.full_name}",
    ))
    db.commit()

    return _person_to_dict(person)


@router.delete("/{person_id}")
def delete_person(
    person_id: int,
    current_user: dict = Depends(require_role("admin")),
    db: Session = Depends(get_db),
):
    person = db.query(Person).filter(Person.id == person_id).first()
    if not person:
        raise HTTPException(status_code=404, detail="Person not found")

    db.add(AuditLog(
        officer_id=current_user.get("officer_id"),
        action_type="Delete",
        person_id=person.id,
        details=f"Deleted person: {person.full_name}",
    ))

    db.delete(person)
    db.commit()
    return {"message": "Person deleted"}


from pydantic import BaseModel
from typing import List

class BulkDeleteRequest(BaseModel):
    person_ids: List[int]

@router.post("/bulk-delete")
def bulk_delete_persons(
    request: BulkDeleteRequest,
    current_user: dict = Depends(require_role("admin", "officer")),
    db: Session = Depends(get_db),
):
    """Delete multiple persons by their IDs."""
    person_ids = request.person_ids
    if not person_ids:
        raise HTTPException(status_code=400, detail="No person IDs provided")

    deleted = 0
    names = []
    for pid in person_ids:
        person = db.query(Person).filter(Person.id == pid).first()
        if person:
            names.append(person.full_name)

            # Delete associated criminal records first
            db.query(CriminalRecord).filter(CriminalRecord.person_id == pid).delete()

            # Delete photo file if exists
            if person.image_path:
                try:
                    photo_path = os.path.join(os.path.dirname(__file__), "..", person.image_path.lstrip("/"))
                    if os.path.exists(photo_path):
                        os.remove(photo_path)
                except Exception:
                    pass

            # Audit log
            db.add(AuditLog(
                officer_id=current_user.get("officer_id"),
                action_type="Delete",
                person_id=person.id,
                details=f"Bulk deleted person: {person.full_name}",
            ))

            db.delete(person)
            deleted += 1

    db.commit()
    return {
        "message": f"{deleted} person(s) deleted successfully",
        "deleted_count": deleted,
        "deleted_names": names,
    }


def _person_to_dict(p: Person) -> dict:
    return {
        "id": p.id,
        "full_name": p.full_name,
        "date_of_birth": p.date_of_birth,
        "gender": p.gender,
        "nationality": p.nationality,
        "address": p.address,
        "government_id_number": p.government_id_number,
        "record_status": p.record_status,
        "risk_level": p.risk_level,
        "image_path": p.image_path,
        "has_embedding": p.face_embedding_encrypted is not None,
        "created_at": p.created_at.isoformat() if p.created_at else None,
        "updated_at": p.updated_at.isoformat() if p.updated_at else None,
    }
