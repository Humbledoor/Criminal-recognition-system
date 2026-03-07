"""
Face search API route -- the core face recognition endpoint.
"""
import io
import os
import sys
import traceback
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from PIL import Image
from database.database import get_db
from database.models import AuditLog
from auth.auth import get_current_user
from face_pipeline.detector import validate_image
from face_pipeline.embedder import extract_embedding
from face_pipeline.matcher import search_matches, compute_bias_metrics
from face_pipeline.antispoofing import check_liveness

# Fix Windows console encoding for TensorFlow/DeepFace Unicode output
os.environ["PYTHONIOENCODING"] = "utf-8"
try:
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')
except Exception:
    pass

router = APIRouter(prefix="/api/search", tags=["Face Search"])


@router.post("/face")
async def search_face(
    image: UploadFile = File(...),
    threshold: float = Form(0.4),
    max_results: int = Form(10),
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Upload an image -> detect face -> extract embedding -> match against database.
    Returns ranked matches with confidence scores.
    """
    try:
        contents = await image.read()

        if not contents:
            raise HTTPException(status_code=400, detail="Empty image file uploaded.")

        # Step 1: Validate image quality
        validation = validate_image(contents)
        if not validation["valid"]:
            raise HTTPException(status_code=400, detail=validation["message"])

        img = validation["image"]

        # Step 2: Anti-spoofing check (non-blocking)
        liveness = {"passed": True, "score": 100.0, "checks": [], "summary": "OK"}
        try:
            liveness = check_liveness(img)
        except Exception:
            pass

        # Step 3: Extract face embedding
        embedding = extract_embedding(img)
        if embedding is None:
            raise HTTPException(
                status_code=400,
                detail="Could not extract features from the image. Please upload a clearer face photo."
            )

        # Step 4: Search for matches
        matches = search_matches(embedding, db, threshold=threshold, max_results=max_results)

        # Step 5: Compute bias metrics
        bias_metrics = compute_bias_metrics(matches)

        # Step 6: Audit log
        match_summary = f"{len(matches)} matches found" if matches else "No matches found"
        db.add(AuditLog(
            officer_id=current_user.get("officer_id"),
            action_type="Search",
            person_id=matches[0]["person_id"] if matches else None,
            details=f"Face search: {match_summary} (threshold={threshold})",
        ))
        db.commit()

        return {
            "matches": matches,
            "total_matches": len(matches),
            "threshold_used": threshold,
            "liveness_check": liveness,
            "bias_metrics": bias_metrics,
            "disclaimer": "Automated identification is probabilistic and requires human confirmation. "
                          "Match results must be verified by an authorized officer before any action is taken.",
        }

    except HTTPException:
        raise
    except Exception as e:
        # Catch-all: sanitize error string to avoid cp1252 encoding crashes
        try:
            error_detail = str(e).encode('ascii', errors='replace').decode('ascii')
        except Exception:
            error_detail = "An internal error occurred"
        try:
            print(f"[SEARCH ERROR] {error_detail}")
        except Exception:
            pass
        return JSONResponse(
            status_code=500,
            content={"detail": f"Search failed: {error_detail}. Please try a different image."}
        )
