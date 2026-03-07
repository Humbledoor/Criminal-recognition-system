"""
Anti-spoofing and image quality analysis.
"""
import numpy as np
from PIL import Image


def check_liveness(img: Image.Image) -> dict:
    """
    Basic liveness / anti-spoofing checks.
    Returns dict with 'passed', 'score', 'checks'.
    """
    checks = []
    arr = np.array(img.convert("RGB"), dtype=np.float64)

    # 1. Texture analysis — real faces have more texture variation
    gray = np.mean(arr, axis=2)
    texture_score = float(gray.std())
    texture_ok = texture_score > 20
    checks.append({
        "name": "Texture Analysis",
        "passed": texture_ok,
        "score": round(texture_score, 2),
        "detail": "Checks natural skin texture variation"
    })

    # 2. Color distribution — real faces have specific color ranges
    r_mean, g_mean, b_mean = arr[:,:,0].mean(), arr[:,:,1].mean(), arr[:,:,2].mean()
    color_variance = float(np.std([r_mean, g_mean, b_mean]))
    color_ok = color_variance > 5
    checks.append({
        "name": "Color Distribution",
        "passed": color_ok,
        "score": round(color_variance, 2),
        "detail": "Validates natural color range"
    })

    # 3. Edge density — real faces have natural edges
    from PIL import ImageFilter
    edges = img.convert("L").filter(ImageFilter.FIND_EDGES)
    edge_arr = np.array(edges, dtype=np.float64)
    edge_density = float(edge_arr.mean())
    edge_ok = edge_density > 5
    checks.append({
        "name": "Edge Density",
        "passed": edge_ok,
        "score": round(edge_density, 2),
        "detail": "Detects flat/printed images"
    })

    # 4. Aspect ratio check — face images should be roughly square-ish
    w, h = img.size
    aspect = w / h if h > 0 else 0
    aspect_ok = 0.5 < aspect < 2.0
    checks.append({
        "name": "Aspect Ratio",
        "passed": aspect_ok,
        "score": round(aspect, 2),
        "detail": "Face images should have reasonable dimensions"
    })

    passed_count = sum(1 for c in checks if c["passed"])
    overall_passed = passed_count >= 3  # At least 3 of 4 checks must pass

    return {
        "passed": overall_passed,
        "score": round(passed_count / len(checks) * 100, 1),
        "checks": checks,
        "summary": f"{passed_count}/{len(checks)} checks passed"
    }
