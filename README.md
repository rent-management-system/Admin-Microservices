# Admin Management Microservice

## Table of Contents
- [Introduction](#introduction)
- [Features](#features)
- [Architecture](#architecture)
- [Design Patterns & Key Concepts](#design-patterns--key-concepts)
- [Technologies Used](#technologies-used)
- [Setup Guide](#setup-guide)
  - [Prerequisites](#prerequisites)
  - [Environment Variables](#environment-variables)
  - [Installation](#installation)
  - [Database Setup](#database-setup)
  - [Running the Application](#running-the-application)
- [Database Schema](#database-schema)
- [API Endpoints](#api-endpoints)
  - [Authentication Proxy](#authentication-proxy)
  - [Admin Endpoints](#admin-endpoints)
  - [Public Property Endpoints](#public-property-endpoints)
  - [Health & Metrics](#health--metrics)
- [Inter-Service Communication](#inter-service-communication)
- [Logging & Caching](#logging--caching)
- [Contributing](#contributing)
- [License](#license)
- [Contact](#contact)

## Introduction
The Admin Management Service is a core backend component of the Rent Management System. It serves as a centralized hub for administrative tasks, providing a secure interface for administrators to manage users, oversee properties, and monitor the health and performance of the entire microservices ecosystem. It acts as an intelligent proxy, aggregating data from various services and exposing a unified API for the admin dashboard frontend.

## Features
-   **Admin Authentication**: Securely authenticates administrators by proxying login requests to the User Management Service.
-   **User Management**: Allows admins to list, view details of, and update user accounts.
-
-   **Property Oversight**: Enables admins to view all property listings from the Property Listing Service and approve pending properties.
-   **System Health Monitoring**: Provides a unified health check endpoint that polls all downstream microservices (User, Property, Payment, etc.) and reports their status.
-   **Aggregated Metrics**: Gathers and aggregates key metrics from across the system for a centralized dashboard view (e.g., total users, total properties, payment stats).
-   **Reporting**: Generates and exports user activity reports in various formats (CSV, PDF).
-   **Centralized Caching**: Uses Redis to cache expensive operations like health checks and reports, improving performance and reducing load on downstream services.
-   **Scheduled Tasks**: Employs a scheduler to periodically refresh cached data, ensuring the admin dashboard remains up-to-date.

## Architecture
This service functions as a **Backend for Frontend (BFF)** for the admin dashboard. It sits between the admin client and the rest of the microservice ecosystem, orchestrating calls and aggregating data to simplify frontend logic.

```mermaid
C4Context
    title System Context for Admin Management Service

    System_Ext(AdminUser, "Administrator", "Manages the system via the Admin Dashboard")
    System_Ext(Supabase, "Supabase Storage", "External object storage for exported reports")

    System_Boundary(RentManagementSystem, "Rent Management System") {
        System(AdminDashboard, "Admin Dashboard", "Frontend application for administrators")
        System(AdminService, "Admin Management Service", "This Service: Central hub for admin tasks and data aggregation")
        System(UserManagementService, "User Management Service", "Manages user authentication and profiles")
        System(PropertyListingService, "Property Listing Service", "Manages property listings and approvals")
        System(PaymentService, "Payment Service", "Handles all payment-related operations")
        System(SearchFilterService, "Search & Filter Service", "Provides advanced search capabilities")
        System(AIRecommender, "AI Recommendation Service", "Provides property recommendations")
        System(NotificationService, "Notification Service", "Handles sending notifications to users")
    }

    Rel(AdminUser, AdminDashboard, "Uses")
    Rel(AdminDashboard, AdminService, "Makes API calls to")

    Rel(AdminService, UserManagementService, "Authenticates admins and manages users via")
    Rel(AdminService, PropertyListingService, "Fetches and approves properties via")
    Rel(AdminService, PaymentService, "Fetches payment metrics from")
    Rel(AdminService, SearchFilterService, "Checks health of")
    Rel(AdminService, AIRecommender, "Checks health of")
    Rel(AdminService, NotificationService, "Checks health of")
    Rel(AdminService, Supabase, "Uploads exported reports to")

    UpdateRelStyle(AdminService, UserManagementService, $offsetY="-40", $offsetX="-10")
    UpdateRelStyle(AdminService, PropertyListingService, $offsetY="-20", $offsetX="-10")
    UpdateRelStyle(AdminService, PaymentService, $offsetY="0", $offsetX="-10")
    UpdateRelStyle(AdminService, SearchFilterService, $offsetY="20", $offsetX="-10")
    UpdateRelStyle(AdminService, AIRecommender, $offsetY="40", $offsetX="-10")
    UpdateRelStyle(AdminService, NotificationService, "Checks health of", $offsetY="60", $offsetX="-10")
```

## Design Patterns & Key Concepts

-   **Backend for Frontend (BFF)**: The service is a classic example of the BFF pattern, tailored specifically for the needs of the admin dashboard. It shields the frontend from the complexity of the microservice architecture.
-   **Proxy Pattern**: Many endpoints, especially for authentication (`/auth/login`) and fetching data from other services, act as intelligent proxies. They forward requests, handle authentication with internal service tokens, and normalize the responses.
-   **Resilient Client**: The service is designed to be robust against failures in downstream services. It employs several strategies for this:
    -   **Multiple Request Attempts**: When communicating with upstream services (e.g., for user updates or auth), it intelligently tries multiple common API patterns (e.g., `POST` with JSON, `POST` with form-data, `PUT`, `PATCH`) until one succeeds.
    -   **Graceful Fallbacks**: For health checks and metrics, it provides clear error states for individual services without bringing the entire admin service down.
-   **Centralized Configuration**: Leverages `pydantic-settings` to manage all configuration via environment variables, adhering to the 12-factor app methodology. This makes the service highly portable across different environments.
-   **Dependency Injection**: Heavily uses FastAPI's `Depends` system to manage dependencies like authentication (`get_current_admin`) and rate limiting, promoting clean, decoupled, and easily testable code.
-   **Repository Pattern (Implicit)**: The `services` layer (`app/services/`) abstracts the logic for interacting with downstream services and the local database, separating business logic from data-fetching concerns.
-   **Caching Strategy**: Implements a time-based caching pattern with Redis for frequently accessed, non-critical data like health status and reports. A background `APScheduler` job refreshes the cache periodically, ensuring data is reasonably fresh while protecting downstream services from excessive traffic.

## Technologies Used
-   **FastAPI**: For building the high-performance, asynchronous API.
-   **SQLAlchemy**: For interacting with the PostgreSQL database to store admin action logs.
-   **Alembic**: For database schema migrations.
-   **PostgreSQL**: Primary database for storing `AdminLogs`.
-   **Redis**: For caching health checks and reports.
-   **Pydantic**: For data validation, serialization, and settings management.
-   **httpx**: Asynchronous HTTP client for robust inter-service communication.
-   **python-jose**: For handling JWTs during authentication.
-   **structlog**: For structured, production-ready logging.
-   **APScheduler**: For running background tasks to refresh caches.
-   **Docker**: For containerization and deployment.

## Setup Guide

### Prerequisites
-   Python 3.10+
-   Docker and Docker Compose
-   `pip` (Python package installer)

### Environment Variables
Create a `.env` file in the root directory by copying `.env.example`.

```
# .env
# Database and Cache
DATABASE_URL="postgresql+asyncpg://user:password@host:port/database"
REDIS_URL="redis://localhost:6379/0"

# Security
JWT_SECRET="your_jwt_secret_key" # Should match the secret used by User Management Service

# Upstream Service URLs
USER_MANAGEMENT_URL="http://localhost:8001"
PROPERTY_LISTING_URL="http://localhost:8002"
PAYMENT_URL="http://localhost:8003"
SEARCH_FILTERS_URL="http://localhost:8004"
AI_RECOMMENDATION_URL="http://localhost:8005"
NOTIFICATION_URL="http://localhost:8006"

# External Services (for report exporting)
SUPABASE_URL="https://your_supabase_url.supabase.co"
SUPABASE_KEY="your_supabase_anon_key"

# Internal Service-to-Service Authentication Tokens
USER_TOKEN="your_user_service_internal_token"
PROPERTY_TOKEN="your_property_service_internal_token"
PAYMENT_TOKEN="your_payment_service_internal_token"
SEARCH_TOKEN="your_search_service_internal_token"
NOTIFICATION_TOKEN="your_notification_service_internal_token"
```

### Installation
1.  **Clone the repository**:
    ```bash
    git clone https://github.com/rent-management-system/Admin-Microservices.git
    cd Admin-Microservices
    ```

2.  **Create and activate a virtual environment**:
    ```bash
    python -m venv .venv
    source .venv/bin/activate
    ```

3.  **Install dependencies**:
    ```bash
    pip install -r requirements.txt
    ```

### Database Setup
This service uses PostgreSQL for logging admin actions.
1.  Ensure your `DATABASE_URL` in `.env` is correct.
2.  **Run database migrations**:
    ```bash
    alembic upgrade head
    ```

### Running the Application
1.  Ensure all dependent services (PostgreSQL, Redis, and other microservices) are running.
2.  **Start the FastAPI server**:
    ```bash
    uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
    ```
The API documentation will be available at `http://localhost:8000/docs`.

## Database Schema
The service maintains a single table, `AdminLogs`, to record actions performed by administrators.

```mermaid
erDiagram
    AdminLogs {
        UUID id PK
        UUID admin_id "ID of the admin who performed the action"
        String action "Description of the action (e.g., 'property_approved')"
        UUID entity_id "ID of the entity affected (e.g., property_id)"
        JSON details "Optional additional details about the action"
        DateTime created_at "Timestamp of the action"
    }
```

## API Endpoints
All endpoints are prefixed with `/api/v1`.

### Authentication Proxy
-   **`POST /auth/login`**: Proxies login credentials to the User Management Service to obtain an access token for an admin.
-   **`POST /auth/change-password`**: Proxies a request for an authenticated admin to change their password.

### Admin Endpoints
*(Requires Admin Authentication)*
-   **`GET /admin/users`**: Lists all users from the User Management Service.
-   **`GET /admin/users/{user_id}`**: Retrieves detailed information for a specific user.
-   **`PUT /admin/users/{user_id}`**: Updates a user's information (role, status, etc.).
-   **`GET /admin/properties`**: Lists all properties from the Property Listing Service, with filtering options.
-   **`POST /admin/properties/{property_id}/approve`**: Approves a pending property listing.
-   **`GET /admin/reports/users`**: Generates a summary report of user statistics.
-   **`GET /admin/reports/export/{type}`**: Exports a report (e.g., 'users') to a file (CSV/PDF) and returns a public URL from Supabase Storage.

### Public Property Endpoints
*(No Authentication Required)*
-   **`GET /properties/public`**: Retrieves a paginated list of all **approved** properties. This is a public-facing endpoint designed for consumption by client applications.
-   **`GET /properties/public/{property_id}`**: Retrieves the full details of a single **approved** property.

### Health & Metrics
-   **`GET /health`**: A simple endpoint that returns "ok", used for basic service availability checks (e.g., by a load balancer).
-   **`GET /admin/health`**: Provides a detailed health status of all downstream microservices. Use `?verbose=true` to see the specific URLs that were checked.
-   **`GET /admin/metrics/totals`**: Returns aggregated totals for key metrics across the system, perfect for dashboard widgets.
-   **`GET /admin/properties/metrics`**: Proxies a request to get detailed metrics from the Property Listing Service.
-   **`GET /admin/payments/metrics`**: Proxies a request to get detailed metrics from the Payment Service.

## Inter-Service Communication
This service communicates extensively with other microservices. It uses `httpx` for all outgoing requests and authenticates using internal-only bearer tokens defined in the environment variables (e.g., `PROPERTY_TOKEN`). The service is designed to be resilient, attempting various common API patterns to ensure compatibility with downstream services.

## Logging & Caching
-   **Logging**: Uses `structlog` to produce structured, JSON-formatted logs. This is ideal for production environments where logs are collected and analyzed by tools like the ELK stack or Datadog.
-   **Caching**: Uses **Redis** to cache the results of expensive or frequently called endpoints, such as `/admin/health` and `/admin/reports/users`. An `APScheduler` background job automatically refreshes this cache every 5 minutes to ensure the data remains reasonably current while protecting downstream services from being overloaded.

## Contributing
Contributions are welcome. Please fork the repository, create a feature branch, and submit a pull request.

## License
This project is licensed under the MIT License.

## Contact
For inquiries or support, please contact the developer:
-   **Email**: dagiteferi2011@gmail.com
-   **WhatsApp**: +251920362324
