"""Authentication endpoints."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request, Response, status

from alphalens.api.deps import AuthServiceDep, CurrentUserDep
from alphalens.api.rate_limit import ip_subject, rate_limit_request
from alphalens.core.config import get_settings
from alphalens.services.auth_service import AuthError, DuplicateUserError, InactiveUserError
from alphalens.schemas.user import TokenResponse, UserCreate, UserLogin, UserProfile

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=TokenResponse)
def register(
    payload: UserCreate,
    service: AuthServiceDep,
    response: Response,
    request: Request,
) -> TokenResponse:
    rate_limit_request(request, route="auth_register", subject=ip_subject(request), settings=get_settings())
    try:
        token = service.register_user(payload)
        _set_auth_cookies(response, token)
        return token
    except DuplicateUserError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc


@router.post("/login", response_model=TokenResponse)
def login(
    payload: UserLogin,
    service: AuthServiceDep,
    response: Response,
    request: Request,
) -> TokenResponse:
    rate_limit_request(request, route="auth_login", subject=ip_subject(request), settings=get_settings())
    try:
        token = service.login_user(payload)
        _set_auth_cookies(response, token)
        return token
    except InactiveUserError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(exc),
        ) from exc
    except AuthError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials.",
        ) from exc


@router.post("/refresh", response_model=TokenResponse)
def refresh(request: Request, service: AuthServiceDep) -> TokenResponse:
    refresh_token = request.cookies.get("alphalens_refresh_token")
    if not refresh_token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Session expired.")
    try:
        return service.refresh_session(refresh_token)
    except InactiveUserError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Account inactive.") from exc
    except AuthError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Session expired.") from exc


@router.post("/logout")
def logout(request: Request, response: Response, service: AuthServiceDep) -> dict[str, bool]:
    refresh_token = request.cookies.get("alphalens_refresh_token")
    if refresh_token:
        service.logout(refresh_token)
    response.delete_cookie("alphalens_refresh_token")
    response.delete_cookie("alphalens_access_token")
    return {"logged_out": True}


def _set_auth_cookies(response: Response, token: TokenResponse) -> None:
    response.set_cookie("alphalens_access_token", token.access_token, httponly=True, samesite="lax")
    if token.refresh_token:
        response.set_cookie("alphalens_refresh_token", token.refresh_token, httponly=True, samesite="lax")


@router.get("/me", response_model=UserProfile)
def me(current_user: CurrentUserDep) -> UserProfile:
    return current_user
