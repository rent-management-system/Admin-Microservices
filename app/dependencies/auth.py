from fastapi import HTTPException, Depends
from fastapi.security import OAuth2PasswordBearer
from app.config import settings
from httpx import AsyncClient
from structlog import get_logger

# Build token and verify URLs robustly whether USER_MANAGEMENT_URL already includes '/api/v1' or not
_um_base = settings.USER_MANAGEMENT_URL.rstrip("/")
_has_v1 = _um_base.endswith("/api/v1")
_login_path = "/auth/login" if _has_v1 else "/api/v1/auth/login"
_verify_path = "/auth/verify" if _has_v1 else "/api/v1/auth/verify"

# Use local proxy endpoint for Swagger to avoid cross-origin/browser CORS issues
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/login")
logger = get_logger()

async def get_current_admin(token: str = Depends(oauth2_scheme)):
    """Verify bearer token with the upstream service using several common patterns.
    Accepts various response shapes and enforces that the user has Admin role.
    """
    async with AsyncClient(timeout=30.0) as client:
        # 1) Preferred: POST JSON {"token": token}
        resp = await client.post(f"{_um_base}{_verify_path}", json={"token": token})
        logger.info(
            "Verify attempt JSON",
            upstream=f"{_um_base}{_verify_path}",
            status_code=resp.status_code,
        )
        # 2) If not accepted, try form-encoded
        if resp.status_code in (400, 401, 404, 405, 415, 422):
            resp = await client.post(
                f"{_um_base}{_verify_path}",
                data={"token": token},
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
            logger.info(
                "Verify attempt form-encoded",
                upstream=f"{_um_base}{_verify_path}",
                status_code=resp.status_code,
            )
        # 3) Some services expect Authorization header and may use GET
        if resp.status_code in (400, 401, 404, 405, 415, 422):
            resp = await client.get(
                f"{_um_base}{_verify_path}",
                headers={"Authorization": f"Bearer {token}"},
            )
            logger.info(
                "Verify attempt GET Bearer",
                upstream=f"{_um_base}{_verify_path}",
                status_code=resp.status_code,
            )
        # 4) Some services accept GET with token in query
        if resp.status_code in (400, 401, 404, 405, 415, 422):
            resp = await client.get(f"{_um_base}{_verify_path}", params={"token": token})
            logger.info(
                "Verify attempt GET ?token=",
                upstream=f"{_um_base}{_verify_path}",
                status_code=resp.status_code,
            )
        # 5) Fallback query param name
        if resp.status_code in (400, 401, 404, 405, 415, 422):
            resp = await client.get(f"{_um_base}{_verify_path}", params={"access_token": token})
            logger.info(
                "Verify attempt GET ?access_token=",
                upstream=f"{_um_base}{_verify_path}",
                status_code=resp.status_code,
            )
        if resp.status_code != 200:
            # Try to capture error body for diagnostics
            try:
                err = resp.json()
            except Exception:
                err = {"detail": resp.text or "Upstream verify error"}
            logger.warning(
                "Verify failed",
                upstream=f"{_um_base}{_verify_path}",
                status_code=resp.status_code,
                error=err,
            )
            raise HTTPException(status_code=401, detail="Invalid token")
        data = resp.json() if resp.headers.get("content-type", "").startswith("application/json") else {"token": resp.text}
        # Accept either {user: {...}} or flat {...}
        user = data.get("user", data)
        # Normalize a consistent 'id' field for downstream code
        uid = user.get("id") or user.get("_id") or user.get("user_id") or user.get("sub") or user.get("uid")
        if uid is not None:
            user["id"] = uid
        role = str(user.get("role", "")).lower()
        if role != "admin":
            raise HTTPException(status_code=403, detail="Admin role required")
        return user
