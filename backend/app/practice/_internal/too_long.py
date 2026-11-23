from fastapi import Request, Response
from fastapi.exception_handlers import request_validation_exception_handler
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from .models import TOO_LONG


async def validation_error(request: Request, error: RequestValidationError) -> Response:
    sentences = [e["msg"] for e in error.errors() if e["type"] == TOO_LONG]
    if not sentences:
        return await request_validation_exception_handler(request, error)
    return JSONResponse({"detail": sentences[0]}, status_code=422)
