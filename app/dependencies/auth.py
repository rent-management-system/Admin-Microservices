from fastapi import HTTPException, Depends
from fastapi.security import OAuth2PasswordBearer
from jose import jwt, JWTError
from app.config import settings
from httpx import AsyncClient

# Build token and verify URLs robustly whether USER_MANAGEMENT_URL already includes '/api/v1' or not
_um_base = settings.USER_MANAGEMENT_URL.rstrip("/")
_has_v1 = _um_base.endswith("/api/v1")
_login_path = "/auth/login" if _has_v1 else "/api/v1/auth/login"
_verify_path = "/auth/verify" if _has_v1 else "/api/v1/auth/verify"

# Use local proxy endpoint for Swagger to avoid cross-origin/browser CORS issues
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/login")

async def get_current_admin(token: str = Depends(oauth2_scheme)):
    try:
        payload = jwt.decode(token, settings.JWT_SECRET, algorithms=["HS256"])
        async with AsyncClient() as client:
            response = await client.post(
                f"{_um_base}{_verify_path}",
                json={"token": token}
            )
            if response.status_code != 200:
                raise HTTPException(status_code=401, detail="Invalid token")
            user = response.json()
            role = str(user.get("role", "")).lower()
            if role != "admin":
                raise HTTPException(status_code=403, detail="Admin role required")
            return user
    except JWTError:
        raise HTTPException(status_code=401, detail="Could not validate credentials")
