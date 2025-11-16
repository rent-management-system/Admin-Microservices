# Admin Management API Documentation

This document provides detailed API documentation for the Admin Management Microservice, intended for frontend integration.

## Base URL
`/api/v1/admin`

## Authentication
All endpoints require a valid JWT token in the `Authorization` header (Bearer token). The authenticated user must have the "Admin" role.

---

### 1. List Users

*   **Method:** `GET`
*   **Path:** `/api/v1/admin/users`
*   **Permissions:** Authenticated Admin
*   **User Types:** Admin
*   **Position in Code:** `app/routers/admin.py` -> `list_users`
*   **Parameters:** None
*   **Response Model:** `List[UserResponse]`
    *   `id`: `str` - Unique identifier of the user.
    *   `email`: `str` - User's email address.
    *   `role`: `str` - User's role (e.g., "Admin", "User", "Landlord").
    *   `phone`: `Optional[str]` - User's phone number.
    *   `is_active`: `bool` - Whether the user account is active.
    *   `created_at`: `str` - Timestamp of user creation.
*   **Examples:**
    *   **Request:**
        ```
        GET /api/v1/admin/users
        Authorization: Bearer <ADMIN_JWT_TOKEN>
        ```
    *   **Response (200 OK):**
        ```json
        [
            {
                "id": "user-id-1",
                "email": "user1@example.com",
                "role": "User",
                "phone": "+1234567890",
                "is_active": true,
                "created_at": "2023-01-01T10:00:00Z"
            },
            {
                "id": "user-id-2",
                "email": "user2@example.com",
                "role": "Landlord",
                "phone": null,
                "is_active": true,
                "created_at": "2023-02-15T11:30:00Z"
            }
        ]
        ```

---

### 2. Update User

*   **Method:** `PUT`
*   **Path:** `/api/v1/admin/users/{user_id}`
*   **Permissions:** Authenticated Admin
*   **User Types:** Admin
*   **Position in Code:** `app/routers/admin.py` -> `update_user_endpoint`
*   **Parameters:**
    *   **Path Parameter:**
        *   `user_id`: `str` - The unique identifier of the user to update.
    *   **Request Body:** `dict` - JSON object containing the fields to update.
        *   Example fields: `email`, `role`, `phone`, `is_active`.
*   **Response Model:** `UserResponse` (updated user object)
*   **Examples:**
    *   **Request:**
        ```
        PUT /api/v1/admin/users/user-id-1
        Authorization: Bearer <ADMIN_JWT_TOKEN>
        Content-Type: application/json

        {
            "role": "Landlord",
            "is_active": false
        }
        ```
    *   **Response (200 OK):**
        ```json
        {
            "id": "user-id-1",
            "email": "user1@example.com",
            "role": "Landlord",
            "phone": "+1234567890",
            "is_active": false,
            "created_at": "2023-01-01T10:00:00Z"
        }
        ```

---

### 3. List Properties

*   **Method:** `GET`
*   **Path:** `/api/v1/admin/properties`
*   **Permissions:** Authenticated Admin
*   **User Types:** Admin
*   **Position in Code:** `app/routers/admin.py` -> `list_properties`
*   **Parameters:** None
*   **Response Model:** `List[PropertyResponse]`
    *   `id`: `str` - Unique identifier of the property.
    *   `title`: `str` - Title of the property listing.
    *   `location`: `str` - Geographical location of the property.
    *   `status`: `str` - Current status of the property (e.g., "pending", "approved", "rejected").
    *   `owner_id`: `str` - Unique identifier of the property owner.
    *   `price`: `float` - Listing price of the property.
    *   `lat`: `Optional[float]` - Latitude coordinate of the property.
    *   `lon`: `Optional[float]` - Longitude coordinate of the property.
*   **Examples:**
    *   **Request:**
        ```
        GET /api/v1/admin/properties
        Authorization: Bearer <ADMIN_JWT_TOKEN>
        ```
    *   **Response (200 OK):**
        ```json
        [
            {
                "id": "property-id-1",
                "title": "Cozy Apartment",
                "location": "Addis Ababa",
                "status": "pending",
                "owner_id": "owner-id-1",
                "price": 1500.00,
                "lat": 8.9806,
                "lon": 38.7578
            },
            {
                "id": "property-id-2",
                "title": "Spacious Villa",
                "location": "Hawassa",
                "status": "approved",
                "owner_id": "owner-id-2",
                "price": 5000.00,
                "lat": 7.0606,
                "lon": 38.4778
            }
        ]
        ```

