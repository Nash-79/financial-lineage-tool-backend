# Authentication & Authorization

## Overview
- JWT bearer tokens for user access.
- Optional API key support for service accounts (`X-API-Key` header).
- Rate limiting is enforced via SlowAPI (per-user/IP with Redis when available).

## Obtaining a Token
`POST /api/auth/login`
```json
{ "username": "admin", "password": "admin123" }
```
Response includes `access_token` and `expires_in`. Store the token client-side and send it as:
```
Authorization: Bearer <access_token>
```

`POST /api/auth/token/refresh` exchanges a valid token for a new one.

## Protected Routes
- Admin, ingestion, files, GitHub, database, and ingestion-log endpoints require authentication.
- In development (`ENVIRONMENT=development`) auth is permissive; in production or when `JWT_REQUIRED=true` missing/invalid tokens return 401.

## Rate Limits
- Default: `RATE_LIMIT_DEFAULT` (env, default `100/minute`).
- Auth endpoints: `RATE_LIMIT_AUTH` (default `5/minute`).
- Chat endpoints: `RATE_LIMIT_CHAT` (default `30/minute`).
- Ingestion endpoints: `RATE_LIMIT_INGEST` (default `10/minute`).
Responses include `X-RateLimit-Limit` and `X-RateLimit-Remaining` headers.

## Frontend Usage
The frontend automatically forwards any stored token (`access_token`, `jwt_token`, or `auth_token`) in the `Authorization` header for all API calls. Ensure login flow stores the token in `localStorage`.
