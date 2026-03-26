"""
Audit log viewing API routes.
Adapted for Firebase Firestore.
"""
from fastapi import APIRouter, Depends
from google.cloud import firestore
from database.database import get_db
from auth.auth import get_current_user, require_role

router = APIRouter(prefix="/api/audit", tags=["Audit Log"])


@router.get("")
def list_audit_logs(
    skip: int = 0,
    limit: int = 100,
    action_type: str = None,
    officer_id: int = None,
    current_user: dict = Depends(require_role("admin", "officer")),
    db: firestore.Client = Depends(get_db),
):
    logs_ref = db.collection("audit_log")
    query = logs_ref
    
    if action_type:
        query = query.where("action_type", "==", action_type)
    if officer_id:
        query = query.where("officer_id", "==", officer_id)

    query = query.order_by("timestamp", direction=firestore.Query.DESCENDING)
    docs = list(query.stream())
    
    total = len(docs)
    paginated_docs = docs[skip : skip + limit]

    results = []
    
    # Simple caching to avoid excessive DB calls
    officers_cache = {}
    persons_cache = {}

    for doc in paginated_docs:
        log = doc.to_dict()
        o_id = log.get("officer_id")
        p_id = log.get("person_id")
        
        # Resolve officer
        if o_id not in officers_cache:
            o_doc = db.collection("officers").document(str(o_id)).get()
            officers_cache[o_id] = o_doc.to_dict() if o_doc.exists else None
            
        officer = officers_cache[o_id]
        
        # Resolve person
        person = None
        if p_id:
            if p_id not in persons_cache:
                p_doc = db.collection("persons").document(str(p_id)).get()
                persons_cache[p_id] = p_doc.to_dict() if p_doc.exists else None
            person = persons_cache[p_id]

        results.append({
            "id": log.get("id"),
            "officer_id": o_id,
            "officer_name": officer.get("full_name") if officer else "Unknown",
            "officer_badge": officer.get("badge_number") if officer else None,
            "action_type": log.get("action_type"),
            "timestamp": log.get("timestamp"),
            "person_id": p_id,
            "person_name": person.get("full_name") if person else None,
            "details": log.get("details"),
            "ip_address": log.get("ip_address"),
        })

    return {"total": total, "logs": results}
