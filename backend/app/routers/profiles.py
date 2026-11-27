from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.auth import client_address, is_throttled, record_failure
from app.clock import Clock, get_clock
from app.db import get_db
from app.profiles import (
    CoachCodeWrongError,
    ConfirmationInvalidError,
    ProfileValidationError,
    confirm,
    sign_up,
)

router = APIRouter(prefix="/api/profiles", tags=["profiles"])

CHECK_EMAIL_MESSAGE = "Check your email for a confirmation link"


class SignUpRequest(BaseModel):
    name: str
    email: str
    phone: str | None = None
    password: str
    coach_code: str | None = None


class MessageResponse(BaseModel):
    message: str


class ConfirmRequest(BaseModel):
    token: str


@router.post("/sign-up", response_model=MessageResponse)
def sign_up_endpoint(
    body: SignUpRequest,
    request: Request,
    db: Session = Depends(get_db),
    clock: Clock = Depends(get_clock),
) -> MessageResponse:
    address = client_address(request)
    if body.coach_code is not None and is_throttled(
        db, kind="coach_code", address=address, clock=clock
    ):
        raise HTTPException(status_code=429, detail="Too many attempts. Try again later")

    try:
        sign_up(
            db,
            name=body.name,
            email=body.email,
            phone=body.phone,
            password=body.password,
            coach_code=body.coach_code,
            clock=clock,
        )
    except ProfileValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except CoachCodeWrongError as exc:
        record_failure(db, kind="coach_code", address=address, clock=clock)
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    return MessageResponse(message=CHECK_EMAIL_MESSAGE)


@router.post("/confirm", response_model=MessageResponse)
def confirm_endpoint(
    body: ConfirmRequest,
    db: Session = Depends(get_db),
    clock: Clock = Depends(get_clock),
) -> MessageResponse:
    try:
        confirm(db, token=body.token, clock=clock)
    except ConfirmationInvalidError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    return MessageResponse(message="Your profile is confirmed")
