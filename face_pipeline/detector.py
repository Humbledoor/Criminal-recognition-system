"""
Face detection with quality checks.
Uses Pillow-based analysis — no heavy ML dependency required.
"""
import io
import numpy as np
from PIL import Image, ImageFilter


def validate_image(image_bytes: bytes) -> dict:
    """
    Validate uploaded image quality.
    Returns dict with 'valid', 'message', and 'image' (PIL Image).
    """
    try:
        img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
    except Exception:
        return {"valid": False, "message": "Invalid image file", "image": None}

    w, h = img.size

    # Minimum resolution check
    if w < 50 or h < 50:
        return {"valid": False, "message": f"Image too small ({w}x{h}). Minimum 50x50 required.", "image": None}

    # Maximum size — resize if too large
    max_dim = 1920
    if w > max_dim or h > max_dim:
        img.thumbnail((max_dim, max_dim), Image.LANCZOS)

    # Blur detection using Pillow edge filter (no scipy needed)
    gray = img.convert("L")
    edges = gray.filter(ImageFilter.FIND_EDGES)
    edge_arr = np.array(edges, dtype=np.float64)
    edge_variance = edge_arr.var()

    # Very lenient blur threshold — only reject extremely blurry images
    if edge_variance < 10:
        return {
            "valid": False,
            "message": f"Image too blurry (edge variance={edge_variance:.1f}). Please provide a sharper image.",
            "image": None
        }

    return {"valid": True, "message": "Image quality OK", "image": img}


def preprocess_image(img: Image.Image, target_size=(160, 160)) -> Image.Image:
    """Preprocess face image: resize, normalize."""
    img = img.resize(target_size, Image.LANCZOS)
    return img
