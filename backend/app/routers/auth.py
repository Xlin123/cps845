from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.auth import (
    SESSION_COOKIE,
    SESSION_LIFETIME,
    client_address,
    get_current_profile,
    is_throttled,
    landing_for,
    record_failure,
)
from app.clock import Clock, get_clock
from app.db import get_db
from app.models import Profile, SignInSession
from app.security import hash_token, new_session_token, verify_password

router = APIRouter(prefix="/api/auth", tags=["auth"])


class SignInRequest(BaseModel):
    email: str
    password: str


class SignInResponse(BaseModel):
    role: str
    landing: str


@router.post("/sign-in", response_model=SignInResponse)
def sign_in(
    body: SignInRequest,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
    clock: Clock = Depends(get_clock),
) -> SignInResponse:
    address = client_address(request)
    if is_throttled(db, kind="sign_in", address=address, clock=clock):
        raise HTTPException(status_code=429, detail="Too many attempts. Try again later")

    profile = db.query(Profile).filter_by(email=body.email.lower()).first()
    if profile is None or not verify_password(body.password, profile.password_hash):
        record_failure(db, kind="sign_in", address=address, clock=clock)
        raise HTTPException(status_code=401, detail="Email address or password is wrong")

    if profile.confirmed_at is None:
        raise HTTPException(status_code=401, detail="Confirm your email address before signing in")

    token = new_session_token()
    now = clock.now()
    db.add(
        SignInSession(
            profile_id=profile.id,
            token_hash=hash_token(token),
            created_at=now,
            expires_at=now + SESSION_LIFETIME,
        )
    )
    db.commit()

    response.set_cookie(
        SESSION_COOKIE,
        token,
        httponly=True,
        samesite="strict",
        secure=request.url.scheme == "https",
        max_age=int(SESSION_LIFETIME.total_seconds()),
    )
    return SignInResponse(role=profile.role.value, landing=landing_for(profile.role))


@router.post("/sign-out", status_code=204)
def sign_out(
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
) -> None:
    token = request.cookies.get(SESSION_COOKIE)
    if token:
        db.query(SignInSession).filter_by(token_hash=hash_token(token)).delete()
        db.commit()
    response.delete_cookie(SESSION_COOKIE)


@router.get("/me", response_model=SignInResponse)
def me(profile: Profile = Depends(get_current_profile)) -> SignInResponse:
    return SignInResponse(role=profile.role.value, landing=landing_for(profile.role))
