from httpx import AsyncClient
from fastapi import HTTPException
from app.config import settings
from structlog import get_logger
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy import insert
from app.models.admin_log import AdminLog
from redis.asyncio import Redis
from datetime import datetime, timezone
from urllib.parse import urlparse
import json

logger = get_logger()

# Initialize Redis client globally for reuse
redis_client: Redis | None = None

async def get_redis_client():
    global redis_client
    if redis_client is None:
        redis_client = Redis.from_url(settings.REDIS_URL)
    return redis_client

def _normalize_user(u: dict) -> dict:
    """Normalize upstream user payload to our schema.
    - Map phone_number -> phone and decode hex-escaped values (e.g., "\\x2b3235...")
    - Ensure id key present (map from common alternatives)
    - Normalize created_at from common alternatives; default to empty string to avoid nulls
    """
    if not isinstance(u, dict):
        return u

    # Normalize ID
    uid = u.get("id") or u.get("_id") or u.get("user_id") or u.get("sub") or u.get("uid")
    if uid is not None:
        u["id"] = uid

    # Normalize phone
    phone = u.get("phone") if u.get("phone") is not None else u.get("phone_number")
    if isinstance(phone, str):
        # Decode hex-escaped byte string like "\\x2b3235312037323139"
        if phone.startswith("\\x"):
            hex_str = phone[2:]
            try:
                decoded = bytes.fromhex(hex_str).decode("utf-8", errors="ignore")
                phone = decoded
            except Exception:
                # Fallback: keep original if decoding fails
                pass
        # Strip spaces commonly embedded in upstream phone formats
        phone = phone.replace(" ", "")
    # Default to empty string if missing to avoid nulls
    if phone is None:
        phone = ""
    u["phone"] = phone

    # Normalize created_at
    created = (
        u.get("created_at")
        or u.get("createdAt")
        or u.get("created_on")
        or u.get("createdOn")
        or u.get("created")
        or u.get("date_created")
        or u.get("createdDate")
    )
    if not created:
        created = datetime.now(timezone.utc).isoformat()
    u["created_at"] = created

    # Normalize role to lowercase string if present
    if "role" in u and isinstance(u["role"], str):
        u["role"] = u["role"].lower()

    return u

# Normalize bases and prefixes from environment
_user_base = settings.USER_MANAGEMENT_URL.rstrip("/")
_user_has_v1 = _user_base.endswith("/api/v1")
_user_prefix = "" if _user_has_v1 else "/api/v1"

_prop_base = settings.PROPERTY_LISTING_URL.rstrip("/")
# A lot of gateways expose docs at /docs; ensure we don't keep that in API base
if "/docs" in _prop_base:
    _prop_base = _prop_base.replace("/docs", "")
_prop_has_v1 = _prop_base.endswith("/api/v1")
_prop_prefix = "" if _prop_has_v1 else "/api/v1"

async def get_users(admin_token: str, skip: int = 0, limit: int = 100):
    async with AsyncClient() as client:
        response = await client.get(
            f"{_user_base}{_user_prefix}/admin/users",
            headers={"Authorization": f"Bearer {admin_token}"},
            params={"skip": skip, "limit": limit},
        )
        response.raise_for_status()
        data = response.json()
        if isinstance(data, list):
            return [_normalize_user(item) for item in data]
        return data

async def get_payment_health():
    base = settings.PAYMENT_URL.rstrip("/")
    async with AsyncClient() as client:
        # Prefer explicit /api/v1/health if base includes /api/v1; otherwise try /health
        url = f"{base}/health"
        resp = await client.get(url)
        # Fallback: if base ends with /api/v1 and first attempt fails, try root /health
        if resp.status_code >= 400 and base.endswith("/api/v1"):
            root = base[: -len("/api/v1")]
            resp = await client.get(f"{root}/health")
        try:
            data = resp.json()
        except Exception:
            data = resp.text or "ok"
        return {"status_code": resp.status_code, "data": data}

