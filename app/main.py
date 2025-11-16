from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi_limiter import FastAPILimiter
from redis.asyncio import Redis
from app.config import settings
from app.routers import admin

app = FastAPI(title="Admin Management Microservice")
app.add_middleware(CORSMiddleware, allow_origins=["https://*.huggingface.co"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

@app.on_event("startup")
async def startup():
    redis = Redis.from_url(settings.REDIS_URL)
    await FastAPILimiter.init(redis)

app.include_router(admin.router)
