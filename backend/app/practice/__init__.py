from fastapi import APIRouter

from ._internal import answers, closing, evidence_panel
from ._internal.too_long import validation_error

router = APIRouter()
router.include_router(answers.router)
router.include_router(closing.router)
router.include_router(evidence_panel.router)

__all__ = ["router", "validation_error"]