async def get_ai_health():
    base = settings.AI_RECOMMENDATION_URL.rstrip("/")
    # Some providers (e.g., HF Spaces) don't expose /health; treat base reachability as healthy
    try:
        async with AsyncClient(timeout=10.0) as client:
            # Try /health
            resp = await client.get(f"{base}/health")
            # Fallback: if base ends with /api/v1, try root /health
            if resp.status_code >= 400 and base.endswith("/api/v1"):
                root = base[: -len("/api/v1")]
                resp = await client.get(f"{root}/health")
            # If still failing, try base and root reachability
            if resp.status_code >= 400:
                resp = await client.get(base)
                if resp.status_code >= 400 and base.endswith("/api/v1"):
                    root = base[: -len("/api/v1")]
                    resp = await client.get(root)
            # Build concise payload
            try:
                payload = resp.json()
            except Exception:
                if 200 <= resp.status_code < 400:
                    payload = {"status": "reachable"}
                else:
                    snippet = (resp.text or "").strip()
                    if snippet and len(snippet) > 200:
                        snippet = snippet[:200] + "..."
                    payload = {"message": snippet or "error"}
            return {"status_code": resp.status_code, "data": payload}
    except Exception as e:
        return {"status": "error", "error": f"{type(e).__name__}: {e}"}

async def get_search_health():
    base = settings.SEARCH_FILTERS_URL.rstrip("/")
    async with AsyncClient(timeout=30.0) as client:
        url = f"{base}/health"
        resp = await client.get(url)
        # No special /api/v1 logic unless base includes it
        if resp.status_code >= 400 and base.endswith("/api/v1"):
            root = base[: -len("/api/v1")]
            resp = await client.get(f"{root}/health")
        try:
            data = resp.json()
        except Exception:
            data = resp.text or "ok"
        return {"status_code": resp.status_code, "data": data}

async def get_payment_metrics():
    base = settings.PAYMENT_URL.rstrip("/")
    async with AsyncClient(timeout=30.0) as client:
        url = f"{base}/metrics"
        resp = await client.get(url)
        logger.info(
            "Payment metrics upstream response (attempt 1)",
            url=url,
            status_code=resp.status_code,
            headers=dict(resp.headers),
            body_text=resp.text,
        )
        if resp.status_code >= 400 and base.endswith("/api/v1"):
            root = base[: -len("/api/v1")]
            url = f"{root}/metrics"
            resp = await client.get(url)
            logger.info(
                "Payment metrics upstream response (attempt 2, fallback)",
                url=url,
                status_code=resp.status_code,
                headers=dict(resp.headers),
                body_text=resp.text,
            )
        try:
            json_data = resp.json()
            logger.info("Payment metrics upstream response (parsed JSON)", data=json_data)
            # Explicitly extract expected keys
            extracted_data = {
                "total_payments": json_data.get("total_payments", 0),
                "pending_payments": json_data.get("pending_payments", 0),
                "success_payments": json_data.get("success_payments", 0),
                "failed_payments": json_data.get("failed_payments", 0),
                "webhook_calls": json_data.get("webhook_calls", 0),
                "initiate_calls": json_data.get("initiate_calls", 0),
                "status_calls": json_data.get("status_calls", 0),
                "timeout_jobs_run": json_data.get("timeout_jobs_run", 0),
                "total_revenue": json_data.get("total_revenue", 0.0), # Assuming float for revenue
            }
            data = extracted_data
        except Exception:
            data = resp.text or "ok"
            logger.info("Payment metrics upstream response (raw text)", data=data)
        return {"status_code": resp.status_code, "data": data}

