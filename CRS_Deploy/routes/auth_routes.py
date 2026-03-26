"""
Authentication API routes.
"""
from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import OAuth2PasswordRequestForm
from google.cloud import firestore
from database.database import get_db, _next_id
from database.models import ActionType
from auth.auth import verify_password, create_access_token, get_current_user
from pydantic import BaseModel
from datetime import datetime

router = APIRouter(prefix="/api/auth", tags=["Authentication"])


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    officer: dict


@router.post("/login", response_model=TokenResponse)
def login(form_data: OAuth2PasswordRequestForm = Depends(), db: firestore.Client = Depends(get_db)):
    officers_ref = db.collection("officers")
    query = officers_ref.where("username", "==", form_data.username).limit(1)
    results = list(query.stream())
    
    if not results:
        raise HTTPException(status_code=401, detail="Invalid credentials")
    
    officer = results[0].to_dict()
    
    if not verify_password(form_data.password, officer.get("hashed_password")):
        raise HTTPException(status_code=401, detail="Invalid credentials")
        
    if not officer.get("is_active"):
        raise HTTPException(status_code=403, detail="Account deactivated")

    token = create_access_token(data={
        "sub": officer.get("username"),
        "officer_id": officer.get("id"),
        "role": officer.get("role"),
        "full_name": officer.get("full_name"),
    })

    # Log login action
    audit_id = _next_id("audit_log")
    db.collection("audit_log").document(str(audit_id)).set({
        "id": audit_id,
        "officer_id": officer.get("id"),
        "action_type": ActionType.LOGIN.value,
        "details": f"Officer {officer.get('username')} logged in",
        "timestamp": datetime.utcnow().isoformat(),
        "person_id": None,
        "ip_address": None
    })

    return TokenResponse(
        access_token=token,
        officer={
            "id": officer.get("id"),
            "username": officer.get("username"),
            "full_name": officer.get("full_name"),
            "role": officer.get("role"),
            "badge_number": officer.get("badge_number"),
            "department": officer.get("department"),
        }
    )


@router.get("/me")
def get_me(current_user: dict = Depends(get_current_user), db: firestore.Client = Depends(get_db)):
    officers_ref = db.collection("officers")
    query = officers_ref.where("username", "==", current_user["sub"]).limit(1)
    results = list(query.stream())
    
    if not results:
        raise HTTPException(status_code=404, detail="Officer not found")
        
    officer = results[0].to_dict()
    
    return {
        "id": officer.get("id"),
        "username": officer.get("username"),
        "full_name": officer.get("full_name"),
        "role": officer.get("role"),
        "badge_number": officer.get("badge_number"),
        "department": officer.get("department"),
    }
