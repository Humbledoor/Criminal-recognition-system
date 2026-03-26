"""
Person management API routes.
"""
import os
import uuid
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from google.cloud import firestore
from database.database import get_db, _next_id
from database.models import ActionType
from database.encryption import encrypt_embedding
from auth.auth import get_current_user, require_role
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
    db: firestore.Client = Depends(get_db),
):
    persons_ref = db.collection("persons")
    query = persons_ref

    if status:
        query = query.where("record_status", "==", status)
    if risk:
        query = query.where("risk_level", "==", risk)
    
    # Note: Firestore lacks built-in ILIKE wildcard text search.
    # In a full production app, use Algolia/ElasticSearch.
    # Here, we fetch all and filter in memory if 'search' is provided.
    
    # Sort by updated_at descending
    query = query.order_by("updated_at", direction=firestore.Query.DESCENDING)
    
    docs = list(query.stream())
    
    # In-memory search filter (case-insensitive substring)
    if search:
        search_lower = search.lower()
        docs = [d for d in docs if search_lower in d.to_dict().get("full_name", "").lower()]
        
    total = len(docs)
    
    # Pagination
    paginated_docs = docs[skip : skip + limit]
    
    persons = []
    for doc in paginated_docs:
        persons.append(_person_to_dict(doc.to_dict()))
        
    return {
        "total": total,
        "persons": persons
    }


@router.get("/{person_id}")
def get_person(person_id: int, current_user: dict = Depends(get_current_user), db: firestore.Client = Depends(get_db)):
    doc_ref = db.collection("persons").document(str(person_id))
    doc = doc_ref.get()
    
    if not doc.exists:
        raise HTTPException(status_code=404, detail="Person not found")
        
    person_data = doc.to_dict()
    result = _person_to_dict(person_data)
    
    # Fetch criminal records for this person
    records_ref = db.collection("criminal_records")
    records_query = records_ref.where("person_id", "==", person_id).order_by("last_updated", direction=firestore.Query.DESCENDING)
    records_docs = records_query.stream()
    
    result["criminal_records"] = [d.to_dict() for d in records_docs]
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
    db: firestore.Client = Depends(get_db),
):
    person_id = _next_id("persons")
    
    person_data = {
        "id": person_id,
        "full_name": full_name,
        "date_of_birth": date_of_birth,
        "gender": gender,
        "nationality": nationality,
        "address": address,
        "government_id_number": government_id_number,
        "record_status": record_status,
        "risk_level": risk_level,
        "face_embedding_encrypted": None,
        "image_path": None,
        "created_at": datetime.utcnow().isoformat(),
        "updated_at": datetime.utcnow().isoformat(),
    }

    # Handle multi-photo upload and embedding generation
    if photos:
        try:
            from face_pipeline.embedder import extract_multi_embedding
        except Exception:
            extract_multi_embedding = None
            
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
                person_data["image_path"] = f"/data/uploads/{filename}"

            # Collect PIL images for multi-embedding
            try:
                img = Image.open(io.BytesIO(contents)).convert("RGB")
                images_for_embedding.append(img)
            except Exception:
                pass

        # Generate averaged embedding from ALL uploaded photos
        if images_for_embedding and extract_multi_embedding:
            try:
                embedding = extract_multi_embedding(images_for_embedding)
                if embedding:
                    person_data["face_embedding_encrypted"] = encrypt_embedding(embedding)
                    print(f"[PERSON] Generated robust embedding from {len(images_for_embedding)} photo(s) for {full_name}")
            except Exception as e:
                print(f"[PERSON] Embedding extraction failed: {e}")

    db.collection("persons").document(str(person_id)).set(person_data)

    # Log action
    photo_count = len(photos) if photos else 0
    audit_id = _next_id("audit_log")
    db.collection("audit_log").document(str(audit_id)).set({
        "id": audit_id,
        "officer_id": current_user.get("officer_id"),
        "action_type": ActionType.ADD.value,
        "person_id": person_id,
        "details": f"Added person: {full_name} ({photo_count} photos)",
        "timestamp": datetime.utcnow().isoformat(),
        "ip_address": None
    })

    return _person_to_dict(person_data)


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
    db: firestore.Client = Depends(get_db),
):
    doc_ref = db.collection("persons").document(str(person_id))
    doc = doc_ref.get()
    
    if not doc.exists:
        raise HTTPException(status_code=404, detail="Person not found")

    person_data = doc.to_dict()
    updates = {}

    if full_name is not None: updates["full_name"] = full_name
    if date_of_birth is not None: updates["date_of_birth"] = date_of_birth
    if gender is not None: updates["gender"] = gender
    if nationality is not None: updates["nationality"] = nationality
    if address is not None: updates["address"] = address
    if government_id_number is not None: updates["government_id_number"] = government_id_number
    if record_status is not None: updates["record_status"] = record_status
    if risk_level is not None: updates["risk_level"] = risk_level
    
    updates["updated_at"] = datetime.utcnow().isoformat()
    
    doc_ref.update(updates)
    person_data.update(updates)

    audit_id = _next_id("audit_log")
    db.collection("audit_log").document(str(audit_id)).set({
        "id": audit_id,
        "officer_id": current_user.get("officer_id"),
        "action_type": ActionType.UPDATE.value,
        "person_id": person_id,
        "details": f"Updated person: {person_data.get('full_name')}",
        "timestamp": datetime.utcnow().isoformat(),
        "ip_address": None
    })

    return _person_to_dict(person_data)


