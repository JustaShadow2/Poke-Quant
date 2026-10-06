"""Card search + grading ROI + vision pre-grade."""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, File, Form, Query, UploadFile

from pokequant.api.deps import get_grading_service
from pokequant.api.schemas import (
    CardSearchResponse,
    CardSummary,
    CardValuationResponse,
    VisionGradeResponse,
    VisionROIResponse,
)
from pokequant.core.errors import ValidationAppError
from pokequant.grading.roi import DEFAULT_GRADING_FEE, DEFAULT_SHIPPING
from pokequant.grading.service import GradingService, card_to_dict

router = APIRouter()


@router.get("/cards/search", response_model=CardSearchResponse)
def search_cards(
    q: str = Query(..., min_length=2, max_length=80),
    limit: int = Query(default=12, ge=1, le=30),
    service: GradingService = Depends(get_grading_service),
) -> CardSearchResponse:
    cards = service.search(q, page_size=limit)
    items = [CardSummary.model_validate(card_to_dict(c)) for c in cards]
    return CardSearchResponse(query=q, count=len(items), items=items)


@router.get("/cards/{card_id}", response_model=CardValuationResponse)
def get_card_valuation(
    card_id: str,
    grading_fee: float = Query(default=DEFAULT_GRADING_FEE, ge=0, le=500),
    shipping: float = Query(default=DEFAULT_SHIPPING, ge=0, le=200),
    service: GradingService = Depends(get_grading_service),
) -> CardValuationResponse:
    payload = service.priced_card(card_id, grading_fee_usd=grading_fee, shipping_usd=shipping)
    return CardValuationResponse.model_validate(payload)


@router.post("/cards/vision-grade", response_model=VisionGradeResponse)
async def vision_grade(
    front: UploadFile = File(...),
    back: Optional[UploadFile] = File(None),
    service: GradingService = Depends(get_grading_service),
) -> VisionGradeResponse:
    front_bytes = await front.read()
    if len(front_bytes) < 64:
        raise ValidationAppError("Front image is empty or too small.")
    if len(front_bytes) > 8_000_000:
        raise ValidationAppError("Front image exceeds 8 MB.")
    back_bytes: Optional[bytes] = None
    if back is not None:
        back_bytes = await back.read()
        if back_bytes and len(back_bytes) > 8_000_000:
            raise ValidationAppError("Back image exceeds 8 MB.")
    payload = service.vision_grade(front_bytes, back_bytes or None)
    return VisionGradeResponse.model_validate(payload)


@router.post("/cards/{card_id}/grade-roi", response_model=VisionROIResponse)
async def vision_conditioned_roi(
    card_id: str,
    front: UploadFile = File(...),
    back: Optional[UploadFile] = File(None),
    grading_fee: float = Form(default=DEFAULT_GRADING_FEE),
    shipping: float = Form(default=DEFAULT_SHIPPING),
    service: GradingService = Depends(get_grading_service),
) -> VisionROIResponse:
    front_bytes = await front.read()
    if len(front_bytes) < 64:
        raise ValidationAppError("Front image is empty or too small.")
    back_bytes = await back.read() if back is not None else None
    vision = service.vision_grade(front_bytes, back_bytes or None)
    predicted = float(vision["predicted_grade"])  # type: ignore[arg-type]
    priced = service.priced_card(
        card_id,
        grading_fee_usd=grading_fee,
        shipping_usd=shipping,
        predicted_grade=predicted,
    )
    return VisionROIResponse.model_validate({"vision": vision, **priced})
