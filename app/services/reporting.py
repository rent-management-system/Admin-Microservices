from httpx import AsyncClient
from app.config import settings
from structlog import get_logger
from redis.asyncio import Redis
import pandas as pd
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Table
import io
import json # Added import for json

logger = get_logger()

async def generate_user_report(lang: str = "en"):
    redis = Redis.from_url(settings.REDIS_URL)
    cache_key = f"report:users:{lang}"
    cached = await redis.get(cache_key)
    if cached:
        return json.loads(cached)

    async with AsyncClient() as client:
        response = await client.get(
            f"{settings.USER_MANAGEMENT_URL}/api/v1/users",
            headers={"Authorization": f"Bearer {settings.USER_TOKEN}"}
        )
        users = response.json()

    df = pd.DataFrame(users)
    report = {
        "total_users": len(df),
        "new_users_month": len(df[df["created_at"].str.contains("2025-11")]),
        "active_users": len(df[df["is_active"] == True]),
        "title": "የተጠቃሚ መረጃ ሪፖርት" if lang == "am" else "User Report"
    }
    await redis.setex(cache_key, 3600, json.dumps(report))
    return report

async def export_report(report_type: str, lang: str = "en"):
    # The prompt provided `globals()[f"generate_{report_type}_report"](lang)`
    # which is not ideal. For now, I'll use a conditional check.
    report_data = {}
    if report_type == "users":
        report_data = await generate_user_report(lang)
    # Add other report types here as they are implemented

    if report_type == "users":
        df = pd.DataFrame([report_data])
        if lang == "am":
            df.columns = ["ጠቅላላ ተጠቃሚዎች", "አዲስ ተጠቃሚዎች", "ንቁ ተጠቃሚዎች", "ርዕስ"]
        csv_buffer = io.StringIO()
        df.to_csv(csv_buffer, index=False)
        async with AsyncClient() as client:
            response = await client.post(
                f"{settings.SUPABASE_URL}/storage/v1/object/reports/{report_type}_{lang}.csv",
                content=csv_buffer.getvalue(),
                headers={"Authorization": f"Bearer {settings.SUPABASE_KEY}"}
            )
            response.raise_for_status() # Ensure to raise for bad responses
            return response.json()["url"]
    # PDF export (example)
    pdf_buffer = io.BytesIO()
    doc = SimpleDocTemplate(pdf_buffer, pagesize=A4)
    # Assuming report_data is a dictionary for PDF, convert to list of lists for Table
    data_for_table = [[key, value] for key, value in report_data.items()]
    table = Table(data_for_table)
    doc.build([table])
    async with AsyncClient() as client:
        response = await client.post(
            f"{settings.SUPABASE_URL}/storage/v1/object/reports/{report_type}_{lang}.pdf",
            content=pdf_buffer.getvalue(),
            headers={"Authorization": f"Bearer {settings.SUPABASE_KEY}"}
        )
        response.raise_for_status() # Ensure to raise for bad responses
        return response.json()["url"]
