"""Google OAuth and session endpoints."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse, Response
from pydantic import BaseModel

from app.auth import get_current_user, issue_token
from app.auth.google import build_google_auth_url, exchange_code_for_profile
from app.auth.store import User, UserStore
from app.config import get_settings

router = APIRouter()


class MeResponse(BaseModel):
    id: str
    email: str
    name: str


@router.get("/google")
async def google_login() -> RedirectResponse:
    settings = get_settings()
    if not settings.google_client_id or not settings.google_client_secret:
        raise HTTPException(status_code=503, detail="Google OAuth is not configured")

    state = uuid.uuid4().hex
    url = build_google_auth_url(state, settings=settings)
    response = RedirectResponse(url=url, status_code=302)
    response.set_cookie(
        "mathbird_oauth_state",
        state,
        httponly=True,
        samesite="lax",
        max_age=600,
        path="/",
    )
    return response


@router.get("/google/callback")
async def google_callback(request: Request, code: str | None = None, state: str | None = None) -> RedirectResponse:
    settings = get_settings()
    if not settings.google_client_id or not settings.google_client_secret:
        raise HTTPException(status_code=503, detail="Google OAuth is not configured")
    if not code:
        raise HTTPException(status_code=400, detail="Missing OAuth code")

    expected_state = request.cookies.get("mathbird_oauth_state")
    if not state or not expected_state or state != expected_state:
        raise HTTPException(status_code=400, detail="Invalid OAuth state")

    profile = await exchange_code_for_profile(code, settings=settings)
    user = UserStore().upsert_google_user(
        profile["sub"],
        profile.get("email") or "",
        profile.get("name") or profile.get("email") or "User",
    )
    token = issue_token(user.id, settings=settings)

    response = RedirectResponse(url=f"{settings.frontend_url}/", status_code=302)
    response.delete_cookie("mathbird_oauth_state", path="/")
    response.set_cookie(
        settings.auth_cookie_name,
        token,
        httponly=True,
        samesite="lax",
        path="/",
        max_age=settings.auth_jwt_expiry_hours * 3600,
    )
    return response


@router.get("/me", response_model=MeResponse)
async def me(user: User = Depends(get_current_user)) -> MeResponse:
    return MeResponse(id=user.id, email=user.email, name=user.name)


@router.post("/logout")
async def logout() -> Response:
    settings = get_settings()
    response = Response(status_code=204)
    response.delete_cookie(settings.auth_cookie_name, path="/")
    return response