---

### 4. Approve Property

*   **Method:** `POST`
*   **Path:** `/api/v1/admin/properties/{property_id}/approve`
*   **Permissions:** Authenticated Admin
*   **User Types:** Admin
*   **Position in Code:** `app/routers/admin.py` -> `approve_property_endpoint`
*   **Parameters:**
    *   **Path Parameter:**
        *   `property_id`: `str` - The unique identifier of the property to approve.
*   **Response Model:** `dict`
*   **Examples:**
    *   **Request:**
        ```
        POST /api/v1/admin/properties/property-id-1/approve
        Authorization: Bearer <ADMIN_JWT_TOKEN>
        ```
    *   **Response (200 OK):**
        ```json
        {
            "status": "success"
        }
        ```

---

### 5. Check Health

*   **Method:** `GET`
*   **Path:** `/api/v1/admin/health`
*   **Permissions:** Authenticated Admin
*   **User Types:** Admin
*   **Position in Code:** `app/routers/admin.py` -> `check_health`
*   **Parameters:** None
*   **Response Model:** `dict` - A dictionary where keys are service names and values are their health status.
*   **Examples:**
    *   **Request:**
        ```
        GET /api/v1/admin/health
        Authorization: Bearer <ADMIN_JWT_TOKEN>
        ```
    *   **Response (200 OK):**
        ```json
        {
            "user_management": {
                "status": "ok"
            },
            "property_listing": {
                "status": "ok"
            },
            "payment_processing": {
                "status": "ok"
            },
            "search_filters": {
                "status": "ok"
            },
            "ai_recommendation": {
                "status": "ok"
            },
            "notification": {
                "status": "ok"
            }
        }
        ```

---

### 6. Generate User Report

*   **Method:** `GET`
*   **Path:** `/api/v1/admin/reports/users`
*   **Permissions:** Authenticated Admin
*   **User Types:** Admin
*   **Position in Code:** `app/routers/admin.py` -> `user_report`
*   **Parameters:**
    *   **Query Parameter:**
        *   `lang`: `str` (Optional, default: "en") - Language for the report title ("en" for English, "am" for Amharic).
*   **Response Model:** `ReportResponse`
    *   `title`: `str` - Title of the report.
    *   `data`: `dict` - Dictionary containing report data (e.g., `total_users`, `new_users_month`, `active_users`).
*   **Examples:**
    *   **Request (English):**
        ```
        GET /api/v1/admin/reports/users?lang=en
        Authorization: Bearer <ADMIN_JWT_TOKEN>
        ```
    *   **Response (200 OK, English):**
        ```json
        {
            "title": "User Report",
            "data": {
                "total_users": 100,
                "new_users_month": 10,
                "active_users": 80
            }
        }
        ```
    *   **Request (Amharic):**
        ```
        GET /api/v1/admin/reports/users?lang=am
        Authorization: Bearer <ADMIN_JWT_TOKEN>
        ```
    *   **Response (200 OK, Amharic):**
        ```json
        {
            "title": "የተጠቃሚ መረጃ ሪፖርት",
            "data": {
                "total_users": 100,
                "new_users_month": 10,
                "active_users": 80
            }
        }
        ```

---

### 7. Export Report

*   **Method:** `GET`
*   **Path:** `/api/v1/admin/reports/export/{type}`
*   **Permissions:** Authenticated Admin
*   **User Types:** Admin
*   **Position in Code:** `app/routers/admin.py` -> `export_report_endpoint`
*   **Parameters:**
    *   **Path Parameter:**
        *   `type`: `str` - The type of report to export (currently only "users" is supported).
    *   **Query Parameter:**
        *   `lang`: `str` (Optional, default: "en") - Language for the report ("en" for English, "am" for Amharic).
*   **Response Model:** `dict`
    *   `file_url`: `str` - URL to the exported report file (CSV or PDF).
*   **Examples:**
    *   **Request (Export User Report as CSV/PDF):**
        ```
        GET /api/v1/admin/reports/export/users?lang=en
        Authorization: Bearer <ADMIN_JWT_TOKEN>
        ```
    *   **Response (200 OK):**
        ```json
        {
            "file_url": "https://supabase.com/storage/v1/object/public/reports/users_en.csv"
        }
        ```
