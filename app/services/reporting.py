from httpx import AsyncClient
from app.config import settings
from structlog import get_logger
from redis.asyncio import Redis
import pandas as pd
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Table
import io
import json 
from datetime import datetime, timezone

logger = get_logger()

# Normalize service bases
_um_base = settings.USER_MANAGEMENT_URL.rstrip("/")
_um_has_v1 = _um_base.endswith("/api/v1")
_um_prefix = "" if _um_has_v1 else "/api/v1"

_supabase_base = settings.SUPABASE_URL.rstrip("/")

async def generate_user_report(lang: str = "en", token: str | None = None):
    redis = Redis.from_url(settings.REDIS_URL)
    cache_key = f"report:users:{lang}"
    cached = await redis.get(cache_key)
    if cached:
        return json.loads(cached)

    async with AsyncClient(timeout=15.0) as client:
        # Prefer admin/users to ensure we get full dataset; fallback to /users if admin path is unavailable
        url_admin = f"{_um_base}{_um_prefix}/admin/users"
        url_public = f"{_um_base}{_um_prefix}/users"
        bearer = token or settings.USER_TOKEN
        headers = {"Authorization": f"Bearer {bearer}"}
        response = await client.get(url_admin, headers=headers, params={"skip": 0, "limit": 1000})
        if response.status_code == 404:
            response = await client.get(url_public, headers=headers, params={"skip": 0, "limit": 1000})
        if 200 <= response.status_code < 300:
            try:
                payload = response.json()
            except Exception:
                payload = []
        else:
            logger.warning(
                "User report upstream fetch failed",
                status_code=response.status_code,
                url=response.request.url if response.request else url_admin,
            )
            payload = []

    # Normalize upstream payload into a list of user dicts
    if isinstance(payload, list):
        users = payload
    elif isinstance(payload, dict):
        # Common wrappers
        if isinstance(payload.get("data"), list):
            users = payload["data"]
        elif isinstance(payload.get("results"), list):
            users = payload["results"]
        else:
            # Single user object or unexpected format
            users = [payload]
    else:
        users = []

    # Normalize fields used in reporting
    norm_users = []
    for u in users:
        if not isinstance(u, dict):
            continue
        created_at = u.get("created_at") or u.get("createdAt") or ""
        is_active = bool(u.get("is_active", False))
        norm_users.append({
            "created_at": str(created_at) if created_at is not None else "",
            "is_active": is_active,
        })

    df = pd.DataFrame(norm_users)
    total_users = len(df)
    # Compute current month (UTC) in YYYY-MM format and count new users this month
    month_prefix = datetime.now(timezone.utc).strftime("%Y-%m")
    created_series = df.get("created_at", pd.Series(dtype=str)).astype(str).fillna("")
    new_users_month = int(created_series.str.startswith(month_prefix).sum())
    active_users = int(df.get("is_active", pd.Series(dtype=bool)).fillna(False).astype(bool).sum())

    report = {
        "total_users": total_users,
        "new_users_month": new_users_month,
        "active_users": active_users,
        "title": "የተጠቃሚ መረጃ ሪፖርት" if lang == "am" else "User Report"
    }
    await redis.setex(cache_key, 3600, json.dumps(report))
    return report

async def export_report(report_type: str, lang: str = "en"):
    # The prompt provided `globals()[f"generate_{report_type}_report"](lang)`
    # which is not ideal. For now, I'll use a conditional check.
    report_data = {}
    # Support aliases: 'users' and 'csv' both export the users report to CSV
    if report_type in ("users", "csv", "users_csv"):
        report_data = await generate_user_report(lang)
    # Add other report types here as they are implemented

    if report_type in ("users", "csv", "users_csv"):
        df = pd.DataFrame([report_data])
        if lang == "am":
            df.columns = ["ጠቅላላ ተጠቃሚዎች", "አዲስ ተጠቃሚዎች", "ንቁ ተጠቃሚዎች", "ርዕስ"]
        csv_buffer = io.StringIO()
        df.to_csv(csv_buffer, index=False)
        async with AsyncClient(timeout=20.0) as client:
            response = await client.post(
                f"{_supabase_base}/storage/v1/object/reports/{report_type}_{lang}.csv",
                content=csv_buffer.getvalue().encode("utf-8"),
                headers={
                    "Authorization": f"Bearer {settings.SUPABASE_KEY}",
                    "apikey": settings.SUPABASE_KEY,
                    "Content-Type": "text/csv",
                    "x-upsert": "true",
                },
            )
            if 200 <= response.status_code < 300:
                body = response.json()
                # Try common keys; if absent, return raw body string
                file_url = body.get("url") or body.get("publicURL") or body.get("Key")
                if not file_url:
                    # As a fallback, if the bucket is public, construct a public URL
                    file_url = f"{_supabase_base}/storage/v1/object/public/reports/{report_type}_{lang}.csv"
                return file_url
            else:
                # Fallback: return data URI so client can still download
                import base64
                b64 = base64.b64encode(csv_buffer.getvalue().encode("utf-8")).decode("ascii")
                return f"data:text/csv;base64,{b64}"
    # PDF export (example)
    pdf_buffer = io.BytesIO()
    doc = SimpleDocTemplate(pdf_buffer, pagesize=A4)
    # Assuming report_data is a dictionary for PDF, convert to list of lists for Table
    data_for_table = [[key, value] for key, value in report_data.items()] if report_data else [["message", "No data available"]]
    table = Table(data_for_table)
    doc.build([table])
    async with AsyncClient(timeout=20.0) as client:
        response = await client.post(
            f"{_supabase_base}/storage/v1/object/reports/{report_type}_{lang}.pdf",
            content=pdf_buffer.getvalue(),
            headers={
                "Authorization": f"Bearer {settings.SUPABASE_KEY}",
                "apikey": settings.SUPABASE_KEY,
                "Content-Type": "application/pdf",
                "x-upsert": "true",
            }
        )
        if 200 <= response.status_code < 300:
            body = response.json()
            file_url = body.get("url") or body.get("publicURL") or body.get("Key")
            if not file_url:
                file_url = f"{_supabase_base}/storage/v1/object/public/reports/{report_type}_{lang}.pdf"
            return file_url
        else:
            import base64
            b64 = base64.b64encode(pdf_buffer.getvalue()).decode("ascii")
            return f"data:application/pdf;base64,{b64}"
