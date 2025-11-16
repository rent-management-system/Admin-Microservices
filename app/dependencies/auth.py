from fastapi import HTTPException, Depends
from fastapi.security import OAuth2PasswordBearer
from jose import jwt, JWTError
from app.config import settings
from httpx import AsyncClient

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/login")

async def get_current_admin(token: str = Depends(oauth2_scheme)):
    try:
        payload = jwt.decode(token, settings.JWT_SECRET, algorithms=["HS256"])
        async with AsyncClient() as client:
            response = await client.post(
                f"{settings.USER_MANAGEMENT_URL}/api/v1/auth/verify",
                json={"token": token}
            )
            if response.status_code != 200:
                raise HTTPException(status_code=401, detail="Invalid token")
            user = response.json()
            if user["role"] != "Admin":
                raise HTTPException(status_code=403, detail="Admin role required")
            return user
    except JWTError:
        raise HTTPException(status_code=401, detail="Could not validate credentials")
