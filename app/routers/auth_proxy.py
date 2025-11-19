from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import OAuth2PasswordRequestForm
from httpx import AsyncClient
from app.config import settings
from structlog import get_logger
from app.dependencies.auth import oauth2_scheme

# Normalize base and paths based on .env
_um_base = settings.USER_MANAGEMENT_URL.rstrip("/")
_has_v1 = _um_base.endswith("/api/v1")
_login_path = "/auth/login" if _has_v1 else "/api/v1/auth/login"
_change_pw_path = "/auth/change-password" if _has_v1 else "/api/v1/auth/change-password"

logger = get_logger()
router = APIRouter()

@router.post("/auth/login")
async def proxy_auth_login(form_data: OAuth2PasswordRequestForm = Depends()):
    # Many services expect JSON {"email": ..., "password": ...}
    json_body = {
        "email": form_data.username,
        "password": form_data.password,
    }
    try:
        async with AsyncClient(timeout=15.0) as client:
            # Attempt JSON first
            resp = await client.post(
                f"{_um_base}{_login_path}", json=json_body
            )
            logger.info(
                "Auth proxy upstream response",
                upstream=f"{_um_base}{_login_path}",
                status_code=resp.status_code,
            )
            # If upstream rejects JSON (common when expecting form-encoded or different field names)
            # If 422 complaining about missing username/password, retry JSON with those field names
            if resp.status_code == 422:
                alt_json = {"username": form_data.username, "password": form_data.password}
                resp = await client.post(f"{_um_base}{_login_path}", json=alt_json)
                logger.info(
                    "Auth proxy retried with JSON username/password",
                    upstream=f"{_um_base}{_login_path}",
                    status_code=resp.status_code,
                )

            # If still failing or upstream rejects JSON content type, retry with form data
            if resp.status_code in (400, 401, 415, 422):
                form_payload = {
                    "username": form_data.username,
                    "password": form_data.password,
                    "grant_type": form_data.grant_type or "password",
                }
                resp = await client.post(
                    f"{_um_base}{_login_path}", data=form_payload,
                    headers={"Content-Type": "application/x-www-form-urlencoded"}
                )
                logger.info(
                    "Auth proxy retried with form-encoded",
                    upstream=f"{_um_base}{_login_path}",
                    status_code=resp.status_code,
                )
        # Pass through JSON on success
        if 200 <= resp.status_code < 300:
            # Some services return tokens as plain text or different structure
            try:
                return resp.json()
            except Exception:
                return {"access_token": resp.text, "token_type": "bearer"}
        # Try to surface upstream JSON error if present
        try:
            err = resp.json()
        except Exception:
            err = {"detail": resp.text or "Upstream error"}
        logger.warning(
            "Auth proxy upstream error",
            upstream=f"{_um_base}{_login_path}",
            status_code=resp.status_code,
            error=err,
        )
        raise HTTPException(status_code=resp.status_code, detail=err)
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Auth proxy exception", error=str(e))
        raise HTTPException(status_code=502, detail=f"Auth proxy error: {e}")

@router.post("/auth/change-password")
async def proxy_change_password(old_password: str, new_password: str, token: str = Depends(oauth2_scheme)):
    """Proxy for admin change password.
    Tries forwarding as query params first (per upstream docs),
    then retries as JSON if upstream returns 400/422.
    Requires Authorization Bearer token from the caller.
    """
    headers = {"Authorization": f"Bearer {token}"}
    try:
        async with AsyncClient(timeout=15.0) as client:
            # Attempt with query params
            resp = await client.post(
                f"{_um_base}{_change_pw_path}", params={
                    "old_password": old_password,
                    "new_password": new_password,
                }, headers=headers
            )
            logger.info(
                "Change-password upstream response",
                upstream=f"{_um_base}{_change_pw_path}",
                status_code=resp.status_code,
            )
            if resp.status_code in (400, 422):
                # Retry with JSON body
                resp = await client.post(
                    f"{_um_base}{_change_pw_path}", json={
                        "old_password": old_password,
                        "new_password": new_password,
                    }, headers=headers
                )
                logger.info(
                    "Change-password retried with JSON",
                    upstream=f"{_um_base}{_change_pw_path}",
                    status_code=resp.status_code,
                )
        if 200 <= resp.status_code < 300:
            try:
                return resp.json()
            except Exception:
                return {"message": resp.text or "password changed"}
        try:
            err = resp.json()
        except Exception:
            err = {"detail": resp.text or "Upstream error"}
        logger.warning(
            "Change-password upstream error",
            upstream=f"{_um_base}{_change_pw_path}",
            status_code=resp.status_code,
            error=err,
        )
        raise HTTPException(status_code=resp.status_code, detail=err)
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Change-password proxy exception", error=str(e))
        raise HTTPException(status_code=502, detail=f"Auth proxy error: {e}")