@router.delete("/{person_id}")
def delete_person(
    person_id: int,
    current_user: dict = Depends(require_role("admin")),
    db: firestore.Client = Depends(get_db),
):
    doc_ref = db.collection("persons").document(str(person_id))
    doc = doc_ref.get()
    
    if not doc.exists:
        raise HTTPException(status_code=404, detail="Person not found")
        
    person_data = doc.to_dict()

    audit_id = _next_id("audit_log")
    db.collection("audit_log").document(str(audit_id)).set({
        "id": audit_id,
        "officer_id": current_user.get("officer_id"),
        "action_type": ActionType.DELETE.value,
        "person_id": person_id,
        "details": f"Deleted person: {person_data.get('full_name')}",
        "timestamp": datetime.utcnow().isoformat(),
        "ip_address": None
    })

    # Delete associated criminal records
    records_ref = db.collection("criminal_records")
    records_docs = records_ref.where("person_id", "==", person_id).stream()
    for r in records_docs:
        r.reference.delete()

    # Delete photo file if exists
    if person_data.get("image_path"):
        try:
            photo_path = os.path.join(os.path.dirname(__file__), "..", person_data["image_path"].lstrip("/"))
            if os.path.exists(photo_path):
                os.remove(photo_path)
        except Exception:
            pass

    doc_ref.delete()
    return {"message": "Person deleted"}


from pydantic import BaseModel
from typing import List

class BulkDeleteRequest(BaseModel):
    person_ids: List[int]

@router.post("/bulk-delete")
def bulk_delete_persons(
    request: BulkDeleteRequest,
    current_user: dict = Depends(require_role("admin", "officer")),
    db: firestore.Client = Depends(get_db),
):
    """Delete multiple persons by their IDs."""
    person_ids = request.person_ids
    if not person_ids:
        raise HTTPException(status_code=400, detail="No person IDs provided")

    deleted = 0
    names = []
    
    batch = db.batch()
    
    for pid in person_ids:
        doc_ref = db.collection("persons").document(str(pid))
        doc = doc_ref.get()
        if doc.exists:
            person_data = doc.to_dict()
            names.append(person_data.get("full_name"))

            # Delete associated criminal records
            records_docs = db.collection("criminal_records").where("person_id", "==", pid).stream()
            for r in records_docs:
                batch.delete(r.reference)

            # Delete photo file if exists
            if person_data.get("image_path"):
                try:
                    photo_path = os.path.join(os.path.dirname(__file__), "..", person_data["image_path"].lstrip("/"))
                    if os.path.exists(photo_path):
                        os.remove(photo_path)
                except Exception:
                    pass

            # Audit log
            audit_id = _next_id("audit_log")
            audit_ref = db.collection("audit_log").document(str(audit_id))
            batch.set(audit_ref, {
                "id": audit_id,
                "officer_id": current_user.get("officer_id"),
                "action_type": ActionType.DELETE.value,
                "person_id": pid,
                "details": f"Bulk deleted person: {person_data.get('full_name')}",
                "timestamp": datetime.utcnow().isoformat(),
                "ip_address": None
            })

            batch.delete(doc_ref)
            deleted += 1

    batch.commit()
    return {
        "message": f"{deleted} person(s) deleted successfully",
        "deleted_count": deleted,
        "deleted_names": names,
    }


def _person_to_dict(p: dict) -> dict:
    return {
        "id": p.get("id"),
        "full_name": p.get("full_name"),
        "date_of_birth": p.get("date_of_birth"),
        "gender": p.get("gender"),
        "nationality": p.get("nationality"),
        "address": p.get("address"),
        "government_id_number": p.get("government_id_number"),
        "record_status": p.get("record_status"),
        "risk_level": p.get("risk_level"),
        "image_path": p.get("image_path"),
        "has_embedding": p.get("face_embedding_encrypted") is not None,
        "created_at": p.get("created_at"),
        "updated_at": p.get("updated_at"),
    }
