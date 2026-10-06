"""Computer-vision card grading: CNN model with heuristic fallback.

Primary: a trained MobileNetV2 multi-head model (see grading/model.py) that
predicts centering, corners, edges, and surface subscores from a card photo.

Fallback: if the trained model checkpoint is not found (e.g., first boot before
training runs), the legacy heuristic pipeline produces scores via classical image
analysis. The heuristic is retained in `_heuristic_grade()` and uses only
Pillow + NumPy.

The public contract (VisionGrade dataclass, grade_image() signature, vision_to_dict())
is unchanged regardless of which backend runs.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
from typing import TYPE_CHECKING, Any, Optional

import numpy as np
from PIL import Image, ImageFilter, ImageOps

# torch / torchvision are an OPTIONAL dependency (the `vision` extra). The module
# must import cleanly without them so the API runs on memory-constrained hosts
# (e.g. Render free tier). When torch is absent, grade_image() transparently
# falls back to the heuristic scorer below. See grading/model.py.
if TYPE_CHECKING:
    from pokequant.grading.model import CardGradeNet

logger = logging.getLogger(__name__)

Image.MAX_IMAGE_PIXELS = 20_000_000


def _torch_available() -> bool:
    """True if torch + torchvision + the model module can be imported."""
    try:
        import torch  # noqa: F401
        import torchvision  # noqa: F401

        return True
    except Exception:
        return False


# ---------------------------------------------------------------------------
# Public data contract (unchanged)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Subgrade:
    name: str
    score: float  # 1-10, PSA-like
    notes: str


@dataclass(frozen=True)
class VisionGrade:
    predicted_grade: float
    centering: Subgrade
    corners: Subgrade
    edges: Subgrade
    surface: Subgrade
    method: str
    disclaimer: str


_DISCLAIMER_MODEL = (
    "CNN-based pre-grade from a photo. Not a PSA grade. Lighting, glare, crop, "
    "and camera quality affect accuracy. Use as a guide for submission decisions."
)

_DISCLAIMER_HEURISTIC = (
    "Heuristic photo analysis, not a PSA grade. Lighting, glare, crop, and camera "
    "quality dominate. Use it to guess whether a copy is closer to a 8, 9, or 10."
)


# ---------------------------------------------------------------------------
# CNN inference
# ---------------------------------------------------------------------------

# Module-level model cache (loaded once, reused across requests).
_cached_model: Optional["CardGradeNet"] = None
_model_loaded: bool = False


def _get_artifact_dir() -> Path:
    """Resolve artifact directory from settings (lazy import to avoid circular deps)."""
    from pokequant.core.config import get_settings
    return Path(get_settings().artifact_dir)


def _get_model() -> Optional["CardGradeNet"]:
    """Load the trained model (cached singleton). Returns None if unavailable.

    Returns None when torch is not installed (the `vision` extra was skipped) or
    when no trained checkpoint exists — in both cases callers fall back to the
    heuristic scorer.
    """
    global _cached_model, _model_loaded
    if _model_loaded:
        return _cached_model
    _model_loaded = True

    if not _torch_available():
        logger.info("torch not installed; using heuristic grader (install the 'vision' extra for the CNN).")
        _cached_model = None
        return None

    from pokequant.grading.model import load_model

    artifact_dir = _get_artifact_dir()
    _cached_model = load_model(artifact_dir)
    if _cached_model is not None:
        logger.info("Loaded trained card-grading CNN from %s", artifact_dir / "vision")
    else:
        logger.info("No trained grading model found; using heuristic fallback.")
    return _cached_model


def _note_for_subscore(name: str, score: float) -> str:
    """Generate a short descriptive note for a CNN-predicted subscore."""
    if score >= 9.5:
        quality = "Excellent"
    elif score >= 8.8:
        quality = "Very good"
    elif score >= 8.0:
        quality = "Good"
    elif score >= 7.0:
        quality = "Fair"
    else:
        quality = "Below average"

    descriptions = {
        "centering": f"{quality} centering detected.",
        "corners": f"{quality} corner condition.",
        "edges": f"{quality} edge condition.",
        "surface": f"{quality} surface condition.",
    }
    return descriptions.get(name, f"{quality}.")


def _cnn_grade(front_bytes: bytes, back_bytes: Optional[bytes] = None) -> VisionGrade:
    """Grade a card image using the trained CNN model."""
    import torch

    from pokequant.grading.model import SUBGRADE_NAMES, get_inference_transform

    model = _get_model()
    assert model is not None  # Caller checks availability first.

    transform = get_inference_transform()
    device = next(model.parameters()).device

    # Process front image.
    front_img = _load_rgb(front_bytes)
    front_tensor = transform(front_img).unsqueeze(0).to(device)  # type: ignore[union-attr]

    with torch.no_grad():
        preds = model(front_tensor)

    subscores: dict[str, float] = {}
    for name in SUBGRADE_NAMES:
        subscores[name] = round(float(preds[name].item()), 2)
    predicted_grade = round(float(preds["predicted_grade"].item()), 2)

    # If back is provided, grade it and take minimum per-subscore.
    if back_bytes:
        back_img = _load_rgb(back_bytes)
        back_tensor = transform(back_img).unsqueeze(0).to(device)  # type: ignore[union-attr]
        with torch.no_grad():
            back_preds = model(back_tensor)
        for name in SUBGRADE_NAMES:
            back_score = float(back_preds[name].item())
            subscores[name] = round(min(subscores[name], back_score), 2)
        back_grade = float(back_preds["predicted_grade"].item())
        predicted_grade = round(min(predicted_grade, back_grade), 2)

    centering = Subgrade("centering", subscores["centering"],
                         _note_for_subscore("centering", subscores["centering"]))
    corners = Subgrade("corners", subscores["corners"],
                       _note_for_subscore("corners", subscores["corners"]))
    edges = Subgrade("edges", subscores["edges"],
                     _note_for_subscore("edges", subscores["edges"]))
    surface = Subgrade("surface", subscores["surface"],
                       _note_for_subscore("surface", subscores["surface"]))

    return VisionGrade(
        predicted_grade=predicted_grade,
        centering=centering,
        corners=corners,
        edges=edges,
        surface=surface,
        method="cnn_v1",
        disclaimer=_DISCLAIMER_MODEL,
    )


# ---------------------------------------------------------------------------
# Heuristic fallback (legacy v0 — retained for environments without a model)
# ---------------------------------------------------------------------------


def _load_rgb(data: bytes) -> Image.Image:
    opened = Image.open(BytesIO(data))
    transposed = ImageOps.exif_transpose(opened)
    rgb: Image.Image = (transposed or opened).convert("RGB")
    rgb.thumbnail((900, 900), Image.Resampling.LANCZOS)
    return rgb


def _to_gray(img: Image.Image) -> np.ndarray:
    arr = np.asarray(img.convert("L"), dtype=np.float32)
    return arr


def _content_bbox(gray: np.ndarray) -> tuple[int, int, int, int]:
    """Tight bbox of the card if it sits on a dark/white scanner background."""
    h, w = gray.shape
    med = float(np.median(gray))
    if med < 80:
        mask = gray > (med + 25)
    else:
        mask = gray < (med + 40)
        if mask.mean() > 0.97:
            return 0, 0, w, h
        mask = gray > max(18.0, med * 0.35)
    rows = np.where(mask.any(axis=1))[0]
    cols = np.where(mask.any(axis=0))[0]
    if rows.size < 10 or cols.size < 10:
        return 0, 0, w, h
    y0, y1 = int(rows[0]), int(rows[-1]) + 1
    x0, x1 = int(cols[0]), int(cols[-1]) + 1
    if (y1 - y0) < h * 0.4 or (x1 - x0) < w * 0.4:
        return 0, 0, w, h
    return x0, y0, x0 + (x1 - x0), y0 + (y1 - y0)


def _border_widths(gray: np.ndarray) -> tuple[float, float, float, float]:
    """Estimate L/R/T/B border widths as a fraction of the card size."""
    h, w = gray.shape
    blur = np.asarray(
        Image.fromarray(gray.astype(np.uint8)).filter(ImageFilter.GaussianBlur(radius=1.5)),
        dtype=np.float32,
    )

    def depth(vec: np.ndarray, length: int) -> float:
        n = min(length, vec.size - 2)
        if n < 8:
            return 0.04 * length
        d = np.abs(np.diff(vec[:n]))
        start = max(3, n // 30)
        thresh = max(8.0, float(np.median(d) + 1.5 * np.std(d)))
        hits = np.where(d[start:] > thresh)[0]
        if hits.size == 0:
            return 0.05 * length
        return float(start + int(hits[0]))

    left = depth(blur.mean(axis=0), w)
    right = depth(blur.mean(axis=0)[::-1], w)
    top = depth(blur.mean(axis=1), h)
    bottom = depth(blur.mean(axis=1)[::-1], h)
    return left / w, right / w, top / h, bottom / h


def _ratio_score(a: float, b: float) -> tuple[float, str]:
    """Map a pair of border fractions to a 1-10 centering subgrade."""
    s = a + b
    if s <= 1e-6:
        return 8.0, "Could not measure inner frame; assumed decent centering."
    left_share = a / s
    dev = abs(left_share - 0.5)

    def _lr_label(ls: float) -> str:
        left_pct = round(ls * 100)
        right_pct = round((1 - ls) * 100)
        return f"{left_pct}/{right_pct}"

    label = _lr_label(left_share)
    if dev <= 0.04:
        score = 10.0 - (dev / 0.04) * 0.4
        return float(np.clip(score, 9.6, 10.0)), f"Centering {label} (tight)."
    if dev <= 0.10:
        score = 9.5 - (dev - 0.04) / 0.06 * 1.3
        return float(np.clip(score, 8.2, 9.5)), f"Centering {label}."
    if dev <= 0.16:
        score = 8.0 - (dev - 0.10) / 0.06 * 1.2
        return float(np.clip(score, 6.5, 8.0)), f"Off-center {label}."
    return 6.2, f"Heavily off-center {label}."


def _whitening_fraction(region: np.ndarray, thresh: float = 225.0) -> float:
    if region.size == 0:
        return 0.0
    return float((region >= thresh).mean())


def _corners_and_edges(gray: np.ndarray) -> tuple[Subgrade, Subgrade]:
    h, w = gray.shape
    cw, ch = max(8, w // 8), max(8, h // 8)
    corners = [
        gray[:ch, :cw],
        gray[:ch, -cw:],
        gray[-ch:, :cw],
        gray[-ch:, -cw:],
    ]
    c_white = float(np.mean([_whitening_fraction(c) for c in corners]))
    ew, eh = max(4, w // 22), max(4, h // 22)
    edges = [
        gray[ch:-ch, :ew],
        gray[ch:-ch, -ew:],
        gray[:eh, cw:-cw],
        gray[-eh:, cw:-cw],
    ]
    e_white = float(np.mean([_whitening_fraction(e) for e in edges if e.size]))

    def wear_score(frac: float, kind: str) -> Subgrade:
        if frac < 0.04:
            return Subgrade(kind, 9.7, "Minimal whitening visible in the photo.")
        if frac < 0.10:
            return Subgrade(kind, 9.1, "Light whitening — likely a 9 if the photo is honest.")
        if frac < 0.18:
            return Subgrade(kind, 8.2, "Noticeable whitening; probably not a 10.")
        if frac < 0.30:
            return Subgrade(kind, 7.2, "Heavy whitening along this region.")
        return Subgrade(kind, 6.2, "Severe wear/whitening in the photo.")

    return wear_score(c_white, "corners"), wear_score(e_white, "edges")


def _surface_score(gray: np.ndarray) -> Subgrade:
    h, w = gray.shape
    y0, y1 = int(h * 0.18), int(h * 0.82)
    x0, x1 = int(w * 0.18), int(w * 0.82)
    interior = gray[y0:y1, x0:x1]
    if interior.size < 100:
        return Subgrade("surface", 8.5, "Not enough interior pixels to judge surface.")
    blur = np.asarray(
        Image.fromarray(interior.astype(np.uint8)).filter(ImageFilter.GaussianBlur(radius=2)),
        dtype=np.float32,
    )
    residual = interior - blur
    hf = float(np.std(residual))
    contrast = float(np.std(interior))
    glare = float((interior > 248).mean())
    if glare > 0.08:
        return Subgrade(
            "surface",
            8.0,
            "Hotspots/glare in the photo — reshoot under even light for a fairer read.",
        )
    if hf < 6 and contrast > 12:
        return Subgrade("surface", 9.6, "Clean interior at photo resolution.")
    if hf < 11:
        return Subgrade("surface", 9.0, "Mild texture/noise; surface looks mostly clean.")
    if hf < 18:
        return Subgrade("surface", 8.1, "Visible speckling or print texture.")
    return Subgrade("surface", 7.0, "Busy surface (scratches, dust, or harsh texture).")


def _heuristic_grade(front_bytes: bytes, back_bytes: Optional[bytes] = None) -> VisionGrade:
    """Legacy heuristic grading (Pillow + NumPy, no trained model)."""
    front = _load_rgb(front_bytes)
    gray = _to_gray(front)
    x0, y0, x1, y1 = _content_bbox(gray)
    card = gray[y0:y1, x0:x1]
    left, right, top, bottom = _border_widths(card)
    lr_score, lr_note = _ratio_score(left, right)
    tb_score, tb_note = _ratio_score(top, bottom)
    centering_val = min(lr_score, tb_score)
    centering = Subgrade(
        "centering",
        round(centering_val, 2),
        f"L/R: {lr_note} T/B: {tb_note}",
    )
    corners, edges = _corners_and_edges(card)
    surface = _surface_score(card)

    predicted = (
        0.22 * centering.score + 0.26 * corners.score + 0.20 * edges.score + 0.32 * surface.score
    )
    if back_bytes:
        back_grade = _heuristic_grade(back_bytes, None)
        predicted = min(predicted, back_grade.predicted_grade)
        surface = Subgrade(
            "surface",
            round(min(surface.score, back_grade.surface.score), 2),
            surface.notes + " Back also inspected.",
        )

    return VisionGrade(
        predicted_grade=round(float(np.clip(predicted, 6.0, 10.0)), 2),
        centering=centering,
        corners=corners,
        edges=edges,
        surface=surface,
        method="heuristic_v0",
        disclaimer=_DISCLAIMER_HEURISTIC,
    )


# ---------------------------------------------------------------------------
# Public API (contract preserved)
# ---------------------------------------------------------------------------


def grade_image(front_bytes: bytes, back_bytes: Optional[bytes] = None) -> VisionGrade:
    """Grade a card photo and return PSA-style subscores.

    Uses the trained CNN if available; falls back to the heuristic otherwise.
    The return type and structure are identical in both cases.
    """
    model = _get_model()
    if model is not None:
        try:
            return _cnn_grade(front_bytes, back_bytes)
        except Exception:
            logger.warning("CNN inference failed; falling back to heuristic.", exc_info=True)
    return _heuristic_grade(front_bytes, back_bytes)


def reload_model() -> None:
    """Force-reload the model from disk (e.g., after training completes)."""
    global _cached_model, _model_loaded
    _model_loaded = False
    _cached_model = None
    _get_model()


def vision_to_dict(grade: VisionGrade) -> dict[str, object]:
    def sub(s: Subgrade) -> dict[str, object]:
        return {"name": s.name, "score": s.score, "notes": s.notes}

    return {
        "predicted_grade": grade.predicted_grade,
        "centering": sub(grade.centering),
        "corners": sub(grade.corners),
        "edges": sub(grade.edges),
        "surface": sub(grade.surface),
        "method": grade.method,
        "disclaimer": grade.disclaimer,
    }
