"""
Dashboard statistics API routes.
Adapted for Firebase Firestore.
"""
from fastapi import APIRouter, Depends
from google.cloud import firestore
from database.database import get_db
from database.models import ActionType
from auth.auth import get_current_user

router = APIRouter(prefix="/api/dashboard", tags=["Dashboard"])


@router.get("/stats")
def get_dashboard_stats(
    current_user: dict = Depends(get_current_user),
    db: firestore.Client = Depends(get_db),
):
    # Fetch all data needed for stats (Firestore doesn't support complex aggregation natively efficiently in the free tier
    # except server-side count(), since Python SDK supports it via `.count().get()` recently).
    
    # We will fetch counts using .count() to save bandwidth where supported,
    # but for group_by we have to fetch the fields.
    
    total_persons = db.collection("persons").count().get()[0][0].value
    total_records = db.collection("criminal_records").count().get()[0][0].value
    total_searches = db.collection("audit_log").where("action_type", "==", ActionType.SEARCH.value).count().get()[0][0].value
    total_officers = db.collection("officers").where("is_active", "==", 1).count().get()[0][0].value

    # Status distribution + computed stats
    status_dist = {}
    risk_dist = {}
    most_wanted = []
    active_cases = 0
    total_criminals = 0
    persons_docs = db.collection("persons").select(["full_name", "record_status", "risk_level", "address"]).stream()
    for p in persons_docs:
        data = p.to_dict()
        s = data.get("record_status") or "Unknown"
        r = data.get("risk_level") or "Unknown"
        status_dist[s] = status_dist.get(s, 0) + 1
        risk_dist[r] = risk_dist.get(r, 0) + 1

        # Count active cases (Under Investigation)
        if s == "Under Investigation":
            active_cases += 1

        # Count criminals (anyone with a record that isn't clean)
        if s in ("Convicted", "Under Investigation"):
            total_criminals += 1

        # Collect most wanted (High risk)
        if r == "High":
            most_wanted.append({
                "id": int(p.id),
                "full_name": data.get("full_name"),
                "record_status": s,
                "risk_level": r,
                "address": data.get("address") or "Unknown",
            })

    # Limit most wanted to top 5
    most_wanted = most_wanted[:5]

    # Crime type distribution
    crime_dist = {}
    records_docs = db.collection("criminal_records").select(["crime_type"]).stream()
    for r in records_docs:
        data = r.to_dict()
        c = data.get("crime_type") or "Unknown"
        crime_dist[c] = crime_dist.get(c, 0) + 1

    # Recent activity (last 20)
    recent_logs_query = db.collection("audit_log").order_by("timestamp", direction=firestore.Query.DESCENDING).limit(20)
    recent_logs = list(recent_logs_query.stream())
    
    recent_activity = []
    latest_detections = []
    officers_cache = {}
    
    for log_doc in recent_logs:
        log = log_doc.to_dict()
        o_id = log.get("officer_id")
        
        if o_id not in officers_cache:
            o_doc = db.collection("officers").document(str(o_id)).get()
            officers_cache[o_id] = o_doc.to_dict() if o_doc.exists else None
            
        officer = officers_cache[o_id]
        
        entry = {
            "id": log.get("id"),
            "action_type": log.get("action_type"),
            "officer_name": officer.get("full_name") if officer else "Unknown",
            "details": log.get("details"),
            "timestamp": log.get("timestamp"),
            "person_id": log.get("person_id"),
        }
        recent_activity.append(entry)

        # Collect latest detections (searches that found matches)
        if log.get("action_type") == ActionType.SEARCH.value and log.get("person_id"):
            latest_detections.append(entry)

    return {
        "total_persons": total_persons,
        "total_records": total_records,
        "total_searches": total_searches,
        "total_officers": total_officers,
        "total_criminals": total_criminals,
        "active_cases": active_cases,
        "most_wanted": most_wanted,
        "latest_detections": latest_detections[:5],
        "status_distribution": status_dist,
        "risk_distribution": risk_dist,
        "crime_distribution": crime_dist,
        "recent_activity": recent_activity,
    }