async def update_user(user_id: str, data: dict, admin_token: str):
    base_admin = f"{_user_base}{_user_prefix}/admin/users/{user_id}"
    base_no_admin = f"{_user_base}{_user_prefix}/users/{user_id}"
    headers = {"Authorization": f"Bearer {admin_token}"}
    candidates = [
        # Common RESTful patterns
        ("PUT", base_admin, "json"),
        ("PATCH", base_admin, "json"),
        ("POST", base_admin, "json"),
        ("POST", base_admin, "form"),
        # Alternate path styles some backends use
        ("POST", base_admin + "/update", "json"),
        ("POST", base_admin + "/update", "form"),
        ("POST", f"{_user_base}{_user_prefix}/admin/users/update/{user_id}", "json"),
        ("POST", f"{_user_base}{_user_prefix}/admin/users/update/{user_id}", "form"),
        # Without /admin prefix
        ("PUT", base_no_admin, "json"),
        ("PATCH", base_no_admin, "json"),
        ("POST", base_no_admin, "json"),
        ("POST", base_no_admin, "form"),
    ]
    last_resp = None
    async with AsyncClient(timeout=20.0) as client:
        for method, url, mode in candidates:
            try:
                if method == "PUT":
                    resp = await client.put(url, json=data, headers=headers)
                elif method == "PATCH":
                    resp = await client.patch(url, json=data, headers=headers)
                else:  # POST
                    if mode == "json":
                        resp = await client.post(url, json=data, headers=headers)
                    else:
                        resp = await client.post(
                            url, data=data,
                            headers={**headers, "Content-Type": "application/x-www-form-urlencoded"}
                        )
                logger.info(
                    "Update user attempt",
                    method=method,
                    mode=mode,
                    status_code=resp.status_code,
                    url=url,
                    body_text=resp.text,
                    headers=dict(resp.headers)
                )
                last_resp = resp
                if 200 <= resp.status_code < 300:
                    try:
                        return _normalize_user(resp.json())
                    except Exception:
                        return {"id": user_id, **data}
                # For method/content issues, continue trying next candidate
                if resp.status_code in (400, 401, 403, 404, 405, 415, 422):
                    continue
                # Unexpected status: break and surface
                break
            except Exception as e:
                logger.warning("Update user exception", method=method, mode=mode, url=url, error=str(e))
                continue
    # If we reach here, all attempts failed; raise with best available info
    if last_resp is not None:
        try:
            err = last_resp.json()
        except Exception:
            err = {"detail": last_resp.text or "Upstream error"}
        logger.warning("Update user failed (all attempts)", status_code=last_resp.status_code, error=err)
        # Propagate upstream status to client with clear message
        msg = err if isinstance(err, dict) else {"detail": str(err)}
        if last_resp.status_code == 405:
            msg = {"detail": "Upstream rejected method for user update. Try PATCH/POST variations or check upstream docs.", **msg}
        raise HTTPException(status_code=last_resp.status_code, detail=msg)
    raise HTTPException(status_code=502, detail="Unable to update user: no valid upstream method/path accepted")

