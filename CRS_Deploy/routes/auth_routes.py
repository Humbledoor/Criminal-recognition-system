"""
Authentication API routes.
"""
from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from database.database import get_db
from database.models import Officer, AuditLog
from auth.auth import verify_password, create_access_token, get_current_user
from pydantic import BaseModel
from datetime import datetime

router = APIRouter(prefix="/api/auth", tags=["Authentication"])


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    officer: dict


@router.post("/login", response_model=TokenResponse)
def login(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    officer = db.query(Officer).filter(Officer.username == form_data.username).first()
    if not officer or not verify_password(form_data.password, officer.hashed_password):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    if not officer.is_active:
        raise HTTPException(status_code=403, detail="Account deactivated")

    token = create_access_token(data={
        "sub": officer.username,
        "officer_id": officer.id,
        "role": officer.role,
        "full_name": officer.full_name,
    })

    # Log login action
    db.add(AuditLog(
        officer_id=officer.id,
        action_type="Login",
        details=f"Officer {officer.username} logged in",
    ))
    db.commit()

    return TokenResponse(
        access_token=token,
        officer={
            "id": officer.id,
            "username": officer.username,
            "full_name": officer.full_name,
            "role": officer.role,
            "badge_number": officer.badge_number,
            "department": officer.department,
        }
    )


@router.get("/me")
def get_me(current_user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    officer = db.query(Officer).filter(Officer.username == current_user["sub"]).first()
    if not officer:
        raise HTTPException(status_code=404, detail="Officer not found")
    return {
        "id": officer.id,
        "username": officer.username,
        "full_name": officer.full_name,
        "role": officer.role,
        "badge_number": officer.badge_number,
        "department": officer.department,
    }
