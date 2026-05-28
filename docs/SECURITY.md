# Security

Summary of the security controls implemented in Phase 9.

## Authentication

**File:** `app/core/security.py`, `app/core/deps.py`

Passwords are hashed with **bcrypt at cost 12**. On login, `verify_password()` calls `bcrypt.checkpw()` in constant time.

Access tokens are signed **HS256 JWTs** with a 15-minute expiry. Refresh tokens use the same algorithm with a 7-day expiry and are delivered as an **httpOnly, SameSite=Lax cookie** — they are never exposed in a JSON response body.

`get_current_user()` in `app/core/deps.py`:
1. Requires a `Authorization: Bearer <token>` header via FastAPI's `HTTPBearer` (raises 401 automatically if missing).
2. Decodes the token with `decode_token()` which raises `JWTError` on any tamper, expiry, or bad signature.
3. Asserts `payload["type"] == "access"` — refresh tokens are explicitly rejected on guarded endpoints.
4. Queries `users` by the `sub` claim (UUID) and returns the ORM object or raises 401.

`SECRET_KEY` must be at least 32 characters; a Pydantic validator in `app/core/config.py` enforces this at startup.

## Rate limiting

**File:** `app/core/rate_limit.py`

Redis-backed sliding window counter applied to all public dictionary endpoints (search, kanji, reibun, analyze).

| Client | Key | Limit |
|---|---|---|
| Anonymous | `rl:ip:{client_ip}` | 60 req / 60 s |
| Authenticated | `rl:user:{user_id}` | 120 req / 60 s |

The limiter reads an optional Bearer token; if it's present and valid, the user key is used, otherwise the IP key. On breach: 429 with `Retry-After: 60`. The limiter **fails open** — if Redis is unreachable it returns without raising, prioritising availability over protection.

Vocabulary and history endpoints carry `get_current_user` but not `rate_limit`; they are implicitly protected by the authentication requirement.

## Input validation

**File:** `app/schemas/validators.py`

`SafeStr` is a custom Pydantic annotated type applied to all user-supplied string query parameters (`q`, `value`, `query`):
- Strips null bytes (`\x00`) — prevents Postgres null-byte injection.
- Raises `ValueError` (→ 422) if the string is blank after stripping.

All query params also carry FastAPI `min_length` / `max_length` constraints enforced before any service code runs. JSONB writes use SQLAlchemy's parameterised queries; no raw SQL string formatting is used anywhere.

## Security headers

**File:** `app/main.py:16–22`, `SecurityHeadersMiddleware`

Every response gets:

| Header | Value |
|---|---|
| `X-Content-Type-Options` | `nosniff` |
| `X-Frame-Options` | `DENY` |
| `Referrer-Policy` | `no-referrer` |

CORS is configured via `CORSMiddleware` with an explicit allowlist (`ALLOWED_ORIGINS`). Credentials are allowed (`allow_credentials=True`) which is required for the httpOnly refresh-token cookie. Methods are explicitly listed: `GET, POST, PATCH, DELETE`.

## Threat model

The primary attack surface is the public dictionary API (search, analyze, kanji detail). Because these endpoints require no authentication, they are the most accessible. The rate limiter mitigates bulk scraping and DoS amplification. The `SafeStr` validator and parameterised queries close the most common injection paths. Dictionary data is read-only in all public handlers — the worst outcome on a public endpoint is a 429 or a 422, not data exfiltration or mutation.

The authenticated surface (vocabulary, history) is narrower: it requires a valid, non-expired, correctly-typed access JWT whose signature is checked against `SECRET_KEY`. Refresh tokens are short-lived secrets stored only in httpOnly cookies, inaccessible to JavaScript. The main residual risk in the authenticated surface is CSRF on the refresh endpoint; this is partially mitigated by `SameSite=Lax` and should be completed with an explicit CSRF token if the frontend is ever hosted on a separate subdomain from the API.

## Test coverage

`tests/test_injection.py` — null-byte and SQL injection probes  
`tests/test_security.py` — JWT tamper, expired token, wrong type, missing token, rate limit boundary
