import uuid
import hmac
import hashlib
from datetime import datetime, timedelta, timezone
from typing import Any, Annotated

import jwt
from fastapi import Depends, HTTPException, status, APIRouter, Request
from pydantic import BaseModel
from redis import Redis
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from .config import settings

bearer = HTTPBearer(auto_error=False)
bootstrap_router = APIRouter(tags=["bootstrap-auth"])
BOOTSTRAP_ISSUER = "nbros-local-bootstrap"
BOOTSTRAP_SUB = uuid.uuid5(uuid.NAMESPACE_URL, "nbros/bootstrap-admin")


class BootstrapCredentials(BaseModel):
    identifier: str
    password: str


def _bootstrap_configured() -> bool:
    return (settings.bootstrap_login_enabled and
            len(settings.bootstrap_admin_password) >= 12 and
            len(settings.bootstrap_signing_secret) >= 32)


@bootstrap_router.post("/api/v1/auth/bootstrap-login", include_in_schema=False)
def bootstrap_login(credentials: BootstrapCredentials, request: Request) -> dict:
    if not _bootstrap_configured():
        raise HTTPException(status_code=404, detail="bootstrap login unavailable")
    # Redis-backed throttling across workers; fail closed if Redis is unavailable.
    client_ip = request.client.host if request.client else "unknown"
    key = "nbros:bootstrap:attempts:" + hashlib.sha256(client_ip.encode()).hexdigest()
    try:
        redis = Redis.from_url(settings.redis_url, socket_connect_timeout=2, socket_timeout=2)
        try:
            attempts = redis.incr(key)
            if attempts == 1:
                redis.expire(key, 900)
        finally:
            redis.close()
    except Exception as exc:
        raise HTTPException(status_code=503, detail="login temporarily unavailable") from exc
    if attempts > 5:
        raise HTTPException(status_code=429, detail="too many attempts")
    email_ok = hmac.compare_digest(credentials.identifier.strip().lower(), settings.bootstrap_admin_email.strip().lower())
    password_ok = hmac.compare_digest(credentials.password, settings.bootstrap_admin_password)
    if not (email_ok and password_ok):
        raise HTTPException(status_code=401, detail="invalid credentials")
    now = datetime.now(timezone.utc)
    token = jwt.encode({"iss": BOOTSTRAP_ISSUER, "aud": settings.auth_audience,
                        "sub": str(BOOTSTRAP_SUB), "sid": str(uuid.uuid4()),
                        "email": settings.bootstrap_admin_email.strip().lower(),
                        "iat": now, "nbf": now, "exp": now + timedelta(hours=1),
                        "token_use": "access"}, settings.bootstrap_signing_secret, algorithm="HS256")
    return {"access_token": token, "expires_in": 3600}


def decode_local_bootstrap_token(token: str) -> dict[str, Any]:
    if not _bootstrap_configured():
        raise HTTPException(status_code=401, detail="invalid access token")
    try:
        claims = jwt.decode(token, settings.bootstrap_signing_secret, algorithms=["HS256"],
                            issuer=BOOTSTRAP_ISSUER, audience=settings.auth_audience,
                            options={"require": ["iss", "sub", "aud", "sid", "iat", "nbf", "exp", "token_use"]})
        if (claims.get("token_use") != "access" or claims.get("sub") != str(BOOTSTRAP_SUB)
                or claims.get("email") != settings.bootstrap_admin_email.strip().lower()):
            raise ValueError("invalid bootstrap identity")
        return claims
    except (jwt.PyJWTError, ValueError) as exc:
        raise HTTPException(status_code=401, detail="invalid access token") from exc


_jwks = jwt.PyJWKClient(settings.auth_jwks_url, cache_keys=True)


def decode_central_access_token(token: str) -> dict[str, Any]:
    try:
        signing_key = _jwks.get_signing_key_from_jwt(token)
        claims = jwt.decode(
            token,
            signing_key.key,
            algorithms=["RS256"],
            audience=settings.auth_audience,
            issuer=settings.auth_issuer,
            options={
                "require": ["iss", "sub", "aud", "sid", "iat", "nbf", "exp", "token_use"],
            },
        )
        if claims.get("token_use") != "access":
            raise ValueError("wrong token type")
        uuid.UUID(str(claims["sub"]))
        uuid.UUID(str(claims["sid"]))
        return claims
    except (jwt.PyJWTError, KeyError, TypeError, ValueError) as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid central access token") from exc


def current_claims(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)],
) -> dict[str, Any]:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="missing bearer token")
    if credentials.credentials.startswith("eyJ"):
        # Local tokens use a distinct signing algorithm and issuer.
        try:
            header = jwt.get_unverified_header(credentials.credentials)
        except jwt.PyJWTError:
            header = {}
        if header.get("alg") == "HS256":
            return decode_local_bootstrap_token(credentials.credentials)
    return decode_central_access_token(credentials.credentials)