async def get_user_by_id(user_id: str, admin_token: str):
    async with AsyncClient(timeout=15.0) as client:
        response = await client.get(
            f"{_user_base}{_user_prefix}/admin/users/{user_id}",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        response.raise_for_status()
        return _normalize_user(response.json())

async def get_properties(
    location: str | None = None,
    min_price: float | None = None,
    max_price: float | None = None,
    amenities: list[str] | None = None,
    search: str | None = None,
    offset: int = 0,
    limit: int = 20,
):
    params = {
        "location": location,
        "min_price": min_price,
        "max_price": max_price,
        "search": search,
        "offset": offset,
        "limit": limit,
    }
    # Filter out None values
    params = {k: v for k, v in params.items() if v is not None}
    # Handle amenities list: property listing often expects repeated query params or comma-separated.
    # We'll send as repeated params if provided.
    async with AsyncClient(timeout=15.0) as client:
        if amenities:
            # httpx will encode list values as repeated params when a list is provided
            params_with_amenities = {**params, "amenities": amenities}
        else:
            params_with_amenities = params
        response = await client.get(
            f"{_prop_base}{_prop_prefix}/properties",
            headers={"Authorization": f"Bearer {settings.PROPERTY_TOKEN}"},
            params=params_with_amenities,
        )
        response.raise_for_status()
        return response.json()

async def approve_property(property_id: str, admin_id: str): 
    async with AsyncClient() as client:
        response = await client.post(
            f"{_prop_base}{_prop_prefix}/properties/{property_id}/approve",
            headers={"Authorization": f"Bearer {settings.PROPERTY_TOKEN}"}
        )
        response.raise_for_status()
        # Log action
        async with AsyncSession(create_async_engine(settings.DATABASE_URL)) as session:
            stmt = insert(AdminLog).values(
                admin_id=admin_id, action="property_approved", entity_id=property_id
            )
            await session.execute(stmt)
            await session.commit()

async def get_health(verbose: bool = False):
    redis = await get_redis_client()
    cache_key = "cached_health_status"

    if not verbose: # Only serve from cache if not verbose
        cached_health = await redis.get(cache_key)
        if cached_health:
            logger.info("Returning cached health status")
            return json.loads(cached_health)

    # Explicit mapping from service key to settings attribute name
    env_map = {
        "user_management": "USER_MANAGEMENT_URL",
        "property_listing": "PROPERTY_LISTING_URL",
        "payment_processing": "PAYMENT_URL",
        "search_filters": "SEARCH_FILTERS_URL",
        "ai_recommendation": "AI_RECOMMENDATION_URL",
        "notification": "NOTIFICATION_URL",
    }
    health = {}
    async with AsyncClient(timeout=10.0) as client:
        for service, attr in env_map.items():
            try:
                # Resolve base URL from settings
                base = getattr(settings, attr, None)
                if not base:
                    health[service] = {
                        "status": "error",
                        "error": f"Missing or empty settings.{attr}",
                    }
                    continue
                base = base.rstrip("/")
                # Some gateways expose docs at /docs; ensure health doesn't target docs path
                if "/docs" in base:
                    base = base.replace("/docs", "")
                tried = []
                # Try base/health first
                url = f"{base}/health"
                tried.append(url)
                resp = await client.get(url)
                # If 4xx/5xx and base ends with /api/v1, try without it
                if resp.status_code >= 400 and base.endswith("/api/v1"):
                    root = base[: -len("/api/v1")]
                    url2 = f"{root}/health"
                    tried.append(url2)
                    resp = await client.get(url2)
                # If /health is not available for ai_recommendation (e.g., HuggingFace Spaces),
                # try the base URL itself as a reachability check and treat 2xx/3xx as healthy.
                if service == "ai_recommendation" and resp.status_code >= 400:
                    # Try GET base (without /health)
                    tried.append(base)
                    resp = await client.get(base)
                    # If base ends with /api/v1 and still failing, try root without it
                    if resp.status_code >= 400 and base.endswith("/api/v1"):
                        root = base[: -len("/api/v1")]
                        tried.append(root)
                        resp = await client.get(root)
                # Build payload
                payload = None
                # Prefer JSON
                try:
                    payload = resp.json()
                except Exception:
                    # For ai_recommendation, consider reachability sufficient and avoid returning massive HTML
                    if service == "ai_recommendation" and 200 <= resp.status_code < 400:
                        payload = {"status": "reachable"}
                    else:
                        # Return concise message instead of huge HTML
                        snippet = (resp.text or "").strip()
                        if snippet and len(snippet) > 200:
                            snippet = snippet[:200] + "..."
                        payload = {"message": snippet or "error"}

                entry = {
                    "status_code": resp.status_code,
                    "data": payload,
                }
                if verbose:
                    entry["tried"] = tried
                health[service] = entry
            except Exception as e:
                # Ensure we never return empty error; include type and message
                err = f"{type(e).__name__}: {e}"
                health[service] = {"status": "error", "error": err}
    # Compute overall summary (treat notification as optional)
    optional = {"notification"}
    ok_services = 0
    error_services = 0
    for k, v in health.items():
        if k in ("overall_status", "summary"):
            continue
        # entries with explicit error
        if isinstance(v, dict) and "status" in v and v.get("status") == "error":
            if k not in optional:
                error_services += 1
            continue
        code = v.get("status_code") if isinstance(v, dict) else None
        if isinstance(code, int) and code < 400:
            ok_services += 1
        else:
            if k not in optional:
                error_services += 1
    if error_services == 0:
        overall = "ok"
    elif ok_services > 0:
        overall = "degraded"
    else:
        overall = "down"
    health["overall_status"] = overall
    health["summary"] = {"ok": ok_services, "errors": error_services, "total": sum(1 for k in env_map.keys() if k not in optional), "optional_ignored": len(optional)}
    
    # Cache the result before returning
    await redis.setex(cache_key, 300, json.dumps(health)) # Cache for 5 minutes
    return health

async def get_property_metrics():
    base = _prop_base
    async with AsyncClient(timeout=15.0) as client:
        url = f"{base}{_prop_prefix}/properties/metrics"
        resp = await client.get(url, headers={"Authorization": f"Bearer {settings.PROPERTY_TOKEN}"})
        # If 4xx/5xx and base ends with /api/v1, try root without it
        if resp.status_code >= 400 and base.endswith("/api/v1"):
            root = base[: -len("/api/v1")]
            resp = await client.get(
                f"{root}/properties/metrics",
                headers={"Authorization": f"Bearer {settings.PROPERTY_TOKEN}"}
            )
        try:
            data = resp.json()
        except Exception:
            data = resp.text or "ok"
        return {"status_code": resp.status_code, "data": data}

async def _extract_count_from_payload(payload) -> int | None:
    """Try common patterns to extract a total count from a JSON payload."""
    try:
        if isinstance(payload, dict):
            for key in ("total", "count", "total_count", "totalItems", "items_total"):
                if isinstance(payload.get(key), int):
                    return int(payload[key])
            # Some APIs wrap list under data/results with a separate total
            meta = payload.get("meta") or payload.get("pagination")
            if isinstance(meta, dict):
                for key in ("total", "count", "total_count"):
                    if isinstance(meta.get(key), int):
                        return int(meta[key])
            # If list is present, we can fallback to its length
            for lk in ("data", "results", "items"):
                if isinstance(payload.get(lk), list):
                    return len(payload[lk])
        elif isinstance(payload, list):
            return len(payload)
    except Exception:
        return None
    return None

async def _head_or_first_for_total(client: AsyncClient, url: str, headers: dict | None = None) -> int | None:
    """Try common approaches to get total count without fetching everything.
    - Try HEAD to see if X-Total-Count header is present
    - Try GET with limit=1 to see headers or meta
    """
    try:
        resp = await client.head(url, headers=headers, params={"limit": 1})
        for hk in ("X-Total-Count", "X-Total", "Total-Count"):
            if hk in resp.headers:
                return int(resp.headers[hk])
    except Exception:
        pass
    try:
        resp = await client.get(url, headers=headers, params={"limit": 1, "skip": 0})
        for hk in ("X-Total-Count", "X-Total", "Total-Count"):
            if hk in resp.headers:
                return int(resp.headers[hk])
        try:
            payload = resp.json()
        except Exception:
            payload = None
        cnt = await _extract_count_from_payload(payload)
        return cnt
    except Exception:
        return None

async def get_dashboard_totals(admin_token: str | None = None) -> dict:
    """Aggregate totals: users, properties, payments, and services health.

    - Users: try /admin/users count endpoints, then header-based totals, then length fallback
    - Properties: try /properties/metrics for total, then similar header/meta fallbacks
    - Payments: use get_payment_metrics and extract total from common fields
    - Services: reuse get_health to compute totals and healthy count
    """
    totals = {
        "total_users": 0,
        "total_properties": 0,
        "total_payments": 0,
        "total_services": 0,
        "healthy_services": 0,
        "properties_by_type": None,
    }

    user_headers = {"Authorization": f"Bearer {admin_token or settings.USER_TOKEN}"}
    prop_headers = {"Authorization": f"Bearer {settings.PROPERTY_TOKEN}"}

    async with AsyncClient(timeout=15.0) as client:
        # Users total
        user_base = _user_base
        uprefix = _user_prefix
        candidates = [
            f"{user_base}{uprefix}/admin/users/count",
            f"{user_base}{uprefix}/users/count",
        ]
        users_total = None
        for u in candidates:
            try:
                r = await client.get(u, headers=user_headers)
                if 200 <= r.status_code < 300:
                    try:
                        body = r.json()
                    except Exception:
                        body = {"total": int(r.text)} if r.text.strip().isdigit() else None
                    users_total = await _extract_count_from_payload(body)
                    if users_total is None and isinstance(body, dict):
                        # Some count endpoints return {count: N}
                        c = body.get("count")
                        if isinstance(c, int):
                            users_total = c
                    if users_total is not None:
                        break
            except Exception:
                continue
        if users_total is None:
            users_total = await _head_or_first_for_total(client, f"{user_base}{uprefix}/admin/users", headers=user_headers)
        if users_total is None:
            # Fallback: get first page with bigger limit
            try:
                r = await client.get(f"{user_base}{uprefix}/admin/users", headers=user_headers, params={"skip": 0, "limit": 1000})
                if 200 <= r.status_code < 300:
                    users_total = await _extract_count_from_payload(r.json())
            except Exception:
                pass
        totals["total_users"] = int(users_total or 0)

        # Properties total
        # Prefer metrics endpoint
        prop_metrics = await get_property_metrics()
        prop_total = None
        prop_by_type: dict[str, int] | None = None
        prop_by_status: dict[str, int] | None = None
        pdata = prop_metrics.get("data") if isinstance(prop_metrics, dict) else None
        if isinstance(pdata, dict):
            for k in ("total_properties", "properties_total", "count", "total"):
                if isinstance(pdata.get(k), int):
                    prop_total = int(pdata[k])
                    break
            # Try extracting breakdown by type from common shapes
            # 1) { by_type: { "apartment": 10, "house": 5 } }
            if isinstance(pdata.get("by_type"), dict):
                # ensure ints
                prop_by_type = {str(t): int(v) for t, v in pdata["by_type"].items() if isinstance(v, int)}
            # 2) { types: { ... } } or { type_breakdown: { ... } }
            for alt in ("types", "type_breakdown", "properties_by_type"):
                if prop_by_type is None and isinstance(pdata.get(alt), dict):
                    prop_by_type = {str(t): int(v) for t, v in pdata[alt].items() if isinstance(v, int)}
            # 3) { by_type: [ { type: "apartment", count: 10 }, ... ] }
            if prop_by_type is None and isinstance(pdata.get("by_type"), list):
                tmp = {}
                for item in pdata["by_type"]:
                    if isinstance(item, dict):
                        t = item.get("type") or item.get("property_type")
                        c = item.get("count") or item.get("total")
                        if isinstance(t, str) and isinstance(c, int):
                            tmp[str(t)] = int(c)
                if tmp:
                    prop_by_type = tmp
            # Status breakdown from common shapes
            if isinstance(pdata.get("by_status"), dict):
                prop_by_status = {str(s): int(v) for s, v in pdata["by_status"].items() if isinstance(v, int)}
            for alt in ("statuses", "status_breakdown", "properties_by_status"):
                if prop_by_status is None and isinstance(pdata.get(alt), dict):
                    prop_by_status = {str(s): int(v) for s, v in pdata[alt].items() if isinstance(v, int)}
            if prop_by_status is None and isinstance(pdata.get("by_status"), list):
                tmp = {}
                for item in pdata["by_status"]:
                    if isinstance(item, dict):
                        s = item.get("status") or item.get("state")
                        c = item.get("count") or item.get("total")
                        if isinstance(s, str) and isinstance(c, int):
                            tmp[str(s)] = int(c)
                if tmp:
                    prop_by_status = tmp
        if prop_total is None:
            prop_total = await _head_or_first_for_total(client, f"{_prop_base}{_prop_prefix}/properties", headers=prop_headers)
        # If we still need totals or type breakdown, fetch first page and compute
        if prop_total is None or prop_by_type is None or prop_by_status is None:
            try:
                r = await client.get(
                    f"{_prop_base}{_prop_prefix}/properties",
                    headers=prop_headers,
                    params={"offset": 0, "limit": 500},
                )
                if 200 <= r.status_code < 300:
                    body = None
                    try:
                        body = r.json()
                    except Exception:
                        body = None
                    if prop_total is None:
                        prop_total = await _extract_count_from_payload(body)
                    # If body is a list, compute types; if dict, look under common keys
                    items = None
                    if isinstance(body, list):
                        items = body
                    elif isinstance(body, dict):
                        for lk in ("data", "results", "items"):
                            if isinstance(body.get(lk), list):
                                items = body[lk]
                                break
                    if isinstance(items, list):
                        counts: dict[str, int] = {}
                        # property type counts
                        if prop_by_type is None:
                            for it in items:
                                if not isinstance(it, dict):
                                    continue
                                t = it.get("type") or it.get("property_type") or it.get("category")
                                if isinstance(t, str) and t.strip():
                                    key = t.strip()
                                    counts[key] = counts.get(key, 0) + 1
                            if counts:
                                prop_by_type = counts
                        # property status counts
                        if prop_by_status is None:
                            s_counts: dict[str, int] = {}
                            for it in items:
                                if not isinstance(it, dict):
                                    continue
                                s = it.get("status") or it.get("state")
                                if isinstance(s, str) and s.strip():
                                    key = s.strip()
                                    s_counts[key] = s_counts.get(key, 0) + 1
                            if s_counts:
                                prop_by_status = s_counts
            except Exception:
                pass
        totals["total_properties"] = int(prop_total or 0)
        if prop_by_type:
            totals["properties_by_type"] = prop_by_type
        if prop_by_status:
            totals["properties_by_status"] = prop_by_status

        # Payments total via payment metrics
        pay_metrics = await get_payment_metrics()
        pay_total = None
        pdata = pay_metrics.get("data") if isinstance(pay_metrics, dict) else None
        if isinstance(pdata, dict):
            for k in ("total_payments", "payments_count", "total_transactions", "count", "total"):
                if isinstance(pdata.get(k), int):
                    pay_total = int(pdata[k])
                    break
        elif isinstance(pdata, str):
            # If metrics came back as string (e.g., Prometheus text), try parsing common pattern
            try:
                import re
                m = re.search(r"payments_total\s+(\d+)", pdata)
                if m:
                    pay_total = int(m.group(1))
            except Exception:
                pass
        totals["total_payments"] = int(pay_total or 0)

    # Services health
    health = await get_health(verbose=False)
    # Exclude summary keys
    service_keys = [k for k in health.keys() if k not in ("overall_status", "summary")]
    total_services = 0
    healthy = 0
    for k in service_keys:
        v = health[k]
        if isinstance(v, dict) and "status" in v and v.get("status") == "error":
            total_services += 1
            continue
        total_services += 1
        code = v.get("status_code") if isinstance(v, dict) else None
        if isinstance(code, int) and code < 400:
            healthy += 1
    totals["total_services"] = total_services
    totals["healthy_services"] = healthy

    return totals
