# Admin Management Frontend API Guide

This document describes how frontend clients should integrate with the Admin Management Microservice.
It reflects the current backend behavior and includes examples, response shapes, and edge cases.

Base URL
- Local dev: http://localhost:8008
- API prefix: /api/v1/admin

Authentication
- All endpoints require a Bearer token via HTTP header:
  Authorization: Bearer <JWT>
- The token must verify upstream and the user must have role "admin".
- Swagger auth: use the local /auth/login to obtain a token for testing.

Common Conventions
- Content-Type: application/json unless noted.
- Query pagination (where supported): skip (int, default 0), limit (int, default 20/100 depending on endpoint).
- Errors are standard FastAPI error shapes or upstream-proxied JSON; handle HTTP status codes and parse "detail".

Schemas
- UserResponse
  {
    id: string,
    email: string,
    role: string,
    phone?: string | null,
    is_active: boolean,
    created_at?: string | null
  }

- UserListResponse
  {
    users: UserResponse[],
    total_users: number
  }

- UserUpdateRequest
  {
    email?: string,
    role?: string,
    phone?: string,
    is_active?: boolean
  }

- ReportResponse
  {
    title: string,
    data: object
  }

- MetricsTotalsResponse
  {
    total_users: number,
    total_properties: number,
    total_payments: number,
    total_services: number,
    healthy_services: number,
    properties_by_type?: { [type: string]: number },
    properties_by_status?: { [status: string]: number }
  }
  - Notes:
    - Users: counts via upstream `/admin/users/count` or headers/meta, with graceful fallbacks.
    - Properties: uses upstream `/properties/metrics` then falls back to headers/meta.
      - When available, the response includes `properties_by_type` for KPI cards (e.g., apartment/house/land counts). If the upstream does not provide a breakdown, backend will sample the first page and compute counts using `type`/`property_type`/`category` fields.
      - Use `properties_by_status` to render status distribution graphs (e.g., approved/pending/rejected). If not provided by the upstream metrics, backend will infer by scanning the first page using `status`/`state` fields.
    - Payments: derives from payment metrics (JSON or Prometheus text).
    - Services: derived from unified health to compute total vs healthy.

Endpoints

1) Auth (for Swagger/dev only)
- POST /auth/login
  - Form fields: username, password (OAuth2 password grant style).
  - Returns upstream token JSON or plain token structure. Use access_token or token as Bearer.

2) Users
- GET /api/v1/admin/users
  - Query: skip (int), limit (int)
  - Returns: UserListResponse
  - Notes: Backend normalizes phone_number -> phone. created_at may be synthesized if absent.

- GET /api/v1/admin/users/{user_id}
  - Returns: UserResponse

- PUT /api/v1/admin/users/{user_id}
  - Body: UserUpdateRequest (partial user fields, e.g., role, is_active)
  - Returns: UserResponse on success.
  - Important: Upstream update API is not finalized. Backend retries several methods/paths.
    If upstream does not support any, you may receive 404/405 with a clear message.
    The upstream User Management Service currently exhibits limitations in supporting user updates via `PUT`/`PATCH`/`POST` methods, often returning `405 Method Not Allowed` or `404 Not Found`. This microservice attempts various patterns, but successful updates depend on the upstream service's capabilities.

3) Properties
- GET /api/v1/admin/properties
  - Query (optional): location, min_price, max_price, amenities (repeatable), search, offset, limit
  - Returns: Property list (see backend schema PropertyResponse)

- POST /api/v1/admin/properties/{property_id}/approve
  - Returns: { status: "success" }

- GET /api/v1/admin/properties/metrics
  - Returns: { status_code: number, data: object|string }
  - Notes: This endpoint proxies upstream and will not 500; it surfaces upstream status_code and payload.

- GET /api/v1/properties/public
  - Query (optional): location, min_price, max_price, amenities (repeatable), search, offset, limit
  - Returns: PropertyListResponse (total: number, items: PropertyResponse[])
  - Notes: Only returns APPROVED listings.

- GET /api/v1/properties/public/{property_id}
  - Returns: PropertyResponse
  - Notes: Returns full details if property is APPROVED; otherwise 404.

4) Payments (Proxies)
- GET /api/v1/admin/payments/metrics
  - Returns: { status_code: number, data: object|string }
  - Notes: The `data` object will include payment metrics such as `total_payments`, `pending_payments`, `success_payments`, `failed_payments`, `webhook_calls`, `initiate_calls`, `status_calls`, `timeout_jobs_run`, and `total_revenue`.

