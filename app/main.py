from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from redis.asyncio import Redis
from app.config import settings
from app.routers import admin
from app.routers import auth_proxy
from app.routers import properties # Import the new properties router
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from app.services.admin import get_health
import json
import asyncio

app = FastAPI(title="Admin Management Microservice")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

scheduler = AsyncIOScheduler()
redis_client: Redis | None = None

async def update_health_cache():
    global redis_client
    if redis_client is None:
        redis_client = Redis.from_url(settings.REDIS_URL)
    health_status = await get_health(verbose=False)
    await redis_client.setex("cached_health_status", 300, json.dumps(health_status)) # Cache for 5 minutes

@app.on_event("startup")
async def startup_event():
    global redis_client
    redis_client = Redis.from_url(settings.REDIS_URL)
    # Run once immediately on startup
    await update_health_cache()
    # Schedule to run every 5 minutes
    scheduler.add_job(update_health_cache, "interval", minutes=5)
    scheduler.start()

@app.on_event("shutdown")
async def shutdown_event():
    scheduler.shutdown()
    if redis_client:
        await redis_client.close()

app.include_router(admin.router)
app.include_router(auth_proxy.router)
app.include_router(properties.router) # Include the new properties router

@app.get("/health")
async def root_health():
    return "ok"