- GET /api/v1/admin/payments/health (legacy alias)
  - Returns: { status_code: number, data: object|string }
  - Prefer unified health (/api/v1/admin/health).

5) Search (Proxy)
- GET /api/v1/admin/search/health (legacy alias)
  - Returns: { status_code: number, data: object|string }
  - Prefer unified health (/api/v1/admin/health).

6) AI (Proxy)
- GET /api/v1/admin/ai/health (legacy alias)
  - Returns: { status_code: number, data: object|string }
  - Notes: For providers without /health (e.g., HF Spaces), reachability is considered healthy and returns { status: "reachable" }.
  - Prefer unified health (/api/v1/admin/health).

7) Unified Health
- GET /api/v1/admin/health
  - Query: verbose (bool, default false)
  - Returns:
    {
      user_management: { status_code?: number, data?: object, status?: "error", error?: string },
      property_listing: { ... },
      payment_processing: { ... },
      search_filters: { ... },
      ai_recommendation: { ... },
      notification: { ... },
      overall_status: "ok" | "degraded" | "down",
      summary: { ok: number, errors: number, total: number, optional_ignored: number }
    }
  - When verbose=true, each service includes tried: string[].
  - Notification is treated as optional and won’t cause overall "down" by itself.

8) Reports
- GET /api/v1/admin/reports/users
  - Query: lang=en|am (default en)
  - Returns: ReportResponse
    {
      title: "User Report" | "የተጠቃሚ መረጃ ሪፖርት",
      data: {
        total_users: number,
        new_users_month: number,   // computed for current UTC month
        active_users: number
      }
    }
  - Auth: Uses the caller’s Bearer token to fetch data; if upstream is unavailable, returns title + zeroes.

- GET /api/v1/admin/reports/export/{type}
  - Path param: type = users | csv | users_csv (CSV of user report)
  - Query: lang=en|am
  - Returns: { file_url: string }
  - Behavior:
    - Attempts to upload CSV/PDF to Supabase storage. On success, returns a public/file URL.
    - On upload failure, returns a data URI (base64). Frontends should detect strings starting with
      data:text/csv;base64, or data:application/pdf;base64, and trigger download accordingly.

HTTP Examples (curl)
- List users
  curl -H "Authorization: Bearer $TOKEN" \
    "http://localhost:8008/api/v1/admin/users?skip=0&limit=50"

- User detail
  curl -H "Authorization: Bearer $TOKEN" \
    "http://localhost:8008/api/v1/admin/users/<USER_ID>"

- Update user (may return 404/405 if upstream disallows)
  curl -X PUT -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' \
    -d '{"role":"owner","is_active":true}' \
    "http://localhost:8008/api/v1/admin/users/<USER_ID>"

- Approve property
  curl -X POST -H "Authorization: Bearer $TOKEN" \
    "http://localhost:8008/api/v1/admin/properties/<PROPERTY_ID>/approve"

- Properties metrics
  curl -H "Authorization: Bearer $TOKEN" \
    "http://localhost:8008/api/v1/admin/properties/metrics"

- List public properties
  curl "http://localhost:8008/api/v1/properties/public?location=Addis Ababa&limit=5"

- Get single public property
  curl "http://localhost:8008/api/v1/properties/public/<PROPERTY_ID>"

- Unified health (concise)
  curl -H "Authorization: Bearer $TOKEN" \
    "http://localhost:8008/api/v1/admin/health"

- Unified health (verbose)
  curl -H "Authorization: Bearer $TOKEN" \
    "http://localhost:8008/api/v1/admin/health?verbose=true"

- User report
  curl -H "Authorization: Bearer $TOKEN" \
    "http://localhost:8008/api/v1/admin/reports/users?lang=en"

- Export report CSV (returns URL or data URI)
  curl -H "Authorization: Bearer $TOKEN" \
    "http://localhost:8008/api/v1/admin/reports/export/csv?lang=en"

Frontend Integration Notes
- Detect data URIs returned by export endpoints and trigger client-side download.
- Handle upstream-proxied responses that include status_code and data.
- For health UI, use overall_status and summary for top-level badges; when verbose, show per-service tried URLs as a diagnostic expand.
- For update user, surface backend messages when 404/405 occurs and guide operators to permissible actions.

Roadmap (for upcoming UI features)
- Service registry endpoint to drive a Services list in UI.
- Audit querying and export endpoints.
- Logs streaming via SSE and on-demand fetch.
- Feature flags and safe control actions (cache clear, reindex).

Contact
- For questions about payloads or adding new endpoints, see `app/routers/admin.py` and `app/services/*` or open an issue.
